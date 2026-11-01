#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""死锁检测 deadlock_detector.py

V4.0 的「死锁熔断」执行器。要解决的问题：

    红蓝双方连续两轮都在复读彼此的观点，谁也没带来新事实，
    讨论却还在继续——这是最典型的"看起来很激烈，其实在原地转"。

判据（全部可计数，不做语义判断）：

  1. **复读**：本轮发言与上一轮（任意一方）相似度 ≥ 阈值；
  2. **无新事实**：本轮没有新增关键论据，且没有新的工具调用结果；
  3. **立场未动**：本轮没有任何有效立场修正；
  4. **无新靶点**：本轮攻击的 claim 集合与上一轮重合度高。

  连续 `rounds_to_deadlock`（默认 2）轮同时满足 1–4 → 判定死锁 → 熔断。

熔断后按 spec 输出固定话术并**切断发言权**，议题移交阶段三的三选一裁决。

诚实边界：相似度是字符二元组 Jaccard，不懂语义。它的作用是抓"明显复读"，
抓不到"换了说法但意思一样"的复读——后者要靠元认知层的模型判断。

用法：
  python deadlock_detector.py check  --state S [--write]
  python deadlock_detector.py fuse   --state S [--reason TEXT]   # 手动强制熔断
  python deadlock_detector.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

FUSE_TEMPLATE = "[系统强制熔断] 双方无法说服彼此，此议题直接交由最终裁决阶段处理。"
ROUNDS_TO_DEADLOCK = 2
SIMILARITY_THRESHOLD = 0.55      # 复读判定阈值
TARGET_OVERLAP_THRESHOLD = 0.8   # 靶点重合度阈值


def log(msg: str) -> None:
    print(f"[deadlock_detector] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[deadlock_detector] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def load_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"状态文件不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path, state) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", str(text or "")).lower(),
                  flags=re.UNICODE)


def _bigrams(text: str) -> set:
    t = _norm(text)
    if not t:
        return set()
    return {t} if len(t) < 2 else {t[i:i + 2] for i in range(len(t) - 1)}


def similarity(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


# --------------------------------------------------------------------------- #
# 逐轮信号
# --------------------------------------------------------------------------- #


def round_speeches(state: dict, round_no: int) -> list:
    """取出某一轮的全部交锋发言（含回合编号）。"""
    out = []
    for e in state.get("clash_exchanges", []) or []:
        if int(e.get("round", 0)) == int(round_no):
            out.append(e)
    # 兼容多轮格式：exchanges 里若带 round2/round3 字段，按轮次取
    for key, entries in (state.get("clash_rounds") or {}).items():
        if int(key) == int(round_no):
            out.extend(entries)
    return out


def _targets(speeches: list) -> set:
    return {s.get("target_claim") for s in speeches if s.get("target_claim")}


def _max_cross_similarity(cur: list, prev: list) -> tuple:
    """本轮与上一轮之间最相似的一对发言。"""
    best = (0.0, None, None)
    for a in cur:
        for b in prev:
            s = similarity(a.get("text", ""), b.get("text", ""))
            if s > best[0]:
                best = (s, a.get("from"), b.get("from"))
    return best


def _new_arguments(state: dict, round_no: int) -> int:
    return len([a for a in (state.get("argument_log") or [])
                if int(a.get("round", -1)) == int(round_no) and a.get("is_new_key_argument")])


def _new_tool_results(state: dict, round_no: int) -> int:
    """只统计**本轮新增**的工具结果。

    阶段一的 tool_results 没有 round 字段，它们属于第 1 轮；
    若在后续轮次里把它们也算作"新事实"，死锁永远检测不出来。
    """
    n = 0
    for t in (state.get("stage1", {}) or {}).get("tool_results", []) or []:
        r = t.get("round")
        if r is None:
            if int(round_no) == 1:
                n += 1
        elif int(r) == int(round_no):
            n += 1
    for v in (state.get("stage2", {}) or {}).get("verifications", []) or []:
        if v.get("result"):
            n += 1
    return n


def _valid_revisions(state: dict, round_no: int) -> int:
    return len([r for r in (state.get("revisions") or [])
                if int(r.get("round", -1)) == int(round_no) and r.get("valid")])


def round_signals(state: dict, round_no: int, prev_no: int = None) -> dict:
    prev_no = prev_no if prev_no is not None else round_no - 1
    cur = round_speeches(state, round_no)
    prev = round_speeches(state, prev_no)

    sim, a, b = _max_cross_similarity(cur, prev) if (cur and prev) else (0.0, None, None)
    t_cur, t_prev = _targets(cur), _targets(prev)
    overlap = 0.0
    if t_cur and t_prev:
        overlap = len(t_cur & t_prev) / len(t_cur | t_prev)

    new_args = _new_arguments(state, round_no)
    new_tools = _new_tool_results(state, round_no)
    revs = _valid_revisions(state, round_no)

    has_prev = bool(prev)
    if has_prev:
        # 有上一轮交锋：复读 = 与上一轮高度相似
        repeated = sim >= SIMILARITY_THRESHOLD
    else:
        # 这是第一轮交锋：没有可复读的对象，改判"本轮是否毫无新意"
        repeated = (new_args == 0 and new_tools == 0 and revs == 0)
    no_new_fact = (new_args == 0 and new_tools == 0)
    no_shift = (revs == 0)
    no_new_target = (t_cur == t_prev) if has_prev else True

    stalled = repeated and no_new_fact and no_shift and no_new_target
    reasons = []
    if repeated:
        if has_prev:
            reasons.append(f"与上一轮最大相似度 {sim:.2f}（≥{SIMILARITY_THRESHOLD}）"
                           f"：{a} 与 {b} 在复读")
        else:
            reasons.append("首轮交锋即无新增论据、无工具查证、无立场修正：属于原地复读")
    if new_args == 0:
        reasons.append("本轮没有新增关键论据")
    if new_tools == 0:
        reasons.append("本轮没有新的工具查证结果")
    if revs == 0:
        reasons.append("本轮没有任何有效立场修正")
    if no_new_target:
        reasons.append(f"攻击靶点与上一轮重合（{sorted(t_cur)}）")

    return {
        "round": round_no,
        "speeches": len(cur),
        "max_similarity": round(sim, 3),
        "most_similar_pair": [a, b] if a else None,
        "target_overlap": round(overlap, 3),
        "new_arguments": new_args,
        "new_tool_results": new_tools,
        "valid_revisions": revs,
        "repeated": repeated,
        "no_new_fact": no_new_fact,
        "no_position_shift": no_shift,
        "no_new_target": no_new_target,
        "stalled": stalled,
        "reasons": reasons,
    }


def check(state: dict, rounds: int = ROUNDS_TO_DEADLOCK) -> dict:
    if state.get("fused"):
        return {
            "needs_judgment": True,
            "already_fused": True,
            "deadlock": True,
            "fuse_message": state.get("fuse_message") or FUSE_TEMPLATE,
            "consecutive_stalled": state.get("fuse_consecutive", rounds),
            "note": "已熔断，不再重新判定；议题应交由阶段三三选一裁决",
        }

    # 找出实际有交锋的轮次
    rounds_with_speeches = sorted({
        int(e.get("round", 0)) for e in (state.get("clash_exchanges") or []) if e.get("round")
    } | {int(k) for k in (state.get("clash_rounds") or {})})
    if not rounds_with_speeches:
        return {
            "needs_judgment": True,
            "already_fused": False,
            "deadlock": False,
            "consecutive_stalled": 0,
            "rounds_analyzed": [],
            "signals": [],
            "note": "尚无交锋记录，无法判定死锁",
        }

    signals = []
    for r in rounds_with_speeches:
        signals.append(round_signals(state, r, r - 1))

    # 从最后一轮往前数连续 stalled 的轮数
    consecutive = 0
    for s in reversed(signals):
        if s["stalled"]:
            consecutive += 1
        else:
            break

    deadlock = consecutive >= rounds
    return {
        "needs_judgment": True,
        "already_fused": False,
        "deadlock": deadlock,
        "consecutive_stalled": consecutive,
        "rounds_analyzed": rounds_with_speeches,
        "threshold_rounds": rounds,
        "signals": signals,
        "latest": signals[-1] if signals else None,
        "fuse_required": deadlock,
        "fuse_message": FUSE_TEMPLATE if deadlock else "",
        "reasons": signals[-1]["reasons"] if deadlock and signals else [],
        "note": ("死锁判定只基于复读/新事实/立场/靶点四项计数；"
                 "换了说法但意思相同的复读抓不到，需元认知层复核"),
    }


def fuse(state_path: str, state: dict, reason: str = "") -> dict:
    """强制熔断：写入状态并切断后续辩论轮次。"""
    result = check(state)
    state["fused"] = True
    state["fused_at_round"] = (result.get("latest") or {}).get("round")
    state["fuse_message"] = FUSE_TEMPLATE
    state["fuse_consecutive"] = max(result.get("consecutive_stalled", 0),
                                    state.get("fuse_consecutive", 0))
    state["fuse_reason"] = reason or "；".join(result.get("reasons", [])) or "手动熔断"
    state["debate_closed"] = True
    save_state(state_path, state)
    return {
        "needs_judgment": False,
        "fused": True,
        "fused_at_round": state["fused_at_round"],
        "fuse_message": FUSE_TEMPLATE,
        "reason": state["fuse_reason"],
        "consecutive_stalled": state["fuse_consecutive"],
        "next_stage": "stage3 铁血裁决（三选一）",
        "note": "辩论发言权已切断：后续不得再提交 stage2 交锋，直接进入投票",
    }


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    def stalled_state():
        """两轮完全复读、无新事实、无修正、靶点相同（真正的死锁场景）。"""
        ex = []
        for rnd in (2, 3):
            ex.extend([
                {"from": "munger", "round": rnd, "target_claim": "M1-1",
                 "text": "你的方案忽略了上下文切换成本，这一项会让预算翻倍"},
                {"from": "musk", "round": rnd, "target_claim": "G2-1",
                 "text": "切换成本只占 9%，不足以推翻结论，我给出可推翻条件"},
                {"from": "jobs", "round": rnd, "target_claim": "M1-1",
                 "text": "这套流程本身就是冗余的，先砍掉再谈成本"},
            ])
        return {
            "clash_exchanges": ex,
            "argument_log": [],          # 两轮都没有新增关键论据
            "revisions": [], "stage1": {"tool_results": []},
            "stage2": {"verifications": []},
        }

    st = stalled_state()
    r = check(st)
    ck(r["deadlock"] is True and r["fuse_required"] is True, "两轮复读被判为死锁")
    ck(r["consecutive_stalled"] >= 2, "连续停滞轮数正确")
    ck(any("复读" in x for x in r["reasons"]), "熔断理由点明复读")
    ck(FUSE_TEMPLATE in r["fuse_message"], "熔断话术与 spec 一致")

    # 有新事实时不应熔断
    alive = stalled_state()
    alive["argument_log"] = [{"round": 3, "is_new_key_argument": True}]
    alive["revisions"] = [{"round": 3, "valid": True}]
    r2 = check(alive)
    ck(r2["deadlock"] is False, "有新事实与新立场时不熔断")
    ck(r2["signals"][-1]["stalled"] is False, "最近一轮有新增论据时不算停滞")

    # 只有一轮时不足以熔断
    one = stalled_state()
    one["clash_exchanges"] = [e for e in one["clash_exchanges"] if e["round"] == 2]
    r3 = check(one)
    ck(r3["deadlock"] is False and r3["consecutive_stalled"] == 1, "单轮停滞不足以熔断")

    # 靶点变化 → 不算死锁
    varied = stalled_state()
    for e in varied["clash_exchanges"]:
        if e["round"] == 3:
            e["target_claim"] = "N9-9"
    r4 = check(varied)
    ck(r4["signals"][-1]["no_new_target"] is False, "靶点变化时 no_new_target 为假")

    # 无交锋
    r5 = check({"clash_exchanges": []})
    ck(r5["deadlock"] is False and "尚无交锋" in r5["note"], "无交锋时不误判死锁")

    # 熔断写入
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "s.json"
        save_state(sp, stalled_state())
        stt = load_state(sp)
        f = fuse(str(sp), stt, "测试熔断")
        ck(f["fused"] is True and f["next_stage"].startswith("stage3"), "熔断后指向阶段三")
        st2 = load_state(sp)
        ck(st2["debate_closed"] is True, "熔断后辩论关闭")
        r6 = check(st2)
        ck(r6["already_fused"] is True, "已熔断状态不会重复判定")

    # 相似度函数
    ck(similarity("完全相同的一句话", "完全相同的一句话") == 1.0, "相同文本相似度为 1")
    ck(similarity("完全不同的内容", "另一件毫不相干的事情") < 0.3, "不同文本相似度低")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="死锁检测与强制熔断（V4.0）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)
    pc.add_argument("--rounds", type=int, default=ROUNDS_TO_DEADLOCK)
    pc.add_argument("--write", action="store_true",
                    help="判定为死锁时自动执行熔断并写回")

    pf = sub.add_parser("fuse")
    pf.add_argument("--state", required=True)
    pf.add_argument("--reason", default="")

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        st = load_state(args.state)
        r = check(st, args.rounds)
        if r.get("deadlock") and args.write:
            r["fused_result"] = fuse(args.state, st, "；".join(r.get("reasons", [])))
            log("判定死锁，已执行强制熔断")
        emit(r)
        return 0
    if args.cmd == "fuse":
        emit(fuse(args.state, load_state(args.state), args.reason))
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语义级死锁检测 deadlock_detector.py（V4.1）

解决的问题：

    红蓝双方连续两轮都在"复读"——但复读往往不是逐字重复，
    而是换个说法、换个例子、同义词替换，核心论点/支撑数据/推导逻辑完全没变。

字符相似度抓不到这种复读。所以本脚本提供**两条路径**：

  A. 结构路径（离线、确定性）
     相似度 ≥0.55 + 无新事实 + 无立场修正 + 靶点未变 → 判死锁

  B. 语义路径（模型裁判、可审计）
     主持人（模型）对每一对"上一轮 vs 本轮"发言做语义判定，标签三选一：
       [REPEAT]    换了说法/同义词/不同例子，核心论点与支撑数据未变
       [PROGRESS]  新证据、新前提、修正观点，或针对性反驳对方特定词句；反问/质疑/要数据也算
       [UNCERTAIN] 无法确定
     把标签写回状态后，本脚本据此判定是否熔断。

  两条路径**任一命中即熔断**。B 路径的意义在于：它把"我觉得他们在重复"变成一条
  可审计的记录（谁判的、判了哪两句、什么理由），而不是主持人的一句感觉。

熔断动作（spec 原文）：
    [系统强制熔断] 双方已陷入实质重复，此议题直接交由最终裁决阶段处理。

用法：
  python deadlock_detector.py check   --state S [--write]
  python deadlock_detector.py judge   --state S [--pair 2-3] [--json]     # 输出待判材料
  python deadlock_detector.py record  --state S --file verdicts.json      # 写回语义判定
  python deadlock_detector.py fuse    --state S [--reason TEXT]
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

FUSE_TEMPLATE = "[系统强制熔断] 双方已陷入实质重复，此议题直接交由最终裁决阶段处理。"
LEGACY_FUSE_TEMPLATE = "[系统强制熔断] 双方无法说服彼此，此议题直接交由最终裁决阶段处理。"
ROUNDS_TO_DEADLOCK = 2
SIMILARITY_THRESHOLD = 0.55
LABELS = ["REPEAT", "PROGRESS", "UNCERTAIN"]
LABEL_TAG = {"REPEAT": "[REPEAT]", "PROGRESS": "[PROGRESS]", "UNCERTAIN": "[UNCERTAIN]"}

# 语义裁判的判定标准（原样来自 spec，供 judge 子命令输出给模型）
JUDGE_CRITERIA = {
    "REPEAT": "两段话表达同一件事，只是换了说法、同义词替换、举了不同例子；"
              "核心论点、支撑数据、推导逻辑完全没变。",
    "PROGRESS": "提出了新证据、新前提、调整了观点，或在反驳对方的特定词句；"
                "反问、质疑、要求提供数据同样算实质推进。",
    "UNCERTAIN": "无法确定（极少数情况）。",
}
JUDGE_IGNORE = ["语气词", "口头禅（如「我同意马斯克说的」「毫无疑问」）"]
JUDGE_FOCUS = ["核心论点", "支撑数据", "推导逻辑"]


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
    out = []
    for e in state.get("clash_exchanges", []) or []:
        if int(e.get("round", 0)) == int(round_no):
            out.append(e)
    for key, entries in (state.get("clash_rounds") or {}).items():
        if int(key) == int(round_no):
            out.extend(entries)
    return out


def _targets(speeches: list) -> set:
    return {s.get("target_claim") for s in speeches if s.get("target_claim")}


def _max_cross_similarity(cur: list, prev: list) -> tuple:
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
    """只统计本轮新增的工具结果；阶段一的 tool_results 属于第 1 轮。"""
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


# --------------------------------------------------------------------------- #
# 语义判定记录
# --------------------------------------------------------------------------- #


def semantic_verdicts(state: dict) -> list:
    return state.get("semantic_verdicts") or []


def verdicts_for_round(state: dict, round_no: int) -> list:
    return [v for v in semantic_verdicts(state) if int(v.get("round", -1)) == int(round_no)]


def round_semantic_summary(state: dict, round_no: int) -> dict:
    """汇总某一轮的语义判定：只要有 REPEAT 且没有 PROGRESS，就算语义复读。"""
    vs = verdicts_for_round(state, round_no)
    labels = [str(v.get("label", "")).upper() for v in vs]
    unknown = [l for l in labels if l not in LABELS]
    repeat = labels.count("REPEAT")
    progress = labels.count("PROGRESS")
    uncertain = labels.count("UNCERTAIN")
    judged = len(labels)
    if judged == 0:
        semantic_repeat = None          # 没判过
    elif progress > 0:
        semantic_repeat = False         # 有新推进，放行
    elif repeat > 0:
        semantic_repeat = True          # 只有复读（可能夹杂 UNCERTAIN）
    else:
        semantic_repeat = None          # 全是 UNCERTAIN
    return {
        "round": round_no,
        "judged_pairs": judged,
        "repeat": repeat,
        "progress": progress,
        "uncertain": uncertain,
        "invalid_labels": unknown,
        "semantic_repeat": semantic_repeat,
        "verdicts": vs,
    }


# --------------------------------------------------------------------------- #
# 结构信号
# --------------------------------------------------------------------------- #


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
        repeated = sim >= SIMILARITY_THRESHOLD
    else:
        repeated = (new_args == 0 and new_tools == 0 and revs == 0)
    no_new_fact = (new_args == 0 and new_tools == 0)
    no_shift = (revs == 0)
    no_new_target = (t_cur == t_prev) if has_prev else True

    struct_stalled = repeated and no_new_fact and no_shift and no_new_target

    sem = round_semantic_summary(state, round_no)
    # 语义判定为 PROGRESS → 即使结构相似度高也放行（新证据可能措辞相似）
    if sem["semantic_repeat"] is False:
        stalled = False
    elif sem["semantic_repeat"] is True:
        stalled = True
    else:
        stalled = struct_stalled

    reasons = []
    if sem["semantic_repeat"] is True:
        ids = [f"{v.get('from')}→{v.get('to')}" for v in sem["verdicts"]
               if str(v.get("label", "")).upper() == "REPEAT"]
        reasons.append(f"语义裁判判定为实质重复：{ids}（换了说法但核心论点未变）")
    elif sem["semantic_repeat"] is False:
        pass
    else:
        if repeated:
            if has_prev:
                reasons.append(f"与上一轮最大相似度 {sim:.2f}（≥{SIMILARITY_THRESHOLD}）："
                               f"{a} 与 {b} 在复读")
            else:
                reasons.append("首轮交锋即无新增论据、无工具查证、无立场修正：属于原地复读")
        if new_args == 0:
            reasons.append("本轮没有新增关键论据")
        if new_tools == 0:
            reasons.append("本轮没有新的工具查证结果")
        if no_shift:
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
        "structural_stalled": struct_stalled,
        "semantic": sem,
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

    rounds_with_speeches = sorted({
        int(e.get("round", 0)) for e in (state.get("clash_exchanges") or []) if e.get("round")
    } | {int(k) for k in (state.get("clash_rounds") or {})}
        | {int(v.get("round", 0)) for v in semantic_verdicts(state) if v.get("round")})
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

    signals = [round_signals(state, r, r - 1) for r in rounds_with_speeches]

    consecutive = 0
    for s in reversed(signals):
        if s["stalled"]:
            consecutive += 1
        else:
            break

    deadlock = consecutive >= rounds
    latest = signals[-1] if signals else None
    semantic_hit = bool(latest and latest["semantic"].get("semantic_repeat") is True)
    return {
        "needs_judgment": True,
        "already_fused": False,
        "deadlock": deadlock,
        "consecutive_stalled": consecutive,
        "rounds_analyzed": rounds_with_speeches,
        "threshold_rounds": rounds,
        "signals": signals,
        "latest": latest,
        "trigger": ("semantic" if semantic_hit else
                    ("structural" if deadlock else "")),
        "fuse_required": deadlock,
        "fuse_message": FUSE_TEMPLATE if deadlock else "",
        "reasons": latest["reasons"] if deadlock and latest else [],
        "semantic_coverage": {
            "judged_pairs": sum(s["semantic"]["judged_pairs"] for s in signals),
            "rounds_with_verdicts": len([s for s in signals
                                         if s["semantic"]["judged_pairs"] > 0]),
        },
        "note": ("死锁判定双路径：语义裁判（REPEAT 且无 PROGRESS）优先；"
                 "无语义判定时退回结构判据（复读/新事实/立场/靶点四项）。"
                 "语义路径可审计：每条判定都记录了 from/to/label/reason。"),
    }


# --------------------------------------------------------------------------- #
# judge：生成待判材料（供主持人/模型执行语义判定）
# --------------------------------------------------------------------------- #


def build_judge_material(state: dict, pair: str = None) -> dict:
    """把"上一轮 vs 本轮"的发言两两配对，输出给模型判定。"""
    rounds = sorted({int(e.get("round", 0)) for e in (state.get("clash_exchanges") or [])
                     if e.get("round")})
    if not rounds:
        die("尚无交锋记录，无法生成待判材料", 3)

    cur_round = rounds[-1]
    prev_round = rounds[-2] if len(rounds) >= 2 else None
    if pair:
        m = re.match(r"^(\d+)-(\d+)$", str(pair))
        if not m:
            die(f"--pair 格式应为 上一轮-当前轮，例如 2-3（收到 {pair!r}）")
        prev_round, cur_round = int(m.group(1)), int(m.group(2))

    cur = round_speeches(state, cur_round)
    prev = round_speeches(state, prev_round) if prev_round is not None else []

    pairs = []
    for c in cur:
        # 同角色的上一轮发言优先；没有就跨角色比
        same = [p for p in prev if p.get("from") == c.get("from")]
        candidates = same or prev
        if not candidates:
            continue
        best = max(candidates, key=lambda p: similarity(c.get("text", ""), p.get("text", "")))
        pairs.append({
            "pair_id": f"{prev_round}->{cur_round}#{len(pairs) + 1}",
            "speaker_a": best.get("from"),
            "text_a": best.get("text", ""),
            "speaker_b": c.get("from"),
            "text_b": c.get("text", ""),
            "structural_similarity": round(similarity(best.get("text", ""), c.get("text", "")), 3),
            "instruction": "只输出 [REPEAT] / [PROGRESS] / [UNCERTAIN] 之一",
        })

    return {
        "needs_judgment": True,
        "prev_round": prev_round,
        "cur_round": cur_round,
        "pairs": pairs,
        "criteria": JUDGE_CRITERIA,
        "ignore": JUDGE_IGNORE,
        "focus": JUDGE_FOCUS,
        "output_format": "每个 pair 输出一个标签，写入 semantic_verdicts 后调用 record 子命令",
        "verdict_schema": {
            "round": "int，被判定为当前轮的轮次号",
            "from": "speaker_a",
            "to": "speaker_b",
            "label": "REPEAT | PROGRESS | UNCERTAIN",
            "reason": "一句话说明依据（可选但建议）",
        },
    }


def record_verdicts(state_path: str, state: dict, payload) -> dict:
    """写回语义判定。payload 可以是数组，或 {"verdicts": [...]}。"""
    if isinstance(payload, dict):
        items = payload.get("verdicts") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    else:
        die("verdicts 必须是数组或 {verdicts: [...]}")
    if not items:
        die("没有收到任何语义判定", 3)

    problems, cleaned = [], []
    for i, v in enumerate(items, 1):
        label = str(v.get("label", "")).strip().upper().strip("[]")
        if label not in LABELS:
            problems.append(f"第 {i} 条 label={v.get('label')!r} 不在 {LABELS} 内")
            continue
        rnd = v.get("round")
        if rnd is None:
            problems.append(f"第 {i} 条缺少 round")
            continue
        cleaned.append({
            "round": int(rnd),
            "from": v.get("from") or v.get("speaker_a"),
            "to": v.get("to") or v.get("speaker_b"),
            "label": label,
            "reason": v.get("reason", ""),
            "pair_id": v.get("pair_id"),
            "judged_by": v.get("judged_by", "host-judge"),
        })
    if problems:
        die("语义判定校验失败：\n  - " + "\n  - ".join(problems), 3)

    state.setdefault("semantic_verdicts", []).extend(cleaned)
    if state_path:                      # 供 orchestrator 内存态调用时跳过落盘
        save_state(state_path, state)
    by_round = {}
    for v in cleaned:
        by_round.setdefault(v["round"], {"REPEAT": 0, "PROGRESS": 0, "UNCERTAIN": 0})
        by_round[v["round"]][v["label"]] += 1
    return {
        "needs_judgment": False,
        "recorded": len(cleaned),
        "by_round": {str(k): v for k, v in sorted(by_round.items())},
        "note": "语义判定已写入 semantic_verdicts；下一步运行 check 判定是否熔断",
    }


def fuse(state_path: str, state: dict, reason: str = "") -> dict:
    result = check(state)
    state["fused"] = True
    state["fused_at_round"] = (result.get("latest") or {}).get("round")
    state["fuse_message"] = FUSE_TEMPLATE
    state["fuse_consecutive"] = max(result.get("consecutive_stalled", 0),
                                    state.get("fuse_consecutive", 0))
    state["fuse_trigger"] = result.get("trigger") or "manual"
    state["fuse_reason"] = reason or "；".join(result.get("reasons", [])) or "手动熔断"
    state["debate_closed"] = True
    save_state(state_path, state)
    return {
        "needs_judgment": False,
        "fused": True,
        "fused_at_round": state["fused_at_round"],
        "fuse_message": FUSE_TEMPLATE,
        "trigger": state["fuse_trigger"],
        "reason": state["fuse_reason"],
        "consecutive_stalled": state["fuse_consecutive"],
        "next_stage": "阶段三 铁血裁决（三选一）",
        "note": "辩论发言权已切断：后续不得再提交 stage2 交锋，直接进入投票",
    }


# --------------------------------------------------------------------------- #
# selftest
# --------------------------------------------------------------------------- #


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    def two_rounds():
        """两轮措辞不同、但核心论点相同的发言（结构相似度低，靠语义裁判抓）。"""
        return {
            "clash_exchanges": [
                {"from": "munger", "round": 2, "target_claim": "M1-1",
                 "text": "你忽略了上下文切换成本，这一项会让预算翻倍"},
                {"from": "musk", "round": 2, "target_claim": "G2-1",
                 "text": "切换成本只占 9%，不足以推翻结论"},
                {"from": "munger", "round": 3, "target_claim": "M1-1",
                 "text": "协调开销你没有计入，实际支出会远超预期"},
                {"from": "musk", "round": 3, "target_claim": "G2-1",
                 "text": "那部分开销占比很低，结论依然站得住"},
            ],
            "argument_log": [], "revisions": [],
            "stage1": {"tool_results": []}, "stage2": {"verifications": []},
        }

    def identical_rounds():
        """两轮逐字重复——结构路径该抓到的场景。"""
        base = [
            {"from": "munger", "target_claim": "M1-1",
             "text": "你忽略了上下文切换成本，这一项会让预算翻倍"},
            {"from": "musk", "target_claim": "G2-1",
             "text": "切换成本只占 9%，不足以推翻结论"},
        ]
        ex = []
        for rnd in (2, 3):
            for e in base:
                e2 = dict(e)
                e2["round"] = rnd
                ex.append(e2)
        return {"clash_exchanges": ex, "argument_log": [], "revisions": [],
                "stage1": {"tool_results": []}, "stage2": {"verifications": []}}

    # ---- 结构路径：逐字重复 ----
    st = identical_rounds()
    r = check(st)
    ck(r["deadlock"] is True and r["trigger"] == "structural",
       "逐字重复时结构路径判死锁")
    ck(FUSE_TEMPLATE in r["fuse_message"], "熔断话术与 V4.1 spec 一致")
    ck(LEGACY_FUSE_TEMPLATE != FUSE_TEMPLATE, "新话术已替换旧话术")

    # ---- 结构路径抓不到的换说法场景 ----
    soft = check(two_rounds())
    ck(soft["deadlock"] is False,
       "换了说法但结构相似度低时，结构路径抓不到（需语义裁判）")

    # ---- 语义路径：判 REPEAT 即熔断（哪怕结构相似度不高）----
    sem = two_rounds()
    sem["semantic_verdicts"] = [
        {"round": 3, "from": "munger", "to": "munger", "label": "REPEAT",
         "reason": "换词，核心论点未变"},
        {"round": 3, "from": "musk", "to": "musk", "label": "REPEAT",
         "reason": "同上"},
    ]
    r2 = check(sem)
    ck(r2["deadlock"] is True and r2["trigger"] == "semantic", "语义 REPEAT 直接触发熔断")
    ck(any("语义裁判" in x for x in r2["reasons"]), "熔断理由点明语义判定")

    # ---- 语义路径：有 PROGRESS 则放行 ----
    prog = two_rounds()
    prog["semantic_verdicts"] = [
        {"round": 3, "from": "munger", "to": "munger", "label": "PROGRESS",
         "reason": "提出了新的协调开销数据"},
    ]
    r3 = check(prog)
    ck(r3["deadlock"] is False, "语义判 PROGRESS 时即使结构相似也放行")

    # ---- 单轮 REPEAT 不足以熔断（需连续两轮）----
    one = two_rounds()
    one["argument_log"] = [{"round": 2, "is_new_key_argument": True}]  # 第 2 轮有推进
    one["semantic_verdicts"] = [{"round": 3, "from": "munger", "to": "munger", "label": "REPEAT"}]
    r4 = check(one)
    ck(r4["deadlock"] is False and r4["consecutive_stalled"] == 1,
       "只有当前轮 REPEAT 时连续停滞为 1，不熔断")

    # ---- 两轮都 REPEAT ----
    both = two_rounds()
    both["semantic_verdicts"] = [
        {"round": 2, "from": "munger", "to": "munger", "label": "REPEAT"},
        {"round": 3, "from": "munger", "to": "munger", "label": "REPEAT"},
    ]
    r5 = check(both)
    ck(r5["deadlock"] is True and r5["consecutive_stalled"] == 2, "连续两轮语义复读触发熔断")

    # ---- UNCERTAIN 不算复读也不算推进 ----
    unc = two_rounds()
    unc["semantic_verdicts"] = [{"round": 3, "from": "a", "to": "b", "label": "UNCERTAIN"}]
    s = round_semantic_summary(unc, 3)
    ck(s["semantic_repeat"] is None, "全为 UNCERTAIN 时语义结论为未定")

    # ---- 新增事实 → 不熔断 ----
    alive = two_rounds()
    alive["argument_log"] = [{"round": 3, "is_new_key_argument": True}]
    alive["revisions"] = [{"round": 3, "valid": True}]
    ck(check(alive)["deadlock"] is False, "有新论据与新立场时不熔断")

    # ---- judge 材料 ----
    mat = build_judge_material(two_rounds())
    ck(mat["cur_round"] == 3 and mat["prev_round"] == 2, "judge 默认取最后两轮")
    ck(len(mat["pairs"]) >= 1, "judge 生成配对材料")
    p0 = mat["pairs"][0]
    for k in ("speaker_a", "text_a", "speaker_b", "text_b", "pair_id"):
        ck(k in p0, f"配对材料含字段 {k}")
    ck(mat["criteria"]["REPEAT"] and mat["criteria"]["PROGRESS"], "judge 输出判定标准")
    ck("反问" in mat["criteria"]["PROGRESS"], "判定标准包含「反问/质疑算推进」")

    # ---- record ----
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "s.json"
        save_state(sp, two_rounds())
        stt = load_state(sp)
        rec = record_verdicts(str(sp), stt, [
            {"round": 3, "from": "munger", "to": "munger", "label": "[REPEAT]",
             "reason": "换词"},
            {"round": 3, "from": "musk", "to": "musk", "label": "progress"},
        ])
        ck(rec["recorded"] == 2, "record 接受带方括号与小写的标签并归一化")
        st2 = load_state(sp)
        ck(st2["semantic_verdicts"][0]["label"] == "REPEAT", "标签归一化为大写")
        ck(len(st2["semantic_verdicts"]) == 2, "判定写回 semantic_verdicts")

        try:
            record_verdicts(str(sp), st2, [{"round": 3, "label": "MAYBE"}])
            ck(False, "非法标签应被拒绝")
        except SystemExit:
            ck(True, "非法标签被拒绝")

        # 熔断
        sp2 = Path(td) / "s2.json"
        save_state(sp2, both)
        f = fuse(str(sp2), load_state(sp2), "测试熔断")
        ck(f["fused"] is True and f["trigger"] == "semantic", "熔断记录触发路径")
        st3 = load_state(sp2)
        ck(st3["debate_closed"] is True, "熔断后辩论关闭")
        ck(check(st3)["already_fused"] is True, "已熔断状态不重复判定")

    ck(similarity("完全相同的一句话", "完全相同的一句话") == 1.0, "相同文本相似度为 1")
    ck(similarity("完全不同的内容", "另一件毫不相干的事情") < 0.3, "不同文本相似度低")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="语义级死锁检测与强制熔断（V4.1）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)
    pc.add_argument("--rounds", type=int, default=ROUNDS_TO_DEADLOCK)
    pc.add_argument("--write", action="store_true", help="判定为死锁时自动熔断并写回")

    pj = sub.add_parser("judge", help="输出待判材料（供主持人做语义判定）")
    pj.add_argument("--state", required=True)
    pj.add_argument("--pair", help="上一轮-当前轮，如 2-3；默认取最后两轮")

    pr = sub.add_parser("record", help="写回语义判定")
    pr.add_argument("--state", required=True)
    pr.add_argument("--file", help="判定 JSON 文件，- 表示 stdin")
    pr.add_argument("--json", help="直接传 JSON")

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
    if args.cmd == "judge":
        emit(build_judge_material(load_state(args.state), args.pair))
        return 0
    if args.cmd == "record":
        st = load_state(args.state)
        raw = args.json if args.json else (
            sys.stdin.read() if args.file == "-"
            else Path(args.file).read_text(encoding="utf-8"))
        emit(record_verdicts(args.state, st, json.loads(raw)))
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

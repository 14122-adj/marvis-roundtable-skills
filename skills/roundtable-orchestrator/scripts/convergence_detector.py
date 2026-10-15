#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收敛检测器 convergence_detector.py

回答一个工程问题：**这场讨论是在推进，还是在原地打转？**

判定纪律（见 docs/output-contract.md §7）：脚本只做可计数的信号提取
（新增关键论据数量、质疑悬空时长、论断重复度、价值分歧占比、注入回应情况），
"是否真的触及根本矛盾"属于语义判断，脚本只给 candidate 并强制标注 needs_judgment。

用法：
  python convergence_detector.py check --state S [--write]
  python convergence_detector.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

VALUE_BASES = {"value_judgment", "intuition"}
SUBSTANTIVE = {"physical_constraint", "empirical", "case", "mechanism"}


def log(msg: str) -> None:
    print(f"[convergence_detector] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[convergence_detector] ERROR: {msg}", file=sys.stderr)
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


def _bigrams(text: str) -> set:
    t = unicodedata.normalize("NFKC", str(text)).lower()
    t = re.sub(r"[\s\W_]+", "", t, flags=re.UNICODE)
    if not t:
        return set()
    if len(t) < 2:
        return {t}
    return {t[i : i + 2] for i in range(len(t) - 1)}


def similarity(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def check(state: dict) -> dict:
    signals = []
    round_no = int(state.get("round", 0))
    roles = state.get("roles", [])
    claims = state.get("claims", [])
    injections = state.get("injections", [])
    divergences = state.get("meta", {}).get("divergences", [])
    hidden = state.get("meta", {}).get("hidden_assumptions", [])
    gaps = state.get("meta", {}).get("information_gaps", [])

    # 1) 每轮新增关键论据数
    per_round = {}
    for entry in state.get("argument_log", []):
        r = int(entry.get("round", 0))
        per_round.setdefault(r, {"claims": 0, "new_key": 0})
        per_round[r]["claims"] += 1
        per_round[r]["new_key"] += 1 if entry.get("is_new_key_argument") else 0

    trailing_zero = 0
    for r in sorted(per_round, reverse=True):
        if per_round[r]["new_key"] == 0:
            trailing_zero += 1
        else:
            break

    if trailing_zero >= 2:
        signals.append(f"连续 {trailing_zero} 轮没有新增关键论据（可能已在表层循环）")
    elif trailing_zero == 1:
        signals.append("最近一轮没有新增关键论据（暂不构成收敛，观察下一轮）")

    # 2) 论断重复度：找出最相似的一对
    worst = (0.0, None, None)
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            if claims[i].get("role") == claims[j].get("role") and claims[i].get("round") == claims[j].get("round"):
                continue
            s = similarity(claims[i].get("text", ""), claims[j].get("text", ""))
            if s > worst[0]:
                worst = (s, claims[i].get("id"), claims[j].get("id"))
    if worst[0] >= 0.7:
        signals.append(f"跨轮重复表述：{worst[1]} 与 {worst[2]} 相似度 {round(worst[0], 2)}（可能是同一观点换说法）")

    # 3) 注入回应情况
    pending = []
    for inj in injections:
        if not inj.get("applied"):
            pending.extend(inj.get("must_respond", []))
    if pending:
        signals.append(f"仍有未注入下一轮的隐性假设：{', '.join(sorted(set(pending)))}")

    # 角色对元认知条目（H/D/G/F/C）的回应由 state_manager 记录在 meta_engagement
    responded_meta = {e.get("meta_id") for e in state.get("meta_engagement", [])
                      if e.get("type") in ("adopt", "refine", "challenge", "support")}
    acknowledged = [h.get("id") for h in hidden if h.get("id") in responded_meta]
    if acknowledged:
        signals.append(f"隐性假设已被角色回应：{', '.join(acknowledged)}（可判断它是否仍然成立）")
    untouched = [h.get("id") for h in hidden if h.get("id") not in responded_meta]
    if hidden and len(untouched) == len(hidden) and round_no >= 2:
        signals.append("全部隐性假设尚未被任何角色正面回应：本轮的元反思注入没有生效")

    # 4) 分歧类型分布
    type_counts = {}
    for d in divergences:
        t = d.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts.get("value"):
        signals.append(f"存在 {type_counts['value']} 处价值分歧：逻辑论证无法消解，应显式承认不可调和")
    if type_counts.get("term"):
        signals.append(f"存在 {type_counts['term']} 处术语分歧：应先统一术语定义再继续辩论")
    if type_counts.get("pseudo"):
        signals.append(f"存在 {type_counts['pseudo']} 处伪分歧：双方立场其实一致，继续争论无增量")
    if type_counts.get("fact") and not gaps:
        signals.append("存在事实分歧但未登记任何信息缺口：事实分歧的消解路径不明")

    # 5) 悬空质疑
    stale = [c["id"] for c in state.get("open_challenges", [])
             if c.get("status") == "open" and round_no - int(c.get("round", c.get("raised_round", round_no))) >= 1]
    if stale:
        signals.append(f"悬空质疑超过一轮未答：{', '.join(stale[:5])}")

    # 6) 视角覆盖：从未提出任何论断的角色
    silent = [r for r in roles if not any(c.get("role") == r for c in claims)]
    if round_no >= 1 and silent:
        signals.append(f"尚未贡献任何论断的角色：{', '.join(silent)}")

    # 7) 根本矛盾 candidate（语义判断，需模型确认）
    root_candidate = bool(
        hidden
        and divergences
        and any(d.get("type") in ("value", "fact", "term") for d in divergences)
        and any(h.get("status") in (None, "open", "challenged") for h in hidden)
    )
    if root_candidate:
        signals.append("候选根因：已登记隐性假设并已分类分歧，可进入根因确认（需模型判断，脚本不代替结论）")

    # 8) 建议
    if round_no == 0:
        recommendation = "continue"
    elif trailing_zero >= 2:
        recommendation = "meta_intervene"
    elif trailing_zero == 1:
        recommendation = "deepen"
    else:
        recommendation = "continue"

    max_rounds = int(state.get("max_rounds", 3))
    close_recommended = False
    if round_no >= max_rounds:
        recommendation = "close"
        close_recommended = True
        signals.append(f"已达到最大轮次 {max_rounds}")
    elif trailing_zero >= 2 and root_candidate:
        recommendation = "close"
        close_recommended = True
        signals.append("连续无新增论据且已识别候选根因：可提前收敛")

    return {
        "needs_judgment": True,
        "round": round_no,
        "per_round_new_key_arguments": {str(k): v for k, v in sorted(per_round.items())},
        "rounds_without_new_argument": trailing_zero,
        "highest_similarity_pair": {"pair": [worst[1], worst[2]] if worst[1] else None,
                                    "similarity": round(worst[0], 3)},
        "divergence_type_counts": type_counts,
        "root_cause_candidate": root_candidate,
        "close_recommended": close_recommended,
        "recommendation": recommendation,
        "signals": signals,
        "note": "root_cause_candidate 只表示具备进入根因确认的结构条件，不构成已挖到根本的断言",
    }


def cmd_check(args) -> int:
    st = load_state(args.state)
    result = check(st)
    if args.write:
        st.setdefault("convergence", {})
        st["convergence"]["rounds_without_new_argument"] = result["rounds_without_new_argument"]
        st["convergence"]["root_cause_reached"] = bool(result["root_cause_candidate"])
        st["convergence"]["root_cause_note"] = "candidate，需模型确认" if result["root_cause_candidate"] else ""
        st["convergence"]["signals"] = result["signals"]
        st["convergence"]["recommendation"] = result["recommendation"]
        save_state(args.state, st)
        log(f"已写回 convergence: recommendation={result['recommendation']}")
    emit(result)
    return 0


def selftest() -> int:
    ok = True

    def check_(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    def base():
        return {
            "round": 1, "max_rounds": 3, "roles": ["musk", "pg"],
            "claims": [], "open_challenges": [], "injections": [],
            "argument_log": [], "meta_engagement": [],
            "meta": {"divergences": [], "hidden_assumptions": [], "information_gaps": []},
        }

    st = base()
    st["argument_log"] = [
        {"round": 1, "role": "musk", "claim_id": "M1-1", "is_new_key_argument": True},
    ]
    st["claims"] = [{"id": "M1-1", "role": "musk", "round": 1, "text": "物理下界决定成本", "responses_received": []}]
    r = check(st)
    check_(r["rounds_without_new_argument"] == 0, "有新增论据时不计为停滞")
    check_(r["recommendation"] == "continue", "正常推进时建议继续")

    st["argument_log"].append({"round": 2, "role": "pg", "claim_id": "P2-1", "is_new_key_argument": False})
    st["argument_log"].append({"round": 3, "role": "pg", "claim_id": "P3-1", "is_new_key_argument": False})
    st["round"] = 3
    st["claims"] += [
        {"id": "P2-1", "role": "pg", "round": 2, "text": "物理下界决定成本的高低", "responses_received": []},
        {"id": "P3-1", "role": "pg", "round": 3, "text": "物理下界决定成本的高低", "responses_received": []},
    ]
    r = check(st)
    check_(r["rounds_without_new_argument"] == 2, "连续两轮无新增论据被识别")
    check_(r["recommendation"] == "close", "达到最大轮次时建议收敛")
    check_(any("重复" in s or "相似度" in s for s in r["signals"]), "重复表述被识别")

    st = base()
    st["meta"]["hidden_assumptions"] = [{"id": "H1", "content": "竞赛必须拿奖才算成功", "status": "open"}]
    st["meta"]["divergences"] = [{"id": "D1", "type": "value"}, {"id": "D2", "type": "fact"}]
    st["meta"]["information_gaps"] = []
    st["injections"] = [{"round": 2, "must_respond": ["H1"], "applied": False}]
    st["claims"] = [{"id": "M1-1", "role": "musk", "round": 1, "text": "x", "responses_received": []}]
    st["round"] = 2
    r = check(st)
    check_(r["root_cause_candidate"] is True, "具备根因确认结构条件时给出 candidate")
    check_(r["needs_judgment"] is True, "候选人标记为需人工/模型判断")
    check_(any("未注入" in s for s in r["signals"]), "未注入的隐性假设被提示")
    check_(any("价值分歧" in s for s in r["signals"]), "价值分歧被提示为不可调和")
    check_(any("事实分歧" in s for s in r["signals"]), "事实分歧缺信息缺口被提示")
    check_(any("尚未被任何角色正面回应" in s for s in r["signals"]), "元反思注入未生效时给出信号")

    st["meta_engagement"] = [{"meta_id": "H1", "from": "musk", "round": 2, "type": "refine", "text": "承认该前提可疑"}]
    r = check(st)
    check_(any("已被角色回应" in s for s in r["signals"]), "角色回应元认知条目被识别")
    check_(not any("尚未被任何角色正面回应" in s for s in r["signals"]), "有回应后不再报注入失效")

    st = base()
    st["round"] = 1
    st["argument_log"] = [{"round": 1, "role": "musk", "claim_id": "M1-1", "is_new_key_argument": False}]
    st["claims"] = [{"id": "M1-1", "role": "musk", "round": 1, "text": "x", "responses_received": []}]
    r = check(st)
    check_(any("尚未贡献" in s for s in r["signals"]), "沉默角色被提示")
    check_(r["recommendation"] in ("deepen", "meta_intervene"), "停滞时给出加深或元认知干预建议")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="圆桌收敛检测器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)
    pc.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分歧类型分类器 divergence_classifier.py

把讨论中的冲突分成四类，因为**只有事实分歧能靠补充信息解决**：
  事实分歧（fact）   —— 需要证据，补上就可能收敛
  价值分歧（value）  —— 逻辑论证无法消解，只能显式承认不可调和
  术语分歧（term）   —— 双方对同一概念定义不同，吵的是词不是事
  伪分歧（pseudo）   —— 双方立场其实一致，只是表述不同

诚实边界：分类依赖语义，本脚本用"论据基础类型 + 表述相似度 + 定义标记词"做
**规则建议**，并把它与模型给出的类型做一致性核对。所有输出都带
needs_judgment 与 rationale，禁止把规则建议当结论使用。

用法：
  python divergence_classifier.py suggest --state S [--write]
  python divergence_classifier.py classify --input divergences.json        # 核对模型给出的分类
  python divergence_classifier.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

TYPES = ["fact", "value", "term", "pseudo"]
VALUE_BASES = {"value_judgment", "intuition"}
SUBSTANTIVE = {"physical_constraint", "empirical", "case", "mechanism"}
REDEF_MARKERS = [r"指的是", r"所谓", r"定义", r"我说的", r"你说的", r"在这里的意思是", r"我理解"]


def log(msg: str) -> None:
    print(f"[divergence_classifier] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[divergence_classifier] ERROR: {msg}", file=sys.stderr)
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
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", str(text)).lower(), flags=re.UNICODE)


def _bigrams(text: str) -> set:
    t = _norm(text)
    if not t:
        return set()
    return {t} if len(t) < 2 else {t[i : i + 2] for i in range(len(t) - 1)}


def similarity(a: str, b: str) -> float:
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def rule_classify(basis_a: str, basis_b: str, sim: float, text_b: str) -> tuple:
    """返回 (type_suggestion, confidence, rationale)。规则只做建议。"""
    b = (basis_b or "").lower()
    if any(re.search(m, str(text_b)) for m in REDEF_MARKERS):
        return "term", 0.45, "回应里出现定义/重命名标记词（指的是、所谓、定义等），可能是在争概念定义"
    if sim >= 0.8:
        return "pseudo", 0.5, f"双方表述相似度 {round(sim, 2)}，立场大概率一致，只有措辞差异"
    if basis_a in VALUE_BASES and basis_b in VALUE_BASES:
        return "value", 0.55, "双方论据均为价值判断/直觉，逻辑论证无法消解"
    if basis_a in SUBSTANTIVE and basis_b in SUBSTANTIVE:
        return "fact", 0.5, "双方都用了实质性论据（实测/案例/机制/约束），冲突点在于事实认定"
    if basis_a in VALUE_BASES or basis_b in VALUE_BASES:
        return "unclear", 0.25, "一方是价值判断、另一方是实质论据：可能是混合分歧，需模型判断"
    return "unclear", 0.2, "论据类型信息不足，规则无法给出有效建议"


def suggest_from_state(state: dict) -> dict:
    claims = {c["id"]: c for c in state.get("claims", [])}
    rounds_claims = {}
    for c in state.get("claims", []):
        rounds_claims.setdefault((c.get("role"), c.get("round")), []).append(c)

    candidates = []
    for ch in state.get("open_challenges", []):
        tgt = claims.get(ch.get("target_claim"))
        if not tgt:
            continue
        challenger_claims = rounds_claims.get((ch.get("from"), ch.get("round", tgt.get("round"))), [])
        if not challenger_claims:
            challenger_claims = [c for c in state.get("claims", []) if c.get("role") == ch.get("from")]
        best = None
        for cc in challenger_claims:
            s = similarity(cc.get("text", ""), tgt.get("text", ""))
            if best is None or s > best[0]:
                best = (s, cc)
        sim, own = (best if best else (0.0, None))
        t, conf, why = rule_classify(tgt.get("basis"), own.get("basis") if own else "", sim,
                                     ch.get("question", ""))
        candidates.append({
            "topic": f"{tgt.get('text', '')[:60]}",
            "sides": {tgt.get("role"): tgt.get("text", "")[:120],
                      ch.get("from"): (own.get("text", "")[:120] if own else ch.get("question", "")[:120])},
            "related_claim": tgt.get("id"),
            "challenge_id": ch.get("id"),
            "type_suggestion": t, "confidence": conf, "rationale": why,
            "resolution_path": {
                "fact": "需要补哪一条实测/公开数据？（应在信息缺口里登记）",
                "value": "承认不可调和：说明各自价值排序，不再试图用逻辑说服",
                "term": "先给双方概念下可操作定义，再重述各自主张",
                "pseudo": "指出表述差异，撤回其中一条以避免重复争论",
                "unclear": "需要模型判断：这属于事实、价值，还是术语问题",
            }.get(t, ""),
            "needs_judgment": True,
        })

    counts = {}
    for c in candidates:
        counts[c["type_suggestion"]] = counts.get(c["type_suggestion"], 0) + 1
    return {
        "needs_judgment": True,
        "candidates_found": len(candidates),
        "type_distribution": counts,
        "candidates": candidates,
        "note": "规则建议仅供参考；价值分歧与伪分歧的区分尤其依赖语境，必须由模型确认。",
    }


def classify_provided(divergences: list) -> dict:
    reviewed = []
    for i, d in enumerate(divergences, 1):
        t = d.get("type")
        if t not in TYPES:
            die(f"第 {i} 条分歧的 type={t!r} 不在 {TYPES} 内")
        sides = d.get("sides", {})
        rule_suggestion, conf, why = None, None, None
        if isinstance(sides, dict) and len(sides) >= 2:
            sides_texts = list(sides.values())
            sim = similarity(str(sides_texts[0]), str(sides_texts[1]))
            rule_suggestion, conf, why = rule_classify("", "", sim, str(sides_texts[1]))
        agreement = "unverifiable"
        if rule_suggestion in TYPES:
            agreement = "match" if rule_suggestion == t else "mismatch"
        reviewed.append({
            "id": d.get("id") or f"D{i}",
            "topic": d.get("topic", ""),
            "type": t,
            "sides": sides,
            "resolution_path": d.get("resolution_path", ""),
            "rule_suggestion": rule_suggestion,
            "rule_confidence": conf,
            "rule_rationale": why,
            "agreement": agreement,
            "needs_judgment": agreement != "match",
            "status": d.get("status", "open"),
        })
    return {
        "needs_judgment": True,
        "reviewed": reviewed,
        "mismatches": [r["id"] for r in reviewed if r["agreement"] == "mismatch"],
        "note": "agreement=mismatch 表示模型分类与规则建议不一致，需要人或模型给出最终裁定。",
    }


def merge_write(state: dict, result: dict) -> list:
    divs = state["meta"].setdefault("divergences", [])
    used = {d.get("id") for d in divs}
    added = []
    for cand in result["candidates"]:
        dup = any(d.get("topic", "")[:40] == cand["topic"][:40] for d in divs)
        if dup:
            continue
        n = 1
        while f"D{n}" in used:
            n += 1
        did = f"D{n}"
        used.add(did)
        divs.append({
            "id": did,
            "type": cand["type_suggestion"],
            "type_source": "rule_suggestion(候选)",
            "topic": cand["topic"],
            "sides": cand["sides"],
            "resolution_path": cand["resolution_path"],
            "confidence": cand["confidence"],
            "rationale": cand["rationale"],
            "related_claim": cand["related_claim"],
            "status": "open",
            "needs_judgment": True,
        })
        added.append(did)
    return added


def selftest() -> int:
    ok = True

    def check(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    check(rule_classify("value_judgment", "value_judgment", 0.2, "")[0] == "value", "双价值判断 → 价值分歧")
    check(rule_classify("empirical", "case", 0.2, "")[0] == "fact", "双实质论据 → 事实分歧")
    check(rule_classify("empirical", "empirical", 0.9, "")[0] == "pseudo", "表述高度相似 → 伪分歧")
    check(rule_classify("empirical", "case", 0.3, "你说的效率指的是什么")[0] == "term", "定义标记词 → 术语分歧")
    check(rule_classify("value_judgment", "empirical", 0.3, "")[0] == "unclear", "混合论据 → 交由模型判断")

    state = {
        "round": 2, "roles": ["musk", "pg"],
        "claims": [
            {"id": "M1-1", "role": "musk", "round": 1, "text": "成本下界由推进剂决定",
             "basis": "physical_constraint", "responses_received": [{"from": "pg", "type": "challenge"}]},
            {"id": "P2-1", "role": "pg", "round": 2, "text": "实际成本由制造良率决定",
             "basis": "case", "responses_received": []},
        ],
        "open_challenges": [{"id": "C1", "from": "pg", "to": "musk", "target_claim": "M1-1",
                             "question": "你的推演忽略了良率", "round": 2, "status": "open"}],
        "meta": {"divergences": []},
    }
    r = suggest_from_state(state)
    check(r["candidates_found"] == 1, "从悬空质疑中派生出分歧候选")
    c = r["candidates"][0]
    check(c["type_suggestion"] == "fact", "实质论据冲突被判为事实分歧候选")
    check(c["needs_judgment"] is True, "候选标注 needs_judgment")
    check("需要补哪一条实测" in c["resolution_path"], "事实分歧给出补证据的消解路径")

    added = merge_write(state, r)
    check(added == ["D1"] and state["meta"]["divergences"][0]["type"] == "fact", "候选写回获得 D 编号")
    check(merge_write(state, r) == [], "重复写回被去重")

    provided = [{"topic": "要不要追求规模", "type": "fact",
                 "sides": {"a": "应该快速扩张", "b": "应该先做深"}}]
    rev = classify_provided(provided)
    check(rev["reviewed"][0]["agreement"] in ("match", "mismatch", "unverifiable"), "模型分类可被核对")
    try:
        classify_provided([{"topic": "x", "type": "nonsense"}])
        check(False, "非法 type 应当报错")
    except SystemExit:
        check(True, "非法 type 被拒绝")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="分歧类型分类器（建议级 + 核对级）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("suggest")
    ps.add_argument("--state", required=True)
    ps.add_argument("--write", action="store_true")
    pc = sub.add_parser("classify")
    pc.add_argument("--input", required=True, help="模型给出的分歧清单 JSON（数组）")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "suggest":
        st = load_state(args.state)
        result = suggest_from_state(st)
        if args.write:
            added = merge_write(st, result)
            save_state(args.state, st)
            result["written_ids"] = added
            log(f"已写回 {len(added)} 条分歧候选: {added}")
        emit(result)
        return 0
    if args.cmd == "classify":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("divergences", [])
        emit(classify_provided(payload))
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

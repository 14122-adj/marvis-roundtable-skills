#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""隐性假设提取器 assumption_extractor.py

元认知监督者的第一件工具：把"所有角色共同默认、但从没被论证过的前提"捞出来。

诚实边界（docs/output-contract.md §7）：
  本脚本**不做语义判定**。它做的是：按句式信号抓片段 → 按相似度聚类 →
  统计"这条前提被几个角色共同使用、有没有人质疑过" → 输出 **候选**，
  每条都带原文证据与 heuristic_score，必须由模型/人工复核后才算隐性假设。
  真实讨论里最要紧的隐性假设常常没有任何句式标记，所以脚本抓不到的部分
  要由 meta-supervisor 的模型侧补齐。

用法：
  python assumption_extractor.py scan --state S [--write]
  python assumption_extractor.py scan --input roles.json          # 无 state 时用角色发言集合
  python assumption_extractor.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

PREMISE_MARKERS = [
    r"前提", r"假设", r"默认", r"大家都", r"众所周知", r"显然", r"本来就",
    r"必须", r"应该", r"通常", r"一般来说", r"行业惯例", r"行业标准", r"行业做法",
    r"一直(都)?这样", r"规则要求", r"按理说", r"毋庸置疑", r"基本共识",
]

SENT_SPLIT = re.compile(r"[。；;\n！!？?]")
CLUSTER_THRESHOLD = 0.6


def log(msg: str) -> None:
    print(f"[assumption_extractor] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[assumption_extractor] ERROR: {msg}", file=sys.stderr)
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
    """字符二元组 Jaccard 相似度。"""
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def containment(a: str, b: str) -> float:
    """Dice 系数：对长度差异更宽容，适合把"同一前提的不同说法"聚到一簇。"""
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return 2 * len(A & B) / (len(A) + len(B))


def extract_fragments(text: str, limit: int = 90) -> list:
    """切句后保留含前提类信号的句子。"""
    out = []
    for sent in SENT_SPLIT.split(str(text or "")):
        s = sent.strip()
        if not s or len(s) < 4:
            continue
        if any(re.search(m, s) for m in PREMISE_MARKERS):
            out.append(s[:limit])
    return out


def collect_candidates(state: dict = None, payload: dict = None) -> list:
    """收集 {role, round, fragment, source} 候选片段。"""
    items = []
    if state:
        for i, p in enumerate(state.get("shared_premises", [])):
            text = p if isinstance(p, str) else p.get("text", "")
            items.append({"role": "R0-共同前提", "round": 0, "fragment": text,
                          "source": "shared_premises", "claim_id": None})
        for c in state.get("claims", []):
            for frag in extract_fragments(c.get("text", "")) + extract_fragments(c.get("evidence", "")):
                items.append({"role": c.get("role"), "round": c.get("round"),
                              "fragment": frag, "source": "claim", "claim_id": c.get("id")})
    if payload:
        entries = payload.get("role_outputs", payload if isinstance(payload, list) else [])
        for entry in entries:
            role = entry.get("role", "unknown")
            rnd = entry.get("round", 0)
            for p in entry.get("premises", []) or []:
                items.append({"role": role, "round": rnd, "fragment": str(p),
                              "source": "declared_premise", "claim_id": None})
            for c in entry.get("claims", []) or []:
                for frag in extract_fragments(c.get("text", "")) + extract_fragments(c.get("evidence", "")):
                    items.append({"role": role, "round": rnd, "fragment": frag,
                                  "source": "claim", "claim_id": c.get("id")})
    return [i for i in items if i["fragment"]]


def cluster(items: list) -> list:
    clusters = []
    for it in items:
        placed = False
        for cl in clusters:
            if containment(it["fragment"], cl["representative"]) >= CLUSTER_THRESHOLD:
                cl["members"].append(it)
                placed = True
                break
        if not placed:
            clusters.append({"representative": it["fragment"], "members": [it]})
    return clusters


def challenged_claim_ids(state: dict) -> set:
    out = set()
    for c in (state or {}).get("claims", []):
        if any(r.get("type") == "challenge" for r in c.get("responses_received", [])):
            out.add(c.get("id"))
    for ch in (state or {}).get("open_challenges", []):
        if ch.get("target_claim"):
            out.add(ch["target_claim"])
    return out


def detect(state: dict = None, payload: dict = None) -> dict:
    items = collect_candidates(state, payload)
    clusters = cluster(items)
    roles_total = len((state or {}).get("roles", [])) or 6
    challenged = challenged_claim_ids(state)
    existing = [h.get("content", "") for h in (state or {}).get("meta", {}).get("hidden_assumptions", [])]

    candidates = []
    for cl in clusters:
        roles = sorted({m["role"] for m in cl["members"]})
        fragments = sorted({m["fragment"] for m in cl["members"]})
        declared = any(m["source"] == "declared_premise" for m in cl["members"])
        explicit_r0 = any(m["source"] == "shared_premises" for m in cl["members"])
        hit_ids = [m["claim_id"] for m in cl["members"] if m["claim_id"]]
        already_challenged = [i for i in hit_ids if i in challenged]

        # 结构启发式：跨角色共现 + 未被质疑 + 显式声明，分越高越值得复核
        score = 0.0
        score += 0.35 if len(roles) >= 2 else 0.0
        score += 0.15 if len(roles) >= max(3, roles_total // 2) else 0.0
        score += 0.25 if declared else 0.0
        score += 0.25 if explicit_r0 else 0.0
        score += 0.15 if len(cl["members"]) >= 3 else 0.0
        if hit_ids and len(already_challenged) == len(hit_ids):
            score -= 0.3  # 都已被质疑过，就不再是"未被讨论的"前提
        score = round(max(0.0, min(1.0, score)), 2)

        if len(roles) < 2 and not declared and not explicit_r0:
            continue  # 单个角色的孤例不算"共同默认"

        if explicit_r0:
            scope = "explicit(编排层 R0 列出的共享前提)"
        elif len(roles) >= roles_total - 1:
            scope = "all"
        elif len(roles) >= 2:
            scope = "majority"
        else:
            scope = "specific"

        dup = any(similarity(fragments[0], e) >= 0.7 for e in existing)
        candidates.append({
            "content": fragments[0],
            "scope": scope,
            "roles": roles,
            "evidence": fragments[:4],
            "sources": sorted({m["source"] for m in cl["members"]}),
            "challenged_claims": already_challenged,
            "heuristic_score": score,
            "duplicate_of_existing": dup,
            "suggested_question": (
                f"如果「{fragments[0][:40]}」这条前提不成立，你的结论还成立吗？"
                "它成立的理由是什么——是实测、是约束，还是习惯？"
            ),
            "challenge_effect": "（需模型填写：若该前提被推翻，讨论走向会怎样变化）",
            "needs_judgment": True,
        })

    candidates.sort(key=lambda c: (-c["heuristic_score"], c["content"]))
    return {
        "needs_judgment": True,
        "candidates_found": len(candidates),
        "candidates": candidates,
        "note": ("句式信号只是入口。没有标记词的隐性假设（例如所有人默认的成败标准）"
                 "脚本抓不到，必须由 meta-supervisor 模型侧补齐并人工核对。"),
        "stats": {"fragments": len(items), "clusters": len(clusters)},
    }


def merge_write(state: dict, result: dict) -> list:
    hidden = state["meta"].setdefault("hidden_assumptions", [])
    used = {h.get("id") for h in hidden}
    added = []
    for cand in result["candidates"]:
        if cand["duplicate_of_existing"]:
            continue
        n = 1
        while f"H{n}" in used:
            n += 1
        hid = f"H{n}"
        used.add(hid)
        hidden.append({
            "id": hid,
            "content": cand["content"],
            "scope": cand["scope"],
            "roles": cand["roles"],
            "first_seen_round": state.get("round", 0),
            "challenge_effect": cand["challenge_effect"],
            "suggested_question": cand["suggested_question"],
            "heuristic_score": cand["heuristic_score"],
            "source": "assumption_extractor(候选)",
            "status": "open",
        })
        added.append(hid)
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

    shared = "参赛作品必须拿到奖项才算成功"
    state = {
        "round": 1, "roles": ["musk", "pg", "jobs"],
        "shared_premises": [shared],
        "claims": [
            {"id": "M1-1", "role": "musk", "round": 1,
             "text": "前提是资源要按边际收益分配", "evidence": "推演", "responses_received": []},
            {"id": "P1-1", "role": "pg", "round": 1,
             "text": "我们的前提是资源应该按边际收益分配", "evidence": "案例", "responses_received": []},
            {"id": "J1-1", "role": "jobs", "round": 1,
             "text": "按行业惯例就该先做评审", "evidence": "惯例", "responses_received": []},
        ],
        "open_challenges": [],
        "meta": {"hidden_assumptions": []},
    }
    r = detect(state)
    check(r["needs_judgment"] is True, "输出标注需要语义判断")
    contents = [c["content"] for c in r["candidates"]]
    check(any("边际收益" in c for c in contents), "跨角色共现的前提被识别为候选")
    top = r["candidates"][0]
    check(top["heuristic_score"] >= 0.35, "跨角色共现给出非零启发式分")
    check(any(c["scope"].startswith("explicit") for c in r["candidates"]), "R0 共享前提被标为 explicit")

    # 单角色孤例不应成为候选
    lone = [c for c in r["candidates"] if c["content"] == "按行业惯例就该先做评审"]
    check(lone == [], "单角色孤例不作为共同假设候选")

    added = merge_write(state, r)
    check(len(added) >= 1 and state["meta"]["hidden_assumptions"][0]["id"] == "H1", "候选写回后获得 H 编号")
    r2 = detect(state)
    check(all(c["duplicate_of_existing"] for c in r2["candidates"]) or r2["candidates"] == [],
          "重复扫描时已登记的假设被判为重复")

    # 已全被质疑的前提降分
    state["open_challenges"] = [{"id": "C1", "target_claim": "M1-1", "status": "open"}]
    r3 = detect(state)
    check(isinstance(r3["candidates"], list) and all(c["needs_judgment"] for c in r3["candidates"]),
          "被质疑前提下调后仍可正常输出且均需复核")
    check_contains = [c for c in r3["candidates"] if "边际收益" in c["content"]]
    check(check_contains and check_contains[0]["challenged_claims"] == ["M1-1"],
          "已被质疑的前提被标注出来（供人判断是否已不再是隐性假设）")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="隐性假设提取器（候选级）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scan")
    ps.add_argument("--state")
    ps.add_argument("--input", help="无 state 时的角色发言 JSON 文件")
    ps.add_argument("--write", action="store_true", help="把候选写回 state.meta.hidden_assumptions")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "scan":
        state = load_state(args.state) if args.state else None
        payload = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else None
        if not state and not payload:
            die("需要 --state 或 --input 之一")
        result = detect(state, payload)
        if args.write:
            if not state:
                die("--write 需要 --state")
            added = merge_write(state, result)
            save_state(args.state, state)
            result["written_ids"] = added
            log(f"已写回 {len(added)} 条候选: {added}")
        emit(result)
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

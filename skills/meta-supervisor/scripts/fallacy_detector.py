#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逻辑谬误检测器 fallacy_detector.py

元认知监督者的第三件工具。定位是**筛子，不是法官**：
它用可解释的规则找出"值得检查的地方"，附上原文片段与触发原因，
由模型/人来判定是否为真谬误。绝不在输出里直接下"某某犯了稻草人谬误"的结论。

检测的六类（与 docs/output-contract.md §4 D 段一致）：
  strawman（稻草人）      —— 质疑的表述与对方原文相似度过低，可能曲解对方主张
  circular（循环论证）    —— 论断互相引用形成环（A 靠 B 支撑、B 靠 A 支撑）
  equivocation（偷换概念）—— 同一术语在不同角色处定义差异过大
  appeal_to_authority（诉诸权威）—— 只提权威/大厂/专家，没有数据或机制
  hasty_generalization（以偏概全）—— 用个案（basis=case）支撑"所有/一定/必然"式结论
  false_dilemma（假二分） —— 话术里只剩两个选项

用法：
  python fallacy_detector.py scan --state S [--write]
  python fallacy_detector.py scan --input role_outputs.json
  python fallacy_detector.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

FALLACY_TYPES = [
    "strawman", "circular", "equivocation",
    "appeal_to_authority", "hasty_generalization", "false_dilemma",
]
SEVERITY = {
    "strawman": "high", "circular": "high", "equivocation": "medium",
    "appeal_to_authority": "medium", "hasty_generalization": "medium", "false_dilemma": "low",
}
CLAIM_ID_RE = re.compile(r"\b([MFGJKP]\d+-\d+)\b")
FALSE_DILEMMA_RE = re.compile(r"(要么.{0,20}要么|不是.{0,15}就是|只有.{0,15}才|非此即彼|除此之外没有|唯一的出路)")
GENERAL_RE = re.compile(r"(所有|全部|任何|都(?:会|要|能)|一定|必然|从来|永远|无一例外|绝对)")
AUTHORITY_RE = re.compile(r"(专家|权威|大师|名企|头部公司|业界公认|大佬|行家|诺贝尔|研究所|官方)")
EVIDENCE_OF_DATA_RE = re.compile(r"(\d|%|％|倍|实验|实测|数据|样本|统计)")
RESTATE_RE = re.compile(r"(对方(?:认为|主张|就是说)|不过是在说|其实就是|等于说|说白了|言下之意)")


def log(msg: str) -> None:
    print(f"[fallacy_detector] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[fallacy_detector] ERROR: {msg}", file=sys.stderr)
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


def find_cycles(edges: dict, max_len: int = 4) -> list:
    """在 claim 引用图里找长度受限的环。"""
    cycles = []
    seen = set()

    def dfs(node, path):
        if len(path) > max_len:
            return
        for nxt in edges.get(node, []):
            if nxt == path[0] and len(path) >= 2:
                key = tuple(sorted(path))
                if key not in seen:
                    seen.add(key)
                    cycles.append(list(path))
                continue
            if nxt in path or nxt not in edges:
                continue
            dfs(nxt, path + [nxt])

    for node in list(edges):
        dfs(node, [node])
    return cycles


def detect(state: dict = None, payload: dict = None) -> dict:
    claims, responses, term_defs = [], [], []
    if state:
        claims = state.get("claims", [])
        for c in claims:
            for r in c.get("responses_received", []):
                r = dict(r)
                r["target"] = c["id"]
                r["target_text"] = c.get("text", "")
                r["target_role"] = c.get("role")
                responses.append(r)
        term_defs = state.get("term_definitions", []) or []
    if payload:
        entries = payload.get("role_outputs", payload if isinstance(payload, list) else [])
        for e in entries:
            for c in e.get("claims", []) or []:
                c = dict(c)
                c.setdefault("role", e.get("role"))
                c.setdefault("round", e.get("round", 0))
                claims.append(c)
            for r in e.get("responses", []) or []:
                r = dict(r)
                r["from"] = e.get("role")
                responses.append(r)
            term_defs.extend(e.get("term_definitions", []) or [])

    by_id = {c.get("id"): c for c in claims}
    out = []

    def add(ftype, role, quote, rationale, related=None, extra=None):
        item = {
            "type": ftype,
            "role": role,
            "quote": str(quote)[:160],
            "severity": SEVERITY.get(ftype, "low"),
            "rationale": rationale,
            "related": related,
            "needs_judgment": True,
            "disclaimer": "规则触发点，不构成谬误认定",
        }
        if extra:
            item.update(extra)
        out.append(item)

    for c in claims:
        text = c.get("text", "")
        evidence = c.get("evidence", "")
        role = c.get("role")
        m = FALSE_DILEMMA_RE.search(text)
        if m:
            add("false_dilemma", role, text,
                f"话术命中「{m.group(0)}」：把选项压缩成两个。需确认是否真有第三种可能。",
                related=c.get("id"))
        if c.get("basis") == "case" and GENERAL_RE.search(text):
            g = GENERAL_RE.search(text).group(0)
            add("hasty_generalization", role, text,
                f"basis=case（个案）却使用「{g}」作全称结论，n=1 不足以支撑。",
                related=c.get("id"), extra={"case_evidence": evidence[:120]})
        if AUTHORITY_RE.search(evidence) and not EVIDENCE_OF_DATA_RE.search(evidence):
            a = AUTHORITY_RE.search(evidence).group(0)
            add("appeal_to_authority", role, evidence,
                f"论据只出现权威来源「{a}」，没有任何数据、机制或可复现路径。",
                related=c.get("id"))

    # 循环论证：主张之间互相引用
    edges = {}
    for c in claims:
        cid = c.get("id")
        refs = set(CLAIM_ID_RE.findall(f"{c.get('evidence','')} {c.get('falsifiable_by','')}"))
        refs.discard(cid)
        if refs:
            edges[cid] = sorted(refs)
    for r in responses:
        if r.get("type") in ("support", "adopt") and r.get("from") and r.get("target"):
            src = None
            for c in claims:
                if c.get("role") == r.get("from") and c.get("id") != r.get("target"):
                    src = c.get("id")
                    break
            if src:
                edges.setdefault(src, [])
                edges[src] = sorted(set(edges[src]) | {r["target"]})
    for cyc in find_cycles(edges):
        add("circular", None, " → ".join(cyc),
            "论断引用关系构成闭环：互相支撑而没有外部证据落点。",
            related=cyc, extra={"cycle": cyc})

    # 稻草人：质疑表述与原文相似度过低
    for r in responses:
        if r.get("type") != "challenge" or not r.get("target_text"):
            continue
        sim = similarity(r.get("text", ""), r.get("target_text", ""))
        if sim < 0.2 and (RESTATE_RE.search(r.get("text", "")) or len(str(r.get("text", ""))) >= 30):
            add("strawman", r.get("from"), r.get("text", ""),
                f"质疑与对方原文相似度仅 {round(sim, 2)}，且使用了转述话术；"
                "核对是否在反驳对方真实主张（而不是更好反驳的版本）。",
                related=r.get("target"),
                extra={"target_text": r.get("target_text", "")[:160], "similarity": round(sim, 3)})

    # 偷换概念：同一术语不同定义
    grouped = {}
    for td in term_defs:
        term = str(td.get("term", "")).strip()
        grouped.setdefault(_norm(term), []).append(td)
    for key, items in grouped.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                if a.get("role") == b.get("role"):
                    continue
                s = similarity(a.get("definition", ""), b.get("definition", ""))
                if s < 0.5:
                    add("equivocation", f"{a.get('role')} vs {b.get('role')}",
                        f"{a.get('term')}: {a.get('definition')} ／ {b.get('term')}: {b.get('definition')}",
                        f"同一术语的两种定义相似度仅 {round(s, 2)}，双方可能在各说各的定义。",
                        related=a.get("term"), extra={"definitions": [a, b]})

    order = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda x: order.get(x["severity"], 3))
    counts = {}
    for f in out:
        counts[f["type"]] = counts.get(f["type"], 0) + 1
    return {
        "needs_judgment": True,
        "candidates_found": len(out),
        "type_distribution": counts,
        "candidates": out,
        "note": ("命中规则不等于成立谬误；未命中也不等于没问题——"
                 "本脚本只覆盖上述六类可规则化的模式。"),
    }


def merge_write(state: dict, result: dict) -> list:
    store = state["meta"].setdefault("fallacies", [])
    used = {f.get("id") for f in store}
    added = []
    for cand in result["candidates"]:
        dup = any(f.get("type") == cand["type"] and f.get("quote", "")[:40] == cand["quote"][:40]
                  for f in store)
        if dup:
            continue
        n = 1
        while f"F{n}" in used:
            n += 1
        fid = f"F{n}"
        used.add(fid)
        entry = dict(cand)
        entry["id"] = fid
        entry["source"] = "fallacy_detector(候选)"
        entry["round"] = state.get("round", 0)
        store.append(entry)
        added.append(fid)
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

    state = {
        "round": 2, "roles": ["musk", "pg", "jobs"],
        "claims": [
            {"id": "M1-1", "role": "musk", "round": 1,
             "text": "成本下界由推进剂决定", "basis": "physical_constraint",
             "evidence": "M1-2 的推演结果支撑", "falsifiable_by": "",
             "responses_received": [{"from": "pg", "type": "challenge",
                                     "text": "对方认为只要压低采购价就能解决全部成本问题，这个想法很天真"}]},
            {"id": "M1-2", "role": "musk", "round": 1,
             "text": "推进剂成本占大头", "basis": "empirical",
             "evidence": "M1-1 的结论反推", "falsifiable_by": "",
             "responses_received": []},
            {"id": "P1-1", "role": "pg", "round": 1,
             "text": "所有创业公司都应该先做小工具", "basis": "case",
             "evidence": "我经历过的一次项目", "falsifiable_by": "",
             "responses_received": []},
            {"id": "J1-1", "role": "jobs", "round": 1,
             "text": "要么做减法要么被复杂度拖死", "basis": "value_judgment",
             "evidence": "行业专家都这么说", "falsifiable_by": "",
             "responses_received": []},
        ],
        "term_definitions": [
            {"term": "效率", "role": "musk", "definition": "单位资源产出的物理量"},
            {"term": "效率", "role": "jobs", "definition": "用户完成任务需要付出的注意力和步骤数"},
        ],
        "meta": {"fallacies": []},
    }
    r = detect(state)
    types = {c["type"] for c in r["candidates"]}
    check(r["needs_judgment"] is True, "输出标注需要判断")
    check("circular" in types, "互相引用的论断被识别为循环论证候选")
    check("strawman" in types, "低相似度转述被识别为稻草人候选")
    check("hasty_generalization" in types, "个案全称结论被识别为以偏概全候选")
    check("false_dilemma" in types, "非此即彼话术被识别为假二分候选")
    check("appeal_to_authority" in types, "只提专家无数据被识别为诉诸权威候选")
    check("equivocation" in types, "同术语不同定义被识别为偷换概念候选")
    cyc = [c for c in r["candidates"] if c["type"] == "circular"][0]
    check(set(cyc["cycle"]) == {"M1-1", "M1-2"}, "环路成员正确")
    check(all(c["needs_judgment"] for c in r["candidates"]), "每条候选都标注需复核")

    added = merge_write(state, r)
    check(len(added) == len(r["candidates"]) and added[0].startswith("F"), "候选写回获得 F 编号")
    check(merge_write(state, r) == [], "重复写回被去重")

    # 干净数据不应误报
    clean = {"round": 1, "roles": ["musk"],
             "claims": [{"id": "M1-1", "role": "musk", "round": 1, "text": "推进剂占比约 70%",
                         "basis": "empirical", "evidence": "公开数据统计 n=12 样本", "falsifiable_by": "实测占比低于 50%",
                         "responses_received": []}],
             "term_definitions": [], "meta": {}}
    rc = detect(clean)
    check(rc["candidates_found"] == 0, "带数据与样本的论断不误报")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="逻辑谬误检测器（候选级）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("scan")
    ps.add_argument("--state")
    ps.add_argument("--input")
    ps.add_argument("--write", action="store_true")
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

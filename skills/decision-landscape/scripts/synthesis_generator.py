#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""决策景观生成器 synthesis_generator.py

Layer 4 的执行器：把讨论状态与元认知报告聚合成分区的**决策景观报告**，
而不是把发言按轮次拼接起来。

六个板块（docs/output-contract.md §6 的正式化）：
  1. 共识区（带共识强度与漂移剔除）
  2. 分歧区（带事实/价值/术语/伪分歧类型与消解路径）
  3. 隐性假设清单（带被回应情况）
  4. 决策建议（高置信度 / 中等 / 需补充信息）
  5. 信息缺口清单
  6. 少数派观点保护

诚实边界（契约 §7）：本脚本只做**结构聚合**。哪些支持是真支持、哪条分歧是否真的不可调和，
必须由模型/人复核——因此输出里凡涉及语义的字段都带 `needs_judgment`。

用法：
  python synthesis_generator.py build --state S [--out REPORT.md] [--json] [--min-support 2]
  python synthesis_generator.py check --state S
  python synthesis_generator.py selftest
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SUPPORT_TYPES = {"support", "adopt"}
CHALLENGE_TYPE = "challenge"
# 报告里禁止出现的断言（防"报告很好看但没有依据"）
FORBIDDEN_ASSERTIONS = ["已达成共识", "已验证", "已挖到根本", "已确认根因", "结论已确定"]


def log(msg: str) -> None:
    print(f"[synthesis_generator] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[synthesis_generator] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def load_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"状态文件不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 聚合
# --------------------------------------------------------------------------- #


def _confidence_level(conf):
    if conf is None:
        return "unknown"
    if conf >= 70:
        return "high"
    if conf >= 40:
        return "medium"
    return "needs_info"


def _responders(claim, kind="support"):
    out = []
    for r in claim.get("responses_received", []):
        t = r.get("type")
        if kind == "support" and t in SUPPORT_TYPES:
            out.append(r)
        elif kind == "challenge" and t == CHALLENGE_TYPE:
            out.append(r)
    return out


def build(state: dict, min_support: int = 2) -> dict:
    roles = state.get("roles", [])
    claims = state.get("claims", [])
    positions = state.get("positions", {})
    meta = state.get("meta", {})
    drifts = {r: (positions.get(r, {}).get("compliance_drift_count") or 0) for r in roles}
    drifted_roles = {r for r, n in drifts.items() if n >= 1}

    claim_by_id = {c["id"]: c for c in claims}

    # ---------- 1. 共识区 ----------
    consensus = []
    for c in claims:
        raw_supporters = sorted({r["from"] for r in _responders(c, "support") if r.get("from")})
        excluded = sorted(set(raw_supporters) & drifted_roles)
        effective = [r for r in raw_supporters if r not in drifted_roles]
        if not raw_supporters:
            continue
        if len(effective) >= len(roles):
            strength = "unanimous"
        elif len(effective) >= min_support:
            strength = "majority"
        else:
            strength = "weak"
        consensus.append({
            "claim_id": c["id"],
            "text": c["text"],
            "basis": c.get("basis"),
            "supporters_raw": raw_supporters,
            "supporters_effective": effective,
            "excluded_by_drift": excluded,
            "strength": strength,
            "counts_toward_consensus": len(effective) >= min_support,
            "needs_judgment": True,
            "note": "结构计数：某角色点了支持，不代表其支持的理由成立",
        })
    consensus.sort(key=lambda x: (not x["counts_toward_consensus"], -len(x["supporters_effective"])))

    # ---------- 2. 分歧区 ----------
    gaps = meta.get("information_gaps", [])
    divergences = []
    for d in meta.get("divergences", []):
        related_gap = None
        topic = str(d.get("topic", ""))
        for g in gaps:
            blob = f"{g.get('missing','')} {g.get('would_flip','')}"
            if topic and (topic[:12] in blob or (g.get("id") and g["id"] in str(d.get("resolution_path", "")))):
                related_gap = g.get("id")
                break
        divergences.append({
            "id": d.get("id"),
            "type": d.get("type"),
            "type_source": d.get("type_source", "model"),
            "topic": topic,
            "sides": d.get("sides", {}),
            "resolution_path": d.get("resolution_path", ""),
            "status": d.get("status", "open"),
            "related_gap": related_gap,
            "needs_gap": d.get("type") == "fact" and not related_gap,
            "needs_judgment": True,
        })
    divergence_by_type = {}
    for d in divergences:
        divergence_by_type.setdefault(str(d["type"]), []).append(d["id"])

    # ---------- 3. 隐性假设清单 ----------
    engagement = {}
    for e in state.get("meta_engagement", []):
        engagement.setdefault(e.get("meta_id"), []).append({
            "from": e.get("from"), "type": e.get("type"), "round": e.get("round"),
        })
    hidden = []
    for h in meta.get("hidden_assumptions", []):
        hid = h.get("id")
        eng = engagement.get(hid, [])
        hidden.append({
            "id": hid,
            "content": h.get("content"),
            "scope": h.get("scope"),
            "status": h.get("status", "open"),
            "responded_by": sorted({e["from"] for e in eng if e.get("from")}),
            "response_types": sorted({str(e["type"]) for e in eng}),
            "challenge_effect": h.get("challenge_effect", ""),
            "suggested_question": h.get("suggested_question", ""),
            "needs_judgment": True,
        })
    registered = {h.get("content") for h in meta.get("hidden_assumptions", [])}
    unregistered_premises = [p for p in state.get("shared_premises", []) if p not in registered]

    # ---------- 4. 决策建议 ----------
    revisions = state.get("revisions", [])
    advice = []
    for role in roles:
        pos = positions.get(role, {})
        if not pos.get("stance_summary"):
            continue
        role_revs = [r for r in revisions if r.get("role") == role and r.get("valid")]
        advice.append({
            "role": role,
            "text": pos.get("stance_summary"),
            "confidence": _confidence_level(pos.get("confidence")),
            "confidence_raw": pos.get("confidence"),
            "will_revise_if": pos.get("will_revise_if", ""),
            "revision_count": pos.get("revision_count", 0),
            "compliance_drift_count": pos.get("compliance_drift_count", 0),
            "evolution": [{"id": r.get("id"), "from": r.get("from"), "to": r.get("to"),
                           "trigger": r.get("trigger")} for r in role_revs],
            "needs_judgment": True,
        })
    advice.sort(key=lambda a: {"high": 0, "medium": 1, "needs_info": 2, "unknown": 3}[a["confidence"]])

    # ---------- 5. 信息缺口 ----------
    gap_list = [{
        "id": g.get("id"),
        "missing": g.get("missing"),
        "would_flip": g.get("would_flip"),
        "cost": g.get("cost"),
        "status": g.get("status", "open"),
        "needs_judgment": True,
    } for g in gaps]

    # ---------- 6. 少数派保护 ----------
    minority = []
    untested = []
    for c in claims:
        sup = _responders(c, "support")
        chl = _responders(c, "challenge")
        if chl and not sup:
            minority.append({
                "role": c.get("role"),
                "claim_id": c["id"],
                "text": c["text"],
                "basis": c.get("basis"),
                "evidence": c.get("evidence", ""),
                "falsifiable_by": c.get("falsifiable_by", ""),
                "challenges": [{"from": r.get("from"), "round": r.get("round"), "text": r.get("text", "")}
                               for r in chl],
                "refuted": False,
                "protection": "未被脚本判定为已反驳，必须完整保留论证",
                "needs_judgment": True,
            })
        elif not c.get("responses_received"):
            untested.append({"claim_id": c["id"], "role": c.get("role"), "text": c["text"]})

    return {
        "schema_version": "1.1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "needs_judgment": True,
        "topic": state.get("topic", ""),
        "session_id": state.get("session_id", ""),
        "mode": state.get("mode"),
        "rounds_completed": state.get("round"),
        "phase": state.get("phase"),
        "min_support": min_support,
        "roles": roles,
        "consensus": consensus,
        "divergences": divergences,
        "divergence_by_type": divergence_by_type,
        "hidden_assumptions": hidden,
        "unregistered_shared_premises": unregistered_premises,
        "advice": advice,
        "information_gaps": gap_list,
        "minority_views": minority,
        "untested_claims": untested,
        "convergence": state.get("convergence", {}),
        "quality_reviews": meta.get("reviews", []),
        "roles_without_claims": [r for r in roles if not any(c.get("role") == r for c in claims)],
    }


def render_markdown(report: dict) -> str:
    r = report

    def line(x=""):
        return x

    L = []
    L.append(f"# 决策景观报告：{r['topic']}")
    L.append("")
    L.append(f"- 会话：`{r['session_id']}`　模式：{r['mode']}　完成轮次：{r['rounds_completed']}　阶段：{r['phase']}")
    L.append(f"- 生成时间：{r['generated_at']}")
    L.append("- **本报告是结构聚合的产物**：所有结论性条目都需复核（`needs_judgment`）；"
             "报告负责把依据摆清楚，不替使用者下最终判断。")
    L.append("")

    # 1 共识区
    L.append("## 一、共识区（候选，需复核）")
    valid = [c for c in r["consensus"] if c["counts_toward_consensus"]]
    if not valid:
        L.append("")
        L.append(f"无。按当前口径（≥{r['min_support']} 个角色的明确支持）没有任何结论达到共识门槛——"
                 "这是正常结果，不为报告完整性而凑条目。")
    for c in valid:
        L.append("")
        L.append(f"- **{c['claim_id']}**（{c['strength']}）{c['text']}")
        L.append(f"  - 支持者：{', '.join(c['supporters_effective']) or '无'}"
                 + (f"；因从众漂移被剔除：{', '.join(c['excluded_by_drift'])}" if c["excluded_by_drift"] else ""))
        L.append(f"  - 论据类型：{c['basis']}")
    weak = [c for c in r["consensus"] if not c["counts_toward_consensus"]]
    if weak:
        L.append("")
        L.append("弱支持（未达门槛，仅供观察）：")
        for c in weak:
            L.append(f"- {c['claim_id']}（支持者 {', '.join(c['supporters_effective']) or '无'}）：{c['text']}")
    L.append("")

    # 2 分歧区
    L.append("## 二、分歧区")
    if not r["divergences"]:
        L.append("")
        L.append("未登记分歧。注意：没有分歧不等于有共识，可能只是没有被检验（见第六节与未检验清单）。")
    type_cn = {"fact": "事实分歧（可补信息解决）", "value": "价值分歧（逻辑无法消解）",
               "term": "术语分歧（需统一定义）", "pseudo": "伪分歧（立场其实一致）",
               "unclear": "待判定（需模型/人裁定）"}
    for d in r["divergences"]:
        L.append("")
        L.append(f"- **{d['id']} · {type_cn.get(str(d['type']), d['type'])}**")
        L.append(f"  - 议题：{d['topic']}")
        for k, v in (d["sides"] or {}).items():
            L.append(f"  - {k}：{v}")
        if d["resolution_path"]:
            L.append(f"  - 消解路径：{d['resolution_path']}")
        if d["needs_gap"]:
            L.append("  - ⚠ 这是事实分歧但没有配套的信息缺口 G：消解路径不明（必须在交付前补上或说明为何不可得）")
    L.append("")

    # 3 隐性假设
    L.append("## 三、隐性假设清单")
    if not r["hidden_assumptions"]:
        L.append("")
        L.append("无登记。若确实一场讨论下来一条都没抓到，应回看元认知层是否按清单执行。")
    for h in r["hidden_assumptions"]:
        L.append("")
        L.append(f"- **{h['id']}**（{h['scope']}，状态 {h['status']}）：{h['content']}")
        L.append(f"  - 被回应的角色：{', '.join(h['responded_by']) or '无'}"
                 + (f"｜回应方式：{', '.join(h['response_types'])}" if h["response_types"] else ""))
        if h["challenge_effect"]:
            L.append(f"  - 若被推翻的影响：{h['challenge_effect']}")
    if r["unregistered_shared_premises"]:
        L.append("")
        L.append("未被登记为 H 的共享前提（完整性缺口，需补登记）：")
        for p in r["unregistered_shared_premises"]:
            L.append(f"- {p}")
    L.append("")

    # 4 决策建议
    L.append("## 四、决策建议（按置信度分级）")
    L.append("")
    L.append("> 置信度是**角色自报值**，不是系统测量值；从众漂移过的角色其置信度不应被计为有效支持。")
    for level, label in (("high", "高置信度（≥70）"), ("medium", "中等置信度（40–69）"),
                         ("needs_info", "需补充信息（<40）"), ("unknown", "未提供置信度")):
        items = [a for a in r["advice"] if a["confidence"] == level]
        if not items:
            continue
        L.append("")
        L.append(f"### {label}")
        for a in items:
            flag = f"　⚠ 从众漂移 {a['compliance_drift_count']} 次" if a["compliance_drift_count"] else ""
            L.append(f"- **{a['role']}**（{a['confidence_raw']}/100{flag}）：{a['text']}")
            if a["will_revise_if"]:
                L.append(f"  - 愿意修正的条件：{a['will_revise_if']}")
            for ev in a["evolution"]:
                L.append(f"  - 立场演化 {ev['id']}：{ev['from']} → **{ev['to']}**（触发：{ev['trigger']}）")
    L.append("")

    # 5 信息缺口
    L.append("## 五、信息缺口清单")
    if not r["information_gaps"]:
        L.append("")
        L.append("无登记。若存在事实分歧，这里应当至少有一条。")
    for g in r["information_gaps"]:
        L.append("")
        L.append(f"- **{g['id']}**（获取成本 {g['cost']}，状态 {g['status']}）")
        L.append(f"  - 缺失信息：{g['missing']}")
        if g["would_flip"]:
            L.append(f"  - 若补上，可能翻转的判断：{g['would_flip']}")
    L.append("")

    # 6 少数派
    L.append("## 六、少数派观点保护")
    if not r["minority_views"]:
        L.append("")
        L.append("无。")
    for m in r["minority_views"]:
        L.append("")
        L.append(f"- **{m['claim_id']}（{m['role']}）**：{m['text']}")
        L.append(f"  - 论据类型：{m['basis']}；证据：{m['evidence'] or '（未提供）'}")
        if m["falsifiable_by"]:
            L.append(f"  - 可被推翻的条件：{m['falsifiable_by']}")
        for ch in m["challenges"]:
            L.append(f"  - 收到的质疑（{ch['from']}，第 {ch['round']} 轮）：{ch['text']}")
        L.append("  - 处置：未被判定为已反驳，**完整保留**；不得以多数意见覆盖。")
    L.append("")

    # 附录
    L.append("## 附录 A · 未被检验的主张")
    if not r["untested_claims"]:
        L.append("")
        L.append("无。")
    else:
        L.append("")
        L.append(f"共 {len(r['untested_claims'])} 条主张从未被任何角色检验——讨论热度与检验覆盖率是两件事：")
        for u in r["untested_claims"]:
            L.append(f"- {u['claim_id']}（{u['role']}）：{u['text'][:80]}")
    if r["roles_without_claims"]:
        L.append("")
        L.append(f"附录 B · 未贡献任何主张的角色：{', '.join(r['roles_without_claims'])}")
    L.append("")
    L.append("---")
    L.append("报告完。所有标记 `needs_judgment` 的条目需在交付前由模型或人复核。")
    return "\n".join(L)


def check(state: dict) -> dict:
    """完整性检查：不判断对错，只找结构上的漏洞。"""
    report = build(state)
    roles = state.get("roles", [])
    positions = state.get("positions", {})
    drifted = [r for r in roles if (positions.get(r, {}).get("compliance_drift_count") or 0) >= 1]

    minority_ok = all(m["refuted"] is False for m in report["minority_views"])
    weak = [c["claim_id"] for c in report["consensus"]
            if c["counts_toward_consensus"] and (c["strength"] == "weak" or c["excluded_by_drift"])]
    gaps_missing = [d["id"] for d in report["divergences"] if d["needs_gap"]]
    warnings = []
    if len(drifted) >= 3:
        warnings.append(f"{len(drifted)} 个角色发生过从众漂移（{', '.join(drifted)}）：当前共识可能是假共识")
    if report["consensus"] and not report["divergences"] and not report["minority_views"]:
        warnings.append("只有共识没有分歧与少数派：高度可疑，通常是检验覆盖率不足")
    if report["roles_without_claims"]:
        warnings.append(f"这些角色没有贡献任何主张：{', '.join(report['roles_without_claims'])}")
    if report["unregistered_shared_premises"]:
        warnings.append("存在未登记为 H 的共享前提，隐性假设清单不完整")

    return {
        "needs_judgment": True,
        "minority_preserved": minority_ok,
        "minority_count": len(report["minority_views"]),
        "weak_consensus": weak,
        "drift_roles": drifted,
        "consensus_suspect": len(drifted) >= 3,
        "gaps_missing_for_fact_divergence": gaps_missing,
        "untested_claims": len(report["untested_claims"]),
        "warnings": warnings,
        "verdict": "pass_with_review" if not (gaps_missing or warnings) else "needs_attention",
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def cmd_build(args) -> int:
    state = load_state(args.state)
    report = build(state, args.min_support)
    if args.json:
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
            log(f"已写入 {args.out}")
        else:
            print(payload)
        return 0
    md = render_markdown(report)
    bad = [p for p in FORBIDDEN_ASSERTIONS if p in md]
    if bad:
        die(f"报告含禁止断言 {bad}（不应声称未执行的动作）", 3)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        log(f"已写入 {args.out}")
    else:
        print(md)
    return 0


def cmd_check(args) -> int:
    emit(check(load_state(args.state)))
    return 0


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    state = {
        "schema_version": "1.0", "session_id": "rt-selftest",
        "topic": "【自检】决策景观", "mode": "rigorous", "round": 2,
        "phase": "closed", "roles": ["musk", "pg", "jobs"], "max_rounds": 3,
        "shared_premises": ["必须拿奖才算成功", "预算固定"],
        "claims": [
            {"id": "M1-1", "role": "musk", "round": 1, "text": "成本由推进剂决定",
             "basis": "mechanism", "evidence": "推演", "falsifiable_by": "实测",
             "responses_received": [{"from": "pg", "type": "support", "round": 2, "text": "同意"},
                                    {"from": "jobs", "type": "support", "round": 2, "text": "同意"}]},
            {"id": "P1-1", "role": "pg", "round": 1, "text": "案例显示按覆盖面分配更好",
             "basis": "case", "evidence": "示例案例", "falsifiable_by": "反例",
             "responses_received": [{"from": "musk", "type": "challenge", "round": 2, "text": "n=1 不足以支撑"}]},
            {"id": "J1-1", "role": "jobs", "round": 1, "text": "砍掉两级评审",
             "basis": "value_judgment", "evidence": "终点倒推", "falsifiable_by": "记录",
             "responses_received": []},
        ],
        "positions": {
            "musk": {"stance_summary": "先算下界", "confidence": 75, "revision_count": 0,
                     "compliance_drift_count": 0, "will_revise_if": "实测数据"},
            "pg": {"stance_summary": "案例优先", "confidence": 45, "revision_count": 0,
                   "compliance_drift_count": 0, "will_revise_if": "反例"},
            "jobs": {"stance_summary": "砍评审", "confidence": 30, "revision_count": 0,
                     "compliance_drift_count": 1, "will_revise_if": ""},
        },
        "revisions": [], "meta_engagement": [{"meta_id": "H1", "from": "pg", "round": 2, "type": "adopt"}],
        "meta": {
            "hidden_assumptions": [{"id": "H1", "content": "必须拿奖才算成功", "scope": "all", "status": "open",
                                    "challenge_effect": "分配逻辑整体改变"}],
            "divergences": [{"id": "D1", "type": "fact", "topic": "成本由什么决定", "sides": {"musk": "推进剂", "pg": "良率"},
                             "resolution_path": "需要实测", "status": "open"},
                            {"id": "D2", "type": "value", "topic": "评审该不该砍", "sides": {"jobs": "该砍", "musk": "先看风险"},
                             "resolution_path": "承认不可调和", "status": "open"}],
            "information_gaps": [], "fallacies": [], "reviews": [],
        },
        "convergence": {"rounds_without_new_argument": 0, "recommendation": "close"},
    }

    rep = build(state)
    # 共识：M1-1 有 pg/jobs 支持
    m = [c for c in rep["consensus"] if c["claim_id"] == "M1-1"][0]
    ck(m["strength"] == "weak" and m["counts_toward_consensus"] is False,
       "支持者中有漂移角色时共识强度被降级为 weak")
    ck(m["excluded_by_drift"] == ["jobs"], "从众漂移角色的支持被剔除")

    # 清除漂移后应当恢复为 majority
    state["positions"]["jobs"]["compliance_drift_count"] = 0
    rep2 = build(state)
    m2 = [c for c in rep2["consensus"] if c["claim_id"] == "M1-1"][0]
    ck(m2["strength"] == "majority" and m2["counts_toward_consensus"] is True,
       "两名角色的明确支持 → majority 共识候选")
    state["positions"]["jobs"]["compliance_drift_count"] = 1
    # 少数派：P1-1 有质疑无支持
    ck([x["claim_id"] for x in rep["minority_views"]] == ["P1-1"], "有质疑无支持的主张进入少数派保护")
    ck(rep["minority_views"][0]["refuted"] is False, "少数派默认标记为未被反驳")
    ck("完整保留" in rep["minority_views"][0]["protection"], "少数派带保护说明")
    # 事实分歧缺信息缺口
    ck([d["id"] for d in rep["divergences"] if d["needs_gap"]] == ["D1"], "事实分歧缺 G 被标记")
    # 未检验主张
    ck([u["claim_id"] for u in rep["untested_claims"]] == ["J1-1"], "从未被回应的主张被单独列出")
    # 建议分级
    levels = {a["role"]: a["confidence"] for a in rep["advice"]}
    ck(levels["musk"] == "high" and levels["pg"] == "medium" and levels["jobs"] == "needs_info",
       "决策建议按置信度分成 high/medium/needs_info")

    md = render_markdown(rep)
    for sec in ["## 一、共识区", "## 二、分歧区", "## 三、隐性假设清单",
                "## 四、决策建议", "## 五、信息缺口清单", "## 六、少数派观点保护"]:
        ck(sec in md, f"报告含板块 {sec}")
    ck(not any(p in md for p in FORBIDDEN_ASSERTIONS), "报告不含禁止断言")
    ck("必须拿奖才算成功" in md and "H1" in md, "隐性假设被写入报告")

    c = check(state)
    ck(c["minority_preserved"] is True, "完整性检查：少数派被保留")
    ck(c["gaps_missing_for_fact_divergence"] == ["D1"], "完整性检查：事实分歧缺缺口被报出")
    ck(c["verdict"] == "needs_attention", "存在缺口时判定为需处理")
    ck(c["drift_roles"] == ["jobs"] and c["consensus_suspect"] is False, "单角色漂移不判为假共识")

    # 三个角色都漂移 → 共识可疑
    for r in state["positions"].values():
        r["compliance_drift_count"] = 1
    c2 = check(state)
    ck(c2["consensus_suspect"] is True and any("假共识" in w for w in c2["warnings"]),
       "多数角色漂移时提示假共识风险")

    # 空状态不应崩
    empty = {"topic": "空", "roles": ["musk"], "session_id": "x", "claims": [], "positions": {},
             "meta": {"hidden_assumptions": [], "divergences": [], "information_gaps": [], "reviews": []},
             "shared_premises": [], "revisions": [], "meta_engagement": [], "convergence": {}}
    md2 = render_markdown(build(empty))
    ck("无。" in md2 or "没有任何结论达到共识门槛" in md2, "空状态生成占位文案而不崩溃")
    ck(check(empty)["minority_preserved"] is True, "空状态完整性检查通过")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="决策景观生成器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--state", required=True)
    pb.add_argument("--out")
    pb.add_argument("--json", action="store_true")
    pb.add_argument("--min-support", type=int, default=2)
    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "build":
        return cmd_build(args)
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

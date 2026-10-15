#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""圆桌讨论状态管理器 state_manager.py

维护 roundtable-state.json：登记角色论断、更新立场基线、推进轮次、生成交接摘要。

设计纪律（见 docs/output-contract.md §7）：
  * 只依赖 Python 标准库；
  * stdout 只输出 JSON（或 --text 时输出人类可读文本），日志一律走 stderr；
  * 语义判断（什么叫隐性假设、什么算根本矛盾）不在这里做，脚本只做结构化工件。

用法示例：
  python state_manager.py init --topic "议题" --out .roundtable
  python state_manager.py begin-round --state .roundtable/rt-x/state.json --round 1
  python state_manager.py add-claims --state S --file musk-round1.json
  python state_manager.py add-position --state S --file musk-round1.json
  python state_manager.py summary --state S --json
  python state_manager.py get --state S --path meta.hidden_assumptions
  python state_manager.py set --state S --path meta.reviews --append --value @review.json
  python state_manager.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = "1.0"
DEFAULT_ROLES = ["musk", "feynman", "munger", "jobs", "karpathy", "pg"]
ROLE_PREFIX = {"musk": "M", "feynman": "F", "munger": "G", "jobs": "J", "karpathy": "K", "pg": "P"}
PREFIX_ROLE = {v: k for k, v in ROLE_PREFIX.items()}
BASIS_ENUM = [
    "physical_constraint",
    "empirical",
    "case",
    "mechanism",
    "analogy",
    "value_judgment",
    "intuition",
]
# 实质性论据基础：只有这些 basis 才有可能算作"新增关键论据"
SUBSTANTIVE_BASIS = {"physical_constraint", "empirical", "case", "mechanism"}
CLAIM_ID_RE = re.compile(r"^([MFGJKP])(\d+)-(\d+)$")
ROUND_PHASE = {
    0: ("prepare", "parallel_isolated"),
    1: ("opening", "parallel_isolated"),
    2: ("probing", "cross_exam"),
    3: ("synthesis", "cross_exam"),
}
ROUND_GOALS = {
    0: [
        "定义议题边界与成功判据",
        "显式列出大家默认接受但未论证的前提（写入 shared_premises）",
    ],
    1: [
        "亮出各自的判断、论据与认知边界（confidence / uncertainty_points / will_revise_if）",
        "本轮为隔离发言：不得把他人发言当作论据来源，避免锚定",
    ],
    2: [
        "探究对方论据中存疑的前提、证据、边界条件",
        "自主选择追问对象（1 人或多人皆可，不作硬性配对）",
        "必须回应编排层注入的隐性假设与未决质疑",
    ],
    3: [
        "整合全部视角，识别矛盾的根源，判断哪些分歧不可调和",
        "明确哪些结论仍需补充信息才能定论",
    ],
    "default": ["整合视角，识别矛盾根源，输出可交接给决策景观的结论"],
}

# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #


def log(msg: str) -> None:
    print(f"[state_manager] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[state_manager] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def _bigrams(text: str) -> set:
    t = _norm(text)
    if not t:
        return set()
    if len(t) < 2:
        return {t}
    return {t[i : i + 2] for i in range(len(t) - 1)}


def similarity(a: str, b: str) -> float:
    """字符二元组的 Jaccard 相似度，用于判断两条论断是否只是换个说法重复。"""
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def load_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"状态文件不存在: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"状态文件不是合法 JSON: {exc}")


def save_state(path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def get_path(data, dotted: str):
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                die(f"路径不存在: {dotted}")
            cur = cur[part]
        else:
            die(f"路径无法继续下钻: {dotted}")
    return cur


def set_path(data, dotted: str, value, append: bool = False):
    parts = dotted.split(".")
    cur = data
    for part in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            if part not in cur or cur[part] is None:
                cur[part] = {}
            cur = cur[part]
    last = parts[-1]
    if append:
        if isinstance(cur, list):
            cur.append(value)
            return cur[-1]
        target = cur.setdefault(last, [])
        if not isinstance(target, list):
            die(f"路径 {dotted} 不是列表，无法 --append")
        target.append(value)
        return target[-1]
    cur[last] = value
    return value


def read_payload(file_arg: str | None, json_arg: str | None):
    """从 --file（支持 - 读 stdin）或 --json 读入 JSON。"""
    if json_arg:
        raw = json_arg
    elif file_arg:
        raw = sys.stdin.read() if file_arg == "-" else Path(file_arg).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    if not raw.strip():
        die("没有收到输入内容（--file / --json / stdin 都为空）")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        die(f"输入不是合法 JSON: {exc}")


# --------------------------------------------------------------------------- #
# 状态骨架
# --------------------------------------------------------------------------- #


def empty_position() -> dict:
    return {
        "stance_summary": "",
        "confidence": None,
        "key_claims": [],
        "uncertainty_points": [],
        "will_revise_if": "",
        "blind_spot_declared": "",
        "revision_count": 0,
        "compliance_drift_count": 0,
    }


def new_state(topic: str, mode: str = "rigorous", max_rounds: int = 3,
              roles=None, session_id: str | None = None) -> dict:
    roles = list(roles or DEFAULT_ROLES)
    unknown = [r for r in roles if r not in ROLE_PREFIX]
    if unknown:
        die(f"未知角色: {unknown}（合法角色: {list(ROLE_PREFIX)}）")
    sid = session_id or ("rt-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex())
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": sid,
        "topic": topic,
        "mode": mode,
        "round": 0,
        "max_rounds": max_rounds,
        "phase": "prepare",
        "roles": roles,
        "interaction_mode": "parallel_isolated",
        "shared_premises": [],
        "positions": {r: empty_position() for r in roles},
        "claims": [],
        "open_challenges": [],
        "meta": {
            "reviews": [],
            "hidden_assumptions": [],
            "divergences": [],
            "information_gaps": [],
            "fallacies": [],
        },
        "injections": [],
        "meta_engagement": [],
        "argument_log": [],
        "revisions": [],
        "convergence": {
            "rounds_without_new_argument": 0,
            "root_cause_reached": False,
            "root_cause_note": "",
            "signals": [],
            "recommendation": "continue",
        },
        "next_round": {
            "round": 1,
            "interaction_mode": "parallel_isolated",
            "goals": [],
            "must_respond": [],
            "may_revise": False,
            "notes": "",
        },
    }


# --------------------------------------------------------------------------- #
# 论断登记
# --------------------------------------------------------------------------- #


def validate_claim_id(claim_id: str, role: str, round_no: int) -> None:
    m = CLAIM_ID_RE.match(str(claim_id or ""))
    if not m:
        die(f"claim id 不合规: {claim_id!r}（应为 <角色前缀><轮次>-<序号>，如 M2-1）")
    prefix, rnd, _seq = m.group(1), int(m.group(2)), m.group(3)
    if PREFIX_ROLE.get(prefix) != role:
        die(f"claim id {claim_id} 的前缀 {prefix} 与角色 {role} 不匹配（应为 {ROLE_PREFIX[role]}）")
    if rnd != int(round_no):
        die(f"claim id {claim_id} 的轮次 {rnd} 与声明的轮次 {round_no} 不一致")


def next_challenge_id(state: dict) -> str:
    used = {c.get("id", "") for c in state["open_challenges"]}
    i = 1
    while f"C{i}" in used:
        i += 1
    return f"C{i}"


def add_claims(state: dict, payload: dict, new_argument: str = "auto") -> dict:
    """登记一个角色一轮发言里的全部 claims，并把 responses 转成质疑登记。"""
    if isinstance(payload, dict) and "claims" in payload:
        role = payload.get("role")
        round_no = payload.get("round", state["round"])
        claims = payload.get("claims") or []
        responses = payload.get("responses") or []
    elif isinstance(payload, list):
        die("add-claims 需要角色发言对象（含 claims），不接受裸列表")
    else:
        role = payload.get("role")
        round_no = payload.get("round", state["round"])
        claims = [payload]
        responses = []

    if role not in state["roles"]:
        die(f"角色 {role!r} 不在本次讨论的角色列表 {state['roles']} 中")
    if not claims:
        die("这条发言里没有 claims")

    existing = list(state["claims"])
    added, warnings = [], []

    for raw in claims:
        cid = raw.get("id")
        validate_claim_id(cid, role, round_no)
        if any(c.get("id") == cid for c in state["claims"]):
            die(f"claim id 重复登记: {cid}")
        basis = raw.get("basis")
        if basis not in BASIS_ENUM:
            die(f"claim {cid} 的 basis={basis!r} 不在枚举 {BASIS_ENUM} 内")
        text = (raw.get("text") or "").strip()
        if not text:
            die(f"claim {cid} 缺少 text")
        if basis == "analogy" and not raw.get("analogy_breaks"):
            warnings.append(f"{cid}: basis=analogy 但未写明类比在何处失效（契约 §3 要求）")
        if basis == "case" and not raw.get("evidence"):
            warnings.append(f"{cid}: basis=case 但 evidence 未写案例来源（契约 §3 要求）")

        best_sim, best_id = 0.0, None
        for e in existing:
            s = similarity(text, e.get("text", ""))
            if s > best_sim:
                best_sim, best_id = s, e.get("id")

        if new_argument == "true":
            is_new = True
        elif new_argument == "false":
            is_new = False
        else:  # auto
            is_new = bool(basis in SUBSTANTIVE_BASIS and best_sim < 0.75)
            if basis not in SUBSTANTIVE_BASIS:
                warnings.append(f"{cid}: basis={basis} 属非实质论据，不计入新增关键论据")

        claim = {
            "id": cid,
            "role": role,
            "round": int(round_no),
            "text": text,
            "basis": basis,
            "evidence": raw.get("evidence", ""),
            "falsifiable_by": raw.get("falsifiable_by", ""),
            "is_new_key_argument": is_new,
            "is_new_key_argument_source": "manual" if new_argument in ("true", "false")
            else f"auto:substantive={basis in SUBSTANTIVE_BASIS},max_similarity={round(best_sim, 3)},nearest={best_id}",
            "responses_received": [],
        }
        state["claims"].append(claim)
        existing.append(claim)
        state["argument_log"].append({
            "round": int(round_no),
            "role": role,
            "claim_id": cid,
            "is_new_key_argument": is_new,
        })
        added.append(cid)

    # 回应登记
    claim_by_id = {c["id"]: c for c in state["claims"]}
    for resp in responses:
        tgt = resp.get("to")
        rtype = resp.get("type", "ignore_with_reason")
        if tgt not in claim_by_id:
            # 指向元认知条目（H 隐性假设 / D 分歧 / G 信息缺口 / F 谬误 / C 质疑）的回应
            if isinstance(tgt, str) and re.match(r"^(H|D|G|F|C)\d+$", tgt):
                state["meta_engagement"].append({
                    "meta_id": tgt,
                    "from": role,
                    "round": int(round_no),
                    "type": rtype,
                    "text": resp.get("text", ""),
                })
                if tgt.startswith("C"):
                    for ch in state["open_challenges"]:
                        if ch.get("id") == tgt and ch.get("to") == role:
                            ch["status"] = "answered"
            else:
                warnings.append(f"回应指向未知条目 {tgt!r}（claim id 应与契约 §3 一致）")
            continue
        claim_by_id[tgt].setdefault("responses_received", []).append(
            {"from": role, "type": rtype, "round": int(round_no), "text": resp.get("text", "")}
        )
        if rtype == "challenge":
            cid = next_challenge_id(state)
            state["open_challenges"].append({
                "id": cid,
                "from": role,
                "to": claim_by_id[tgt]["role"],
                "target_claim": tgt,
                "question": resp.get("text", ""),
                "round": int(round_no),
                "status": "open",
            })

    return {"registered": added, "warnings": warnings,
            "claims": [c for c in state["claims"] if c["id"] in added]}


def add_position(state: dict, payload: dict) -> dict:
    """用角色发言更新立场基线（含 epistemic_status）。"""
    role = payload.get("role")
    if role not in state["positions"]:
        die(f"角色 {role!r} 不在本次讨论中")
    pos = state["positions"][role]
    if payload.get("position"):
        pos["stance_summary"] = payload["position"]
    es = payload.get("epistemic_status") or {}
    if es:
        conf = es.get("confidence")
        if conf is not None:
            try:
                conf = int(conf)
            except (TypeError, ValueError):
                die(f"{role} 的 confidence 不是整数: {es.get('confidence')!r}")
            if not 0 <= conf <= 100:
                die(f"{role} 的 confidence 超出 0-100: {conf}")
            pos["confidence"] = conf
        if es.get("uncertainty_points"):
            pos["uncertainty_points"] = list(es["uncertainty_points"])
            if pos["confidence"] is not None and pos["confidence"] >= 90:
                log(f"提示: {role} 置信度 {pos['confidence']} 却列了不确定点，请确认不是自相矛盾")
        if es.get("will_revise_if"):
            pos["will_revise_if"] = es["will_revise_if"]
    if payload.get("blind_spot_declared"):
        pos["blind_spot_declared"] = payload["blind_spot_declared"]
    ids = [c.get("id") for c in (payload.get("claims") or []) if c.get("id")]
    if ids:
        pos["key_claims"] = sorted(set(pos.get("key_claims", [])) | set(ids))
    return pos


# --------------------------------------------------------------------------- #
# 轮次推进
# --------------------------------------------------------------------------- #


def begin_round(state: dict, n: int) -> dict:
    if n < 1:
        die("轮次必须 >= 1")
    if n > int(state.get("max_rounds", 3)):
        die(f"轮次 {n} 超过 max_rounds={state['max_rounds']}")
    phase, mode = ROUND_PHASE.get(n, ("synthesis", "cross_exam"))
    state["round"] = int(n)
    state["phase"] = phase
    state["interaction_mode"] = mode

    must_respond, notes = [], []
    for inj in state["injections"]:
        if int(inj.get("round", -1)) == int(n) and not inj.get("applied"):
            must_respond.extend(inj.get("must_respond", []))
            if inj.get("forbidden"):
                notes.append("禁止：" + "；".join(inj["forbidden"]))
            if inj.get("note"):
                notes.append(inj["note"])
            inj["applied"] = True

    goals = ROUND_GOALS.get(n, ROUND_GOALS["default"])
    state["next_round"] = {
        "round": int(n),
        "interaction_mode": mode,
        "goals": list(goals),
        "must_respond": sorted(set(must_respond)),
        "may_revise": n >= 2,
        "notes": " | ".join(notes),
    }
    return state["next_round"]


# --------------------------------------------------------------------------- #
# 摘要与交接块
# --------------------------------------------------------------------------- #


def handoff_block(state: dict) -> dict:
    by_id = {c["id"]: c for c in state["claims"]}
    supporters, challengers = {}, {}
    for c in state["claims"]:
        for r in c.get("responses_received", []):
            if r.get("type") in ("support", "adopt"):
                supporters.setdefault(c["id"], set()).add(r.get("from"))
            elif r.get("type") == "challenge":
                challengers.setdefault(c["id"], set()).add(r.get("from"))

    consensus, minority = [], []
    for c in state["claims"]:
        sup = sorted(supporters.get(c["id"], set()))
        if len(sup) >= 2:
            strength = "unanimous" if len(sup) >= max(2, len(state["roles"]) - 1) else "majority"
            consensus.append({"claim_id": c["id"], "text": c["text"][:120], "supporters": sup,
                              "strength": strength})
        if c["id"] in challengers and not sup:
            minority.append({"role": c["role"], "claim_id": c["id"], "text": c["text"],
                             "challengers": sorted(challengers[c["id"]]), "refuted": False,
                             "note": "脚本无法判定是否已被有效反驳，需模型/人工复核"})

    advice = []
    for role, pos in state["positions"].items():
        conf = pos.get("confidence")
        if conf is None or not pos.get("stance_summary"):
            continue
        level = "high" if conf >= 70 else ("medium" if conf >= 40 else "needs_info")
        advice.append({"role": role, "text": pos["stance_summary"], "confidence": level,
                       "confidence_raw": conf, "will_revise_if": pos.get("will_revise_if", "")})

    return {
        "needs_judgment": True,
        "topic": state["topic"],
        "rounds_completed": state["round"],
        "consensus_candidates": consensus,
        "divergence_map": [d.get("id") for d in state["meta"]["divergences"]],
        "hidden_assumption_list": [h.get("id") for h in state["meta"]["hidden_assumptions"]],
        "information_gaps": [g.get("id") for g in state["meta"]["information_gaps"]],
        "minority_views": minority,
        "confidence_weighted_advice": advice,
        "unanswered_claims": [c["id"] for c in state["claims"] if not c.get("responses_received")],
    }


def summarize(state: dict, as_text: bool = False):
    stats = {}
    for entry in state["argument_log"]:
        r = entry["round"]
        s = stats.setdefault(r, {"claims": 0, "new_key": 0, "roles": set()})
        s["claims"] += 1
        s["new_key"] += 1 if entry.get("is_new_key_argument") else 0
        s["roles"].add(entry["role"])
    per_round = {str(k): {"claims": v["claims"], "new_key_arguments": v["new_key"],
                          "roles": sorted(v["roles"])} for k, v in sorted(stats.items())}
    open_ch = [c["id"] for c in state["open_challenges"] if c.get("status") == "open"]
    data = {
        "session_id": state["session_id"],
        "topic": state["topic"],
        "round": state["round"],
        "phase": state["phase"],
        "interaction_mode": state["interaction_mode"],
        "per_round": per_round,
        "open_challenges": open_ch,
        "convergence": state["convergence"],
        "handoff": handoff_block(state),
    }
    if not as_text:
        return data

    lines = [
        f"# 圆桌讨论摘要  {state['session_id']}",
        f"议题：{state['topic']}",
        f"进度：第 {state['round']}/{state['max_rounds']} 轮 · 阶段 {state['phase']} · 交互模式 {state['interaction_mode']}",
        "",
        "## 各轮论据统计",
    ]
    for r, v in per_round.items():
        lines.append(f"- 第 {r} 轮：论断 {v['claims']} 条，其中新增关键论据 {v['new_key_arguments']} 条，"
                     f"参与角色 {', '.join(v['roles'])}")
    lines.append("")
    lines.append(f"## 未决质疑（{len(open_ch)}）")
    lines += [f"- {c['id']}: {c['from']} → {c['to']}，指向 {c['target_claim']}：{c['question'][:80]}"
              for c in state["open_challenges"] if c.get("status") == "open"] or ["- 无"]
    lines.append("")
    h = data["handoff"]
    lines.append(f"## 共识候选（{len(h['consensus_candidates'])}，需人工/模型复核）")
    lines += [f"- {c['claim_id']}（{c['strength']}，支持者 {', '.join(c['supporters'])}）：{c['text']}"
              for c in h["consensus_candidates"]] or ["- 无"]
    lines.append("")
    lines.append(f"## 少数派观点（{len(h['minority_views']) }，未被脚本判定为已反驳，必须完整保留）")
    lines += [f"- [{m['role']}] {m['claim_id']}：{m['text'][:100]}" for m in h["minority_views"]] or ["- 无"]
    lines.append("")
    lines.append("## 讨论质量信号")
    lines.append(f"- 连续无新增关键论据轮数：{state['convergence']['rounds_without_new_argument']}")
    lines.append(f"- 根因触及：{state['convergence']['root_cause_reached']}　建议：{state['convergence']['recommendation']}")
    lines += [f"  · {s}" for s in state["convergence"].get("signals", [])]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="圆桌讨论状态管理器")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="新建讨论状态文件")
    pi.add_argument("--topic", required=True)
    pi.add_argument("--out", default=".roundtable", help="输出目录，最终写入 <out>/<session_id>/state.json")
    pi.add_argument("--state", help="直接指定 state.json 路径（优先于 --out）")
    pi.add_argument("--mode", default="rigorous", choices=["rigorous", "simulation"])
    pi.add_argument("--max-rounds", type=int, default=3)
    pi.add_argument("--roles", default=",".join(DEFAULT_ROLES))
    pi.add_argument("--session-id", default=None)

    pg = sub.add_parser("get", help="读取状态中的某个路径")
    pg.add_argument("--state", required=True)
    pg.add_argument("--path", required=True)

    ps = sub.add_parser("set", help="写入状态中的某个路径")
    ps.add_argument("--state", required=True)
    ps.add_argument("--path", required=True)
    ps.add_argument("--value", required=True, help="JSON 字面量，或 @文件路径")
    ps.add_argument("--append", action="store_true")

    pa = sub.add_parser("add-claims", help="登记角色发言中的 claims 与 responses")
    pa.add_argument("--state", required=True)
    pa.add_argument("--file", help="角色发言 JSON 文件，- 表示 stdin")
    pa.add_argument("--json", help="直接传 JSON 字面量")
    pa.add_argument("--new-argument", default="auto", choices=["auto", "true", "false"])
    pa.add_argument("--dry-run", action="store_true")

    pp = sub.add_parser("add-position", help="更新角色立场基线")
    pp.add_argument("--state", required=True)
    pp.add_argument("--file")
    pp.add_argument("--json")
    pp.add_argument("--dry-run", action="store_true")

    pr = sub.add_parser("begin-round", help="推进到第 N 轮并生成本轮目标")
    pr.add_argument("--state", required=True)
    pr.add_argument("--round", type=int, required=True)

    pc = sub.add_parser("close", help="关闭讨论")
    pc.add_argument("--state", required=True)
    pc.add_argument("--reason", default="")
    pc.add_argument("--root-cause", action="store_true", help="标记已触及根本矛盾")
    pc.add_argument("--note", default="")

    psu = sub.add_parser("summary", help="输出摘要与交接块")
    psu.add_argument("--state", required=True)
    psu.add_argument("--json", action="store_true", help="输出 JSON（默认输出文本）")

    sub.add_parser("selftest", help="自检")
    return p


def cmd_init(args) -> dict:
    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    state = new_state(args.topic, args.mode, args.max_rounds, roles, args.session_id)
    path = Path(args.state) if args.state else Path(args.out) / state["session_id"] / "state.json"
    save_state(path, state)
    log(f"已创建状态文件: {path}")
    return {"state_path": str(path), "session_id": state["session_id"], "roles": roles}


def cmd_set(args) -> dict:
    state = load_state(args.state)
    value = args.value
    if value.startswith("@"):
        value = Path(value[1:]).read_text(encoding="utf-8").strip()
    try:
        value = json.loads(value)
    except json.JSONDecodeError:
        pass  # 允许传裸字符串
    set_path(state, args.path, value, append=args.append)
    save_state(args.state, state)
    return {"path": args.path, "append": args.append, "ok": True}


def cmd_summary(args):
    state = load_state(args.state)
    if args.json:
        emit(summarize(state, as_text=False))
    else:
        print(summarize(state, as_text=True))
    return None


def selftest() -> int:
    import tempfile

    ok = True

    def check(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)
        else:
            print(f"  ok: {msg}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "state.json"
        st = new_state("自检议题：是否引入元认知角色", session_id="rt-selftest")
        save_state(path, st)
        st = load_state(path)
        check(st["schema_version"] == SCHEMA_VERSION, "状态可写入并读回")

        begin_round(st, 1)
        check(st["interaction_mode"] == "parallel_isolated", "第 1 轮为隔离模式")
        payload = {
            "role": "musk", "round": 1, "position": "应当先做物理约束推演",
            "claims": [{"id": "M1-1", "text": "火箭成本的物理下界是推进剂成本",
                        "basis": "physical_constraint", "evidence": "推进剂占比推演"}],
            "responses": [],
            "epistemic_status": {"confidence": 70, "uncertainty_points": ["制造工艺数据缺失"],
                                 "will_revise_if": "出现可复现的制造成本数据"},
        }
        add_claims(st, payload)
        add_position(st, payload)
        check(st["claims"][0]["is_new_key_argument"] is True, "实质性新论断被标记为新增关键论据")
        check(st["positions"]["musk"]["confidence"] == 70, "立场基线已更新")

        # 同义重复不应算新增
        dup = dict(payload)
        dup["claims"] = [{"id": "M1-2", "text": "火箭成本的物理下界就是推进剂成本",
                          "basis": "physical_constraint", "evidence": "同上"}]
        add_claims(st, dup)
        check(st["claims"][1]["is_new_key_argument"] is False, "同义重复不计入新增关键论据")

        # 交叉质疑登记
        begin_round(st, 2)
        check(st["interaction_mode"] == "cross_exam", "第 2 轮为交叉模式")
        add_claims(st, {
            "role": "pg", "round": 2, "position": "需要案例支撑",
            "claims": [{"id": "P2-1", "text": "至少一个真实案例证明了成本可以下降",
                        "basis": "case", "evidence": "某公开案例"}],
            "responses": [{"to": "M1-1", "type": "challenge", "text": "下界推演忽略了工艺良率"}],
            "epistemic_status": {"confidence": 55, "uncertainty_points": ["案例不具代表性"],
                                 "will_revise_if": "出现反例"},
        })
        check(len(st["open_challenges"]) == 1, "质疑被登记为 open_challenges")
        check(st["claims"][0]["responses_received"][0]["from"] == "pg", "回应回写到目标 claim")

        # 路径读写
        set_path(st, "meta.reviews", {"round": 1, "note": "x"}, append=True)
        check(get_path(st, "meta.reviews")[0]["note"] == "x", "dotted path 读写正常")

        h = handoff_block(st)
        check(any(m["claim_id"] == "M1-1" for m in h["minority_views"]), "少数派观点被保留")
        check(h["needs_judgment"] is True, "交接块标注 needs_judgment")

        # 非法 id 必须被拒
        try:
            add_claims(st, {"role": "jobs", "round": 2,
                            "claims": [{"id": "X2-1", "text": "t", "basis": "empirical"}]})
            check(False, "非法 claim id 应当报错")
        except SystemExit:
            check(True, "非法 claim id 被拒绝")

        save_state(path, st)
        check(json.loads(path.read_text(encoding="utf-8"))["session_id"] == "rt-selftest", "状态可持久化")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "init":
        emit(cmd_init(args))
    elif args.cmd == "get":
        emit(get_path(load_state(args.state), args.path))
    elif args.cmd == "set":
        emit(cmd_set(args))
    elif args.cmd == "add-claims":
        st = load_state(args.state)
        result = add_claims(st, read_payload(args.file, args.json), args.new_argument)
        if not args.dry_run:
            save_state(args.state, st)
        emit(result)
    elif args.cmd == "add-position":
        st = load_state(args.state)
        pos = add_position(st, read_payload(args.file, args.json))
        if not args.dry_run:
            save_state(args.state, st)
        emit(pos)
    elif args.cmd == "begin-round":
        st = load_state(args.state)
        nr = begin_round(st, args.round)
        save_state(args.state, st)
        emit(nr)
    elif args.cmd == "close":
        st = load_state(args.state)
        st["phase"] = "closed"
        st["convergence"]["recommendation"] = "close"
        st["convergence"]["close_reason"] = args.reason
        if args.root_cause:
            st["convergence"]["root_cause_reached"] = True
            st["convergence"]["root_cause_note"] = args.note
        save_state(args.state, st)
        emit({"phase": "closed", "recommendation": "close", "root_cause_reached": st["convergence"]["root_cause_reached"]})
    elif args.cmd == "summary":
        cmd_summary(args)
    elif args.cmd == "selftest":
        return selftest()
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

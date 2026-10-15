#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""立场修正追踪器 revision_tracker.py

Layer 3（观点迭代）的执行器。它回答两个问题：
  1. 这次修正**算不算有效修正**？（有证据支撑，还是跟着多数人走）
  2. 修正之后，这个角色下一轮的**立场基线**是什么？

反从众机制（这是本文件最重要的部分）：
  真实的讨论里，最坏的情况不是有人固执，而是所有人为了"达成共识"悄悄投降。
  因此：**没有引用新证据/新论证的修正不改变立场基线**，只被记为
  compliance_drift（从众漂移）并累计计数，供元认知层在下一轮点名。

用法：
  python revision_tracker.py record --state S --file pg-round2.json [--write] [--allow-uncited]
  python revision_tracker.py list --state S [--role pg]
  python revision_tracker.py baseline --state S --role pg
  python revision_tracker.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

LEVELS = ["micro", "local", "foundational"]
CLAIM_ID_RE = re.compile(r"\b([MFGJKP]\d+-\d+)\b")
META_ID_RE = re.compile(r"\b([HDGFC]\d+)\b")
DRIFT_PHRASES = ["为了达成共识", "为推进讨论", "大多数人", "大家都", "保持一致", "顺应主流", "少数服从多数"]
PREMISE_WORDS = ["前提", "假设", "底层", "根本", "出发点"]


def log(msg: str) -> None:
    print(f"[revision_tracker] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[revision_tracker] ERROR: {msg}", file=sys.stderr)
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


def all_known_ids(state: dict) -> set:
    ids = {c.get("id") for c in state.get("claims", [])}
    ids |= {c.get("id") for c in state.get("open_challenges", [])}
    meta = state.get("meta", {})
    for key in ("hidden_assumptions", "divergences", "information_gaps", "fallacies"):
        ids |= {x.get("id") for x in meta.get(key, [])}
    for inj in state.get("injections", []):
        ids |= set(inj.get("must_respond", []))
    for e in state.get("meta_engagement", []):
        ids.add(e.get("meta_id"))
    ids.discard(None)
    return ids


def validate_revision(state: dict, rev: dict, allow_uncited: bool = False) -> dict:
    role = rev.get("role")
    if role not in state.get("positions", {}):
        die(f"角色 {role!r} 不在本次讨论中")
    round_no = int(rev.get("round", state.get("round", 0)))
    warnings, errors = [], []

    for field in ("trigger", "level", "from", "to", "reason"):
        if not str(rev.get(field, "")).strip():
            errors.append(f"缺少必填字段 {field}")
    if "remaining_doubt" not in rev:
        warnings.append("未提供 remaining_doubt（契约 §5 要求写出修正后仍不确定的地方）")
    level = rev.get("level")
    if level not in LEVELS:
        errors.append(f"level={level!r} 不在 {LEVELS} 内")

    trigger = str(rev.get("trigger", ""))
    cited_claims = CLAIM_ID_RE.findall(trigger)
    cited_meta = META_ID_RE.findall(trigger)
    cited = cited_claims + cited_meta
    known = all_known_ids(state)
    unknown_cited = [i for i in cited if i not in known]
    if unknown_cited:
        warnings.append(f"trigger 引用的条目在状态里不存在：{', '.join(unknown_cited)}（可能是笔误或尚未登记）")

    drift_hits = [p for p in DRIFT_PHRASES if p in trigger + " " + str(rev.get("reason", ""))]
    cited_valid = bool(cited) or allow_uncited
    drift = False
    invalid_reason = None
    if not cited_valid:
        drift = True
        invalid_reason = "trigger 未引用任何新证据/新论证（claim id 或 H/D/G/F/C 编号），疑似从众漂移"
    elif drift_hits and not cited_claims:
        drift = True
        invalid_reason = f"修正理由出现从众类表述：{drift_hits}，且未引用新事实证据"

    downgraded = False
    if level == "foundational":
        reason = str(rev.get("reason", ""))
        if len(reason) < 30 or not any(w in reason for w in PREMISE_WORDS):
            downgraded = True
            level = "local"
            warnings.append("foundational 级修正未说明「初始前提错在哪」，按契约 §5 降级为 local")

    # 反复横跳：新立场回到此前被放弃的立场
    unstable = False
    prior = [r for r in state.get("revisions", []) if r.get("role") == role]
    for old in prior:
        if similarity(rev.get("to", ""), old.get("from", "")) >= 0.7 and \
           similarity(rev.get("from", ""), old.get("to", "")) >= 0.7:
            unstable = True
            warnings.append(f"新立场与此前被放弃的立场（{old.get('id')} 的 from）高度相似：可能是在来回横跳")
            break
    if len(prior) >= 3:
        unstable = True
        warnings.append(f"{role} 已修正 {len(prior)} 次，累计修正次数偏多，建议元认知层介入核查")

    valid = not errors and not drift
    return {
        "role": role,
        "round": round_no,
        "trigger": trigger,
        "level": level,
        "level_original": rev.get("level"),
        "from": rev.get("from", ""),
        "to": rev.get("to", ""),
        "reason": rev.get("reason", ""),
        "remaining_doubt": rev.get("remaining_doubt", ""),
        "cited": cited,
        "valid": valid,
        "drift_suspected": drift,
        "unstable": unstable,
        "downgraded": downgraded,
        "invalid_reason": invalid_reason,
        "errors": errors,
        "warnings": warnings,
    }


def record(state: dict, rev: dict, allow_uncited: bool = False, write: bool = False) -> dict:
    result = validate_revision(state, rev, allow_uncited)
    if result["errors"]:
        die("修正记录不合法：" + "；".join(result["errors"]))
    stored = dict(result)
    stored.pop("errors", None)
    action = "baseline_updated" if result["valid"] else "baseline_unchanged(compliance_drift)"
    if write:
        revs = state.setdefault("revisions", [])
        used = {r.get("id") for r in revs}
        n = 1
        while f"R{n}" in used:
            n += 1
        stored["id"] = f"R{n}"
        revs.append(stored)

        pos = state["positions"][result["role"]]
        if result["valid"]:
            if result["to"]:
                pos["stance_summary"] = result["to"]
            pos["revision_count"] = int(pos.get("revision_count", 0)) + 1
        else:
            pos["compliance_drift_count"] = int(pos.get("compliance_drift_count", 0)) + 1
    stored["action"] = action
    stored["position_after"] = state["positions"][result["role"]]["stance_summary"]
    return stored


def baseline(state: dict, role: str) -> dict:
    if role not in state.get("positions", {}):
        die(f"角色 {role!r} 不在本次讨论中")
    pos = state["positions"][role]
    revs = [r for r in state.get("revisions", []) if r.get("role") == role and r.get("valid")]
    source = "initial"
    if revs:
        latest = revs[-1]
        source = f"revision {latest.get('id')}(round {latest.get('round')})"
    return {
        "role": role,
        "stance_summary": pos.get("stance_summary", ""),
        "source": source,
        "confidence": pos.get("confidence"),
        "will_revise_if": pos.get("will_revise_if", ""),
        "remaining_doubt": revs[-1].get("remaining_doubt") if revs else "",
        "revision_count": pos.get("revision_count", 0),
        "compliance_drift_count": pos.get("compliance_drift_count", 0),
        "history": [{"id": r.get("id"), "round": r.get("round"), "level": r.get("level"),
                     "from": r.get("from"), "to": r.get("to")} for r in revs],
        "note": "该基线即角色下一轮发言的起点；修正历史不删除，from 永远保留",
    }


def selftest() -> int:
    ok = True

    def check(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    def base_state():
        return {
            "round": 2, "roles": ["pg", "musk"],
            "claims": [{"id": "M1-1", "role": "musk", "round": 1, "text": "成本下界由推进剂决定"}],
            "open_challenges": [{"id": "C1", "from": "pg", "to": "musk", "target_claim": "M1-1", "status": "open"}],
            "meta": {"hidden_assumptions": [{"id": "H1", "content": "必须拿奖才算成功"}],
                     "divergences": [], "information_gaps": [], "fallacies": []},
            "meta_engagement": [], "injections": [], "revisions": [],
            "positions": {"pg": {"stance_summary": "先做案例归纳就够", "confidence": 40,
                                 "revision_count": 0, "compliance_drift_count": 0},
                          "musk": {"stance_summary": "先算物理下界", "confidence": 70,
                                   "revision_count": 0, "compliance_drift_count": 0}},
        }

    st = base_state()
    good = {"role": "pg", "round": 2, "level": "local",
            "trigger": "被 M1-1 的推演说服，且元认知提出 H1",
            "from": "只需要案例归纳", "to": "案例归纳需要配合量级估算",
            "reason": "案例无法覆盖未发生的情形，量级估算能补上边界",
            "remaining_doubt": "量级估算的误差范围有多大"}
    r = record(st, good, write=True)
    check(r["valid"] is True, "引用了新论证的修正被判为有效")
    check(r["action"] == "baseline_updated", "有效修正更新基线")
    check(st["positions"]["pg"]["stance_summary"] == good["to"], "基线文本被替换为新立场")
    check(st["positions"]["pg"]["revision_count"] == 1, "修正计数 +1")
    check(st["revisions"][0]["id"] == "R1", "修正记录获得 R 编号")
    check(st["revisions"][0]["from"] == good["from"], "原立场被保留在记录里")

    drift = {"role": "pg", "round": 3, "level": "local",
             "trigger": "多数人都认为应该这样", "from": "案例归纳需要配合量级估算",
             "to": "还是只做案例归纳", "reason": "为了达成共识，大家保持一致",
             "remaining_doubt": ""}
    before = st["positions"]["pg"]["stance_summary"]
    r2 = record(st, drift, write=True)
    check(r2["valid"] is False and r2["drift_suspected"] is True, "无新证据的修正被判为从众漂移")
    check(r2["action"].startswith("baseline_unchanged"), "从众漂移不改变立场基线")
    check(st["positions"]["pg"]["stance_summary"] == before, "基线在漂移时确实没有被改写")
    check(st["positions"]["pg"]["compliance_drift_count"] == 1, "漂移计数 +1")

    fd = {"role": "musk", "round": 3, "level": "foundational",
          "trigger": "H1 被证明是错的预设", "from": "先算下界", "to": "先问成功标准是谁定的",
          "reason": "短", "remaining_doubt": ""}
    r3 = record(st, fd, write=True)
    check(r3["level"] == "local" and r3["downgraded"] is True, "解释不足的 foundational 被降级为 local")

    fd2 = {"role": "musk", "round": 3, "level": "foundational",
           "trigger": "H1 被证明是错的预设", "from": "先算下界", "to": "先追问成功标准",
           "reason": "我的初始前提是成本决定一切，但 H1 说明成功标准本身才是更底层的假设",
           "remaining_doubt": "成功标准能否被量化"}
    r4 = record(st, fd2, write=True)
    check(r4["level"] == "foundational" and r4["downgraded"] is False, "说清前提错在哪的底层修正被保留")

    # 反复横跳
    st2 = base_state()
    st2["revisions"] = [{"id": "R1", "role": "pg", "from": "只用案例", "to": "案例加量级估算", "valid": True}]
    back = dict(good)
    back["from"] = "案例加量级估算"
    back["to"] = "只用案例"
    r5 = record(st2, back)
    check(r5["unstable"] is True, "回到被放弃的立场被判为反复横跳")

    # 无引用
    r6 = record(base_state(), {"role": "pg", "round": 2, "level": "micro",
                               "trigger": "感觉不太对", "from": "a", "to": "b",
                               "reason": "只是改个说法", "remaining_doubt": "无"})
    check(r6["valid"] is False, "无任何引用的修正被判为无效")
    r7 = record(base_state(), {"role": "pg", "round": 2, "level": "micro",
                               "trigger": "感觉不太对", "from": "a", "to": "b",
                               "reason": "外部输入", "remaining_doubt": "无"}, allow_uncited=True)
    check(r7["valid"] is True, "--allow-uncited 时允许无引用修正（用于用户直接提供新事实）")

    # 字段缺失必须报错
    try:
        record(base_state(), {"role": "pg", "round": 2, "level": "micro", "trigger": "x"})
        check(False, "缺字段应当报错")
    except SystemExit:
        check(True, "缺字段被拒绝")

    b = baseline(st, "musk")
    check(b["source"].startswith("revision"), "基线来源指向最新有效修正")
    check(b["history"], "基线包含修正历史")
    check(b["remaining_doubt"], "基线带出 remaining_doubt")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="立场修正追踪器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("record")
    pr.add_argument("--state", required=True)
    pr.add_argument("--file")
    pr.add_argument("--json")
    pr.add_argument("--write", action="store_true")
    pr.add_argument("--allow-uncited", action="store_true",
                    help="允许 trigger 不引用任何 id（用于用户直接提供了外部新事实的场景）")

    pl = sub.add_parser("list")
    pl.add_argument("--state", required=True)
    pl.add_argument("--role")

    pb = sub.add_parser("baseline")
    pb.add_argument("--state", required=True)
    pb.add_argument("--role", required=True)

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "record":
        st = load_state(args.state)
        raw = args.json if args.json else (
            sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8"))
        payload = json.loads(raw)
        rev = payload.get("revision", payload)
        rev.setdefault("role", payload.get("role"))
        rev.setdefault("round", payload.get("round"))
        out = record(st, rev, args.allow_uncited, args.write)
        if args.write:
            save_state(args.state, st)
        emit(out)
        return 0
    if args.cmd == "list":
        st = load_state(args.state)
        revs = st.get("revisions", [])
        if args.role:
            revs = [r for r in revs if r.get("role") == args.role]
        emit({"count": len(revs), "revisions": revs})
        return 0
    if args.cmd == "baseline":
        emit(baseline(load_state(args.state), args.role))
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

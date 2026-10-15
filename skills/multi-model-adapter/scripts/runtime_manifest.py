#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""异构基座适配器 runtime_manifest.py

问题：所有角色跑在同一个底座模型上时，**底层认知偏见是共通的**，
再多角色也只是在同一套盲区里打转。

本脚本做两件可验证的事：
  1. `emit`：把每个角色编译成独立**调用包**（提示骨架 + 上下文要求 + 输出契约 + 隔离要求
     + provider/model 占位），交给支持多 provider 的宿主分别执行；
  2. `merge`：把各宿主返回的结果按契约校验（ID 前缀、轮次、basis 枚举、重复 ID、必填字段）
     后合回同一个讨论状态。

诚实边界：**真实的多 provider 调用在本环境未验证**。可运行的是调用包生成与合并校验；
"真的用不同模型跑起来"取决于宿主是否具备多 provider 能力。未指定 provider/model 时一律
写 `unspecified`，绝不猜测或编造模型名。

用法：
  python runtime_manifest.py emit --state S --round 2 --out DIR [--assignment assignment.json]
  python runtime_manifest.py merge --state S --dir DIR [--state-manager PATH] [--dry-run]
  python runtime_manifest.py selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROLE_PREFIX = {"musk": "M", "feynman": "F", "munger": "G", "jobs": "J", "karpathy": "K", "pg": "P"}
PREFIX_ROLE = {v: k for k, v in ROLE_PREFIX.items()}
BASIS_ENUM = ["physical_constraint", "empirical", "case", "mechanism", "analogy",
              "value_judgment", "intuition"]
RESPONSE_TYPES = ["support", "challenge", "refine", "adopt", "ignore_with_reason"]
CLAIM_ID_RE = re.compile(r"^([MFGJKP])(\d+)-(\d+)$")
CONTRACT_FIELDS = ["role", "round", "position", "claims", "responses", "blind_spot_declared",
                   "epistemic_status", "confidence", "uncertainty_points", "will_revise_if"]
ROUND_PHASE = {1: ("opening", "parallel_isolated"), 2: ("probing", "cross_exam"),
               3: ("synthesis", "cross_exam")}
SCHEMA_VERSION = "1.1"


def log(msg: str) -> None:
    print(f"[runtime_manifest] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[runtime_manifest] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def load_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"状态文件不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def canonical_hash(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# emit
# --------------------------------------------------------------------------- #


def round_context(state: dict, round_no: int) -> dict:
    phase, mode = ROUND_PHASE.get(round_no, ("synthesis", "cross_exam"))
    nr = state.get("next_round") or {}
    if nr.get("round") == round_no:
        mode = nr.get("interaction_mode", mode)
        phase = phase
        goals = nr.get("goals", [])
        must_respond = nr.get("must_respond", [])
        may_revise = nr.get("may_revise", round_no >= 2)
        notes = nr.get("notes", "")
    else:
        goals, must_respond, may_revise, notes = [], [], round_no >= 2, ""
        for inj in state.get("injections", []):
            if int(inj.get("round", -1)) == round_no and not inj.get("applied"):
                must_respond.extend(inj.get("must_respond", []))
                notes = (notes + " | " + inj.get("note", "")).strip(" |")
    forbidden = []
    for inj in state.get("injections", []):
        if int(inj.get("round", -1)) == round_no:
            forbidden.extend(inj.get("forbidden", []))
    return {"phase": phase, "interaction_mode": mode, "goals": goals,
            "must_respond": sorted(set(must_respond)), "may_revise": may_revise,
            "forbidden": sorted(set(forbidden)), "notes": notes}


def parse_assignment(path, roles: list) -> tuple:
    if not path:
        return {r: {"provider": "unspecified", "model": "unspecified"} for r in roles}, "single_host"
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "providers" in data:
        strategy = data.get("strategy", "round_robin")
        if strategy != "round_robin":
            die(f"未支持的分配策略 {strategy!r}（目前支持 round_robin 或显式映射）")
        providers = data["providers"]
        if not providers:
            die("providers 列表为空")
        assign = {r: {"provider": providers[i % len(providers)], "model": "unspecified"}
                  for i, r in enumerate(roles)}
        return assign, "round_robin"
    assign = {}
    for r in roles:
        entry = data.get(r) or {}
        assign[r] = {"provider": entry.get("provider", "unspecified"),
                     "model": entry.get("model", "unspecified")}
    return assign, "explicit"


def payload_schema(role: str, round_no: int) -> dict:
    return {
        "type": "object",
        "required": ["role", "round", "claims"],
        "properties": {
            "role": {"const": role},
            "round": {"const": round_no},
            "id_prefix": {"const": ROLE_PREFIX[role]},
            "position": {"type": "string"},
            "claims": {"type": "array", "items": {
                "required": ["id", "text", "basis"],
                "properties": {
                    "id": {"pattern": f"^{ROLE_PREFIX[role]}{round_no}-\\d+$"},
                    "text": {"type": "string"},
                    "basis": {"enum": BASIS_ENUM},
                    "evidence": {"type": "string"},
                    "falsifiable_by": {"type": "string"},
                }}},
            "responses": {"type": "array", "items": {
                "required": ["to", "type", "text"],
                "properties": {"to": {"type": "string"}, "type": {"enum": RESPONSE_TYPES},
                               "text": {"type": "string"}}}},
            "blind_spot_declared": {"type": "string"},
            "epistemic_status": {"properties": {
                "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                "uncertainty_points": {"type": "array"},
                "will_revise_if": {"type": "string"}}},
        },
    }


def build_task(state: dict, role: str, round_no: int, ctx: dict, assign: dict) -> dict:
    isolation = ctx["interaction_mode"] == "parallel_isolated"
    skeleton = "\n".join([
        f"# 圆桌角色任务包 · {role} · 第 {round_no} 轮",
        "",
        "## 角色技能正文（由宿主注入对应 skills/role-<x>/SKILL.md 的完整内容）",
        "<ROLE_SKILL_BODY>",
        "",
        "## 本轮目标",
        "<ROUND_GOALS>",
        "",
        "## 强制回应项（本轮必须至少正面回应其中一条）",
        "<MUST_RESPOND>",
        "",
        "## 可见历史（由宿主按隔离要求注入：第 1 轮为空）",
        "<VISIBLE_HISTORY>",
        "",
        "## 输出要求",
        "只输出一个可解析的 YAML/JSON 对象，字段遵循下方 payload_schema；",
        "禁止自创字段、禁止改动 ID 前缀与 basis 枚举、禁止编造证据或数据来源。",
        "",
        f"## 隔离要求：{'本轮必须看不到其他角色的发言（防锚定）' if isolation else '允许自由交叉：可自行选择追问对象'}",
    ])
    return {
        "schema_version": SCHEMA_VERSION,
        "role": role,
        "round": round_no,
        "phase": ctx["phase"],
        "interaction_mode": ctx["interaction_mode"],
        "isolation": isolation,
        "goals": ctx["goals"],
        "must_respond": ctx["must_respond"],
        "forbidden": ctx["forbidden"],
        "may_revise": ctx["may_revise"],
        "notes": ctx["notes"],
        "provider": assign[role]["provider"],
        "model": assign[role]["model"],
        "contract_summary": {
            "fields": CONTRACT_FIELDS,
            "id_prefix": ROLE_PREFIX[role],
            "id_pattern": f"{ROLE_PREFIX[role]}{round_no}-<序号>",
            "basis_enum": BASIS_ENUM,
            "response_types": RESPONSE_TYPES,
            "meta_id_pattern": "H/D/G/F/C + 序号",
        },
        "payload_schema": payload_schema(role, round_no),
        "prompt_skeleton": skeleton,
        "result_file": f"roles/{role}.result.json",
        "state_path": str(Path(state.get("_path", "")).resolve()) if state.get("_path") else "",
    }


def cmd_emit(args) -> int:
    state = load_state(args.state)
    state["_path"] = args.state
    roles = state.get("roles", [])
    if not roles:
        die("状态里没有 roles")
    ctx = round_context(state, args.round)
    assign, strategy = parse_assignment(args.assignment, roles)

    out = Path(args.out)
    (out / "roles").mkdir(parents=True, exist_ok=True)

    hashes, tasks = {}, []
    for role in roles:
        task = build_task(state, role, args.round, ctx, assign)
        path = out / "roles" / f"{role}.task.json"
        path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        hashes[role] = canonical_hash(task)
        tasks.append(role)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "state_path": str(Path(args.state).resolve()),
        "session_id": state.get("session_id"),
        "topic": state.get("topic"),
        "round": args.round,
        "phase": ctx["phase"],
        "interaction_mode": ctx["interaction_mode"],
        "isolation_required": ctx["interaction_mode"] == "parallel_isolated",
        "roles": roles,
        "provider_assignment": assign,
        "strategy": strategy,
        "bundle_sha256": hashes,
        "notes": [
            "provider/model 为 unspecified 表示宿主未指定：禁止猜测或编造模型名",
            "真实多 provider 调用需宿主支持；本仓库仅保证调用包生成与合并校验可运行",
            "合并前请勿修改 result 文件中的 id 与 basis：merge 会按契约拒绝不合规结果",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    log(f"已生成 {len(roles)} 个调用包 → {out}")
    emit_json({"out": str(out), "roles": tasks, "strategy": strategy,
               "isolation_required": manifest["isolation_required"],
               "unspecified_roles": [r for r in roles if assign[r]["provider"] == "unspecified"]})
    return 0


# --------------------------------------------------------------------------- #
# merge
# --------------------------------------------------------------------------- #


def validate_result(payload: dict, role: str, round_no: int, existing_ids: set) -> list:
    errors, warnings = [], []
    if payload.get("role") != role:
        errors.append({"code": "UNKNOWN_ROLE",
                       "detail": f"文件名角色 {role} 与 payload.role={payload.get('role')!r} 不一致"})
    if payload.get("round") is not None and int(payload.get("round")) != int(round_no):
        errors.append({"code": "ROUND_MISMATCH",
                       "detail": f"payload.round={payload.get('round')} 与任务包轮次 {round_no} 不一致"})

    claims = payload.get("claims") or []
    responses = payload.get("responses") or []
    if not claims and not responses:
        errors.append({"code": "MISSING_FIELD", "detail": "claims 与 responses 同时为空"})
    if not payload.get("epistemic_status"):
        warnings.append({"code": "MISSING_FIELD", "detail": "缺少 epistemic_status（契约 §3 要求）"})
    if not payload.get("position"):
        warnings.append({"code": "MISSING_FIELD", "detail": "缺少 position（本轮立场基线）"})
    if not payload.get("blind_spot_declared"):
        warnings.append({"code": "MISSING_FIELD", "detail": "缺少 blind_spot_declared"})

    seen = set()
    for c in claims:
        cid = c.get("id")
        m = CLAIM_ID_RE.match(str(cid or ""))
        if not m:
            errors.append({"code": "ID_PREFIX_MISMATCH",
                           "detail": f"claim id {cid!r} 不符合 <前缀><轮次>-<序号>"})
            continue
        prefix, rnd = m.group(1), int(m.group(2))
        if PREFIX_ROLE.get(prefix) != role:
            errors.append({"code": "ID_PREFIX_MISMATCH",
                           "detail": f"{cid} 的前缀 {prefix} 不属于角色 {role}（应为 {ROLE_PREFIX[role]}）"})
        if rnd != int(round_no):
            errors.append({"code": "ROUND_MISMATCH", "detail": f"{cid} 的轮次 {rnd} 与任务包轮次不一致"})
        if cid in seen or cid in existing_ids:
            errors.append({"code": "DUPLICATE_ID", "detail": f"claim id 重复: {cid}"})
        seen.add(cid)
        if c.get("basis") not in BASIS_ENUM:
            errors.append({"code": "BASIS_INVALID",
                           "detail": f"{cid} 的 basis={c.get('basis')!r} 不在枚举内"})
        if not str(c.get("text", "")).strip():
            errors.append({"code": "MISSING_FIELD", "detail": f"{cid} 缺少 text"})
    for r in responses:
        if not r.get("to") or not r.get("type"):
            errors.append({"code": "MISSING_FIELD", "detail": "responses 项缺少 to/type"})
        elif r.get("type") not in RESPONSE_TYPES:
            errors.append({"code": "BASIS_INVALID",
                           "detail": f"responses.type={r.get('type')!r} 不在 {RESPONSE_TYPES} 内"})
    return errors, warnings


def cmd_merge(args) -> int:
    state = load_state(args.state)
    d = Path(args.dir)
    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        die(f"缺少 manifest.json：{manifest_path}（先执行 emit）")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roles = manifest.get("roles", [])
    round_no = int(manifest.get("round", state.get("round", 1)))
    existing_ids = {c.get("id") for c in state.get("claims", [])}

    results, accepted, rejected = {}, [], []
    for role in roles:
        p = d / "roles" / f"{role}.result.json"
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            rejected.append({"role": role, "errors": [{"code": "INVALID_JSON", "detail": str(exc)}],
                             "warnings": []})
            continue
        errs, warns = validate_result(payload, role, round_no, existing_ids)
        results[role] = payload
        if errs:
            rejected.append({"role": role, "errors": errs, "warnings": warns})
        else:
            accepted.append({"role": role, "claims": [c.get("id") for c in payload.get("claims", [])],
                             "responses": len(payload.get("responses", [])), "warnings": warns})

    missing_roles = [r for r in roles if r not in results]
    validated_dir = d / "validated"
    commands = []
    merge_errors = []

    if accepted and not args.dry_run:
        validated_dir.mkdir(parents=True, exist_ok=True)
        for item in accepted:
            p = validated_dir / f"{item['role']}.json"
            p.write_text(json.dumps(results[item["role"]], ensure_ascii=False, indent=2),
                         encoding="utf-8")
            if args.state_manager:
                sm = args.state_manager
                for sub in ("add-claims", "add-position"):
                    proc = subprocess.run([sys.executable, sm, sub, "--state", args.state,
                                           "--file", str(p)],
                                          capture_output=True, text=True,
                                          encoding="utf-8", errors="replace")
                    if proc.returncode != 0:
                        merge_errors.append({"role": item["role"], "step": sub,
                                             "returncode": proc.returncode,
                                             "stderr": (proc.stderr or "")[-300:]})
            else:
                commands.append(f"python state_manager.py add-claims --state {args.state} "
                                f"--file {p}")
                commands.append(f"python state_manager.py add-position --state {args.state} "
                                f"--file {p}")

    payload = {
        "needs_judgment": True,
        "round": round_no,
        "dry_run": bool(args.dry_run),
        "state_manager_used": bool(args.state_manager) and not args.dry_run,
        "accepted": accepted,
        "rejected": rejected,
        "missing_roles": missing_roles,
        "merge_errors": merge_errors,
        "validated_dir": str(validated_dir) if accepted and not args.dry_run else "",
        "commands": commands,
        "next_steps": [
            "合并后必须再跑一次 convergence_detector.py check（跨模型结果同样需要收敛判定）",
            "若 missing_roles 非空，不得静默跳过：要么补跑，要么在报告里显式记录缺席视角",
        ],
    }
    emit_json(payload)
    return 1 if (rejected or merge_errors) else 0


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

    import io
    import contextlib
    import tempfile

    this_file = Path(__file__).resolve()
    state_manager = this_file.parents[2] / "roundtable-orchestrator" / "scripts" / "state_manager.py"

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state = {
            "schema_version": "1.0", "session_id": "rt-mm-selftest", "topic": "异构基座自检",
            "mode": "rigorous", "round": 1, "max_rounds": 3, "phase": "opening",
            "roles": ["musk", "pg"], "interaction_mode": "parallel_isolated",
            "shared_premises": [], "positions": {"musk": {}, "pg": {}}, "claims": [],
            "open_challenges": [], "meta_engagement": [], "revisions": [],
            "meta": {"hidden_assumptions": [], "divergences": [], "information_gaps": [],
                     "fallacies": [], "reviews": []},
            "injections": [{"round": 2, "must_respond": ["H1"], "forbidden": ["继续争论X"],
                            "applied": False}],
            "argument_log": [], "convergence": {}, "next_round": {},
        }
        sp = tdp / "state.json"
        sp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        # emit：无 assignment → 全部 unspecified
        out1 = tdp / "bundle1"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = main(["emit", "--state", str(sp), "--round", "2", "--out", str(out1)])
        ck(rc == 0, "emit 正常执行")
        man = json.loads((out1 / "manifest.json").read_text(encoding="utf-8"))
        ck(all(v["provider"] == "unspecified" for v in man["provider_assignment"].values()),
           "未指定 assignment 时 provider/model 一律 unspecified")
        ck(man["strategy"] == "single_host", "未指定时策略记为 single_host")
        ck(man["isolation_required"] is False, "第 2 轮为交叉模式，不要求隔离")
        ck(man["bundle_sha256"] and len(man["bundle_sha256"]) == 2, "每个角色都有调用包哈希")
        task = json.loads((out1 / "roles" / "musk.task.json").read_text(encoding="utf-8"))
        ck(task["contract_summary"]["id_prefix"] == "M", "调用包写明 ID 前缀")
        ck(task["payload_schema"]["properties"]["claims"]["items"]["properties"]["id"]["pattern"]
           == "^M2-\\d+$", "payload_schema 把本轮 ID 形式约束为 ^M2-\\d+$")
        ck("H1" in task["must_respond"], "强制回应项进入调用包")

        # emit：round_robin 分配
        asg = tdp / "assignment.json"
        asg.write_text(json.dumps({"providers": ["provider-a", "provider-b"],
                                   "strategy": "round_robin"}, ensure_ascii=False),
                       encoding="utf-8")
        out2 = tdp / "bundle2"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["emit", "--state", str(sp), "--round", "2", "--out", str(out2),
                  "--assignment", str(asg)])
        man2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
        provs = [man2["provider_assignment"][r]["provider"] for r in ["musk", "pg"]]
        ck(provs == ["provider-a", "provider-b"], "round_robin 依角色顺序分配 provider")
        ck(man2["provider_assignment"]["musk"]["model"] == "unspecified",
           "未指定 model 时写 unspecified 而不是编造模型名")

        # 第 1 轮隔离标记
        out3 = tdp / "bundle3"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["emit", "--state", str(sp), "--round", "1", "--out", str(out3)])
        man3 = json.loads((out3 / "manifest.json").read_text(encoding="utf-8"))
        ck(man3["isolation_required"] is True, "第 1 轮调用包要求隔离")

        # merge：一个合法 + 一个违规
        (out1 / "roles" / "musk.result.json").write_text(json.dumps({
            "role": "musk", "round": 2, "position": "先算下界",
            "claims": [{"id": "M2-1", "text": "包装成本必须计入下界", "basis": "empirical",
                        "evidence": "示例数据", "falsifiable_by": "实测占比低于15%"}],
            "responses": [{"to": "H1", "type": "refine", "text": "H1 决定结论是否成立"}],
            "blind_spot_declared": "看不到组织政治",
            "epistemic_status": {"confidence": 60, "uncertainty_points": ["缺实测"],
                                 "will_revise_if": "出现实测占比"},
        }, ensure_ascii=False), encoding="utf-8")
        (out1 / "roles" / "pg.result.json").write_text(json.dumps({
            "role": "pg", "round": 2, "position": "案例优先",
            "claims": [{"id": "PG2-1", "text": "案例显示相反", "basis": "telepathy"},
                       {"id": "M2-9", "text": "不属于 pg", "basis": "case"}],
            "responses": [{"to": "H1", "type": "not_a_type", "text": "x"}],
        }, ensure_ascii=False), encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["merge", "--state", str(sp), "--dir", str(out1), "--dry-run"])
        merged = json.loads(buf.getvalue())
        ck(rc == 1, "存在违规结果时 merge 返回非零")
        ck([a["role"] for a in merged["accepted"]] == ["musk"], "合法结果被接受")
        codes = {e["code"] for r in merged["rejected"] for e in r["errors"]}
        ck("ID_PREFIX_MISMATCH" in codes, "前缀不符被拒绝（PG2-1 / M2-9）")
        ck("BASIS_INVALID" in codes, "非法 basis 与非法 response type 被拒绝")
        ck(merged["missing_roles"] == [], "两个角色都提交了结果，无缺失")
        ck(merged["dry_run"] is True and merged["validated_dir"] == "", "dry-run 不写 validated")

        # merge 并真正写回状态（集成 state_manager）
        if state_manager.exists():
            with contextlib.redirect_stdout(io.StringIO()):
                rc2 = main(["merge", "--state", str(sp), "--dir", str(out1),
                            "--state-manager", str(state_manager)])
            st_after = json.loads(sp.read_text(encoding="utf-8"))
            ck(rc2 == 1, "同一批结果仍有违规项（pg），整体返回非零")
            ck([c["id"] for c in st_after["claims"]] == ["M2-1"],
               "合法结果被 state_manager 登记进状态文件")
            ck((out1 / "validated" / "musk.json").exists(), "合法结果写入 validated 目录")
            ck((out1 / "validated" / "pg.json").exists() is False, "违规结果不写入 validated")
        else:
            ck(False, "找不到 state_manager.py，无法做合并集成测试")

        # 缺结果文件 → missing_roles
        out4 = tdp / "bundle4"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["emit", "--state", str(sp), "--round", "3", "--out", str(out4)])
        buf4 = io.StringIO()
        with contextlib.redirect_stdout(buf4):
            main(["merge", "--state", str(sp), "--dir", str(out4), "--dry-run"])
        ck(sorted(json.loads(buf4.getvalue())["missing_roles"]) == ["musk", "pg"],
           "结果缺失时显式报告 missing_roles（不静默跳过）")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="异构基座适配器：调用包生成与结果合并")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("emit")
    pe.add_argument("--state", required=True)
    pe.add_argument("--round", type=int, required=True)
    pe.add_argument("--out", required=True)
    pe.add_argument("--assignment")
    pm = sub.add_parser("merge")
    pm.add_argument("--state", required=True)
    pm.add_argument("--dir", required=True)
    pm.add_argument("--state-manager")
    pm.add_argument("--dry-run", action="store_true")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "emit":
        return cmd_emit(args)
    if args.cmd == "merge":
        return cmd_merge(args)
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""认知噪声注入器 noise_injector.py

Layer 5（可选，默认关闭）的执行器。它注入三种**可控的不完美**：
  1. 选择性注意：只看见部分历史，且必须声明忽略了什么；
  2. 表达偏好：先说结论 / 先说顾虑 / 保守 / 冒险；
  3. 置信度传导：低置信度必须带保留语气，高置信度必须自陈可能错在哪。

红线（写进代码而不是只写在文档里）：
  * 只有 `mode=simulation` 允许启用；`rigorous` 下直接拒绝（退出码 3）；
  * 噪声**只改变"看见什么"和"怎么说"**：manifest 里只记录 id，绝不改写论断原文；
  * 每条选择都可用 `--seed` 复现，禁止不可复现的随机。

用法：
  python noise_injector.py plan --state S --role pg [--seed 7] [--attention 0.6]
                                [--style auto|conclusion_first|concern_first|conservative|adventurous] [--write]
  python noise_injector.py check --state S
  python noise_injector.py selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

STYLES = ["conclusion_first", "concern_first", "conservative", "adventurous"]
STYLE_CN = {
    "conclusion_first": "先说结论，再补理由",
    "concern_first": "先说顾虑，再说结论",
    "conservative": "倾向保守估计，主动加安全边界",
    "adventurous": "倾向激进方案，但必须自己写出最大下行风险",
}
DEFAULT_ATTENTION = 0.6


def log(msg: str) -> None:
    print(f"[noise_injector] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[noise_injector] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def load_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"状态文件不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path, state) -> None:
    import os
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def _rank(seed: int, role: str, item_id: str) -> str:
    return hashlib.sha256(f"{seed}:{role}:{item_id}".encode("utf-8")).hexdigest()


def tone_rules(confidence):
    if confidence is None:
        return ["未提供 confidence：必须先给出 0-100 的置信度，否则不得进入发言"]
    if confidence < 40:
        return ["使用保留语气（我倾向…／这可能是错的／我不确定）",
                "必须写明这个判断最可能错在哪里",
                "不得使用「显然」「必然」等绝对化措辞"]
    if confidence >= 90:
        return ["必须写出「我可能错在哪」",
                "不得使用绝对化措辞，除非有实测数据支撑"]
    return ["正常表述", "必须给出 will_revise_if（什么条件下愿意修正）"]


def pick_style(seed: int, role: str, style: str) -> str:
    if style and style != "auto":
        if style not in STYLES:
            die(f"style={style!r} 不在 {STYLES} 内或不为 auto")
        return style
    idx = int(_rank(seed, role, "style")[:8], 16) % len(STYLES)
    return STYLES[idx]


def history_items(state: dict) -> list:
    items = []
    for c in state.get("claims", []):
        items.append({"id": c.get("id"), "role": c.get("role"), "round": c.get("round"),
                      "kind": "claim"})
    for ch in state.get("open_challenges", []):
        items.append({"id": ch.get("id"), "role": ch.get("from"), "round": ch.get("round"),
                      "kind": "challenge"})
    meta = state.get("meta", {})
    for key, kind in (("hidden_assumptions", "assumption"), ("divergences", "divergence"),
                      ("information_gaps", "gap"), ("fallacies", "fallacy")):
        for x in meta.get(key, []):
            items.append({"id": x.get("id"), "role": None, "round": None, "kind": kind})
    return [i for i in items if i["id"]]


def make_plan(state: dict, role: str, seed: int, attention: float, style: str) -> dict:
    if role not in state.get("roles", []):
        die(f"角色 {role!r} 不在本次讨论中")
    if not 0.1 <= attention <= 1.0:
        die("attention 必须在 0.1–1.0 之间")

    items = history_items(state)
    own = {i["id"] for i in items if i["role"] == role}          # 角色永远记得自己的主张
    others = [i for i in items if i["id"] not in own]
    others_sorted = sorted(others, key=lambda i: _rank(seed, role, i["id"]))

    quota = len(others_sorted) if attention >= 0.999 else int(round(attention * len(others_sorted)))
    noticed_others = others_sorted[:quota]
    ignored = others_sorted[quota:]
    noticed = sorted(own | {i["id"] for i in noticed_others})

    pos = state.get("positions", {}).get(role, {})
    conf = pos.get("confidence")
    rules = tone_rules(conf)
    chosen_style = pick_style(seed, role, style)

    warnings = []
    ignored_ids = {i["id"] for i in ignored}
    pending = state.get("next_round", {}).get("must_respond", []) or []
    missing_required = [m for m in pending if m in ignored_ids]
    if missing_required:
        warnings.append(
            f"被忽略的历史里包含编排层强制回应的条目 {missing_required}："
            "强制项不适用注意力筛选，必须放回可见范围（见下方 noticed 修正）")
        noticed = sorted(set(noticed) | set(missing_required))
        ignored = [i for i in ignored if i["id"] not in set(missing_required)]
        ignored_ids = {i["id"] for i in ignored}
    challenges_against = [c["id"] for c in state.get("open_challenges", [])
                          if c.get("to") == role and c["id"] in ignored_ids]
    if challenges_against:
        warnings.append(
            f"被忽略的历史里有针对该角色的未答质疑 {challenges_against}："
            "若下一轮被追问，必须如实承认「本轮没有注意到」，不得假装已回应")
    if attention > 0.9:
        warnings.append("注意力比例 >0.9，噪声几乎不起作用（只影响措辞档位）")

    return {
        "needs_judgment": True,
        "mode": state.get("mode"),
        "mode_ok": True,
        "role": role,
        "round": state.get("round", 0) + 1,
        "seed": seed,
        "attention_ratio": attention,
        "history_total": len(items),
        "noticed": noticed,
        "ignored": [i["id"] for i in ignored],
        "style_profile": {"key": chosen_style, "description": STYLE_CN[chosen_style]},
        "confidence_raw": conf,
        "tone_rules": rules,
        "warnings": warnings,
        "note": "选择性注意只影响可见范围：被忽略的条目不得被引用，但也不得假装它不存在",
    }


def write_manifest(state_path: str, state: dict, plan: dict) -> dict:
    store = state.setdefault("attention_manifests", [])
    used = {m.get("id") for m in store}
    n = 1
    while f"AM{n}" in used:
        n += 1
    manifest = {
        "id": f"AM{n}",
        "role": plan["role"],
        "round": plan["round"],
        "seed": plan["seed"],
        "attention_ratio": plan["attention_ratio"],
        "noticed": plan["noticed"],
        "ignored": plan["ignored"],
        "style_profile": plan["style_profile"]["key"],
        "tone_rules": plan["tone_rules"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    store.append(manifest)
    save_state(state_path, state)
    return manifest


def check(state: dict) -> dict:
    mode = state.get("mode")
    manifests = state.get("attention_manifests", []) or []
    known_ids = {i["id"] for i in history_items(state)}
    violations, warnings = [], []

    for m in manifests:
        mid = m.get("id")
        if mode != "simulation":
            violations.append({"manifest": mid, "issue": "rigorous 模式下不允许认知噪声",
                               "severity": "high"})
        noticed, ignored = m.get("noticed") or [], m.get("ignored") or []
        if not isinstance(noticed, list) or not isinstance(ignored, list):
            violations.append({"manifest": mid, "issue": "noticed/ignored 必须是 id 列表",
                               "severity": "high"})
            continue
        if any(not isinstance(x, str) for x in noticed + ignored):
            violations.append({"manifest": mid,
                               "issue": "manifest 只允许记录 id，检测到非字符串内容（疑似改写原文）",
                               "severity": "high"})
            continue
        overlap = set(noticed) & set(ignored)
        if overlap:
            violations.append({"manifest": mid, "issue": f"noticed 与 ignored 重叠：{sorted(overlap)}",
                               "severity": "medium"})
        unknown = [x for x in noticed + ignored if x not in known_ids]
        if unknown:
            violations.append({"manifest": mid,
                               "issue": f"引用了状态中不存在的条目：{unknown}",
                               "severity": "medium"})
        if not m.get("attention_ratio"):
            warnings.append(f"{mid} 未记录 attention_ratio，无法复现注意力筛选")

    roles_with_claims = {c.get("role") for c in state.get("claims", [])}
    declared = {(m.get("role"), m.get("round")) for m in manifests}
    round_now = state.get("round", 0)
    if mode == "simulation":
        for r in roles_with_claims:
            if not any(role == r for role, _ in declared):
                warnings.append(f"{r} 在 simulation 模式下没有注意力声明（可能未启用噪声）")
        for (role, rnd) in declared:
            if rnd and rnd <= round_now and not any(
                    m.get("role") == role and m.get("round") == rnd for m in manifests):
                warnings.append(f"{role} 第 {rnd} 轮缺少注意力声明")

    return {
        "needs_judgment": True,
        "mode": mode,
        "manifests": len(manifests),
        "mode_violations": [v for v in violations if v["severity"] == "high"],
        "violations": violations,
        "warnings": warnings,
        "facts_untouched": not any(v["issue"].startswith("manifest 只允许") for v in violations),
        "verdict": "reject" if violations else ("pass_with_warnings" if warnings else "pass"),
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

    def base(mode="simulation", conf=55):
        claims = []
        for i in range(6):
            claims.append({"id": f"M1-{i+1}", "role": "musk", "round": 1, "text": f"马斯克论断{i}",
                           "responses_received": []})
            claims.append({"id": f"P1-{i+1}", "role": "pg", "round": 1, "text": f"pg 论断{i}",
                           "responses_received": []})
        return {
            "mode": mode, "round": 1, "roles": ["musk", "pg"],
            "claims": claims,
            "open_challenges": [{"id": "C1", "from": "pg", "to": "musk", "round": 1,
                                 "target_claim": "M1-1", "status": "open"}],
            "meta": {"hidden_assumptions": [{"id": "H1", "content": "前提"}],
                     "divergences": [], "information_gaps": [], "fallacies": []},
            "positions": {"musk": {"confidence": conf}, "pg": {"confidence": 80}},
            "next_round": {"must_respond": []},
        }

    st = base()
    plan = make_plan(st, "musk", seed=7, attention=0.5, style="auto")
    ck(all(i in plan["noticed"] for i in ["M1-1", "M1-3"]), "角色始终看得见自己的主张")
    ck(plan["ignored"], "低注意力比例下产生忽略清单")
    ck(set(plan["noticed"]) | set(plan["ignored"]) ==
       {c["id"] for c in st["claims"]} | {"C1", "H1"}, "可见与忽略覆盖全部历史条目")
    ck(not (set(plan["noticed"]) & set(plan["ignored"])), "可见与忽略不重叠")

    p2 = make_plan(st, "musk", seed=7, attention=0.5, style="auto")
    ck(p2["noticed"] == plan["noticed"] and p2["style_profile"] == plan["style_profile"],
       "同种子结果可复现")
    diffs = sum(1 for s in range(1, 8)
                if make_plan(st, "musk", seed=s, attention=0.5, style="auto")["noticed"] != plan["noticed"])
    ck(diffs > 0, "不同种子产生不同的注意力选择")

    full = make_plan(st, "musk", seed=7, attention=1.0, style="conclusion_first")
    ck(full["ignored"] == [], "attention=1.0 时不忽略任何条目")
    ck(full["style_profile"]["key"] == "conclusion_first", "显式指定表达档位被采纳")

    low = make_plan(base(conf=30), "musk", seed=3, attention=0.6, style="auto")
    high = make_plan(base(conf=95), "musk", seed=3, attention=0.6, style="auto")
    ck(any("保留语气" in r for r in low["tone_rules"]), "低置信度要求保留语气")
    ck(any("我可能错在哪" in r for r in high["tone_rules"]), "高置信度要求自陈可能错误")

    forced = base()
    forced["next_round"]["must_respond"] = ["P1-1"]
    forcing, found_seed = None, None
    for s in range(1, 80):
        probe = make_plan(base(), "musk", seed=s, attention=0.2, style="auto")
        if "P1-1" in probe["ignored"]:
            found_seed = s
            forcing = make_plan(forced, "musk", seed=s, attention=0.2, style="auto")
            break
    ck(forcing is not None and "P1-1" in forcing["noticed"],
       f"强制回应项不受注意力筛选影响（seed={found_seed}）")
    ck(forcing is not None and any("强制" in w for w in forcing["warnings"]),
       "强制项被拉回可见范围时给出告警")

    ch = base()
    ch["open_challenges"] = [{"id": "C9", "from": "pg", "to": "musk", "round": 1,
                              "target_claim": "M1-1", "status": "open"}]
    res = None
    for s in range(1, 40):
        cand = make_plan(ch, "musk", seed=s, attention=0.3, style="auto")
        if "C9" in cand["ignored"]:
            res = cand
            break
    ck(res is not None and any("没有注意到" in w for w in res["warnings"]),
       "忽略掉针对自己的质疑时给出「必须承认没注意到」的告警")

    # rigorous 模式必须被脚本级拒绝（不能只靠文档纪律）
    import contextlib
    import io
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        rp = Path(td) / "rigorous.json"
        rp.write_text(json.dumps(base(mode="rigorous"), ensure_ascii=False), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(["plan", "--state", str(rp), "--role", "musk"])
        ck(rc == 3 and '"mode_ok": false' in buf.getvalue(),
           "rigorous 模式下 plan 直接拒绝（退出码 3）")

        sp = Path(td) / "sim.json"
        sp.write_text(json.dumps(base(mode="simulation"), ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            rc2 = main(["plan", "--state", str(sp), "--role", "musk", "--write"])
        ck(rc2 == 0, "simulation 模式下 plan 正常执行")
        st2 = json.loads(sp.read_text(encoding="utf-8"))
        ck(st2["attention_manifests"][0]["id"] == "AM1" and st2["attention_manifests"][0]["ignored"],
           "--write 把注意力声明写入状态（含忽略清单）")
        with contextlib.redirect_stdout(io.StringIO()):
            rc3 = main(["check", "--state", str(sp)])
        ck(rc3 == 0, "check 可在写入后正常运行")

    # check：rigorous 中出现 manifest → 违规
    bad = base(mode="rigorous")
    bad["attention_manifests"] = [{"id": "AM1", "role": "musk", "round": 2, "attention_ratio": 0.5,
                                   "noticed": ["M1-1"], "ignored": []}]
    c = check(bad)
    ck(c["verdict"] == "reject" and c["mode_violations"], "rigorous 模式下的噪声记录被判违规")

    good = base()
    good["attention_manifests"] = [{"id": "AM1", "role": "musk", "round": 2, "attention_ratio": 0.5,
                                    "noticed": ["M1-1"], "ignored": ["P1-1"]}]
    c2 = check(good)
    ck(c2["verdict"] in ("pass", "pass_with_warnings") and c2["facts_untouched"], "合法记录通过检查")
    ck(not any("不存在" in v["issue"] for v in c2["violations"]), "合法记录不报未知条目")

    fake = base()
    fake["attention_manifests"] = [{"id": "AM1", "role": "musk", "round": 2, "attention_ratio": 0.5,
                                    "noticed": ["M1-1"], "ignored": ["Z9-9"]}]
    c3 = check(fake)
    ck(any("不存在" in v["issue"] for v in c3["violations"]), "引用不存在条目被判违规")

    rewritten = base()
    rewritten["attention_manifests"] = [{"id": "AM1", "role": "musk", "round": 2, "attention_ratio": 0.5,
                                         "noticed": [{"id": "M1-1", "text": "改写后的文本"}],
                                         "ignored": []}]
    c4 = check(rewritten)
    ck(c4["facts_untouched"] is False, "检测到改写原文（非 id 结构）被判违规")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="认知噪声注入器（仅 simulation 模式）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("plan")
    pp.add_argument("--state", required=True)
    pp.add_argument("--role", required=True)
    pp.add_argument("--seed", type=int, default=7)
    pp.add_argument("--attention", type=float, default=DEFAULT_ATTENTION)
    pp.add_argument("--style", default="auto")
    pp.add_argument("--write", action="store_true")
    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "plan":
        state = load_state(args.state)
        if state.get("mode") != "simulation":
            emit({
                "mode_ok": False,
                "error": f"当前 mode={state.get('mode')!r}，认知噪声仅在 simulation 模式下可用",
                "hint": "若确实需要真人质感，请用 state_manager.py init --mode simulation 重开会话；"
                        "rigorous 模式下严禁启用噪声（会降低严谨性且不可追溯）",
            })
            return 3
        plan = make_plan(state, args.role, args.seed, args.attention, args.style)
        if args.write:
            plan["manifest"] = write_manifest(args.state, state, plan)
            log(f"已写入注意力声明 {plan['manifest']['id']}")
        emit(plan)
        return 0
    if args.cmd == "check":
        emit(check(load_state(args.state)))
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

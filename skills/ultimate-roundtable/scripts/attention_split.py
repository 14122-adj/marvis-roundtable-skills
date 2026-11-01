#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""注意力分舱 attention_split.py

V4.0 的「分舱机制」执行器。核心命题：

    上下文超载会让角色产生"脑雾"——记得住所有历史，反而什么都抓不住。

分舱的做法：每个角色只拿到**与自己核心视角相关**的那一小片历史，
其余条目进入 `muted`（屏蔽）清单，不进入它的上下文。

六个舱位（`role → 关注镜头`）：

| 角色 | 镜头 | 关注什么 |
|---|---|---|
| musk | 物理与成本 | 约束、量级、下界、成本结构 |
| feynman | 可检验性 | 定义、可观测判据、反例、伪理解 |
| munger | 风险与激励 | 失败路径、激励错位、二阶效应、长期 |
| jobs | 复杂度 | 减法、冗余、环节、使用者 |
| karpathy | 可复现 | 指标、证据链、基线、实验设计 |
| pg | 案例 | 真实案例、n=1、模式、反例 |

纪律（写进代码而不是只写文档）：

1. **分舱只影响"看见什么"，不改写任何原文**——`muted` 只记录 id，绝不复制或改写内容；
2. **北极星相关条目永不屏蔽**：与 `north_star` 有关的条目对所有角色可见；
3. **强制条目永不屏蔽**：`must_respond` / `must_resolve` 里的 id 一律可见；
4. **150 字闸门**（阶段一发言长度上限）独立检查，与分舱互不替代。

用法：
  python attention_split.py plan   --state S --role pg [--limit 150] [--write]
  python attention_split.py check  --state S
  python attention_split.py lenses                       # 打印六个舱位的镜头定义
  python attention_split.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

SIX_ROLES = ["musk", "feynman", "munger", "jobs", "karpathy", "pg"]
SPEECH_LIMIT = 150          # 阶段一每条发言的字数上限
NORTH_STAR_TAG = "north_star"

# 每个角色的镜头：关键词表（中文字面匹配，不做语义理解）
LENSES = {
    "musk": {
        "label": "物理与成本",
        "keywords": ["约束", "物理", "成本", "量级", "下界", "预算", "投入", "产出",
                     "能耗", "产能", "极限", "单价", "倍数"],
    },
    "feynman": {
        "label": "可检验性",
        "keywords": ["定义", "口径", "可观测", "可测", "反例", "证伪", "检验",
                     "什么意思", "无法验证", "伪理解", "判据"],
    },
    "munger": {
        "label": "风险与激励",
        "keywords": ["风险", "失败", "激励", "考核", "长期", "二阶", "损失",
                     "合规", "反向", "倒推", "谁受损", "代理"],
    },
    "jobs": {
        "label": "复杂度",
        "keywords": ["冗余", "环节", "减法", "简化", "流程", "审批", "评审",
                     "使用者", "没人需要", "砍掉", "步骤"],
    },
    "karpathy": {
        "label": "可复现",
        "keywords": ["指标", "证据", "基线", "实验", "样本", "复现", "对照",
                     "消融", "泄漏", "可测", "评测", "数据源"],
    },
    "pg": {
        "label": "案例",
        "keywords": ["案例", "实例", "例子", "见过", "真实", "两次", "团队",
                     "n=1", "泛化", "反例", "经历"],
    },
}

LENS_CN = {r: v["label"] for r, v in LENSES.items()}


def log(msg: str) -> None:
    print(f"[attention_split] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[attention_split] ERROR: {msg}", file=sys.stderr)
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
    return unicodedata.normalize("NFKC", str(text or ""))


def char_len(text: str) -> int:
    """中文字数：去掉空白与标点后计数（与"150 字"的直觉一致）。"""
    t = _norm(text)
    t = re.sub(r"[\s\W_]+", "", t, flags=re.UNICODE)
    return len(t)


def hits(text: str, keywords: list) -> list:
    t = _norm(text)
    return [k for k in keywords if k in t]


# --------------------------------------------------------------------------- #
# 历史条目收集
# --------------------------------------------------------------------------- #


def history_items(state: dict) -> list:
    """把状态里所有可被"看见"的条目拍平成统一列表。"""
    items = []
    for c in state.get("claims", []) or []:
        items.append({"id": c.get("id"), "kind": "claim", "role": c.get("role"),
                      "text": (c.get("text", "") + " " + c.get("evidence", "")),
                      "tags": c.get("tags", [])})
    for e in state.get("clash_exchanges", []) or []:
        items.append({"id": f"X-{e.get('from')}-{e.get('target_claim') or 'na'}",
                      "kind": "exchange", "role": e.get("from"),
                      "text": (e.get("text", "") + " " + str(e.get("inner_thought", ""))),
                      "tags": []})
    for ch in state.get("open_challenges", []) or []:
        items.append({"id": ch.get("id"), "kind": "challenge", "role": ch.get("from"),
                      "text": ch.get("question", ""), "tags": []})
    meta = state.get("meta", {}) or {}
    for key, kind in (("hidden_assumptions", "assumption"), ("divergences", "divergence"),
                      ("information_gaps", "gap"), ("fallacies", "fallacy")):
        for x in meta.get(key, []) or []:
            items.append({"id": x.get("id"), "kind": kind, "role": None,
                          "text": json.dumps(x, ensure_ascii=False), "tags": []})
    for t in (state.get("stage1", {}) or {}).get("tool_results", []) or []:
        items.append({"id": f"T-{t.get('role')}", "kind": "tool", "role": t.get("role"),
                      "text": f"{t.get('query','')} {t.get('result','')}", "tags": []})
    return [i for i in items if i["id"]]


def forced_ids(state: dict) -> set:
    """北极星 + 强制条目：对所有角色可见，永不被屏蔽。"""
    forced = set()
    ns = (state.get("stage0") or {}).get("north_star") or state.get("north_star") or ""
    if ns:
        for it in history_items(state):
            if hits(it["text"], [ns]) or NORTH_STAR_TAG in (it.get("tags") or []):
                forced.add(it["id"])
    for inj in state.get("injections", []) or []:
        forced.update(inj.get("must_respond", []) or [])
        forced.update(inj.get("must_resolve", []) or [])
    for inj in (state.get("next_round") or {}).get("must_respond", []) or []:
        forced.add(inj)
    return forced


# --------------------------------------------------------------------------- #
# 分舱
# --------------------------------------------------------------------------- #


def plan(state: dict, role: str, limit: int = SPEECH_LIMIT) -> dict:
    if role not in LENSES:
        die(f"角色 {role!r} 不在 {SIX_ROLES} 内")
    lens = LENSES[role]
    items = history_items(state)
    forced = forced_ids(state)
    ns = (state.get("stage0") or {}).get("north_star") or state.get("north_star") or ""

    visible, muted, reasons = [], [], {}
    for it in items:
        matched = hits(it["text"], lens["keywords"])
        own = it.get("role") == role
        if it["id"] in forced:
            visible.append(it["id"])
            reasons[it["id"]] = "forced(北极星/强制条目)"
        elif own:
            visible.append(it["id"])
            reasons[it["id"]] = "own(自己的发言)"
        elif matched:
            visible.append(it["id"])
            reasons[it["id"]] = f"lens(命中 {matched[:2]})"
        else:
            muted.append(it["id"])

    total = len(items)
    ratio = round(len(visible) / total, 3) if total else 0.0
    warnings = []
    if not ns:
        warnings.append("尚未设定北极星指标：分舱缺少焦点，建议先执行 stage0")
    if total and len(visible) == total:
        warnings.append("全部分舱可见：历史条目太少或关键词过宽，分舱未起作用")
    if total and not visible:
        warnings.append("全部分舱被屏蔽：镜头关键词可能与该议题不匹配，检查 LENSES")

    return {
        "needs_judgment": True,
        "role": role,
        "lens": {"key": role, "label": lens["label"], "keywords": lens["keywords"]},
        "north_star": ns,
        "speech_limit": limit,
        "history_total": total,
        "visible": visible,
        "muted": muted,
        "visible_ratio": ratio,
        "reasons": reasons,
        "warnings": warnings,
        "note": ("分舱只影响'看得见什么'，不改写任何原文；"
                 "muted 里的内容不得被引用，被追问时应承认'这不在我的镜头里'"),
    }


def check(state: dict) -> dict:
    """校验已写入的分舱声明：结构合法、未改写原文、强制条目未被屏蔽。"""
    manifests = state.get("attention_splits") or []
    known = {i["id"]: i for i in history_items(state)}
    forced = forced_ids(state)
    violations, warnings = [], []

    for m in manifests:
        mid = f"{m.get('role')}@{m.get('round', '?')}"
        vis, mut = m.get("visible") or [], m.get("muted") or []
        if any(not isinstance(x, str) for x in vis + mut):
            violations.append({"manifest": mid,
                               "issue": "只允许记录 id，检测到非字符串内容（疑似改写原文）",
                               "severity": "high"})
            continue
        overlap = set(vis) & set(mut)
        if overlap:
            violations.append({"manifest": mid, "issue": f"visible 与 muted 重叠：{sorted(overlap)}",
                               "severity": "medium"})
        unknown = [x for x in vis + mut if x not in known]
        if unknown:
            violations.append({"manifest": mid, "issue": f"引用不存在的条目：{unknown}",
                               "severity": "medium"})
        blocked_forced = [x for x in mut if x in forced]
        if blocked_forced:
            violations.append({"manifest": mid,
                               "issue": f"北极星/强制条目被屏蔽：{blocked_forced}",
                               "severity": "high"})
        if not m.get("north_star"):
            warnings.append(f"{mid} 未记录北极星指标")

    # 150 字闸门
    over = []
    for c in (state.get("stage1", {}) or {}).get("confessions", []) or []:
        n = char_len(c.get("text", ""))
        if n > SPEECH_LIMIT:
            over.append({"role": c.get("role"), "chars": n})
    if over:
        violations.append({"manifest": "stage1",
                           "issue": f"发言超过 {SPEECH_LIMIT} 字：{over}",
                           "severity": "high"})

    return {
        "needs_judgment": True,
        "manifests": len(manifests),
        "violations": violations,
        "warnings": warnings,
        "speech_limit": SPEECH_LIMIT,
        "facts_untouched": not any(v["issue"].startswith("只允许记录") for v in violations),
        "verdict": "reject" if violations else ("pass_with_warnings" if warnings else "pass"),
    }


def write_manifest(state_path: str, state: dict, p: dict, round_no: int = 1) -> dict:
    store = state.setdefault("attention_splits", [])
    entry = {
        "role": p["role"],
        "round": round_no,
        "lens": p["lens"]["label"],
        "north_star": p["north_star"],
        "visible": p["visible"],
        "muted": p["muted"],
        "visible_ratio": p["visible_ratio"],
        "speech_limit": p["speech_limit"],
    }
    store.append(entry)
    save_state(state_path, state)
    return entry


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    def base():
        return {
            "north_star": "",
            "stage0": {"north_star": "月活"},
            "claims": [
                {"id": "M1-1", "role": "musk",
                 "text": "评审的固定成本是主项，量级约为每次 3 人时", "evidence": ""},
                {"id": "F1-1", "role": "feynman",
                 "text": "「效率」的口径必须先定义，否则无法验证", "evidence": ""},
                {"id": "G1-1", "role": "munger",
                 "text": "缩短考核周期会让长期项目承担风险", "evidence": ""},
                {"id": "J1-1", "role": "jobs",
                 "text": "复议环节是冗余的，应当砍掉", "evidence": ""},
                {"id": "K1-1", "role": "karpathy",
                 "text": "需要对照实验与基线，否则指标不可复现", "evidence": ""},
                {"id": "P1-1", "role": "pg",
                 "text": "我见过两个团队只改频次，半年后回到原状", "evidence": ""},
            ],
            "open_challenges": [],
            "clash_exchanges": [],
            "meta": {"hidden_assumptions": [{"id": "H1", "content": "月活是唯一目标"}],
                     "divergences": [], "information_gaps": [], "fallacies": []},
            "stage1": {"tool_results": []},
            "injections": [{"round": 2, "must_respond": ["H1"]}],
        }

    st = base()
    p_musk = plan(st, "musk")
    ck(p_musk["lens"]["label"] == "物理与成本", "musk 的镜头是物理与成本")
    ck("M1-1" in p_musk["visible"], "自己的发言永远可见")
    ck("J1-1" in p_musk["muted"], "无关的复杂度发言被屏蔽（musk 看不到 jobs 的减法）")
    ck("H1" in p_musk["visible"], "强制条目（H1）不被屏蔽")
    ck(0 < p_musk["visible_ratio"] < 1, "分舱后可见比例介于 0 和 1 之间")

    p_jobs = plan(st, "jobs")
    ck("J1-1" in p_jobs["visible"], "jobs 看得见自己的减法主张")
    ck(p_jobs["visible"] != p_musk["visible"], "不同角色的可见集合不同（分舱生效）")

    p_pg = plan(st, "pg")
    ck("P1-1" in p_pg["visible"], "pg 看得见自己的案例")

    # 北极星相关条目对所有角色可见
    st["claims"].append({"id": "M1-2", "role": "musk",
                         "text": "月活提升到 10 万需要多少获客预算", "evidence": ""})
    p_f = plan(st, "feynman")
    ck("M1-2" in p_f["visible"], "提到北极星的条目对所有角色可见")

    # 全可见时给出警告
    tiny = {"stage0": {"north_star": "月活"}, "claims": [
        {"id": "M1-1", "role": "musk", "text": "月活是核心指标", "evidence": ""}],
        "open_challenges": [], "clash_exchanges": [], "meta": {}, "stage1": {}, "injections": []}
    ck(any("未起作用" in w for w in plan(tiny, "pg")["warnings"]), "全可见时给出分舱失效警告")

    # 无北极星时警告
    no_ns = base()
    no_ns["stage0"] = {}
    no_ns["north_star"] = ""
    ck(any("北极星" in w for w in plan(no_ns, "musk")["warnings"]), "缺北极星时给出警告")

    # 字数闸门
    ck(char_len("这是一句话。") == 5, "字数统计忽略标点")
    ck(char_len("a b c") == 3, "字数统计忽略空格")

    # check：合法 manifest
    good = base()
    good["attention_splits"] = [{"role": "musk", "round": 1, "north_star": "月活",
                                 "visible": ["M1-1", "H1"], "muted": ["J1-1"]}]
    good["stage1"]["confessions"] = [{"role": "musk", "text": "短发言"}]
    c1 = check(good)
    ck(c1["verdict"] in ("pass", "pass_with_warnings"), "合法分舱记录通过检查")
    ck(c1["facts_untouched"] is True, "未检测到改写原文")

    # check：屏蔽了强制条目
    bad = base()
    bad["attention_splits"] = [{"role": "musk", "round": 1, "north_star": "月活",
                                "visible": ["M1-1"], "muted": ["H1"]}]
    c2 = check(bad)
    ck(c2["verdict"] == "reject" and any("强制条目被屏蔽" in v["issue"] for v in c2["violations"]),
       "屏蔽强制条目被判违规")

    # check：发言超 150 字
    long = base()
    long["stage1"]["confessions"] = [{"role": "musk", "text": "字" * 200}]
    c3 = check(long)
    ck(c3["verdict"] == "reject" and any("150" in v["issue"] for v in c3["violations"]),
       "发言超 150 字被判违规")

    # check：改写原文（非字符串）
    rew = base()
    rew["attention_splits"] = [{"role": "musk", "round": 1, "north_star": "月活",
                                "visible": [{"id": "M1-1", "text": "改写"}], "muted": []}]
    c4 = check(rew)
    ck(c4["facts_untouched"] is False, "检测到改写原文被判违规")

    # 写入
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "s.json"
        save_state(sp, base())
        stt = load_state(sp)
        entry = write_manifest(str(sp), stt, plan(stt, "pg"))
        ck(entry["role"] == "pg" and load_state(sp)["attention_splits"][0]["role"] == "pg",
           "分舱声明可写回状态")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="注意力分舱（V4.0）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("plan")
    pp.add_argument("--state", required=True)
    pp.add_argument("--role", required=True)
    pp.add_argument("--limit", type=int, default=SPEECH_LIMIT)
    pp.add_argument("--round", type=int, default=1)
    pp.add_argument("--write", action="store_true")

    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)

    sub.add_parser("lenses")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "plan":
        st = load_state(args.state)
        p = plan(st, args.role, args.limit)
        if args.write:
            p["manifest"] = write_manifest(args.state, st, p, args.round)
            log(f"已写入分舱声明：{args.role} 可见 {len(p['visible'])}/{p['history_total']}")
        emit(p)
        return 0
    if args.cmd == "check":
        emit(check(load_state(args.state)))
        return 0
    if args.cmd == "lenses":
        emit({"speech_limit": SPEECH_LIMIT,
              "lenses": {r: {"label": v["label"], "keywords": v["keywords"]}
                         for r, v in LENSES.items()}})
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

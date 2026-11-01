#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终极圆桌编排引擎 ultimate_orchestrator.py

`ultimate-roundtable` v2.0.0 的执行器。把"六人轮流发言"升级成四阶段高密度决策推演：

  阶段一 极速摊牌与工具诉求 —— 每个角色必须给出 [数据诉求]，并标注数据是**真实获取**还是**模拟**
  阶段二 幽灵干预与红蓝对抗 —— 内心戏 (Inner Thought) + [打断] + 3v3 强制分营 + 火花检测
  阶段三 沙盘推演        —— 逐月推演、[召唤]临时角色、存活率算术评估
  阶段四 元认知降维打击   —— 共同隐性假设 + ≤200 字长期记忆

设计纪律（与 spec 逐条对应）：

  * "禁止和稀泥"不是口号：`stage2` 会调用火花检测，**无火花则拒绝推进**（退出码 4），
    并把重开理由逐条打印出来。
  * "拒绝废话"同样是可检查的：空洞发言（"我觉得挺好的""各有优劣"）会被计数，
    占比超阈值直接判定无火花。
  * 数据必须诚实：每条数据诉求要么有真实工具返回（`source: tool`），要么明确标
    `simulated: true`。**不允许把模拟数据伪装成真实数据**——这一点由 `check` 强制。
  * 最终报告格式是冻结的（见 `render_report`），字段缺失或出现禁止断言即报错。

用法：
  python ultimate_orchestrator.py init    --topic "议题" [--out DIR] [--mode rigorous]
  python ultimate_orchestrator.py stage1  --state S --file roles.json   [--write]
  python ultimate_orchestrator.py stage2  --state S --file clash.json   [--write]
  python ultimate_orchestrator.py stage3  --state S --file sandbox.json [--write]
  python ultimate_orchestrator.py stage4  --state S --file meta.json    [--write]
  python ultimate_orchestrator.py report  --state S [--out REPORT.md] [--json]
  python ultimate_orchestrator.py check   --state S
  python ultimate_orchestrator.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clash_analyzer import (civilian_audit, spark, survival_score)  # noqa: E402
from memory_store import intro as memory_intro, recall as memory_recall  # noqa: E402
from memory_store import remember as memory_remember  # noqa: E402
from memory_store import resolve_store as memory_store_path  # noqa: E402
from attention_split import (SPEECH_LIMIT, LENSES, char_len, check as split_check,  # noqa: E402
                             plan as split_plan, write_manifest as split_write)
from deadlock_detector import (FUSE_TEMPLATE, LEGACY_FUSE_TEMPLATE, check as deadlock_check,  # noqa: E402
                               fuse as deadlock_fuse, build_judge_material,
                               record_verdicts as deadlock_record)

SCHEMA_VERSION = "4.1.0"
SIX_ROLES = ["musk", "feynman", "munger", "jobs", "karpathy", "pg"]
ROLE_CN = {"musk": "马斯克", "feynman": "费曼", "munger": "芒格",
           "jobs": "乔布斯", "karpathy": "Karpathy", "pg": "Paul Graham"}
STAGES = ["stage0", "stage1", "stage2", "stage3", "stage4"]
OPTION_KEYS = ["A", "B", "C"]
OPTION_LABELS = {"A": "激进方案 A", "B": "保守方案 B", "C": "降维方案 C"}
OPTION_DEFS = {
    "A": "激进派：高收益高风险",
    "B": "保守派：低收益低风险",
    "C": "奇招：跳出当前框架的物理/降维解法",
}
# 咨询体措辞：V4 最终输出中绝对禁止
CONSULTANT_PHRASES = [
    "一方面", "另一方面", "视具体情况而定", "具体问题具体分析", "因人而异",
    "综合考虑", "权衡利弊", "建议进一步", "可能需要", "大概", "也许", "或许",
    "酌情", "看情况", "有待观察",
]

DATA_DEMAND_RE = re.compile(r"\[数据诉求[:：]\s*(.+?)\]")
INNER_THOUGHT_RE = re.compile(r"\(Inner Thought[:：]\s*(.+?)\)", re.S)
INTERRUPT_RE = re.compile(r"\[打断\]")
VERIFY_INTERRUPT_RE = re.compile(r"\[打断并验真\]")
TOOL_CALL_RE = re.compile(r"\[Tool Call[:：]\s*(Search|Code)\]\s*(.+?)(?:\n|$)", re.I)
STANCE_AFTER_RE = re.compile(r"基于(?:此|该|这)(?:数据|结果|查证)")
SUMMON_RE = re.compile(r"\[召唤[:：]\s*(.+?)\]")
MEMORY_LIMIT = 200
TOOL_KINDS = ["Search", "Code"]

# 报告里禁止出现的断言（拒绝"和稀泥"式措辞 + 防伪造完成状态）
FORBIDDEN_PHRASES = [
    "已达成共识", "已验证", "已挖到根本", "结论已确定", "大家都同意",
    "我觉得挺好的", "各有优劣", "见仁见智", "综合考虑吧",
]


def log(msg: str) -> None:
    print(f"[ultimate] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[ultimate] ERROR: {msg}", file=sys.stderr)
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


def read_payload(args) -> dict:
    raw = args.json if getattr(args, "json", None) else (
        sys.stdin.read() if getattr(args, "file", None) == "-"
        else Path(args.file).read_text(encoding="utf-8"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        die(f"输入不是合法 JSON: {exc}")


# --------------------------------------------------------------------------- #
# 状态骨架
# --------------------------------------------------------------------------- #


def new_state(topic: str, mode: str = "rigorous") -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": "ur-" + datetime.now().strftime("%Y%m%d-%H%M%S"),
        "topic": topic,
        "mode": mode,
        "stage": "init",
        "stages_done": [],
        "roles": list(SIX_ROLES),
        "role_cn": ROLE_CN,
        "north_star": "",
        "stage0": {"memory_loaded": [], "opening_line": "", "store": "", "north_star": ""},
        "stage1": {"confessions": [], "data_demands": [], "tool_results": [],
                   "low_confidence": []},
        "stage2": {"exchanges": [], "camps": {}, "spark": None, "verifications": []},
        "stage3": {"options": {}, "votes": {}, "decision": "", "action_plan": {}},
        "stage4": {"meta": {}, "memory": "", "memory_written": False},
        "camps": {},
        "clash_exchanges": [],
        "attention_splits": [],
        "fused": False,
        "debate_closed": False,
        "sandbox": {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------- #
# 阶段零：记忆唤醒（V3 新增）
# --------------------------------------------------------------------------- #


def run_stage0(state: dict, payload: dict) -> dict:
    """读取历史 [MEMORY_UPDATE]，输出 spec 规定的开场白。

    spec 说"仅限新会话的第一轮"，因此重复执行 stage0 会更新开场白但不重复计入 stages_done。
    """
    store = payload.get("store") or None
    path = memory_store_path(store)
    limit = int(payload.get("limit", 3))
    memories = memory_recall(path, limit=limit)
    opening = memory_intro(path, limit=limit)

    # V4 · 北极星指标：全场唯一的焦点，后续所有发言必须围绕它
    north_star = str(payload.get("north_star") or "").strip()
    if not north_star:
        die("阶段零缺少 north_star（北极星指标）：V4 要求全场只有一个焦点指标，"
            "例如「月活」「利润率」「存活率」", 3)

    state["north_star"] = north_star
    state["stage0"] = {
        "memory_loaded": memories,
        "opening_line": opening,
        "store": str(path),
        "memory_count": len(memories),
        "north_star": north_star,
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    if "stage0" not in state["stages_done"]:
        state["stages_done"].append("stage0")
    state["stage"] = "stage0_done"
    return {"stage": "stage0", "ok": True, "opening_line": opening,
            "north_star": north_star,
            "memory_count": len(memories), "store": str(path),
            "focus_rule": f"本轮起所有发言必须围绕「{north_star}」，偏离即视为无效发言",
            "memories": [{"id": m.get("id"), "text": m.get("text"),
                          "created_at": m.get("created_at")} for m in memories]}


# --------------------------------------------------------------------------- #
# 阶段一：摊牌与数据诉求
# --------------------------------------------------------------------------- #


def _parse_tool_calls(text: str) -> list:
    return [{"kind": m.group(1).capitalize(), "detail": m.group(2).strip()}
            for m in TOOL_CALL_RE.finditer(str(text))]


def _check_tool_closure(role: str, text: str, tool: dict, problems: list) -> dict:
    """V3 闭环要求：所有 [数据诉求] 必须有对应的 [Tool Call] 结果，不允许抛出问题就跑。"""
    calls = _parse_tool_calls(text)
    if not calls:
        problems.append(f"{role} 缺少 [Tool Call: Search|Code] 标记：V3 要求数据诉求必须闭环")
    if not STANCE_AFTER_RE.search(text):
        problems.append(f"{role} 拿到工具结果后没有明确表态"
                        f"（必须出现「基于此数据，我的观点是…」）")
    return {"calls": calls, "closed": bool(calls) and bool(STANCE_AFTER_RE.search(text))}


def run_stage1(state: dict, payload: dict) -> dict:
    confessions = payload.get("confessions") or []
    if not isinstance(confessions, list) or not confessions:
        die("stage1 需要 confessions 数组（六个角色各一条）")
    if "stage0" not in state["stages_done"]:
        die("必须先完成阶段零（stage0）：北极星指标未锚定前不得开始交底", 3)

    north_star = state.get("north_star") or ""
    seen, problems, demands, results = set(), [], [], []
    low_confidence, splits = [], []
    for i, c in enumerate(confessions, 1):
        role = c.get("role")
        if role not in SIX_ROLES:
            problems.append(f"第 {i} 条角色 {role!r} 不在六人名单内")
            continue
        if role in seen:
            problems.append(f"角色 {role} 重复发言（六个角色各一条）")
        seen.add(role)

        text = str(c.get("text", ""))

        # V4 · 分舱机制：150 字上限，强行过滤废话
        n_chars = char_len(text)
        if n_chars > SPEECH_LIMIT:
            problems.append(f"{role} 发言 {n_chars} 字，超过分舱上限 {SPEECH_LIMIT} 字："
                            f"V4 要求只讲底线逻辑，不许铺陈")

        # V4 · 焦点锚定：偏离北极星即视为无效发言
        if north_star and north_star not in text:
            problems.append(f"{role} 的发言未提及北极星指标「{north_star}」："
                            f"V4 要求所有发言围绕唯一焦点指标")

        m = DATA_DEMAND_RE.search(text)
        if not m:
            problems.append(f"{role} 缺少 [数据诉求: ...] 标记（阶段一强制）")
        else:
            demands.append({"role": role, "demand": m.group(1).strip()})

        tool = c.get("tool_result") or {}
        if not tool:
            problems.append(f"{role} 没有 tool_result：必须真实调用工具或明确标注模拟")
            continue
        source = tool.get("source")
        simulated = bool(tool.get("simulated"))
        if source == "tool" and simulated:
            problems.append(f"{role} 标注矛盾：source=tool 但 simulated=true")
        if source != "tool" and not simulated:
            problems.append(f"{role} 的 tool_result 既不是真实工具返回（source=tool）"
                            f"也没有标 simulated=true —— 不允许把模拟数据伪装成真实数据")
        results.append({"role": role, "source": source, "simulated": simulated,
                        "tool": tool.get("tool", ""), "query": tool.get("query", ""),
                        "result": tool.get("result", ""), "obtained_at": tool.get("obtained_at", "")})
        closure = _check_tool_closure(role, text, tool, problems)
        results[-1]["tool_calls"] = closure["calls"]
        results[-1]["closure_ok"] = closure["closed"]
        if not closure["closed"]:
            low_confidence.append({"role": role, "reason": "缺少工具闭环，视为低置信度发言"})

    missing = [r for r in SIX_ROLES if r not in seen]
    if missing:
        problems.append(f"缺少角色发言：{', '.join(missing)}")

    if problems:
        die("阶段一校验失败：\n  - " + "\n  - ".join(problems), 3)

    # 先把阶段一写进状态，分舱才有历史可分（顺序不能颠倒）
    state["stage1"] = {"confessions": confessions, "data_demands": demands,
                       "tool_results": results, "low_confidence": low_confidence}

    # 生成六份分舱声明（每个角色只看自己镜头内的历史）
    splits = [split_plan(state, role) for role in SIX_ROLES]
    state["attention_splits"] = [{
        "role": p["role"], "round": 1, "lens": p["lens"]["label"],
        "north_star": p["north_star"], "visible": p["visible"], "muted": p["muted"],
        "visible_ratio": p["visible_ratio"], "speech_limit": p["speech_limit"],
    } for p in splits]

    state["camps"] = state.get("camps") or {}
    if "stage1" not in state["stages_done"]:
        state["stages_done"].append("stage1")
    state["stage"] = "stage1_done"
    return {"stage": "stage1", "ok": True, "roles": len(seen),
            "data_demands": len(demands),
            "real_tool_calls": len([r for r in results if r["source"] == "tool"]),
            "simulated": len([r for r in results if r["simulated"]]),
            "closure_ok": len([r for r in results if r.get("closure_ok")]),
            "demands": demands}


# --------------------------------------------------------------------------- #
# 阶段二：内心戏 + 打断 + 红蓝对抗
# --------------------------------------------------------------------------- #


def run_stage2(state: dict, payload: dict) -> dict:
    if "stage1" not in state["stages_done"]:
        die("必须先完成阶段一（stage1）", 3)
    if state.get("debate_closed"):
        die(f"辩论已被强制熔断（{state.get('fuse_message', FUSE_TEMPLATE)}）："
            f"不得再提交 stage2 交锋，请直接进入阶段三铁血裁决", 3)
    if "stage0" not in state["stages_done"]:
        die("必须先完成阶段零（stage0）：北极星指标未锚定前不得开始对抗", 3)

    camps = payload.get("camps") or {}
    blue, red = camps.get("blue") or [], camps.get("red") or []
    problems = []
    if len(blue) != 3 or len(red) != 3:
        problems.append(f"红蓝必须各 3 人（当前 blue={len(blue)} red={len(red)}）")
    if set(blue) & set(red):
        problems.append(f"同一角色不能同时在两营：{sorted(set(blue) & set(red))}")
    unknown = [r for r in blue + red if r not in SIX_ROLES]
    if unknown:
        problems.append(f"未知角色：{unknown}")

    exchanges = payload.get("exchanges") or []
    if not exchanges:
        problems.append("exchanges 为空：没有交锋就不算对抗")

    cleaned = []
    verifications = []
    for i, e in enumerate(exchanges, 1):
        role = e.get("from")
        text = str(e.get("text", ""))
        if role not in SIX_ROLES:
            problems.append(f"第 {i} 条发言角色 {role!r} 非法")
            continue
        it = e.get("inner_thought") or ""
        if not it and INNER_THOUGHT_RE.search(text):
            it = INNER_THOUGHT_RE.search(text).group(1).strip()
        if not it:
            problems.append(f"第 {i} 条（{role}）缺少 (Inner Thought: ...)：阶段二每个角色发言前必须先输出内心戏")

        # V3 · [打断并验真]：触发后必须给出验真结果，否则就是"打断完就跑"
        verify = bool(e.get("verify")) or bool(VERIFY_INTERRUPT_RE.search(text))
        v_result = e.get("verify_result") or {}
        if verify:
            calls = _parse_tool_calls(text)
            if not calls and not v_result:
                problems.append(
                    f"第 {i} 条（{role}）使用了 [打断并验真]，但没有 [Tool Call] 也没有 verify_result："
                    f"验真必须落地，不能只打断不查证")
            verifications.append({
                "from": role,
                "target_claim": e.get("target_claim"),
                "tool_calls": calls,
                "result": v_result.get("result", ""),
                "source": v_result.get("source", "tool" if calls else ""),
                "simulated": bool(v_result.get("simulated")),
                "verdict": v_result.get("verdict", "inconclusive"),
            })

        cleaned.append({
            "from": role,
            "round": 2,
            "camp": "blue" if role in blue else ("red" if role in red else None),
            "inner_thought": it,
            "interrupt": bool(e.get("interrupt")) or bool(INTERRUPT_RE.search(text)),
            "verify": verify,
            "target_claim": e.get("target_claim"),
            "text": text,
            "evidence": e.get("evidence", ""),
        })

    if problems:
        die("阶段二校验失败：\n  - " + "\n  - ".join(problems), 3)

    state["camps"] = {"blue": blue, "red": red}
    state["clash_exchanges"] = cleaned
    state["stage2"] = {"exchanges": cleaned, "camps": state["camps"], "spark": None,
                       "verifications": verifications}

    sp = spark(state, 2)
    state["stage2"]["spark"] = sp
    state["clash_spark"] = {**state.get("clash_spark", {}), "2": sp}

    if not sp["sparked"]:
        state["stage"] = "stage2_no_spark"
        emit({"stage": "stage2", "ok": False, "verdict": "no_spark",
              "reopen_required": True, "reasons": sp["reasons"], "spark": sp,
              "action": "按 spec 强制重开一轮红蓝对抗：针对下列理由逐条补强后再次提交 stage2"})
        raise SystemExit(4)

    # V4.1 · 语义级死锁检测：先接收主持人写回的语义判定，再双路径判定
    incoming = payload.get("semantic_verdicts") or []
    if incoming:
        deadlock_record("", state, incoming)
        log(f"接收 {len(incoming)} 条语义判定")

    dl = deadlock_check(state)
    state["stage2"]["deadlock"] = dl
    if dl.get("deadlock"):
        fused = deadlock_fuse("", state, "；".join(dl.get("reasons", [])))
        state["stage2"]["fused"] = fused
        if "stage2" not in state["stages_done"]:
            state["stages_done"].append("stage2")
        state["stage"] = "stage2_fused"
        emit({"stage": "stage2", "ok": True, "verdict": "deadlock_fused",
              "fuse_message": FUSE_TEMPLATE,
              "trigger": dl.get("trigger"),
              "reasons": dl.get("reasons", []),
              "consecutive_stalled": dl.get("consecutive_stalled"),
              "deadlock": dl,
              "next": "辩论已终止，直接进入阶段三铁血裁决（三选一）"})
        return {"stage": "stage2", "ok": True, "verdict": "deadlock_fused",
                "blue": blue, "red": red, "fused": True,
                "trigger": dl.get("trigger"),
                "fuse_message": FUSE_TEMPLATE, "reasons": dl.get("reasons", [])}

    if "stage2" not in state["stages_done"]:
        state["stages_done"].append("stage2")
    state["stage"] = "stage2_done"
    # 放行时也把待判材料带出去：主持人应在下一轮前完成语义判定
    judge_hint = None
    if not dl.get("semantic_coverage", {}).get("judged_pairs"):
        try:
            judge_hint = build_judge_material(state)
        except SystemExit:
            judge_hint = None
    return {"stage": "stage2", "ok": True, "verdict": "sparked",
            "blue": blue, "red": red,
            "interrupts": len([e for e in cleaned if e["interrupt"]]),
            "verifications": len(verifications),
            "deadlock": dl,
            "semantic_judge_required": judge_hint is not None,
            "semantic_judge_material": judge_hint,
            "spark": sp}


# --------------------------------------------------------------------------- #
# 阶段三：铁血裁决（三选一）
# --------------------------------------------------------------------------- #


def _validate_options(options: dict, problems: list) -> None:
    if not isinstance(options, dict):
        problems.append("options 必须是 {A,B,C} 对象")
        return
    missing = [k for k in OPTION_KEYS if k not in options]
    if missing:
        problems.append(f"缺少方案：{missing}（V4 强制 A/B/C 三选一）")
    texts = []
    for k in OPTION_KEYS:
        opt = options.get(k) or {}
        if not isinstance(opt, dict):
            problems.append(f"方案 {k} 必须是对象")
            continue
        desc = str(opt.get("summary") or "").strip()
        if not desc:
            problems.append(f"方案 {k} 缺少 summary（一句话说清这个方案做什么）")
        elif len(desc) > 120:
            problems.append(f"方案 {k} 的 summary 超过 120 字：V4 要求一句话说清")
        texts.append(_norm_cn(desc))
        # kind 可由 OPTION_DEFS 自动补齐：它是展示用的固定标签，不是用户的判断。
        # 缺了就补，不因此拒绝——真正该拒绝的是 summary 为空或三方案换皮。
        if not opt.get("kind"):
            opt["kind"] = OPTION_DEFS[k]
    # 互斥性：三个方案不能是同一句话的复读
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if texts[i] and texts[i] == texts[j]:
                problems.append(f"方案 {OPTION_KEYS[i]} 与 {OPTION_KEYS[j]} 描述完全相同："
                                f"V4 要求三个方案互斥，不许换皮")


def _norm_cn(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(text or ""), flags=re.UNICODE)


def run_stage3(state: dict, payload: dict) -> dict:
    """V4 铁血裁决：A/B/C 三选一 + 最后一轮投票（不再辩论）。"""
    if "stage2" not in state["stages_done"]:
        die("必须先完成阶段二（红蓝对抗）", 3)
    if state.get("fused") and not state.get("debate_closed"):
        die("熔断状态异常：debate_closed 未置位", 3)

    problems = []
    options = payload.get("options") or {}
    _validate_options(options, problems)

    votes = payload.get("votes") or {}
    if not isinstance(votes, dict):
        problems.append("votes 必须是 {角色: A|B|C} 对象")
        votes = {}
    unknown_voters = [r for r in votes if r not in SIX_ROLES]
    if unknown_voters:
        problems.append(f"投票人不在六人名单内：{unknown_voters}")
    missing_voters = [r for r in SIX_ROLES if r not in votes]
    if missing_voters:
        problems.append(f"缺少投票：{missing_voters}（V4 要求六人全部投出最后一票）")
    bad_ballots = {r: v for r, v in votes.items() if v not in OPTION_KEYS}
    if bad_ballots:
        problems.append(f"票投给了不存在的方案：{bad_ballots}")

    reasons = payload.get("vote_reasons") or {}
    for r in votes:
        if not str(reasons.get(r, "")).strip():
            problems.append(f"{r} 投票缺少理由（V4 要求陈述理由，不再互相辩论）")

    decision = str(payload.get("decision") or "").strip().upper()
    if decision not in OPTION_KEYS:
        problems.append(f"缺少 decision 或取值非法（{decision!r}）：必须明确拍板 A/B/C 之一")

    if problems:
        die("阶段三校验失败：\n  - " + "\n  - ".join(problems), 3)

    tally = {k: sorted([r for r, v in votes.items() if v == k]) for k in OPTION_KEYS}
    top = max(tally, key=lambda k: len(tally[k]))
    warnings = []
    if decision != top:
        warnings.append(f"拍板结论 {decision} 与票数最高方案 {top}"
                        f"（{len(tally[top])} 票）不一致：主持人需说明为何否决多数票")
    if not str(payload.get("decision_reason") or "").strip():
        warnings.append("未记录 decision_reason（为什么选它）：建议补充，便于事后追溯")

    state["stage3"] = {
        "options": {k: {**{"kind": OPTION_DEFS[k]}, **(options.get(k) or {})} for k in OPTION_KEYS},
        "votes": votes,
        "vote_reasons": reasons,
        "tally": tally,
        "decision": decision,
        "decision_reason": str(payload.get("decision_reason") or ""),
        "top_by_votes": top,
    }
    if "stage3" not in state["stages_done"]:
        state["stages_done"].append("stage3")
    state["stage"] = "stage3_done"
    return {"stage": "stage3", "ok": True, "decision": decision,
            "tally": {k: len(v) for k, v in tally.items()},
            "top_by_votes": top, "warnings": warnings,
            "options": {k: state["stage3"]["options"][k].get("summary", "") for k in OPTION_KEYS}}


# --------------------------------------------------------------------------- #
# 阶段三B（可选）：沙盘推演
# --------------------------------------------------------------------------- #


def run_sandbox(state: dict, payload: dict) -> dict:
    if "stage2" not in state["stages_done"]:
        die("必须先完成阶段二（且红蓝对抗必须打出火花）", 3)

    sandbox = payload.get("sandbox") or {}
    problems = []
    plan_name = sandbox.get("plan") or sandbox.get("chosen_plan")
    if not plan_name:
        problems.append("缺少 sandbox.plan（被推演的综合方案名）")

    timeline = sandbox.get("timeline") or []
    if len(timeline) < 3:
        problems.append(f"timeline 至少需要 3 个月度节点（当前 {len(timeline)}）："
                        "沙盘不能只靠嘴说")
    for i, t in enumerate(timeline, 1):
        if not t.get("month"):
            problems.append(f"第 {i} 个时间点缺少 month")
        if not t.get("event"):
            problems.append(f"第 {i} 个时间点缺少 event（会发生什么）")
        if t.get("metric") is None and not t.get("error"):
            problems.append(f"第 {i} 个时间点既没有 metric 也没有 error：推演必须给出可观测结果")

    runners = sandbox.get("runners") or []
    if not set(runners) >= {"karpathy", "musk"}:
        problems.append("沙盘必须由 karpathy 与马斯克主推（spec 要求）")

    summons = payload.get("summons") or sandbox.get("summons") or []
    for s in summons:
        if not s.get("role"):
            problems.append("召唤条目缺少 role（如「法务专家」）")
        if not s.get("reason"):
            problems.append(f"召唤 {s.get('role')} 缺少 reason（为什么出现了认知盲区）")
        if not s.get("statement"):
            problems.append(f"召唤 {s.get('role')} 缺少 statement（该角色说了什么）")

    # V3 · 现实沙盘：必须引入真实工具（代码执行/搜索）验证至少一条假设
    sandbox_tools = sandbox.get("tool_calls") or payload.get("tool_calls") or []
    if not sandbox_tools:
        problems.append(
            "沙盘缺少 tool_calls：V3 要求沙盘阶段必须用外部工具（代码执行/搜索）验证假设，"
            "不能只靠嘴说")
    for i, tc in enumerate(sandbox_tools, 1):
        if tc.get("kind") not in TOOL_KINDS:
            problems.append(f"第 {i} 个 tool_call 的 kind={tc.get('kind')!r} 不在 {TOOL_KINDS} 内")
        if not tc.get("purpose"):
            problems.append(f"第 {i} 个 tool_call 缺少 purpose（要验证哪条假设）")
        if not tc.get("result"):
            problems.append(f"第 {i} 个 tool_call 缺少 result（验证结果不能为空）")
        if tc.get("kind") == "Code" and not tc.get("code"):
            problems.append(f"第 {i} 个 Code 调用缺少 code 字段")
        if tc.get("source") != "tool" and not tc.get("simulated"):
            problems.append(f"第 {i} 个 tool_call 既非真实调用（source=tool）也未标 simulated=true")

    if problems:
        die("阶段三校验失败：\n  - " + "\n  - ".join(problems), 3)

    scenario = {
        "plan": plan_name,
        "risks": sandbox.get("risks") or [],
        "key_assumptions": sandbox.get("key_assumptions") or [],
        "attacks": sandbox.get("attacks") or [],
        "plan_slots": sandbox.get("action_plan") or {},
    }
    surv = survival_score({
        "risks": scenario["risks"],
        "key_assumptions": scenario["key_assumptions"],
        "attacks": scenario["attacks"],
        "plan": sandbox.get("action_plan") or {},
    })

    state["sandbox"] = {**sandbox, "tool_calls": sandbox_tools, "evaluation": surv}
    # 沙盘是阶段三的可选补充，写入 stage3.sandbox 而不是覆盖三选一裁决
    state.setdefault("stage3", {})
    state["stage3"]["sandbox"] = state["sandbox"]
    state["stage3"]["summons"] = summons
    if summons:
        state.setdefault("summoned_roles", []).extend(summons)
    if "sandbox" not in state["stages_done"]:
        state["stages_done"].append("sandbox")
    state["stage"] = "sandbox_done"
    return {"stage": "sandbox", "ok": True, "plan": plan_name,
            "timeline_months": len(timeline),
            "tool_calls": len(sandbox_tools),
            "summoned": [s.get("role") for s in summons],
            "survival": surv}


# --------------------------------------------------------------------------- #
# 阶段四：战术级行动清单 + 记忆沉淀
# --------------------------------------------------------------------------- #


def _validate_action_plan(ap: dict, problems: list) -> None:
    """V4 颗粒度下探：负责人 / Start / KPI / Kill 四要素缺一不可，且必须带数字。"""
    if not isinstance(ap, dict):
        problems.append("action_plan 必须是对象")
        return
    owner = str(ap.get("owner") or "").strip()
    if not owner:
        problems.append("action_plan.owner 缺失（必须指定负责人角色）")
    elif owner not in SIX_ROLES and not owner.startswith("召唤"):
        problems.append(f"action_plan.owner={owner!r} 不在六人名单内（或未标注为召唤角色）")

    for field, label in (("start", "第一步（Start）"), ("kpi", "关键指标（KPI）"),
                         ("kill", "止损红线（Kill）")):
        val = str(ap.get(field) or "").strip()
        if not val:
            problems.append(f"action_plan.{field} 缺失（{label}）")
            continue
        # 颗粒度：KPI 与 Kill 必须含数字，否则就是咨询体
        if field in ("kpi", "kill") and not re.search(r"\d", val):
            problems.append(f"action_plan.{field} 没有具体数字（{label}）："
                            f"V4 禁止「大概、也许、建议」，必须给出可判定的数值")
        if re.search(r"大概|也许|或许|酌情|视情况|建议进一步|综合考虑", val):
            problems.append(f"action_plan.{field} 含模糊措辞（{label}）："
                            f"V4 要求明确指令与数字")

    if not (ap.get("need_info") or []):
        problems.append("action_plan.need_info 为空：至少列出一条仍需补充调研的信息")


def run_stage4(state: dict, payload: dict) -> dict:
    if "stage3" not in state["stages_done"]:
        die("必须先完成阶段三（铁血裁决）", 3)

    meta = payload.get("meta") or payload
    problems = []
    shared = meta.get("shared_hidden_assumption") or ""
    if not shared:
        problems.append("缺少 shared_hidden_assumption（大家始终没跳出的共同隐性假设）")
    broken = meta.get("assumption_broken") or []
    if not broken:
        problems.append("缺少 assumption_broken（被前两轮交锋证明为错的前提，至少 1 条）")
    ignored = meta.get("ignored_dimension") or ""
    if not ignored:
        problems.append("缺少 ignored_dimension（被忽略的成本维度）")
    memory = str(meta.get("memory") or "").strip()
    if not memory:
        problems.append("缺少 memory（长期记忆）")
    elif len(memory) > MEMORY_LIMIT:
        problems.append(f"长期记忆 {len(memory)} 字，超过 {MEMORY_LIMIT} 字上限")

    action_plan = payload.get("action_plan") or meta.get("action_plan") or {}
    _validate_action_plan(action_plan, problems)

    if problems:
        die("阶段四校验失败：\n  - " + "\n  - ".join(problems), 3)

    persist = payload.get("persist_memory", True)
    written = None
    if persist:
        store = payload.get("store") or None
        written = memory_remember(
            memory_store_path(store), memory,
            tags=meta.get("memory_tags") or ["终极圆桌"],
            session=state.get("session_id", ""),
            topic=state.get("topic", ""),
        )

    state["stage4"] = {"meta": meta, "memory": memory,
                       "action_plan": action_plan,
                       "memory_written": bool(written),
                       "memory_entry": written}
    if "stage4" not in state["stages_done"]:
        state["stages_done"].append("stage4")
    state["stage"] = "stage4_done"
    return {"stage": "stage4", "ok": True, "memory_chars": len(memory),
            "shared_hidden_assumption": shared,
            "owner": action_plan.get("owner"),
            "memory_written": bool(written),
            "memory_id": (written or {}).get("id"),
            "memory_store": str(memory_store_path(payload.get("store") or None)) if written else ""}


# --------------------------------------------------------------------------- #
# 报告渲染（格式冻结）
# --------------------------------------------------------------------------- #


def collect_report_data(state: dict) -> dict:
    s1 = state.get("stage1", {})
    s2 = state.get("stage2", {})
    sb = state.get("sandbox", {})
    s3 = state.get("stage3", {})
    s4 = state.get("stage4", {})
    s4meta = s4.get("meta", {})
    surv = sb.get("evaluation") or {}

    return {
        "topic": state.get("topic", ""),
        "session_id": state.get("session_id", ""),
        "stage": state.get("stage"),
        "stages_done": state.get("stages_done", []),
        "north_star": state.get("north_star") or state.get("stage0", {}).get("north_star", ""),
        "assumption_broken": s4meta.get("assumption_broken") or [],
        "ignored_dimension": s4meta.get("ignored_dimension", ""),
        "shared_hidden_assumption": s4meta.get("shared_hidden_assumption", ""),
        # V4 · 三选一裁决
        "options": s3.get("options", {}),
        "votes": s3.get("votes", {}),
        "vote_reasons": s3.get("vote_reasons", {}),
        "tally": s3.get("tally", {}),
        "decision": s3.get("decision", ""),
        "decision_reason": s3.get("decision_reason", ""),
        # V4 · 战术级行动清单
        "action_plan": s4.get("action_plan") or {},
        "memory": s4.get("memory", ""),
        "memory_written": s4.get("memory_written", False),
        "memory_entry": s4.get("memory_entry"),
        "data_demands": s1.get("data_demands", []),
        "tool_results": s1.get("tool_results", []),
        "low_confidence": s1.get("low_confidence", []),
        "camps": s2.get("camps", {}),
        "verifications": s2.get("verifications", []),
        "summons": s3.get("summons", []) or state.get("stage3", {}).get("summons", []),
        "sandbox_tools": sb.get("tool_calls", []),
        "survival_rate": surv.get("survival_rate"),
        "spark": s2.get("spark") or {},
        "deadlock": s2.get("deadlock") or {},
        "fused": bool(state.get("fused")),
        "fuse_message": state.get("fuse_message", ""),
        "memory_loaded": state.get("stage0", {}).get("memory_loaded", []),
        "opening_line": state.get("stage0", {}).get("opening_line", ""),
        "attention_splits": state.get("attention_splits", []),
    }


def _bullets(items, empty="（未提供）"):
    if not items:
        return f"- {empty}"
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append(f"  - {it.get('text') or it.get('name') or json.dumps(it, ensure_ascii=False)}")
        else:
            out.append(f"  - {it}")
    return "\n".join(out)


def render_report(state: dict) -> str:
    """V4.1 冻结报告格式（五节，与 spec 逐字对应）。

    V4 相对 V3 的变化：
      * 新增第 1 节「北极星指标与底线假设」（全场唯一焦点）；
      * 新增第 3 节「铁血裁决（三选一）」——A/B/C 互斥方案 + 投票 + 拍板；
      * 第 4 节从「存活率」换成「战术级行动清单」——负责人 / Start / KPI / Kill / Need Info；
      * 存活率降级为过程留痕（V4 关注落地，不关注概率）。
    """
    d = collect_report_data(state)
    ap = d["action_plan"] or {}
    if not d["north_star"]:
        die("缺少北极星指标（先执行 stage0）", 3)
    if not d["decision"]:
        die("缺少最终拍板结论（先执行 stage3 三选一）", 3)
    for f in ("owner", "start", "kpi", "kill"):
        if not str(ap.get(f) or "").strip():
            die(f"战术级行动清单缺少 {f}：V4 拒绝咨询体，必须给出可执行指令", 3)
    if not d["memory"]:
        die("缺少长期记忆（先执行 stage4）", 3)

    sim_count = len([t for t in d["tool_results"] if t.get("simulated")])
    real_count = len([t for t in d["tool_results"] if t.get("source") == "tool"])

    L = []
    L.append("### ⚔️ 终极圆桌决策报告 V4.1")
    L.append("")
    L.append(f"> 议题：{d['topic']}　会话：`{d['session_id']}`")
    L.append(f"> 外部数据：真实工具调用 {real_count} 条 / 模拟 {sim_count} 条")
    if d["opening_line"]:
        L.append(f"> {d['opening_line']}")
    L.append("")

    # ---- 1. 北极星与底线假设 ----
    L.append("#### 📌 1. 北极星指标与底线假设")
    L.append(f"- 本次推演的核心指标：**{d['north_star']}**")
    if d["shared_hidden_assumption"]:
        L.append(f"- 我们击穿的隐性假设：**{d['shared_hidden_assumption']}**")
    for item in d["assumption_broken"]:
        L.append(f"- 底线假设被推翻：一开始默认了 {item}，交锋证明这是错的。")
    if d["ignored_dimension"]:
        L.append(f"- 被忽略的成本维度：{d['ignored_dimension']}")
    L.append("")

    # ---- 2. 证据链 ----
    L.append("#### 🔗 2. 证据链与外部验证")
    if not d["tool_results"] and not d["sandbox_tools"]:
        L.append("- （本次未引入任何外部数据：按 V4 纪律，这样的会议不应产出决策报告）")
    for i, t in enumerate(d["tool_results"], 1):
        kind = "真实工具" if t.get("source") == "tool" else "模拟"
        calls = t.get("tool_calls") or []
        call_desc = "；".join(f"[{c['kind']}] {c['detail']}" for c in calls) or "未标注 Tool Call"
        L.append(f"- 数据 {i}（{t.get('role')}，来源：{kind}）：{t.get('query', '') or '—'}")
        L.append(f"  - 调用：{call_desc}")
        L.append(f"  - 结果：{str(t.get('result', ''))[:160]}")
    for i, t in enumerate(d["sandbox_tools"], 1):
        kind = "真实" if t.get("source") == "tool" else "模拟"
        L.append(f"- 工具验证 {i}（{kind}·{t.get('kind', '')}）：{t.get('purpose', '')}")
        L.append(f"  - 运行结果：{str(t.get('result', ''))[:200]}")
    if d["verifications"]:
        L.append(f"- **打断并验真 {len(d['verifications'])} 次**：")
        for v in d["verifications"]:
            L.append(f"  - {v.get('from')} 对 {v.get('target_claim') or '（未指定靶点）'} → "
                     f"{v.get('verdict')}：{str(v.get('result', ''))[:120]}")
    L.append("")

    # ---- 3. 铁血裁决 ----
    L.append("#### 🚦 3. 铁血裁决（三选一）")
    tally = d["tally"]
    for k in OPTION_KEYS:
        opt = d["options"].get(k) or {}
        supporters = tally.get(k) or []
        L.append(f"- **{OPTION_LABELS[k]}**：{opt.get('summary', '（未提供）')}"
                 f"（投票支持：{'、'.join(supporters) if supporters else '无'}）")
        if opt.get("kind"):
            L.append(f"  - 定位：{opt['kind']}")
    L.append(f"- 🏆 **最终拍板结论**：采用方案 {d['decision']}")
    if d["decision_reason"]:
        L.append(f"  - 拍板理由：{d['decision_reason']}")
    if d["fused"]:
        L.append(f"  - 熔断记录：{d['fuse_message']}")
    L.append("")

    # ---- 4. 战术级行动清单 ----
    L.append("#### 🎯 4. 战术级行动清单 (Action Items)")
    L.append(f"- **负责人**：{ap.get('owner', '')}")
    L.append(f"- **第一步（Start）**：{ap.get('start', '')}")
    L.append(f"- **关键指标（KPI）**：{ap.get('kpi', '')}")
    L.append(f"- **止损红线（Kill）**：{ap.get('kill', '')}")
    need = ap.get("need_info") or []
    L.append(f"- **补充调研（Need Info）**：{'；'.join(need) if need else '（无）'}")
    L.append("")

    # ---- 5. 长期记忆 ----
    L.append("#### 🧠 5. 长期记忆写入")
    L.append(f"- `[MEMORY_UPDATE]`：{d['memory']}")
    if d["memory_written"]:
        entry = d["memory_entry"] or {}
        L.append(f"  - 已写入记忆库：`{entry.get('id', '')}`（{entry.get('chars', 0)} 字）")
    else:
        L.append("  - ⚠ 未写入记忆库（本次以 persist_memory=false 运行，仅用于测试）")
    L.append("")
    L.append("---")
    L.append("")
    L.append("**过程留痕（不属于报告正文）**")
    L.append("")
    L.append(f"- 阶段一数据诉求 {len(d['data_demands'])} 条：")
    L.extend([f"  - [{x['role']}] {x['demand']}" for x in d["data_demands"]])
    camps = d["camps"]
    L.append(f"- 红蓝分组：蓝军 {camps.get('blue', [])} ｜ 红军 {camps.get('red', [])}")
    sp = d["spark"]
    L.append(f"- 对抗火花：攻击 {sp.get('attack_count')} / 防御 {sp.get('defense_count')} / "
             f"靶点 {sp.get('target_spread')} / 空洞发言 {sp.get('hollow_count')} → "
             f"**{sp.get('verdict', 'unknown')}**")
    dl = d["deadlock"] or {}
    if dl:
        L.append(f"- 死锁检测：连续停滞 {dl.get('consecutive_stalled', 0)} 轮 → "
                 f"{'已熔断' if d['fused'] else '未熔断'}")
    splits = d["attention_splits"] or []
    if splits:
        L.append("- 注意力分舱：")
        for s in splits:
            L.append(f"  - {s.get('role')}（{s.get('lens')}）："
                     f"可见 {len(s.get('visible') or [])} 条，屏蔽 {len(s.get('muted') or [])} 条")
    if d["low_confidence"]:
        L.append(f"- 低置信度发言：{[x.get('role') for x in d['low_confidence']]}")
    if d["survival_rate"] is not None:
        L.append(f"- 沙盘存活率（参考）：{d['survival_rate']}%")
    if d["summons"]:
        L.append(f"- 动态召唤：{', '.join(s.get('role', '') for s in d['summons'])}")
    L.append(f"- 历史记忆加载：{len(d['memory_loaded'])} 条")

    md = "\n".join(L)
    bad = [p for p in FORBIDDEN_PHRASES + CONSULTANT_PHRASES if p in md]
    if bad:
        die(f"报告含禁止措辞 {bad}（V4 禁止和稀泥与咨询体：一方面/另一方面/视具体情况而定）", 3)
    return md


# --------------------------------------------------------------------------- #
# 完整性检查
# --------------------------------------------------------------------------- #


def check(state: dict) -> dict:
    issues, warnings = [], []
    done = state.get("stages_done", [])
    for st in STAGES:
        if st not in done:
            issues.append(f"阶段未完成：{st}")

    if not state.get("north_star"):
        issues.append("未设定北极星指标（V4 要求全场唯一焦点）")

    s1 = state.get("stage1", {})
    results = s1.get("tool_results") or []
    fake = [r for r in results if r.get("source") != "tool" and not r.get("simulated")]
    if fake:
        issues.append(f"有 {len(fake)} 条数据既非真实工具返回也未标注模拟："
                      f"{[r['role'] for r in fake]}")

    sp = (state.get("stage2") or {}).get("spark") or {}
    if sp and not sp.get("sparked"):
        issues.append("红蓝对抗未打出火花（必须重开一轮）")

    # V4 · 分舱与 150 字闸门
    sc = split_check(state)
    for v in sc.get("violations", []):
        issues.append(f"注意力分舱：{v['issue']}")

    # V4 · 死锁（未熔断但已满足条件时提示）
    dl = (state.get("stage2") or {}).get("deadlock") or {}
    if dl.get("deadlock") and not state.get("fused"):
        warnings.append("已满足死锁条件但未熔断：应执行 deadlock_detector.py fuse")

    # V4 · 三选一
    s3 = state.get("stage3") or {}
    if not s3.get("decision"):
        issues.append("未完成铁血裁决（缺少 decision：A/B/C）")
    tally = s3.get("tally") or {}
    if s3.get("decision") and tally:
        top = max(tally, key=lambda k: len(tally.get(k) or []))
        if s3["decision"] != top:
            warnings.append(f"拍板 {s3['decision']} 与票数最高 {top} 不一致：需记录否决理由")

    # V4 · 战术级行动清单
    ap = (state.get("stage4") or {}).get("action_plan") or {}
    for f in ("owner", "start", "kpi", "kill"):
        if not str(ap.get(f) or "").strip():
            issues.append(f"战术清单缺少 {f}（V4 拒绝咨询体）")
    for f in ("kpi", "kill"):
        val = str(ap.get(f) or "")
        if val and not re.search(r"\d", val):
            issues.append(f"战术清单 {f} 没有具体数字：必须可判定")
    if not (ap.get("need_info") or []):
        issues.append("战术清单 need_info 为空")

    memory = state.get("stage4", {}).get("memory", "")
    if memory and len(memory) > MEMORY_LIMIT:
        issues.append(f"长期记忆 {len(memory)} 字超过上限 {MEMORY_LIMIT}")

    sb = state.get("sandbox") or {}
    surv = sb.get("evaluation") or {}
    if surv.get("band") == "low":
        warnings.append(f"沙盘存活率 {surv.get('survival_rate')}% 属 low 分档：建议补 Need Info")

    # V1.6 · 平民视角审计：精英共识时提示召唤
    civ = civilian_audit(state)
    if civ["should_summon"]:
        warnings.append(
            f"精英视角盲区：{'；'.join(civ['reasons'])}。"
            f"建议召唤 {'、'.join(civ['suggested_roles'])}"
            f"（clash_analyzer.py civilian 可查看详情）")
    for qp in civ["quality_problems"]:
        warnings.append(f"平民角色「{qp['role']}」发言缺 {qp['missing']}：{qp['note']}")

    return {
        "needs_judgment": True,
        "stages_done": done,
        "stage": state.get("stage"),
        "north_star": state.get("north_star", ""),
        "issues": issues,
        "warnings": warnings,
        "decision": s3.get("decision", ""),
        "survival_rate": surv.get("survival_rate"),
        "sparked": sp.get("sparked"),
        "fused": bool(state.get("fused")),
        "civilian_audit": civ,
        "ready_to_report": not issues,
        "verdict": "ready" if not issues else "not_ready",
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def cmd_init(args) -> int:
    st = new_state(args.topic, args.mode)
    out = Path(args.out) if args.out else Path(".ultimate") / st["session_id"]
    out.mkdir(parents=True, exist_ok=True)
    path = out / "state.json"
    save_state(path, st)
    log(f"已创建终极圆桌状态：{path}")
    emit({"state_path": str(path), "session_id": st["session_id"],
          "roles": st["roles"], "next": "stage0"})
    return 0


def cmd_stage(args) -> int:
    st = load_state(args.state)
    payload = read_payload(args)
    fn = {"stage0": run_stage0, "stage1": run_stage1, "stage2": run_stage2,
          "stage3": run_stage3, "sandbox": run_sandbox, "stage4": run_stage4}[args.cmd]
    result = fn(st, payload)
    if args.write:
        save_state(args.state, st)
        log(f"已写回状态：stage={st['stage']}")
    emit(result)
    return 0


def cmd_report(args) -> int:
    st = load_state(args.state)
    if args.json:
        emit(collect_report_data(st))
        return 0
    md = render_report(st)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        log(f"报告已写入 {args.out}")
        emit({"report": args.out, "chars": len(md)})
    else:
        print(md)
    return 0


def cmd_check(args) -> int:
    st = load_state(args.state)
    r = check(st)
    emit(r)
    return 0 if r["ready_to_report"] else 1


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

    NORTH_STAR = "月活"

    def stage1_payload():
        conf = []
        for i, role in enumerate(SIX_ROLES):
            tool = ({"source": "tool", "tool": "web_search", "query": "示例查询",
                     "result": "示例返回", "obtained_at": "2026-11-01"} if i % 2 == 0
                    else {"source": "text", "simulated": True, "tool": "simulated_search",
                          "query": "示例查询", "result": "模拟返回"})
            conf.append({"role": role,
                         "text": f"{NORTH_STAR} 是关键。[数据诉求: 需要指标{i}] "
                                 f"[Tool Call: Search] 关键词：指标{i}。"
                                 f"基于此数据，我的观点是：结论 {i}。",
                         "tool_result": tool})
        return {"confessions": conf}

    def stage2_payload():
        return {
            "camps": {"blue": ["munger", "jobs", "pg"], "red": ["musk", "feynman", "karpathy"]},
            "exchanges": [
                {"from": "munger", "target_claim": "M1-1", "interrupt": True,
                 "inner_thought": "他没算失败率，我先打这里",
                 "text": "[打断] 你的推演假设组织愿意改考核，这个假设没被验证",
                 "evidence": "历史案例"},
                {"from": "jobs", "target_claim": "M1-2",
                 "inner_thought": "这堆流程没人真需要",
                 "text": "方案多出两个审批环节，砍掉后成本降 30%", "evidence": "减法清单"},
                {"from": "pg", "target_claim": "M1-1",
                 "inner_thought": "我只有一个案例，但必须顶住",
                 "text": "[打断并验真] 我要现场查证。[Tool Call: Search] 关键词：失效案例。"
                         "基于此数据，我的观点是：该做法已失效。",
                 "evidence": "示例案例", "verify": True,
                 "verify_result": {"result": "模拟检索：2 个案例显示失效",
                                   "simulated": True, "verdict": "supported"}},
                {"from": "musk", "target_claim": "P2-1",
                 "inner_thought": "包装成本量级太小",
                 "text": "接受包装成本，但它只占 3%，不改变结论", "evidence": "量级估算"},
                {"from": "feynman", "target_claim": "J2-1",
                 "inner_thought": "他连谁不需要都答不上来",
                 "text": "「没人需要」需要可观测判据", "evidence": "可操作化要求"},
                {"from": "karpathy", "target_claim": "G3-1",
                 "inner_thought": "指标会被反噬",
                 "text": "把获奖率当唯一指标会被包装行为反噬", "evidence": "古德哈特"},
            ],
        }

    def stage3_payload():
        return {
            "options": {
                "A": {"summary": "全量改为季度评审，三个月内切换完毕", "kind": OPTION_DEFS["A"]},
                "B": {"summary": "维持年度评审，只把材料准备流程精简一半", "kind": OPTION_DEFS["B"]},
                "C": {"summary": "取消固定评审，改为触发式评审：指标跌破阈值才开", "kind": OPTION_DEFS["C"]},
            },
            "votes": {"musk": "A", "feynman": "C", "munger": "B",
                      "jobs": "C", "karpathy": "C", "pg": "B"},
            "vote_reasons": {
                "musk": "月活增长窗口只有三个月，慢一步就没了",
                "feynman": "触发式评审有可观测判据，其他两个都在拍脑袋",
                "munger": "全量切换的失败路径太多，先精简材料更稳",
                "jobs": "固定评审本身就是冗余，触发式最省",
                "karpathy": "触发式可做对照实验，指标可复现",
                "pg": "我见过全量切换失败的案例，选保守",
            },
            "decision": "C",
            "decision_reason": "C 拿到 3 票且在方案 C 上红蓝双方都承认判据可观测；A 的下行风险未被防住",
        }

    def stage4_payload(store=None):
        payload = {"meta": {
            "shared_hidden_assumption": "评审的价值等于它拦下了多少项目",
            "assumption_broken": ["评审频次是成本主项"],
            "ignored_dimension": "上下文切换成本与申诉合规成本",
            "memory": "评审类流程的优化对象不是频次而是单次固定开销；"
                      "先定义成功标准再谈资源分配。",
            "memory_tags": ["评审", "流程"],
        }, "action_plan": {
            "owner": "karpathy",
            "start": "本周在 2 个团队上线触发式评审，阈值设为月活跌破 8%",
            "kpi": "30 天内触发 5 次以内，月活不低于 9%",
            "kill": "如果 30 天内触发超过 12 次，立刻停止并回滚到年度评审",
            "need_info": ["过去两年每次评审的平均人时", "触发阈值的敏感性测试结果"],
        }, "persist_memory": False}
        if store:
            payload["store"] = store
        return payload

    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "state.json"
        st = new_state("【自检】终极圆桌 V4")
        save_state(sp, st)

        # ---- 阶段零：记忆唤醒 + 北极星 ----
        mem = Path(td) / "mem.jsonl"
        try:
            run_stage0(st, {"store": str(mem)})
            ck(False, "缺北极星应被拒绝")
        except SystemExit:
            ck(True, "阶段零缺 north_star 被拒绝")

        r0 = run_stage0(st, {"store": str(mem), "north_star": NORTH_STAR})
        ck(r0["ok"] and r0["north_star"] == NORTH_STAR, "阶段零记录北极星指标")
        ck("月活" in r0["focus_rule"], "阶段零输出焦点规则")

        # ---- 阶段一 ----
        try:
            run_stage2(st, stage2_payload())
            ck(False, "跳过阶段一应被拒绝")
        except SystemExit:
            ck(True, "跳过阶段一被拒绝")

        # 150 字闸门
        long_p = stage1_payload()
        long_p["confessions"][0]["text"] = NORTH_STAR + "字" * 200 + "[数据诉求: x]"
        try:
            run_stage1(st, long_p)
            ck(False, "超 150 字应被拒绝")
        except SystemExit:
            ck(True, "发言超过 150 字被拒绝（分舱机制）")

        # 偏离北极星
        off = stage1_payload()
        off["confessions"][0]["text"] = ("这次讨论的重点是流程优化。[数据诉求: x] "
                                         "[Tool Call: Search] 关键词：x。基于此数据，我的观点是：x。")
        try:
            run_stage1(st, off)
            ck(False, "偏离北极星应被拒绝")
        except SystemExit:
            ck(True, "发言未围绕北极星被拒绝")

        # 伪装数据
        fake = stage1_payload()
        fake["confessions"][1]["tool_result"] = {"source": "text", "result": "看起来很真"}
        try:
            run_stage1(st, fake)
            ck(False, "伪装数据应被拒绝")
        except SystemExit:
            ck(True, "把模拟数据伪装成真实数据被拒绝")

        # 缺 Tool Call 闭环
        noc = stage1_payload()
        noc["confessions"][0]["text"] = f"{NORTH_STAR} 是核心。[数据诉求: 需要指标]"
        try:
            run_stage1(st, noc)
            ck(False, "缺 Tool Call 应被拒绝")
        except SystemExit:
            ck(True, "缺 [Tool Call] 闭环被拒绝")

        r1 = run_stage1(st, stage1_payload())
        ck(r1["ok"] and r1["roles"] == 6, "阶段一接受六人完整发言")
        ck(len(st["attention_splits"]) == 6, "阶段一为六个角色各生成一份分舱声明")
        ck(any(s["muted"] for s in st["attention_splits"]), "分舱确实屏蔽了部分历史")

        # ---- 阶段二 ----
        no_it = stage2_payload()
        no_it["exchanges"][0].pop("inner_thought")
        try:
            run_stage2(st, no_it)
            ck(False, "缺内心戏应被拒绝")
        except SystemExit:
            ck(True, "缺少内心戏被拒绝")

        no_verify = stage2_payload()
        no_verify["exchanges"][2].pop("verify_result")
        no_verify["exchanges"][2]["text"] = "[打断并验真] 你说该做法有效。"
        try:
            run_stage2(st, no_verify)
            ck(False, "验真无结果应被拒绝")
        except SystemExit:
            ck(True, "[打断并验真] 没有验真结果被拒绝")

        hollow = {"camps": {"blue": ["munger", "jobs", "pg"],
                            "red": ["musk", "feynman", "karpathy"]},
                  "exchanges": [{"from": r, "inner_thought": "随便吧", "text": "我觉得挺好的"}
                                for r in SIX_ROLES]}
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                run_stage2(st, hollow)
            ck(False, "空洞发言应触发重开")
        except SystemExit as exc:
            ck(exc.code == 4, "空洞发言触发退出码 4（强制重开）")

        r2 = run_stage2(st, stage2_payload())
        ck(r2["ok"] and r2["verdict"] == "sparked", "有交锋的对抗被判为打出火花")
        ck(r2["interrupts"] == 1 and r2["verifications"] == 1, "打断与验真被分别计数")

        # ---- 死锁熔断 ----
        dead = json.loads(json.dumps(st))
        dead["clash_exchanges"] = []
        for rnd in (2, 3):
            for e in stage2_payload()["exchanges"]:
                e2 = dict(e)
                e2["round"] = rnd
                dead["clash_exchanges"].append(e2)
        dead["argument_log"] = []
        dead["revisions"] = []
        dead["stage2"] = {"verifications": []}
        dl = deadlock_check(dead)
        ck(dl["deadlock"] is True, "两轮逐字复读被判为死锁（结构路径）")
        ck(FUSE_TEMPLATE in dl["fuse_message"], "熔断话术与 V4.1 spec 一致")

        # V4.1 · 语义级死锁：换说法但核心论点未变，结构路径抓不到，靠语义裁判
        sem_state = json.loads(json.dumps(st))
        sem_state["clash_exchanges"] = [
            {"from": "munger", "round": 2, "target_claim": "M1-1",
             "text": "你忽略了上下文切换成本，这一项会让预算翻倍"},
            {"from": "munger", "round": 3, "target_claim": "M1-1",
             "text": "协调开销你没有计入，实际支出会远超预期"},
        ]
        sem_state["argument_log"] = []
        sem_state["revisions"] = []
        sem_state["stage2"] = {"verifications": []}
        sem_state["semantic_verdicts"] = []
        structural = deadlock_check(sem_state)
        ck(structural["deadlock"] is False, "换说法场景下结构路径抓不到（预期）")

        sem_state["semantic_verdicts"] = [
            {"round": 2, "from": "munger", "to": "munger", "label": "REPEAT",
             "reason": "换词，核心论点未变"},
            {"round": 3, "from": "munger", "to": "munger", "label": "REPEAT",
             "reason": "同上"},
        ]
        semantic = deadlock_check(sem_state)
        ck(semantic["deadlock"] is True and semantic["trigger"] == "semantic",
           "语义 REPEAT 触发熔断（语义路径）")

        # 语义 PROGRESS 时放行
        prog_state = json.loads(json.dumps(sem_state))
        prog_state["semantic_verdicts"] = [
            {"round": 2, "from": "munger", "to": "munger", "label": "PROGRESS",
             "reason": "提出新的协调开销数据"},
            {"round": 3, "from": "munger", "to": "munger", "label": "PROGRESS"},
        ]
        ck(deadlock_check(prog_state)["deadlock"] is False, "语义 PROGRESS 时放行")

        # stage2 可直接接收 semantic_verdicts
        sem_in = json.loads(json.dumps(st))
        sem_in["stages_done"] = ["stage0", "stage1"]
        sem_in["stage2"] = {}
        sem_payload = stage2_payload()
        sem_payload["exchanges"] = sem_payload["exchanges"] + [
            {"from": "munger", "round": 2, "target_claim": "M1-1",
             "text": "协调开销你没计入，实际支出会远超预期",
             "inner_thought": "我再说一遍，看他有没有新数据"},
        ]
        sem_payload["semantic_verdicts"] = [
            {"round": 2, "from": "munger", "to": "munger", "label": "REPEAT",
             "reason": "与上一轮同义"},
        ]
        run_stage2(sem_in, sem_payload)
        ck(len(sem_in.get("semantic_verdicts", [])) == 1,
           "stage2 可直接接收 semantic_verdicts 并写回状态")

        # 熔断后不得再提交 stage2
        fused_state = json.loads(json.dumps(st))
        fused_state["fused"] = True
        fused_state["debate_closed"] = True
        try:
            run_stage2(fused_state, stage2_payload())
            ck(False, "熔断后仍提交交锋应被拒绝")
        except SystemExit:
            ck(True, "熔断后不得再提交 stage2（发言权已切断）")

        # ---- 阶段三：三选一 ----
        bad3 = stage3_payload()
        bad3["options"].pop("C")
        try:
            run_stage3(st, bad3)
            ck(False, "缺方案 C 应被拒绝")
        except SystemExit:
            ck(True, "缺少 A/B/C 之一被拒绝")

        same = stage3_payload()
        same["options"]["B"]["summary"] = same["options"]["A"]["summary"]
        try:
            run_stage3(st, same)
            ck(False, "方案重复应被拒绝")
        except SystemExit:
            ck(True, "三个方案描述相同时被拒绝（必须互斥）")

        novote = stage3_payload()
        novote["votes"].pop("pg")
        try:
            run_stage3(st, novote)
            ck(False, "缺投票应被拒绝")
        except SystemExit:
            ck(True, "六人未全部投票被拒绝")

        badballot = stage3_payload()
        badballot["votes"]["musk"] = "D"
        try:
            run_stage3(st, badballot)
            ck(False, "非法票应被拒绝")
        except SystemExit:
            ck(True, "票投给不存在的方案被拒绝")

        r3 = run_stage3(st, stage3_payload())
        ck(r3["ok"] and r3["decision"] == "C", "阶段三接受三选一并记录拍板")
        ck(r3["tally"]["C"] == 3, "票数统计正确（C 得 3 票）")

        # ---- 阶段四：战术级清单 ----
        for field in ("owner", "start", "kpi", "kill"):
            bad4 = stage4_payload()
            bad4["action_plan"].pop(field)
            try:
                run_stage4(st, bad4)
                ck(False, f"缺 {field} 应被拒绝")
            except SystemExit:
                ck(True, f"战术清单缺 {field} 被拒绝")

        nondigit = stage4_payload()
        nondigit["action_plan"]["kill"] = "如果效果不好就停止"
        try:
            run_stage4(st, nondigit)
            ck(False, "Kill 无数字应被拒绝")
        except SystemExit:
            ck(True, "止损红线没有具体数字被拒绝（拒绝咨询体）")

        vague = stage4_payload()
        vague["action_plan"]["kpi"] = "大概提升 10% 左右"
        try:
            run_stage4(st, vague)
            ck(False, "模糊措辞应被拒绝")
        except SystemExit:
            ck(True, "KPI 含「大概」被拒绝")

        r4 = run_stage4(st, stage4_payload())
        ck(r4["ok"] and r4["owner"] == "karpathy", "阶段四接受完整战术清单")

        # persist_memory=true 时写库
        st2 = json.loads(json.dumps(st))
        st2["stage4"] = {}
        mem2 = Path(td) / "mem2.jsonl"
        p4 = stage4_payload(store=str(mem2))
        p4["persist_memory"] = True
        r4b = run_stage4(st2, p4)
        ck(r4b["memory_written"] is True and mem2.exists(), "persist_memory=true 时写入记忆库")

        # ---- 报告 ----
        md = render_report(st)
        for sec in ["### ⚔️ 终极圆桌决策报告 V4.1",
                    "#### 📌 1. 北极星指标与底线假设",
                    "#### 🔗 2. 证据链与外部验证",
                    "#### 🚦 3. 铁血裁决（三选一）",
                    "#### 🎯 4. 战术级行动清单 (Action Items)",
                    "#### 🧠 5. 长期记忆写入"]:
            ck(sec in md, f"报告含 V4 章节 {sec}")
        ck("🏆 **最终拍板结论**：采用方案 C" in md, "报告写明最终拍板")
        for label in ("**负责人**", "第一步（Start）", "关键指标（KPI）", "止损红线（Kill）"):
            ck(label in md, f"报告含战术清单项 {label}")
        ck("[MEMORY_UPDATE]" in md, "包含 MEMORY_UPDATE")
        ck(not any(p in md for p in FORBIDDEN_PHRASES + CONSULTANT_PHRASES),
           "报告不含禁止措辞与咨询体")

        broken = json.loads(json.dumps(st))
        broken["stage4"]["action_plan"]["kill"] = ""
        try:
            render_report(broken)
            ck(False, "缺 Kill 应拒绝出报告")
        except SystemExit:
            ck(True, "战术清单有空项时拒绝出报告")

        # ---- check ----
        c = check(st)
        ck(c["ready_to_report"] is True and c["verdict"] == "ready", "完整状态判定为可交付")
        ck(c["stages_done"] == STAGES, "五个阶段全部记录")
        ck(c["north_star"] == NORTH_STAR and c["decision"] == "C", "检查结果带出北极星与裁决")

        half = new_state("半成品")
        c2 = check(half)
        ck(c2["ready_to_report"] is False and len(c2["issues"]) >= 4, "半成品被判定为不可交付")

        # V1.6 · 平民视角审计接入 check()
        ck("civilian_audit" in c, "check() 输出平民视角审计")
        ck(c["civilian_audit"]["civilian_summoned"] == [], "演示状态下未召唤平民角色")

        # ---- CLI 端到端 ----
        cli_state = Path(td) / "cli.json"
        save_state(cli_state, new_state("CLI 自检 V4"))
        steps = (("stage0", {"store": str(Path(td) / "cli-mem.jsonl"), "north_star": NORTH_STAR}),
                 ("stage1", stage1_payload()), ("stage2", stage2_payload()),
                 ("stage3", stage3_payload()), ("stage4", stage4_payload()))
        for name, payload in steps:
            pf = Path(td) / f"{name}.json"
            pf.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main([name, "--state", str(cli_state), "--file", str(pf), "--write"])
            ck(rc == 0, f"CLI {name} 正常执行并写回")
        st_cli = json.loads(cli_state.read_text(encoding="utf-8"))
        ck(st_cli["stage"] == "stage4_done", "CLI 全流程后阶段为 stage4_done")
        out_md = Path(td) / "report.md"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["report", "--state", str(cli_state), "--out", str(out_md)])
        ck(out_md.exists() and "终极圆桌决策报告 V4.1" in out_md.read_text(encoding="utf-8"),
           "CLI report 生成 V4 报告文件")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="终极圆桌编排引擎 V4（战术指挥部）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("--topic", required=True)
    pi.add_argument("--out")
    pi.add_argument("--mode", default="rigorous", choices=["rigorous", "simulation"])

    for name in STAGES + ["sandbox"]:
        p = sub.add_parser(name)
        p.add_argument("--state", required=True)
        p.add_argument("--file")
        p.add_argument("--json")
        p.add_argument("--write", action="store_true")

    pr = sub.add_parser("report")
    pr.add_argument("--state", required=True)
    pr.add_argument("--out")
    pr.add_argument("--json", action="store_true")

    pc = sub.add_parser("check")
    pc.add_argument("--state", required=True)

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd in STAGES or args.cmd == "sandbox":
        return cmd_stage(args)
    if args.cmd == "report":
        return cmd_report(args)
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

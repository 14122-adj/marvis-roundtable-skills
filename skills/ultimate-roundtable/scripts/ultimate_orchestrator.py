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

from clash_analyzer import spark, survival_score  # noqa: E402
from memory_store import intro as memory_intro, recall as memory_recall  # noqa: E402
from memory_store import remember as memory_remember  # noqa: E402
from memory_store import resolve_store as memory_store_path  # noqa: E402

SCHEMA_VERSION = "3.0.0"
SIX_ROLES = ["musk", "feynman", "munger", "jobs", "karpathy", "pg"]
ROLE_CN = {"musk": "马斯克", "feynman": "费曼", "munger": "芒格",
           "jobs": "乔布斯", "karpathy": "Karpathy", "pg": "Paul Graham"}
STAGES = ["stage0", "stage1", "stage2", "stage3", "stage4"]

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
        "stage0": {"memory_loaded": [], "opening_line": "", "store": ""},
        "stage1": {"confessions": [], "data_demands": [], "tool_results": []},
        "stage2": {"exchanges": [], "camps": {}, "spark": None},
        "stage3": {"sandbox": {}, "summons": []},
        "stage4": {"meta": {}, "memory": "", "memory_written": False},
        "camps": {},
        "clash_exchanges": [],
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

    state["stage0"] = {
        "memory_loaded": memories,
        "opening_line": opening,
        "store": str(path),
        "memory_count": len(memories),
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    if "stage0" not in state["stages_done"]:
        state["stages_done"].append("stage0")
    state["stage"] = "stage0_done"
    return {"stage": "stage0", "ok": True, "opening_line": opening,
            "memory_count": len(memories), "store": str(path),
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

    seen, problems, demands, results = set(), [], [], []
    for i, c in enumerate(confessions, 1):
        role = c.get("role")
        if role not in SIX_ROLES:
            problems.append(f"第 {i} 条角色 {role!r} 不在六人名单内")
            continue
        if role in seen:
            problems.append(f"角色 {role} 重复发言（六个角色各一条）")
        seen.add(role)

        text = str(c.get("text", ""))
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

    missing = [r for r in SIX_ROLES if r not in seen]
    if missing:
        problems.append(f"缺少角色发言：{', '.join(missing)}")

    if problems:
        die("阶段一校验失败：\n  - " + "\n  - ".join(problems), 3)

    state["stage1"] = {"confessions": confessions, "data_demands": demands,
                       "tool_results": results}
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

    if "stage2" not in state["stages_done"]:
        state["stages_done"].append("stage2")
    state["stage"] = "stage2_done"
    return {"stage": "stage2", "ok": True, "verdict": "sparked",
            "blue": blue, "red": red,
            "interrupts": len([e for e in cleaned if e["interrupt"]]),
            "verifications": len(verifications),
            "spark": sp}


# --------------------------------------------------------------------------- #
# 阶段三：沙盘推演
# --------------------------------------------------------------------------- #


def run_stage3(state: dict, payload: dict) -> dict:
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
    state["stage3"] = {"sandbox": state["sandbox"], "summons": summons}
    if summons:
        state.setdefault("summoned_roles", []).extend(summons)
    if "stage3" not in state["stages_done"]:
        state["stages_done"].append("stage3")
    state["stage"] = "stage3_done"
    return {"stage": "stage3", "ok": True, "plan": plan_name,
            "timeline_months": len(timeline),
            "tool_calls": len(sandbox_tools),
            "summoned": [s.get("role") for s in summons],
            "survival": surv}


# --------------------------------------------------------------------------- #
# 阶段四：元认知终局
# --------------------------------------------------------------------------- #


def run_stage4(state: dict, payload: dict) -> dict:
    if "stage3" not in state["stages_done"]:
        die("必须先完成阶段三（沙盘推演）", 3)

    meta = payload.get("meta") or payload
    problems = []
    shared = meta.get("shared_hidden_assumption") or ""
    if not shared:
        problems.append("缺少 shared_hidden_assumption（大家始终没跳出的共同隐性假设）")
    broken = meta.get("assumption_broken") or []
    if not broken:
        problems.append("缺少 assumption_broken（被沙盘证明为错的前提，至少 1 条）")
    ignored = meta.get("ignored_dimension") or ""
    if not ignored:
        problems.append("缺少 ignored_dimension（被忽略的成本维度）")
    memory = str(meta.get("memory") or "").strip()
    if not memory:
        problems.append("缺少 memory（长期记忆）")
    elif len(memory) > MEMORY_LIMIT:
        problems.append(f"长期记忆 {len(memory)} 字，超过 {MEMORY_LIMIT} 字上限")

    if problems:
        die("阶段四校验失败：\n  - " + "\n  - ".join(problems), 3)

    # V3 · 记忆沉淀：写入跨会话记忆库（可用 --no-persist 关闭，仅测试用）
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
                       "memory_written": bool(written),
                       "memory_entry": written}
    if "stage4" not in state["stages_done"]:
        state["stages_done"].append("stage4")
    state["stage"] = "stage4_done"
    return {"stage": "stage4", "ok": True, "memory_chars": len(memory),
            "shared_hidden_assumption": shared,
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
    s4 = state.get("stage4", {}).get("meta", {})
    surv = sb.get("evaluation") or {}

    action = sb.get("action_plan") or {}
    return {
        "topic": state.get("topic", ""),
        "session_id": state.get("session_id", ""),
        "stage": state.get("stage"),
        "stages_done": state.get("stages_done", []),
        "consensus": s4.get("consensus") or sb.get("consensus") or "",
        "core_divergence": s4.get("core_divergence") or sb.get("core_divergence") or "",
        "assumption_broken": s4.get("assumption_broken") or [],
        "ignored_dimension": s4.get("ignored_dimension", ""),
        "shared_hidden_assumption": s4.get("shared_hidden_assumption", ""),
        "do": action.get("do") or [],
        "dont": action.get("dont") or [],
        "need_info": action.get("need_info") or [],
        "survival_rate": surv.get("survival_rate"),
        "survival_band": surv.get("band"),
        "worst_risk": (surv.get("worst_risk") or {}).get("name", ""),
        "memory": state.get("stage4", {}).get("memory", ""),
        "memory_written": state.get("stage4", {}).get("memory_written", False),
        "memory_entry": state.get("stage4", {}).get("memory_entry"),
        "data_demands": s1.get("data_demands", []),
        "tool_results": s1.get("tool_results", []),
        "camps": s2.get("camps", {}),
        "verifications": s2.get("verifications", []),
        "summons": state.get("stage3", {}).get("summons", []),
        "sandbox_tools": sb.get("tool_calls", []),
        "spark": s2.get("spark") or {},
        "memory_loaded": state.get("stage0", {}).get("memory_loaded", []),
        "opening_line": state.get("stage0", {}).get("opening_line", ""),
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
    """V3.0 冻结报告格式（五节，与 spec 逐字对应）。

    注意 V3 相对 V2 的变化：
      * 第 1 节从「核心共识与分歧底牌」换成「本次会议引入的外部数据 / 工具结果」；
      * 共识与分歧移入报告末尾的「过程留痕」，不再占据正文五节之一。
    """
    d = collect_report_data(state)
    if not d["do"] or not d["dont"] or not d["need_info"]:
        die("行动指令三栏（Do / Don't / Need Info）必须都非空：拒绝和稀泥", 3)
    if d["survival_rate"] is None:
        die("缺少存活率评估（先执行 stage3）", 3)
    if not d["memory"]:
        die("缺少长期记忆（先执行 stage4）", 3)

    sim_count = len([t for t in d["tool_results"] if t.get("simulated")])
    real_count = len([t for t in d["tool_results"] if t.get("source") == "tool"])
    sandbox_real = len([t for t in d["sandbox_tools"]
                        if t.get("source") == "tool"])
    sandbox_sim = len([t for t in d["sandbox_tools"]
                       if t.get("simulated")])

    L = []
    L.append("### 📊 终极圆桌决策报告 V3.0")
    L.append("")
    L.append(f"> 议题：{d['topic']}　会话：`{d['session_id']}`")
    L.append(f"> 数据来源：阶段一 真实工具调用 {real_count} 条 / 模拟 {sim_count} 条；"
             f"沙盘 真实 {sandbox_real} 条 / 模拟 {sandbox_sim} 条")
    if d["opening_line"]:
        L.append(f"> {d['opening_line']}")
    L.append("")

    # ---- 1. 外部数据 / 工具结果 ----
    L.append("#### 🔗 1. 本次会议引入的外部数据 / 工具结果")
    if not d["tool_results"] and not d["sandbox_tools"]:
        L.append("- （本次未引入任何外部数据：按 V3 纪律，这样的会议不应产出决策报告）")
    for i, t in enumerate(d["tool_results"], 1):
        kind = "真实工具" if t.get("source") == "tool" else "模拟"
        calls = t.get("tool_calls") or []
        call_desc = "；".join(f"[{c['kind']}] {c['detail']}" for c in calls) or "未标注 Tool Call"
        L.append(f"- 数据 {i}（{t.get('role')}，来源：{kind}{'·' + t.get('tool', '') if t.get('tool') else ''}）："
                 f"{t.get('query', '') or '—'}")
        L.append(f"  - 调用：{call_desc}")
        L.append(f"  - 结果：{str(t.get('result', ''))[:160]}")
    for i, t in enumerate(d["sandbox_tools"], 1):
        kind = "真实" if t.get("source") == "tool" else "模拟"
        L.append(f"- 沙盘工具 {i}（{kind}{'·' + t['kind'] if t.get('kind') else ''}）："
                 f"{t.get('purpose', '')}")
        if t.get("code"):
            L.append("  ```python")
            for line in str(t["code"]).splitlines():
                L.append(f"  {line}")
            L.append("  ```")
        L.append(f"  - 运行结果：{str(t.get('result', ''))[:200]}")
    if d["verifications"]:
        L.append("")
        L.append(f"- **打断并验真 {len(d['verifications'])} 次**：")
        for v in d["verifications"]:
            L.append(f"  - {v.get('from')} 对 {v.get('target_claim') or '（未指定靶点）'} 验真 → "
                     f"{v.get('verdict')}：{str(v.get('result', ''))[:120]}")
    L.append("")

    # ---- 2. 隐性假设 ----
    L.append("#### 🧠 2. 击穿的隐性假设（元认知发现）")
    if d["shared_hidden_assumption"]:
        L.append(f"- 全程共同的隐性假设：**{d['shared_hidden_assumption']}**")
    for item in d["assumption_broken"]:
        L.append(f"- 我们一开始默认了 {item}，但外部数据证明这是错的。")
    if d["ignored_dimension"]:
        L.append(f"- 我们忽略了 {d['ignored_dimension']} 维度的成本。")
    L.append("")

    # ---- 3. 行动指令 ----
    L.append("#### 🎯 3. 行动指令 (Action Items)")
    L.append(f"- ✅ **Do（立刻执行）**：{'；'.join(d['do'])}")
    L.append(f"- ❌ **Don't（绝对禁区）**：{'；'.join(d['dont'])}")
    L.append(f"- 🔍 **Need Info（需要补充调研）**：{'；'.join(d['need_info'])}")
    L.append("")

    # ---- 4. 存活率 ----
    L.append("#### 🛡️ 4. 沙盘存活率评估")
    L.append(f"- 当前方案预估存活率：{d['survival_rate']}%")
    L.append(f"- 最致命的潜在风险点：{d['worst_risk'] or '（未登记风险，这本身就是最大风险）'}")
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
    if d["consensus"] or d["core_divergence"]:
        L.append(f"- 共识：{d['consensus'] or '（未提供）'}")
        L.append(f"- 核心分歧：{d['core_divergence'] or '（未提供）'}")
    L.append(f"- 阶段一数据诉求 {len(d['data_demands'])} 条：")
    L.extend([f"  - [{x['role']}] {x['demand']}" for x in d["data_demands"]])
    camps = d["camps"]
    L.append(f"- 红蓝分组：蓝军 {camps.get('blue', [])} ｜ 红军 {camps.get('red', [])}")
    sp = d["spark"]
    L.append(f"- 对抗火花：攻击 {sp.get('attack_count')} / 防御 {sp.get('defense_count')} / "
             f"靶点 {sp.get('target_spread')} / 空洞发言 {sp.get('hollow_count')} → "
             f"**{sp.get('verdict', 'unknown')}**")
    if d["summons"]:
        L.append(f"- 动态召唤：{', '.join(s.get('role', '') for s in d['summons'])}")
    else:
        L.append("- 动态召唤：本轮无（未出现跨领域认知盲区）")
    L.append(f"- 历史记忆加载：{len(d['memory_loaded'])} 条")

    md = "\n".join(L)
    bad = [p for p in FORBIDDEN_PHRASES if p in md]
    if bad:
        die(f"报告含禁止措辞 {bad}（禁止和稀泥 / 禁止伪造完成状态）", 3)
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

    s1 = state.get("stage1", {})
    results = s1.get("tool_results") or []
    fake = [r for r in results if r.get("source") != "tool" and not r.get("simulated")]
    if fake:
        issues.append(f"有 {len(fake)} 条数据既非真实工具返回也未标注模拟："
                      f"{[r['role'] for r in fake]}")

    sp = (state.get("stage2") or {}).get("spark") or {}
    if sp and not sp.get("sparked"):
        issues.append("红蓝对抗未打出火花（必须重开一轮）")

    sb = state.get("sandbox") or {}
    if len(sb.get("timeline") or []) < 3:
        warnings.append("沙盘时间线少于 3 个节点")
    surv = sb.get("evaluation") or {}
    if surv.get("band") == "low":
        warnings.append(f"存活率 {surv.get('survival_rate')}% 属于 low 分档："
                        "按纪律不得直接交付，应先补 Need Info 或改设计")

    action = sb.get("action_plan") or {}
    for k in ("do", "dont", "need_info"):
        if not action.get(k):
            issues.append(f"行动清单 {k} 栏为空（拒绝和稀泥）")

    memory = state.get("stage4", {}).get("memory", "")
    if memory and len(memory) > MEMORY_LIMIT:
        issues.append(f"长期记忆 {len(memory)} 字超过上限 {MEMORY_LIMIT}")

    return {
        "needs_judgment": True,
        "stages_done": done,
        "stage": state.get("stage"),
        "issues": issues,
        "warnings": warnings,
        "survival_rate": surv.get("survival_rate"),
        "survival_band": surv.get("band"),
        "sparked": sp.get("sparked"),
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
          "stage3": run_stage3, "stage4": run_stage4}[args.cmd]
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

    def stage1_payload(simulated_mix=True):
        conf = []
        for i, role in enumerate(SIX_ROLES):
            tool = ({"source": "tool", "tool": "web_search", "query": "示例查询",
                     "result": "示例返回", "obtained_at": "2026-11-01"} if i % 2 == 0
                    else {"source": "text", "simulated": True, "tool": "simulated_search",
                          "query": "示例查询", "result": "模拟返回"})
            conf.append({"role": role,
                         "text": f"我的结论依赖一项关键数据。[数据诉求: 需要示例指标{i}] "
                                 f"[Tool Call: Search] 关键词：示例指标{i}。"
                                 f"基于此数据，我的观点是：示例结论 {i}。",
                         "tool_result": tool})
        return {"confessions": conf}

    def stage2_payload():
        return {
            "camps": {"blue": ["munger", "jobs", "pg"], "red": ["musk", "feynman", "karpathy"]},
            "exchanges": [
                {"from": "munger", "target_claim": "M1-1", "interrupt": True,
                 "inner_thought": "他根本没算过失败率，我先把他按在地上",
                 "text": "[打断] 你的下界推演假设了组织愿意改变考核，这个假设没被验证",
                 "evidence": "历史案例"},
                {"from": "jobs", "target_claim": "M1-2",
                 "inner_thought": "这堆流程没人真的需要，但我先不撕破脸",
                 "text": "这套方案多出两个审批环节，砍掉之后成本降 30%", "evidence": "减法清单"},
                {"from": "pg", "target_claim": "M1-1",
                 "inner_thought": "我只有一个案例，但我必须用它顶住",
                 "text": "[打断并验真] 你说按获奖概率分配有效，我要现场查证。"
                         "[Tool Call: Search] 关键词：按获奖概率分配 失效案例。"
                         "基于此数据，我的观点是：该做法在两个团队上已失效。",
                 "evidence": "示例案例",
                 "verify": True,
                 "verify_result": {"result": "模拟检索：2 个案例显示失效", "source": "text",
                                   "simulated": True, "verdict": "supported"}},
                {"from": "musk", "target_claim": "P2-1",
                 "inner_thought": "包装成本量级太小，不值得改结论",
                 "text": "接受包装成本，但它只占 3%，不改变下界结论", "evidence": "量级估算"},
                {"from": "feynman", "target_claim": "J2-1",
                 "inner_thought": "他连「没人需要」是谁说的都答不上来",
                 "text": "「没人需要」需要一个可观测判据，否则无法检验", "evidence": "可操作化要求"},
                {"from": "karpathy", "target_claim": "G3-1",
                 "inner_thought": "指标被优化到极致就会作弊，这条没人提",
                 "text": "把获奖率当唯一指标会被包装行为反噬，需要第二指标", "evidence": "古德哈特"},
            ],
        }

    def stage3_payload():
        return {
            "sandbox": {
                "plan": "方案 A：按能力覆盖分配 + 保留一级评审",
                "runners": ["karpathy", "musk"],
                "timeline": [
                    {"month": 1, "event": "评审表上线，团队开始包装材料", "metric": "包装投入占比 12%"},
                    {"month": 3, "event": "包装成本吃掉预算", "metric": "有效产出下降 8%"},
                    {"month": 6, "event": "长期项目被挤占", "error": "两个跨年度项目停摆"},
                ],
                "risks": [
                    {"name": "包装成本失控", "severity": 0.8, "probability": 0.6},
                    {"name": "长期项目停摆", "severity": 0.9, "probability": 0.4},
                    {"name": "评审反弹", "severity": 0.3, "probability": 0.5},
                ],
                "key_assumptions": [
                    {"text": "成功标准=获奖", "evidence": ""},
                    {"text": "包装成本可控", "evidence": "示例量级估算"},
                    {"text": "团队会配合新口径", "evidence": ""},
                ],
                "attacks": [{"text": "包装成本", "defended": True},
                            {"text": "长期项目", "defended": False}],
                "action_plan": {"do": ["先在小范围试点新口径"],
                                "dont": ["不要一次性全量切换"],
                                "need_info": ["包装成本占真实比例"]},
                "consensus": "现行分配规则本身在制造额外成本",
                "core_divergence": "成功标准是否必须等于获奖（价值分歧，未解决）",
                "tool_calls": [
                    {"kind": "Code", "source": "tool",
                     "purpose": "验证包装成本占比是否会让结论反转",
                     "code": "rate = 0.12\nprint('包装成本占比', rate, '→ 结论反转' if rate > 0.15 else '→ 结论不变')",
                     "result": "包装成本占比 0.12 → 结论不变"},
                ],
            },
            "summons": [{"role": "法务专家", "reason": "评审口径变更涉及评奖规则与合规",
                         "statement": "改口径需要同步修改评奖细则，否则评奖结果可被申诉"}],
        }

    def stage4_payload():
        return {"meta": {
            "shared_hidden_assumption": "成功必须用获奖来度量",
            "assumption_broken": ["成功标准等于获奖数", "包装成本可以忽略"],
            "ignored_dimension": "组织信任与长期项目机会成本",
            "memory": "分配机制一旦以单一可包装指标为度量，就会催生为指标服务的成本；"
                      "先定义成功标准再谈资源分配，是这类议题唯一的前置动作。",
            "consensus": "现行规则在制造额外成本",
            "core_divergence": "成功标准是否必须等于获奖（价值分歧，未解决）",
        }, "persist_memory": False}

    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "state.json"
        st = new_state("【自检】终极圆桌")
        save_state(sp, st)

        # 阶段零：记忆唤醒（用临时记忆库，不污染真实仓库）
        mem = Path(td) / "mem.jsonl"
        r0 = run_stage0(st, {"store": str(mem)})
        ck(r0["ok"] and r0["memory_count"] == 0, "空记忆库时阶段零正常执行")
        ck("无记忆记录" in r0["opening_line"], "无历史时开场白明确说明")
        from memory_store import remember as _remember
        _remember(mem, "评审类流程的优化对象不是频次而是单次固定开销", tags=["评审"])
        r0b = run_stage0(st, {"store": str(mem)})
        ck(r0b["memory_count"] == 1 and "单次固定开销" in r0b["opening_line"],
           "有历史记忆时被读入开场白")
        ck(st["stages_done"].count("stage0") == 1, "重复执行阶段零不重复登记")

        # 阶段顺序强制
        try:
            run_stage2(st, stage2_payload())
            ck(False, "跳过阶段一应被拒绝")
        except SystemExit:
            ck(True, "跳过阶段一被拒绝")

        # 阶段一：缺数据诉求 / 伪装数据
        bad = stage1_payload()
        bad["confessions"][0]["text"] = "我觉得应该先做数据"
        try:
            run_stage1(st, bad)
            ck(False, "缺 [数据诉求] 应被拒绝")
        except SystemExit:
            ck(True, "缺少 [数据诉求] 被拒绝")

        fake = stage1_payload()
        fake["confessions"][1]["tool_result"] = {"source": "text", "result": "看起来很真"}
        try:
            run_stage1(st, fake)
            ck(False, "伪装数据应被拒绝")
        except SystemExit:
            ck(True, "把模拟数据伪装成真实数据被拒绝")

        r1 = run_stage1(st, stage1_payload())
        ck(r1["ok"] and r1["roles"] == 6, "阶段一接受六人完整发言")
        ck(r1["data_demands"] == 6, "六条数据诉求全部被提取")
        ck(r1["real_tool_calls"] == 3 and r1["simulated"] == 3, "真实调用与模拟数据被分别计数")

        # 阶段二：缺内心戏
        no_it = stage2_payload()
        no_it["exchanges"][0].pop("inner_thought")
        try:
            run_stage2(st, no_it)
            ck(False, "缺 Inner Thought 应被拒绝")
        except SystemExit:
            ck(True, "缺少内心戏被拒绝")

        # 阶段二：分营人数不对
        bad_camp = stage2_payload()
        bad_camp["camps"] = {"blue": ["munger", "jobs"], "red": ["musk", "feynman", "karpathy", "pg"]}
        try:
            run_stage2(st, bad_camp)
            ck(False, "红蓝各 3 人应被强制")
        except SystemExit:
            ck(True, "红蓝人数不为 3v3 被拒绝")

        # 阶段二：空洞发言 → 无火花 → 退出码 4
        hollow = {"camps": {"blue": ["munger", "jobs", "pg"],
                            "red": ["musk", "feynman", "karpathy"]},
                  "exchanges": [{"from": r, "inner_thought": "随便吧",
                                 "text": "我觉得挺好的"} for r in SIX_ROLES]}
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                run_stage2(st, hollow)
            ck(False, "空洞发言应触发重开")
        except SystemExit as exc:
            ck(exc.code == 4, "空洞发言触发退出码 4（强制重开）")
            ck("reopen_required" in buf.getvalue(), "输出包含 reopen_required")

        r2 = run_stage2(st, stage2_payload())
        ck(r2["ok"] and r2["verdict"] == "sparked", "有交锋的对抗被判为打出火花")
        ck(r2["interrupts"] == 1, "打断被识别并计数")
        ck(len(r2["blue"]) == 3 and len(r2["red"]) == 3, "红蓝各 3 人")

        # 阶段三：时间线不足 / 缺主推
        bad_sb = stage3_payload()
        bad_sb["sandbox"]["timeline"] = bad_sb["sandbox"]["timeline"][:1]
        try:
            run_stage3(st, bad_sb)
            ck(False, "沙盘节点不足应被拒绝")
        except SystemExit:
            ck(True, "沙盘时间线少于 3 个节点被拒绝")

        bad_run = stage3_payload()
        bad_run["sandbox"]["runners"] = ["feynman"]
        try:
            run_stage3(st, bad_run)
            ck(False, "主推角色不符应被拒绝")
        except SystemExit:
            ck(True, "沙盘主推必须含 karpathy 与马斯克")

        r3 = run_stage3(st, stage3_payload())
        ck(r3["ok"] and r3["timeline_months"] == 3, "沙盘三节点通过")
        ck(r3["summoned"] == ["法务专家"], "动态召唤被记录")
        ck(r3["tool_calls"] == 1, "沙盘工具调用被记录")
        ck(0 <= r3["survival"]["survival_rate"] <= 100, "存活率在 0-100 区间")

        # V3：沙盘没有工具调用必须被拒绝
        no_tool = stage3_payload()
        no_tool["sandbox"].pop("tool_calls")
        try:
            run_stage3(st, no_tool)
            ck(False, "沙盘缺工具调用应被拒绝")
        except SystemExit:
            ck(True, "沙盘缺 tool_calls 被拒绝（V3 现实沙盘要求）")

        # V3：[打断并验真] 只打断不查证必须被拒绝
        no_verify = stage2_payload()
        no_verify["exchanges"][2].pop("verify_result")
        no_verify["exchanges"][2]["text"] = "[打断并验真] 你说按获奖概率分配有效。"
        try:
            run_stage2(st, no_verify)
            ck(False, "验真无结果应被拒绝")
        except SystemExit:
            ck(True, "[打断并验真] 没有验真结果被拒绝")

        # 阶段四：记忆超长
        long_mem = stage4_payload()
        long_mem["meta"]["memory"] = "记" * 260
        try:
            run_stage4(st, long_mem)
            ck(False, "长期记忆超 200 字应被拒绝")
        except SystemExit:
            ck(True, "长期记忆超过 200 字被拒绝")

        r4 = run_stage4(st, stage4_payload())
        ck(r4["ok"] and r4["memory_chars"] <= MEMORY_LIMIT, "长期记忆在 200 字内")
        ck(r4["memory_written"] is False, "persist_memory=false 时不写入记忆库")

        # V3：persist_memory=true 时必须真的写进记忆库
        st2 = json.loads(json.dumps(st))
        st2["stage4"] = {}
        mem2 = Path(td) / "mem2.jsonl"
        p4 = stage4_payload()
        p4["persist_memory"] = True
        p4["store"] = str(mem2)
        r4b = run_stage4(st2, p4)
        ck(r4b["memory_written"] is True and mem2.exists(), "persist_memory=true 时写入记忆库")
        ck(len(mem2.read_text(encoding="utf-8").splitlines()) == 1, "记忆库中恰好一条新记忆")

        # 报告（V3 五节）
        md = render_report(st)
        for sec in ["### 📊 终极圆桌决策报告 V3.0",
                    "#### 🔗 1. 本次会议引入的外部数据 / 工具结果",
                    "#### 🧠 2. 击穿的隐性假设（元认知发现）",
                    "#### 🎯 3. 行动指令 (Action Items)",
                    "#### 🛡️ 4. 沙盘存活率评估",
                    "#### 🧠 5. 长期记忆写入"]:
            ck(sec in md, f"报告含 V3 章节 {sec}")
        ck("✅ **Do（立刻执行）**" in md and "❌ **Don't（绝对禁区）**" in md
           and "🔍 **Need Info（需要补充调研）**" in md, "三栏行动指令齐备")
        ck("[MEMORY_UPDATE]" in md, "包含 MEMORY_UPDATE")
        ck(f"{st['sandbox']['evaluation']['survival_rate']}%" in md, "存活率写入报告")
        ck(not any(p in md for p in FORBIDDEN_PHRASES), "报告不含禁止措辞")

        # 报告缺内容必须拒绝
        broken = json.loads(json.dumps(st))
        broken["sandbox"]["action_plan"]["dont"] = []
        try:
            render_report(broken)
            ck(False, "行动栏为空应拒绝出报告")
        except SystemExit:
            ck(True, "行动指令有空栏时拒绝出报告（拒绝和稀泥）")

        # check
        c = check(st)
        ck(c["ready_to_report"] is True and c["verdict"] == "ready", "完整状态判定为可交付")
        ck(c["stages_done"] == STAGES, "五个阶段全部记录")

        half = new_state("半成品")
        c2 = check(half)
        ck(c2["ready_to_report"] is False and len(c2["issues"]) >= 4, "半成品被判定为不可交付")

        # 端到端 CLI（含 --write 落盘）
        cli_state = Path(td) / "cli.json"
        save_state(cli_state, new_state("CLI 自检"))
        for name, payload in (("stage0", {"store": str(Path(td) / "cli-mem.jsonl")}),
                              ("stage1", stage1_payload()), ("stage2", stage2_payload()),
                              ("stage3", stage3_payload()), ("stage4", stage4_payload())):
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
        ck(out_md.exists() and "终极圆桌决策报告" in out_md.read_text(encoding="utf-8"),
           "CLI report 生成报告文件")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="终极圆桌编排引擎（四阶段）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init")
    pi.add_argument("--topic", required=True)
    pi.add_argument("--out")
    pi.add_argument("--mode", default="rigorous", choices=["rigorous", "simulation"])

    for name in STAGES:
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
    if args.cmd in STAGES:
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""轮次控制器 round_controller.py

职责：根据当前讨论状态，决定"下一轮怎么走"——但只决定**目标与覆盖缺口**，
不决定"谁必须和谁说话"。硬性配对（第一轮必须一对一、第三轮必须联动≥2 人）
已被明确废弃，见 docs/output-contract.md §2。

本脚本输出的是 advisory（建议性）计划：
  * 轮次、阶段、交互模式、本轮目标（来自契约的固定表）；
  * 必须回应的元认知条目（来自 injections，这一项才是强制的）；
  * 覆盖缺口：哪些论断从未被任何人检验、哪些质疑悬空未答；
  * needs_judgment 标记：涉及语义判断的部分一律交回模型。

用法：
  python round_controller.py plan --state S [--write]
  python round_controller.py coverage --state S
  python round_controller.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

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


def log(msg: str) -> None:
    print(f"[round_controller] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[round_controller] ERROR: {msg}", file=sys.stderr)
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


def coverage(state: dict) -> dict:
    """结构化的覆盖度统计：只数"有没有被检验"，不判断"检验得好不好"。"""
    roles = state.get("roles", [])
    claims = state.get("claims", [])
    challenges = state.get("open_challenges", [])

    per_role = {}
    for r in roles:
        mine = [c for c in claims if c.get("role") == r]
        untested = [c["id"] for c in mine if not c.get("responses_received")]
        challenged = [c["id"] for c in mine
                      if any(x.get("type") == "challenge" for x in c.get("responses_received", []))]
        per_role[r] = {
            "claims": len(mine),
            "untested_claims": untested,
            "challenged_claims": challenged,
            "open_challenges_raised": len([c for c in challenges if c.get("from") == r and c.get("status") == "open"]),
            "open_challenges_against": len([c for c in challenges if c.get("to") == r and c.get("status") == "open"]),
        }

    # 单点依赖：所有论断都指向同一个角色的情况（说明讨论被一个人带节奏）
    target_counts = {}
    for c in claims:
        for resp in c.get("responses_received", []):
            target_counts[c.get("role")] = target_counts.get(c.get("role"), 0) + 1

    injections = [i for i in state.get("injections", [])]
    pending = []
    for inj in injections:
        if not inj.get("applied"):
            pending.extend(inj.get("must_respond", []))

    return {
        "needs_judgment": True,
        "round": state.get("round", 0),
        "per_role": per_role,
        "untested_total": sum(len(v["untested_claims"]) for v in per_role.values()),
        "open_challenges_total": len([c for c in challenges if c.get("status") == "open"]),
        "response_attention": target_counts,
        "pending_must_respond": sorted(set(pending)),
        "note": "covered/untested 只是结构计数；某条论断被回应不等于被有效反驳，需模型判断",
    }


def plan(state: dict) -> dict:
    cur = int(state.get("round", 0))
    max_rounds = int(state.get("max_rounds", 3))
    nxt = cur + 1

    if state.get("phase") == "closed" or nxt > max_rounds:
        return {
            "action": "close",
            "round": cur,
            "reason": f"已完成 {cur}/{max_rounds} 轮" if nxt > max_rounds else "讨论已关闭",
            "handoff_command": "python state_manager.py summary --state <state> --json",
        }

    phase, mode = ROUND_PHASE.get(nxt, ("synthesis", "cross_exam"))
    goals = list(ROUND_GOALS.get(nxt, ROUND_GOALS["default"]))

    must_respond, forbidden, notes = [], [], []
    for inj in state.get("injections", []):
        if int(inj.get("round", -1)) == nxt and not inj.get("applied"):
            must_respond.extend(inj.get("must_respond", []))
            forbidden.extend(inj.get("forbidden", []))
            if inj.get("note"):
                notes.append(inj["note"])

    cov = coverage(state)
    # advisory：优先检验"从未被检验的论断"和"悬空质疑"，但这是建议不是强制配对
    advisory = {
        "prioritize_untested_claims": [
            cid for r in state.get("roles", []) for cid in cov["per_role"][r]["untested_claims"]
        ][:8],
        "unanswered_challenges": [c["id"] for c in state.get("open_challenges", [])
                                  if c.get("status") == "open"][:8],
        "note": "建议优先处理清单；角色可自主选择追问 1 人或多人，不得据此强制配对",
    }

    blocked = []
    if nxt >= 2 and not state.get("meta", {}).get("reviews"):
        blocked.append("第 2 轮之前缺少元认知报告：必须先生成 META REVIEW，否则隐性假设无处注入")

    activation = {
        "mode": mode,
        "parallel_batch": state.get("roles", []) if mode == "parallel_isolated" else [],
        "note": ("全部角色同时独立发言，互相不可见；这是唯一保留的形式约束，用于防锚定"
                 if mode == "parallel_isolated"
                 else "自由交叉：谁追问谁由角色自行判断，编排层不做配对"),
    }

    return {
        "needs_judgment": False,
        "action": "run_round",
        "round": nxt,
        "phase": phase,
        "interaction_mode": mode,
        "goals": goals,
        "must_respond": sorted(set(must_respond)),
        "forbidden": forbidden,
        "may_revise": nxt >= 2,
        "activation": activation,
        "advisory": advisory,
        "blocked_prerequisites": blocked,
        "notes": " | ".join(notes),
        "round_command": f"python state_manager.py begin-round --state <state> --round {nxt}",
    }


def cmd_plan(args) -> int:
    st = load_state(args.state)
    p = plan(st)
    if args.write and p.get("action") == "run_round":
        st["next_round"] = {
            "round": p["round"],
            "interaction_mode": p["interaction_mode"],
            "goals": p["goals"],
            "must_respond": p["must_respond"],
            "may_revise": p["may_revise"],
            "notes": p["notes"],
        }
        save_state(args.state, st)
        log(f"已写入 next_round: 第 {p['round']} 轮")
    emit(p)
    return 0


def cmd_coverage(args) -> int:
    emit(coverage(load_state(args.state)))
    return 0


def selftest() -> int:
    ok = True

    def check(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    st = {
        "round": 0, "max_rounds": 3, "phase": "prepare",
        "roles": ["musk", "pg"], "claims": [], "open_challenges": [],
        "injections": [], "meta": {"reviews": []}, "next_round": {},
    }
    p = plan(st)
    check(p["round"] == 1 and p["interaction_mode"] == "parallel_isolated", "第 1 轮计划为隔离轮")
    check(p["activation"]["parallel_batch"] == ["musk", "pg"], "隔离轮给出并行批次")

    st["round"] = 1
    p = plan(st)
    check(p["round"] == 2 and p["interaction_mode"] == "cross_exam", "第 2 轮计划为交叉轮")
    check(any("缺少元认知报告" in b for b in p["blocked_prerequisites"]), "缺元认知报告时给出前置阻塞提示")
    check(p["activation"]["parallel_batch"] == [], "交叉轮不锁配对")
    check(not any("必须" in g and "联动" in g for g in p["goals"]), "目标里没有硬性形式约束")

    st["meta"]["reviews"] = [{"round": 1}]
    st["injections"] = [{"round": 2, "must_respond": ["H1"], "forbidden": ["继续争论X"], "applied": False}]
    p = plan(st)
    check(p["must_respond"] == ["H1"], "注入的隐性假设成为强制回应项")
    check(p["must_respond"] and p["activation"]["mode"] == "cross_exam", "强制项与自由交叉并存")

    st["claims"] = [
        {"id": "M1-1", "role": "musk", "responses_received": []},
        {"id": "P1-1", "role": "pg", "responses_received": [{"from": "musk", "type": "challenge"}]},
    ]
    st["open_challenges"] = [{"id": "C1", "from": "musk", "to": "pg", "status": "open"}]
    cov = coverage(st)
    check(cov["per_role"]["musk"]["untested_claims"] == ["M1-1"], "未检验论断被识别")
    check(cov["per_role"]["pg"]["challenged_claims"] == ["P1-1"], "被质疑论断被识别")
    check(cov["open_challenges_total"] == 1, "悬空质疑计数正确")
    p = plan(st)
    check("M1-1" in p["advisory"]["prioritize_untested_claims"], "建议清单包含未检验论断")
    check("配对" in p["advisory"]["note"], "建议清单明确声明不强制配对")

    st["round"] = 3
    p = plan(st)
    check(p["action"] == "close" and "handoff_command" in p, "超过最大轮数时建议关闭并给出交接命令")

    st["round"] = 2
    st["phase"] = "closed"
    check(plan(st)["action"] == "close", "已关闭状态不再开新轮")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="圆桌轮次控制器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("plan", help="规划下一轮")
    pp.add_argument("--state", required=True)
    pp.add_argument("--write", action="store_true")
    pc = sub.add_parser("coverage", help="覆盖度统计")
    pc.add_argument("--state", required=True)
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "plan":
        return cmd_plan(args)
    if args.cmd == "coverage":
        return cmd_coverage(args)
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

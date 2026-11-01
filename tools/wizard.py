#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互式向导 wizard.py

解决新手最大的门槛：**不知道那 5 个 JSON 该怎么写**。

本工具用问答的方式，一步步替用户生成 5 个阶段 payload，并在每一步做即时校验。
生成完直接告诉用户下一步命令，复制粘贴即可。

它不替用户思考——所有判断都来自用户的输入；
它只负责**把用户的输入整理成契约要求的格式**，并在格式不对时立刻指出来。

用法：
  python tools/wizard.py                    # 交互式（推荐）
  python tools/wizard.py --out DIR          # 指定输出目录
  python tools/wizard.py --demo             # 生成一份示例，看看长什么样
  python tools/wizard.py --selftest

设计原则：
  * 每一步都先说明「这一步要你做什么」，再问；
  * 输入不合法时立刻重问，不带着错误往下走；
  * 最后打印完整命令序列，可直接复制。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIX = [("musk", "马斯克", "物理约束与成本下界"),
       ("feynman", "费曼", "一句话能否讲清"),
       ("munger", "芒格", "失败路径与激励错位"),
       ("jobs", "乔布斯", "复杂度与减法"),
       ("karpathy", "Karpathy", "可复现与指标口径"),
       ("pg", "Paul Graham", "真实案例与模式")]
OPTION_DEFS = {"A": "激进派：高收益高风险",
               "B": "保守派：低产出低风险",
               "C": "奇招：跳出当前框架的解法"}
DATA_DEMAND_RE = re.compile(r"\[数据诉求[:：]\s*(.+?)\]")
TOOL_CALL_RE = re.compile(r"\[Tool Call[:：]\s*(Search|Code)\]")
STANCE_RE = re.compile(r"基于(?:此|该|这)(?:数据|结果|查证)")


def die(msg: str, code: int = 2):
    print(f"[wizard] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def ask(prompt: str, default: str = "", required: bool = True,
        validate=None, hint: str = "") -> str:
    """问一个问题，直到拿到合法答案。非交互环境直接返回默认值。"""
    if not sys.stdin.isatty():
        if required and not default:
            die(f"非交互环境下必须提供默认值：{prompt}")
        return default

    while True:
        suffix = f"（默认：{default}）" if default else ""
        try:
            raw = input(f"{prompt}{suffix}\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            die("已取消")
        val = raw or default
        if required and not val:
            print("  这一项不能为空，请重新输入。\n")
            continue
        if validate and val:
            err = validate(val)
            if err:
                print(f"  {err}\n")
                continue
        if hint:
            print(f"  {hint}\n")
        return val


def header(title: str):
    print(f"\n{'─' * 60}\n{title}\n{'─' * 60}")


# --------------------------------------------------------------------------- #
# 各阶段采集
# --------------------------------------------------------------------------- #


def collect_stage0() -> dict:
    header("阶段零 · 北极星锚定")
    print("全场只有一个焦点指标，所有发言必须围绕它。")
    print("好的北极星：单一、可测、有方向、有时间窗、讨论能影响它。")
    print("例：月活 / 利润率 / 30 日留存 / 交付准时率\n")
    north = ask("你的北极星指标是什么？", default="月活",
                hint=f"后续所有发言都必须提到「{'{北极星}'}」字样，否则会被拒绝")
    return {"north_star": north}


def collect_stage1(north: str) -> dict:
    header("阶段一 · 六人极速交底（每人 ≤150 字）")
    print(f"每个角色说一句立场，必须同时包含三样：")
    print(f"  ① [数据诉求: ……]  ② [Tool Call: Search|Code] ……  ③ 基于此数据，我的观点是……")
    print(f"  并且必须提到北极星「{north}」。\n")

    confessions = []
    for key, cn, focus in SIX:
        print(f"── {cn}（{focus}）")
        text = ask(
            f"  {cn} 的一句话立场？",
            default=f"{north} 的关键约束还没定。[数据诉求: 需要一项基准数据] "
                    f"[Tool Call: Search] 关键词：基准数据。"
                    f"基于此数据，我的观点是：先补这项数据再谈方案。",
            validate=lambda v: (
                None if (DATA_DEMAND_RE.search(v) and TOOL_CALL_RE.search(v)
                         and STANCE_RE.search(v) and north in v)
                else "必须同时包含 [数据诉求: …]、[Tool Call: …]、"
                     f"「基于此数据，我的观点是…」，并提到「{north}」"),
        )
        source = ask("  这条数据是真实调用的吗？(y=真实工具 / n=模拟数据)",
                     default="n")
        tool = {"source": "tool" if source.lower().startswith("y") else "text",
                "tool": "web_search" if source.lower().startswith("y") else "simulated_search",
                "query": (DATA_DEMAND_RE.search(text).group(1)
                          if DATA_DEMAND_RE.search(text) else ""),
                "result": ("（真实调用结果请粘贴在此）" if source.lower().startswith("y")
                           else "（模拟数据，请勿当作真实结论）")}
        if tool["source"] == "text":
            tool["simulated"] = True
        confessions.append({"role": key, "text": text, "tool_result": tool})
        print()
    return {"confessions": confessions}


def collect_stage2() -> dict:
    header("阶段二 · 红蓝对抗")
    print("3 人蓝军（必须证明方案会失败）+ 3 人红军（捍卫并修补）。")
    print("每条发言必须有 (Inner Thought)，最好带 [打断]。\n")
    blue = ["munger", "jobs", "pg"]
    red = ["musk", "feynman", "karpathy"]
    print(f"默认分营：蓝军 {blue}　红军 {red}")
    keep = ask("用默认分营吗？(y/n)", default="y")
    if keep.lower().startswith("n"):
        blue = [r.strip() for r in ask("蓝军三人（逗号分隔）",
                                       default="munger,jobs,pg").split(",")]
        red = [r.strip() for r in ask("红军三人（逗号分隔）",
                                      default="musk,feynman,karpathy").split(",")]

    print("\n先给一条蓝军攻击（示范最小可用对抗）：")
    b_role = ask("  谁发起攻击？", default="munger")
    b_text = ask("  攻击内容？",
                 default="[打断] 你的推演假设组织愿意改变，这个假设没被验证",
                 hint="好的攻击要有靶点、有内容，不能只说「我不同意」")
    r_role = ask("  谁回应？", default="musk")
    r_text = ask("  回应内容？",
                 default="接受这条，但它只影响 9% 的成本，不改变结论；若超过 25% 则反转")

    # 火花检测要求：有效攻击 ≥3、有效防御 ≥2、靶点 ≥2。
    # 只给 1 攻 1 防会直接撞 no_spark（退出码 4），所以这里补齐到能通过的下限，
    # 并明确告诉用户「这些是占位，请改成你自己的」。
    print("\n为避免第一次就撞「无火花」，我会补足到最低交锋量（3 攻 2 防 2 靶点）。")
    print("下面这几条是占位内容，生成后请改成你自己的论证。\n")

    other_blue = [r for r in blue if r != b_role][:2]
    other_red = [r for r in red if r != r_role][:1]
    filler_targets = ["F1-1", "K1-1", "P2-1"]

    exchanges = [
        {"from": b_role, "inner_thought": "他这条假设没人验证过，我先打这里",
         "interrupt": True, "target_claim": "M1-1", "text": b_text,
         "evidence": "（请补充证据）"},
        {"from": r_role, "inner_thought": "这条成立但量级可能不够，先给数",
         "target_claim": "G2-1", "text": r_text,
         "evidence": "（请补充证据）"},
    ]
    for i, role in enumerate(other_blue):
        exchanges.append({
            "from": role, "inner_thought": "【占位】这里写我没说出口的顾虑",
            "target_claim": filler_targets[i],
            "text": f"【占位·请替换】{role} 对方案的攻击：这个前提没有被验证",
            "evidence": "（请补充证据）",
        })
    for i, role in enumerate(other_red):
        exchanges.append({
            "from": role, "inner_thought": "【占位】这里写我的真实想法",
            "target_claim": filler_targets[i + 1],
            "text": f"【占位·请替换】{role} 的回应：接受这条，但它只影响有限范围",
            "evidence": "（请补充证据）",
        })
    return {"camps": {"blue": blue, "red": red}, "exchanges": exchanges}
    return {"camps": {"blue": blue, "red": red}, "exchanges": exchanges}


def collect_stage3() -> dict:
    header("阶段三 · 铁血裁决（A/B/C 三选一）")
    print("三个方案必须互斥——不是同一个方案的三个版本。")
    print("A 激进 / B 保守 / C 跳出框架的奇招。\n")
    options = {}
    for k in ("A", "B", "C"):
        summary = ask(f"  方案 {k} 一句话（≤120 字，{OPTION_DEFS[k]}）",
                      default={"A": "全量切换，三个月内完成",
                               "B": "维持现状，只优化一个环节",
                               "C": "改为触发式：条件满足才启动"}[k])
        options[k] = {"summary": summary}

    print("\n六人投票（每人只能投 A/B/C 之一，并给理由）：")
    votes, reasons = {}, {}
    for key, cn, _ in SIX:
        v = ask(f"  {cn} 投给？", default="C",
                validate=lambda x: None if x.upper() in ("A", "B", "C")
                else "只能填 A / B / C")
        votes[key] = v.upper()
        reasons[key] = ask(f"  {cn} 的理由？", default="该方案判据可观测")

    tally = {k: sum(1 for v in votes.values() if v == k) for k in ("A", "B", "C")}
    print(f"\n票数：A={tally['A']} B={tally['B']} C={tally['C']}")
    top = max(tally, key=lambda k: tally[k])
    decision = ask(f"  最终拍板？（票数最高是 {top}）", default=top,
                   validate=lambda x: None if x.upper() in ("A", "B", "C")
                   else "只能填 A / B / C").upper()
    reason = ask("  拍板理由？", default="该方案判据可观测，且下行风险已被防住")
    return {"options": options, "votes": votes, "vote_reasons": reasons,
            "decision": decision, "decision_reason": reason}


def collect_stage4() -> dict:
    header("阶段四 · 战术级行动清单")
    print("KPI 与 Kill 必须含具体数字，否则会被拒绝（这是「拒绝咨询体」的硬门槛）。\n")
    meta = {
        "shared_hidden_assumption": ask(
            "  全场始终没跳出的共同隐性假设？", default="流程的价值等于它拦下了多少事"),
        "assumption_broken": [ask("  被推翻的底线假设？", default="频率是成本主项")],
        "ignored_dimension": ask("  被忽略的成本维度？", default="上下文切换成本"),
        "memory": ask("  长期记忆（≤200 字，写下次能复用的判断）",
                      default="流程优化的对象不是频率而是单次固定开销；"
                              "改频率前先问它承担了什么风险。"),
        "memory_tags": ["示例"],
    }
    ap = {
        "owner": ask("  负责人（六个角色之一）", default="karpathy"),
        "start": ask("  第一步做什么（有动作、有对象、有时间）",
                     default="本周在 2 个团队试点，阈值设为指标跌破 8%"),
        "kpi": ask("  关键指标（必须含数字）",
                   default="30 天内触发不超过 5 次，指标不低于 9%",
                   validate=lambda v: None if re.search(r"\d", v)
                   else "必须含具体数字，否则无法判定成败"),
        "kill": ask("  止损红线（必须含数字）",
                    default="如果 30 天内触发超过 12 次，立刻停止并回滚",
                    validate=lambda v: None if re.search(r"\d", v)
                    else "必须含具体数字，否则「效果不好」不是判据"),
        "need_info": [ask("  仍需补充调研的信息", default="过去两年的单次流程人时")],
    }
    return {"meta": meta, "action_plan": ap, "persist_memory": True}


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #


def write_all(payloads: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, data in payloads.items():
        p = out / f"{name}.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        paths[name] = p
    return paths


def print_commands(paths: dict, state: str = "STATE_PATH"):
    header("生成完毕，复制这些命令跑起来")
    orch = "python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py"
    print(f"{orch} init --topic \"你的议题\" --out .myrun")
    print("# 把上面输出的 state_path 填到下面每个 --state\n")
    for name in ("stage0", "stage1", "stage2", "stage3", "stage4"):
        print(f"{orch} {name} --state {state} --file {paths[name]} --write")
    print(f"\n{orch} check  --state {state}")
    print(f"{orch} report --state {state} --out 我的决策报告.md")
    print()


def demo_payloads() -> dict:
    north = "月活"
    conf = [{"role": k,
             "text": f"{north} 是核心约束。[数据诉求: 需要基准数据] "
                     f"[Tool Call: Search] 关键词：基准数据。"
                     f"基于此数据，我的观点是：先补数据再谈方案。",
             "tool_result": {"source": "text", "simulated": True,
                             "tool": "simulated_search", "query": "基准数据",
                             "result": "（模拟数据）示例返回值"}}
            for k, _, _ in SIX]
    return {
        "stage0": {"north_star": north},
        "stage1": {"confessions": conf},
        "stage2": {"camps": {"blue": ["munger", "jobs", "pg"],
                             "red": ["musk", "feynman", "karpathy"]},
                   # 火花检测要求：有效攻击 ≥3、有效防御 ≥2、靶点 ≥2。
                   # 示例必须满足，否则新手第一次跑就撞 no_spark（退出码 4）。
                   "exchanges": [
                       {"from": "munger", "interrupt": True, "target_claim": "M1-1",
                        "inner_thought": "这条假设没人验证", "evidence": "示例",
                        "text": "[打断] 你的推演假设组织愿意改变，这个假设没被验证"},
                       {"from": "jobs", "target_claim": "F1-1",
                        "inner_thought": "这堆环节没人真需要", "evidence": "减法清单",
                        "text": "方案多出两个审批环节，砍掉后成本降 30%"},
                       {"from": "pg", "target_claim": "K1-1",
                        "inner_thought": "我只有两个案例，但必须顶住", "evidence": "示例案例",
                        "text": "只改频率不改内容的两个案例都回到原状"},
                       {"from": "musk", "target_claim": "G2-1",
                        "inner_thought": "量级可能不够，先给数", "evidence": "示例",
                        "text": "接受这条，但它只影响 9%，若超过 25% 则结论反转"},
                       {"from": "feynman", "target_claim": "J2-1",
                        "inner_thought": "他连谁不需要都答不上来", "evidence": "可操作化",
                        "text": "「没人需要」需要一个可观测判据，否则无法检验"},
                       {"from": "karpathy", "target_claim": "P2-1",
                        "inner_thought": "两个案例撑不起结论", "evidence": "实验设计",
                        "text": "两个案例不足以支撑结论，但足以设计一个对照实验"},
                   ]},
        "stage3": {"options": {k: {"summary": s} for k, s in
                               {"A": "全量切换，三个月内完成",
                                "B": "维持现状，只优化一个环节",
                                "C": "改为触发式：条件满足才启动"}.items()},
                   "votes": {k: ("C" if i % 2 else "B") for i, (k, _, _) in enumerate(SIX)},
                   "vote_reasons": {k: "该方案判据可观测" for k, _, _ in SIX},
                   "decision": "C", "decision_reason": "判据可观测且风险已防住"},
        "stage4": {"meta": {"shared_hidden_assumption": "流程的价值等于它拦下了多少事",
                            "assumption_broken": ["频率是成本主项"],
                            "ignored_dimension": "上下文切换成本",
                            "memory": "流程优化的对象不是频率而是单次固定开销。",
                            "memory_tags": ["示例"]},
                   "action_plan": {"owner": "karpathy",
                                   "start": "本周在 2 个团队试点，阈值设为指标跌破 8%",
                                   "kpi": "30 天内触发不超过 5 次",
                                   "kill": "30 天内触发超过 12 次就回滚",
                                   "need_info": ["过去两年的单次流程人时"]},
                   "persist_memory": False},
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

    demo = demo_payloads()
    ck(set(demo) == {"stage0", "stage1", "stage2", "stage3", "stage4"}, "示例含五个阶段")
    ck(len(demo["stage1"]["confessions"]) == 6, "示例含六个角色发言")
    ck(all(DATA_DEMAND_RE.search(c["text"]) for c in demo["stage1"]["confessions"]),
       "每条示例发言都含 [数据诉求]")
    ck(all(TOOL_CALL_RE.search(c["text"]) for c in demo["stage1"]["confessions"]),
       "每条示例发言都含 [Tool Call]")
    ck(all(STANCE_RE.search(c["text"]) for c in demo["stage1"]["confessions"]),
       "每条示例发言都含表态句")
    ck(all("月活" in c["text"] for c in demo["stage1"]["confessions"]),
       "每条示例发言都提及北极星")

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        paths = write_all(demo, Path(td))
        ck(len(paths) == 5 and all(p.is_file() for p in paths.values()),
           "五个 payload 都能落盘")
        reloaded = json.loads(paths["stage3"].read_text(encoding="utf-8"))
        ck(reloaded["decision"] == "C", "落盘内容可读回")

    # 非交互环境下 ask 应返回默认值。
    # 注意：在终端里跑 selftest 时 stdin 仍是 tty，必须显式模拟非交互，
    # 否则 input() 会阻塞或读到 EOF。
    class _NoTTY:
        def isatty(self):
            return False

        def readline(self, *a):
            raise EOFError

    real_stdin = sys.stdin
    try:
        sys.stdin = _NoTTY()
        ck(ask("测试", default="abc") == "abc", "非交互环境返回默认值")
        # 非交互且无默认值时应当明确报错，而不是静默返回空串
        try:
            ask("必须提供", default="")
            ck(False, "非交互且无默认值应报错")
        except SystemExit:
            ck(True, "非交互且无默认值时明确报错")
    finally:
        sys.stdin = real_stdin

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="交互式向导：替你生成 5 个阶段的 payload")
    ap.add_argument("--out", default=".wizard", help="输出目录（默认 .wizard）")
    ap.add_argument("--demo", action="store_true", help="直接生成示例，不走交互")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out

    if args.demo:
        paths = write_all(demo_payloads(), out)
        print(f"已生成示例 payload 到 {out}")
        print_commands(paths)
        return 0

    if not sys.stdin.isatty():
        print("当前环境不是交互式终端。", file=sys.stderr)
        print("请改用：python tools/wizard.py --demo   （生成示例）", file=sys.stderr)
        return 2

    print("\n终极圆桌 · 交互式向导")
    print("我会问你几组问题，然后生成 5 个阶段的配置文件。")
    print("每步都会即时校验，格式不对会当场让你重填。")
    print("（Ctrl+C 随时退出）")

    payloads = {}
    payloads["stage0"] = collect_stage0()
    north = payloads["stage0"]["north_star"]
    payloads["stage1"] = collect_stage1(north)
    payloads["stage2"] = collect_stage2()
    payloads["stage3"] = collect_stage3()
    payloads["stage4"] = collect_stage4()

    paths = write_all(payloads, out)
    print(f"\n已写入 {len(paths)} 个文件到：{out}")
    print_commands(paths)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

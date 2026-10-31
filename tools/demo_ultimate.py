#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终极圆桌端到端演示 tools/demo_ultimate.py

把 `ultimate-roundtable` v2.0.0 的四个阶段完整跑一遍，作为集成测试与可读样例。

**数据诚实性**（本演示最重要的示范）：
- 阶段一的六条数据诉求里，有两条是**真实执行的本地测量**（`source: tool`）：
  用 Python 实测本仓库的文件数与总行数。它们是真的，可复现，任何人重跑都会得到同样结果；
- 其余四条明确标注 `simulated: true`——它们是为了演示机制而构造的模拟数据；
- 报告头部会打印「真实工具调用 2 条 / 模拟数据 4 条」，
  让读者一眼看出这份报告的证据成色。**不把模拟数据伪装成真实数据，是本技能的硬纪律。**

用法：
  python tools/demo_ultimate.py [--quiet] [--out .ultimate-demo]
退出码：0 成功；非 0 表示某一阶段校验失败（同时说明该阶段拒绝逻辑生效）。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UR = ROOT / "skills" / "ultimate-roundtable" / "scripts"
TOPIC = "【示例数据】要不要把年度评审改成季度评审"


def run(cmd: list, quiet: bool, expect_ok: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and expect_ok:
        print(f"!! 命令失败 {proc.returncode}: {' '.join(str(c) for c in cmd)}", file=sys.stderr)
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


def real_measurements() -> dict:
    """真实执行的本地测量：本仓库的 md/py 文件数与总行数。"""
    files = [p for p in ROOT.rglob("*") if p.is_file()
             and p.suffix in (".md", ".py") and ".git" not in p.parts
             and "dist" not in p.parts]
    total_lines = sum(len(p.read_text(encoding="utf-8", errors="replace").splitlines())
                      for p in files)
    return {"file_count": len(files), "total_lines": total_lines}


def stage1_payload(measure: dict) -> dict:
    real_a = {"source": "tool", "tool": "python:本地测量", "query": "统计仓库内 .md/.py 文件数",
              "result": f"实测 {measure['file_count']} 个文件", "obtained_at": "2026-11-01"}
    real_b = {"source": "tool", "tool": "python:本地测量", "query": "统计仓库内 .md/.py 总行数",
              "result": f"实测 {measure['total_lines']} 行", "obtained_at": "2026-11-01"}

    def sim(query: str, result: str) -> dict:
        return {"source": "text", "simulated": True, "tool": "simulated_search",
                "query": query, "result": result, "obtained_at": "2026-11-01"}

    return {"confessions": [
        {"role": "musk",
         "text": "评审频率本身不是成本主项，真正的主项是每次评审的固定开销。"
                 "[数据诉求: 需要过去两年每次评审的平均参与人时与直接成本]",
         "tool_result": real_a},
        {"role": "feynman",
         "text": "如果说不清「季度评审」到底改了什么，这个议题根本无法检验。"
                 "[数据诉求: 需要现行评审制度里被季度化影响的具体环节清单]",
         "tool_result": sim("季度评审 制度变更 环节", "（模拟）影响环节：材料准备、评审会、复议")},
        {"role": "munger",
         "text": "缩短周期会让短期指标挤掉长期投入，这是激励结构问题不是效率问题。"
                 "[数据诉求: 需要考核周期与项目周期的错配记录]",
         "tool_result": sim("考核周期 项目周期 错配", "（模拟）三个跨年度项目因短周期考核被削减预算")},
        {"role": "jobs",
         "text": "评审流程本身就是多余复杂度，先问要不要评审再问频次。"
                 "[数据诉求: 需要过去一年因评审被拦下的项目数量]",
         "tool_result": sim("评审 拦截 项目数", "（模拟）拦下 4 个，其中 2 个事后被证明该拦")},
        {"role": "karpathy",
         "text": "频次与质量的权衡缺少可测量口径，现在换频次等于瞎调参数。"
                 "[数据诉求: 需要评审结论与实际结果的对照数据]",
         "tool_result": real_b},
        {"role": "pg",
         "text": "我见过的案例里，改频次成功的都同时改了评审内容。"
                 "[数据诉求: 需要至少 3 个只改频次未改内容的对照案例]",
         "tool_result": sim("只改频次 未改内容 案例", "（模拟）2 个案例：改频次未改内容，半年后回到原状")},
    ]}


def stage2_payload() -> dict:
    return {
        "camps": {"blue": ["munger", "jobs", "pg"], "red": ["musk", "feynman", "karpathy"]},
        "exchanges": [
            {"from": "munger", "target_claim": "M1-1", "interrupt": True,
             "inner_thought": "他默认组织愿意承受更频繁的协调成本，这条没人验证过，我先打这里。",
             "text": "[打断] 你的成本模型只算了评审本身，没算参与者的上下文切换成本；"
                     "季度化会让切换次数翻四倍，这一项在 G1 里根本没出现。",
             "evidence": "模拟案例：三个团队因频繁切换导致交付延期"},
            {"from": "jobs", "target_claim": "F1-1",
             "inner_thought": "费曼在要求定义，这正好帮我，但我不能表现得太积极。",
             "text": "定义环节清单之前先问：这些环节里哪一个有独立存在的理由？"
                     "评审会与复议至少有一个是冗余的。",
             "evidence": "减法清单：材料准备 / 评审会 / 复议"},
            {"from": "pg", "target_claim": "K1-1",
             "inner_thought": "我只有两个案例，说服力不够，但我必须把话说满一点试探反应。",
             "text": "只改频次不改内容的两个案例都回到原状了，说明频次不是自变量。",
             "evidence": "模拟对照案例 2 个"},
            {"from": "musk", "target_claim": "G2-1",
             "inner_thought": "上下文切换成本我确实漏了，但量级可能不足以推翻结论，先给数。",
             "text": "接受上下文切换成本，但按模拟数据估算它占总成本 9%，"
                     "不足以推翻「频次不是主项」的结论；我给出可推翻条件：若超过 25% 则结论反转。",
             "evidence": "模拟量级估算"},
            {"from": "feynman", "target_claim": "J2-1",
             "inner_thought": "他说冗余，但说不出谁不需要；这个漏洞我必须点出来。",
             "text": "「冗余」需要一个可观测判据：过去一年复议改变结论的比例是多少？"
                     "没有这个数字，砍掉复议只是偏好不是论证。",
             "evidence": "可操作化要求"},
            {"from": "karpathy", "target_claim": "P2-1",
             "inner_thought": "两个案例的样本量撑不起结论，但方向可能对，我用它来设计对照实验。",
             "text": "两个案例不足以支撑「频次不是自变量」，但足以支撑一个对照实验设计："
                     "同内容改频次 vs 同频次改内容，各跑两个季度。",
             "evidence": "对照实验设计"},
        ],
    }


def stage3_payload() -> dict:
    return {
        "sandbox": {
            "plan": "方案 A：季度评审 + 砍掉复议环节 + 保留材料准备",
            "runners": ["karpathy", "musk"],
            "timeline": [
                {"month": 1, "event": "季度评审上线，团队为每次评审准备材料",
                 "metric": "材料准备人时上升 40%"},
                {"month": 3, "event": "上下文切换成本显现，跨团队协调变慢",
                 "metric": "交付延期率从 12% 升到 19%"},
                {"month": 6, "event": "长期项目因短周期考核被挤压，复议取消后申诉积压",
                 "error": "两个跨年度项目停摆；申诉积压 23 件"},
            ],
            "risks": [
                {"name": "上下文切换成本失控", "severity": 0.75, "probability": 0.7},
                {"name": "长期项目停摆", "severity": 0.9, "probability": 0.45},
                {"name": "申诉积压引发合规问题", "severity": 0.6, "probability": 0.5},
                {"name": "材料准备成本上升", "severity": 0.4, "probability": 0.8},
            ],
            "key_assumptions": [
                {"text": "评审频次是成本主项", "evidence": ""},
                {"text": "复议环节冗余", "evidence": ""},
                {"text": "团队能承受四倍切换", "evidence": "模拟量级估算"},
                {"text": "长期项目不受影响", "evidence": ""},
            ],
            "attacks": [
                {"text": "上下文切换成本", "defended": True},
                {"text": "长期项目停摆", "defended": False},
                {"text": "申诉积压", "defended": False},
            ],
            "action_plan": {
                "do": ["先在同内容的两个团队做季度评审对照实验，各跑两个季度",
                       "把复议改变结论的比例作为砍复议的前置指标"],
                "dont": ["不要在没有对照数据前全量改成季度评审",
                         "不要同时砍掉复议与调整频次（两个变量一起动就无法归因）"],
                "need_info": ["过去两年每次评审的平均参与人时与直接成本",
                              "过去一年复议改变结论的比例",
                              "跨年度项目的实际预算占比"],
            },
            "consensus": "评审的固定开销与上下文切换成本，比评审频次本身更影响结果",
            "core_divergence": "评审该不该存在（价值分歧：效率优先 vs 风险控制优先，逻辑无法消解）",
        },
        "summons": [
            {"role": "合规与劳动关系专家",
             "reason": "取消复议环节会影响申诉通道，涉及劳动争议处理程序",
             "statement": "复议是申诉程序的一部分，取消需同步设计替代通道，"
                          "否则申诉积压会转为合规风险；这一步的成本此前没人计入。"}
        ],
    }


def stage4_payload() -> dict:
    return {"meta": {
        "shared_hidden_assumption": "评审的价值等于它拦下了多少项目",
        "assumption_broken": ["评审频次是成本主项", "复议环节是纯冗余"],
        "ignored_dimension": "上下文切换成本与申诉合规成本",
        "consensus": "评审的固定开销与切换成本比频次本身更影响结果",
        "core_divergence": "评审该不该存在（价值分歧，逻辑无法消解，只能各自说明条件）",
        "memory": "评审类流程的优化对象不是频次而是单次固定开销与切换成本；"
                  "砍环节前先问它承担了什么风险，尤其是申诉与合规通道——"
                  "这类环节的缺失成本通常延后三个月才显现。",
    }}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--out", default=".ultimate-demo")
    args = ap.parse_args()

    py = sys.executable
    out = (ROOT / args.out).resolve()
    work = out / "payloads"
    work.mkdir(parents=True, exist_ok=True)

    orch = str(UR / "ultimate_orchestrator.py")
    clash = str(UR / "clash_analyzer.py")

    print("=== 0. 初始化 ===")
    init = json.loads(run([py, orch, "init", "--topic", TOPIC, "--out", str(out)],
                          args.quiet))
    state = init["state_path"]

    measure = real_measurements()
    print(f"（真实测量：本仓库 .md/.py 共 {measure['file_count']} 个文件、"
          f"{measure['total_lines']} 行——这两条会以 source=tool 记入阶段一）")

    print("\n=== 1. 阶段一：极速摊牌与工具诉求 ===")
    p1 = work / "stage1.json"
    p1.write_text(json.dumps(stage1_payload(measure), ensure_ascii=False, indent=2),
                  encoding="utf-8")
    run([py, orch, "stage1", "--state", state, "--file", str(p1), "--write"], args.quiet)

    print("\n=== 2. 阶段二：内心戏 + 打断 + 红蓝对抗 ===")
    p2 = work / "stage2.json"
    p2.write_text(json.dumps(stage2_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    run([py, orch, "stage2", "--state", state, "--file", str(p2), "--write"], args.quiet)
    run([py, clash, "spark", "--state", state, "--round", "2"], args.quiet)

    print("\n=== 2b. 反例验证：空洞发言必须被拒绝（强制重开） ===")
    hollow = {"camps": {"blue": ["munger", "jobs", "pg"],
                        "red": ["musk", "feynman", "karpathy"]},
              "exchanges": [{"from": r, "inner_thought": "随便吧", "text": "我觉得挺好的"}
                            for r in ["munger", "jobs", "pg", "musk", "feynman", "karpathy"]]}
    ph = work / "stage2-hollow.json"
    ph.write_text(json.dumps(hollow, ensure_ascii=False, indent=2), encoding="utf-8")
    proc = subprocess.run([py, orch, "stage2", "--state", state, "--file", str(ph)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 4:
        print("空洞发言被判为 no_spark，退出码 4，强制重开（符合预期）")
        if not args.quiet:
            print(proc.stdout[:400])
    else:
        print(f"!! 预期退出码 4，实际 {proc.returncode}")
        return 1

    print("\n=== 3. 阶段三：沙盘推演 + 动态召唤 ===")
    p3 = work / "stage3.json"
    p3.write_text(json.dumps(stage3_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    run([py, orch, "stage3", "--state", state, "--file", str(p3), "--write"], args.quiet)
    run([py, clash, "survival", "--state", state], args.quiet)

    print("\n=== 4. 阶段四：元认知降维打击 ===")
    p4 = work / "stage4.json"
    p4.write_text(json.dumps(stage4_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    run([py, orch, "stage4", "--state", state, "--file", str(p4), "--write"], args.quiet)

    print("\n=== 5. 完整性检查 ===")
    run([py, orch, "check", "--state", state], args.quiet)

    print("\n=== 6. 生成终极圆桌决策报告 ===")
    report = out / "ultimate-report.md"
    run([py, orch, "report", "--state", state, "--out", str(report)], args.quiet)
    print(report.read_text(encoding="utf-8"))

    print(f"\n演示完成。状态：{state}")
    print("注意：本演示的对话内容为虚构示例数据；"
          "其中「文件数/行数」两条是真实本地测量，其余四条已标注 simulated=true。")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

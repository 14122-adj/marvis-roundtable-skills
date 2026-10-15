#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端演示 tools/demo_session.py

用一份**示例数据**（对话内容均为虚构演示，非真实调研）跑完整个流水线：
R0 共享前提 → R1 隔离立论 → 元认知扫描 + 注入 → R2 自由交叉（含一次有效修正与一次从众漂移）
→ 收敛检测 → 交接摘要。

它同时是一次集成测试：任何一步失败都会以非零退出码结束。

用法：
  python tools/demo_session.py [--out .roundtable-demo] [--quiet]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "skills" / "roundtable-orchestrator" / "scripts"
META = ROOT / "skills" / "meta-supervisor" / "scripts"
EVO = ROOT / "skills" / "position-evolution" / "scripts"

TOPIC = "【示例数据】科创竞赛资源应该怎么分配"

SHARED_PREMISES = [
    "竞赛必须拿奖才算成功",  # 本演示要挖出来的隐性假设
    "资源总量固定，不讨论外部争取",
]

ROUND1 = [
    {
        "role": "musk", "round": 1,
        "position": "先算单位获奖产出的成本下界，再谈分配比例",
        "claims": [
            {"id": "M1-1",
             "text": "固定预算下真正可优化的是单位获奖产出的成本，而不是获奖数量",
             "basis": "mechanism", "evidence": "成本=投入/产出；产出口径未定义时不存在最优解",
             "falsifiable_by": "存在与成本无关的分配准则"},
            {"id": "M1-2",
             "text": "若目标是能力覆盖，资源应按覆盖面分配而不是按获奖概率分配",
             "basis": "value_judgment", "evidence": "两种目标下最优分配不同",
             "falsifiable_by": "能证明两种目标的最优分配一致"},
        ],
        "blind_spot_declared": "看不到评审制度与激励结构造成的扭曲",
        "epistemic_status": {"confidence": 70,
                             "uncertainty_points": ["成功标准由谁定义不清楚"],
                             "will_revise_if": "若成功标准被明确为能力覆盖，我改为覆盖面分配"},
    },
    {
        "role": "feynman", "round": 1,
        "position": "先定义「获奖」和「资源」，否则大家在答两道不同的题",
        "claims": [
            {"id": "F1-1",
             "text": "如果不能用一句话说清「资源」指钱还是指人，这一轮的结论都无法检验",
             "basis": "mechanism", "evidence": "可操作化要求能被观察；两种口径下的最优分配不同",
             "falsifiable_by": "给出统一且可测量的口径定义"},
        ],
        "blind_spot_declared": "过度简化会丢掉组织政治这个真实约束",
        "epistemic_status": {"confidence": 60,
                             "uncertainty_points": ["我无法判断组织内真实的决策权归属"],
                             "will_revise_if": "出现可测量的口径定义"},
    },
    {
        "role": "munger", "round": 1,
        "position": "想让这件事彻底失败，就让所有人按获奖概率分钱、同时只考核一年",
        "claims": [
            {"id": "G1-1",
             "text": "以一年为考核周期分配资源，长期能力项目必然被挤掉",
             "basis": "mechanism", "evidence": "失败路径倒推：短周期激励下长期收益不可见",
             "falsifiable_by": "存在跨周期保护机制（如多年期预算）"},
        ],
        "blind_spot_declared": "保守倾向会低估突破性项目的价值",
        "epistemic_status": {"confidence": 65,
                             "uncertainty_points": ["不同组织考核周期差异很大"],
                             "will_revise_if": "看到跨周期保护机制的实际运作"},
    },
    {
        "role": "jobs", "round": 1,
        "position": "现在这套分配流程本身就是多余的复杂度，先砍掉两级评审",
        "claims": [
            {"id": "J1-1",
             "text": "若只能保留一件事，就是让资源跟着使用者的实际需求走，而不是跟着评审表走",
             "basis": "value_judgment", "evidence": "终点倒推：没人真正需要的环节是两级评审",
             "falsifiable_by": "能说明这两级评审防止过具体损失"},
        ],
        "blind_spot_declared": "会把必要的冗余当成复杂度砍掉",
        "epistemic_status": {"confidence": 50,
                             "uncertainty_points": ["无法量化评审防住了多少风险"],
                             "will_revise_if": "出现评审阻止损失的案例"},
    },
    {
        "role": "karpathy", "round": 1,
        "position": "先把「分配」拆成可独立验证的模块，再谈比例",
        "claims": [
            {"id": "K1-1",
             "text": "分配规则与评估口径未固定前，任何比例讨论都不可复现",
             "basis": "mechanism", "evidence": "缺少接口定义（谁评、评什么、何时评）；不可复现的结论不能作为依据",
             "falsifiable_by": "给出完整接口定义后比例可被检验"},
        ],
        "blind_spot_declared": "容易把价值问题误当工程问题处理",
        "epistemic_status": {"confidence": 75,
                             "uncertainty_points": ["不知道现有系统里是否已有这套接口约定"],
                             "will_revise_if": "现有系统已有接口约定"},
    },
    {
        "role": "pg", "round": 1,
        "position": "先给一个真实案例：有团队按能力覆盖分配，两年内获奖反而增加",
        "claims": [
            {"id": "P1-1",
             "text": "评审口径不透明时，资源集中在「最可能获奖」的项目会带来系统性偏差",
             "basis": "case", "evidence": "示例案例（虚构演示）：按能力覆盖分配后两年获奖数反升",
             "falsifiable_by": "出现反向案例"},
        ],
        "blind_spot_declared": "单个案例容易过度泛化",
        "epistemic_status": {"confidence": 40,
                             "uncertainty_points": ["n=1，这个案例不能当统计证据"],
                             "will_revise_if": "出现反例或多案例不一致"},
    },
]

ROUND2 = [
    {
        "role": "pg", "round": 2,
        "position": "我先回应元认知提出的 H1：我的结论确实依赖「必须拿奖」这个前提",
        "claims": [
            {"id": "P2-1",
             "text": "为让项目「看起来获奖概率高」而做的包装成本，是当前分配规则的隐性成本",
             "basis": "case", "evidence": "示例案例（虚构演示）：三个团队都做了材料的过度包装",
             "falsifiable_by": "统计包装投入占比接近零"},
        ],
        "responses": [
            {"to": "M1-1", "type": "challenge",
             "text": "你的成本下界推演只算了直接投入，忽略了为迎合评审口径产生的包装成本"},
            {"to": "H1", "type": "adopt",
             "text": "我承认 P1-1 的结论只在该前提成立时才成立；如果成功标准改成能力覆盖，案例结论要重写"},
        ],
        "blind_spot_declared": "案例来自我熟悉的场景，可能不代表更大范围",
        "epistemic_status": {"confidence": 45,
                             "uncertainty_points": ["包装成本占比没有数据"],
                             "will_revise_if": "出现包装成本占比的实测数据"},
    },
    {
        "role": "musk", "round": 2,
        "position": "接受 P2-1 的补充：下界推演需要把包装成本计入",
        "claims": [
            {"id": "M2-1",
             "text": "若包装成本占比超过总投入的 15%，则规则本身的成本高于选题偏差的成本",
             "basis": "empirical", "evidence": "按示例数据的量级估算", "falsifiable_by": "实测占比低于 15%"},
        ],
        "responses": [
            {"to": "P2-1", "type": "adopt", "text": "这部分成本我确实漏算了，纳入下界推演"},
            {"to": "H1", "type": "refine",
             "text": "H1 成立与否直接决定 M1-2 是否成立：我的分配准则依赖对「成功」的定义"},
        ],
        "blind_spot_declared": "仍然看不到组织内部的政治博弈过程",
        "epistemic_status": {"confidence": 62,
                             "uncertainty_points": ["包装成本占比缺实测数据"],
                             "will_revise_if": "出现实测的包装成本占比"},
        "revision": {
            "trigger": "P2-1 提出的包装成本，以及元认知登记的 H1",
            "level": "local",
            "from": "单位获奖产出的成本是唯一可优化量",
            "to": "单位有效产出的成本才是可优化量，其中必须计入为迎合口径产生的包装成本",
            "reason": "原结论把「产出」默认为获奖数，而包装成本说明该口径本身会制造额外成本；原结论的范围需要收窄",
            "remaining_doubt": "有效产出的口径由谁定义，这是价值问题不是事实问题",
        },
    },
    {
        "role": "feynman", "round": 2,
        "position": "H1 是我这一轮最主要的回应对象：它让「分配」这道题换了题干",
        "claims": [
            {"id": "F2-1",
             "text": "如果「成功」的定义没写下来，这场讨论的结论无法被任何人验证或推翻",
             "basis": "mechanism", "evidence": "不可检验的结论在讨论结束后无法被使用", "falsifiable_by": "写出一份可操作的成败定义"},
        ],
        "responses": [
            {"to": "H1", "type": "challenge",
             "text": "H1（必须拿奖才算成功）从未被论证过；在它被明确之前，任何比例都是猜的"},
            {"to": "J1-1", "type": "challenge",
             "text": "砍掉评审要能说清「没人需要」是谁的判断；使用者包含未来的人，他们没法投票"},
        ],
        "blind_spot_declared": "把难以量化但真实存在的价值也一并简化掉了",
        "epistemic_status": {"confidence": 58,
                             "uncertainty_points": ["不知道谁能定义成功标准"],
                             "will_revise_if": "有人给出可操作的成败定义"},
    },
    {
        "role": "jobs", "round": 2,
        "position": "维持减法主张，但承认「没人需要」需要证据",
        "claims": [
            {"id": "J2-1",
             "text": "两级评审若无法说明它防止了什么，就应该先停掉一级试运行",
             "basis": "value_judgment", "evidence": "减法清单：评审表、二次答辩、汇总打分表", "falsifiable_by": "出现某次评审阻止损失的记录"},
        ],
        "responses": [
            {"to": "H1", "type": "support",
             "text": "同意 H1 值得质疑：如果成功标准改成能力覆盖，现在的评审表大半是多余的"},
            {"to": "F2-1", "type": "refine",
             "text": "接受「需要证据」这一要求，改成先停一级做对照"},
        ],
        "blind_spot_declared": "对制度性风险不敏感",
        "epistemic_status": {"confidence": 52,
                             "uncertainty_points": ["不知道停一级会漏掉什么"],
                             "will_revise_if": "出现评审拦截风险的记录"},
        "revision": {
            "trigger": "大家都觉得减少评审是共识，为了推进讨论我也同意",
            "level": "local",
            "from": "先砍掉两级评审",
            "to": "砍掉一级评审",
            "reason": "为了达成共识，与多数人保持一致",
            "remaining_doubt": "",
        },
    },
]


def run(cmd: list, quiet: bool, expect_ok: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 and expect_ok:
        print(f"!! 命令失败 {proc.returncode}: {' '.join(str(c) for c in cmd)}", file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    if not quiet:
        label = " ".join(str(c) for c in cmd[2:4])
        print(f"\n$ {Path(cmd[1]).name} {label}")
        print(proc.stdout.rstrip())
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".roundtable-demo")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    out = (ROOT / args.out).resolve()
    work = out / "payloads"
    work.mkdir(parents=True, exist_ok=True)

    py = sys.executable
    sm = str(ORCH / "state_manager.py")
    rc = str(ORCH / "round_controller.py")
    cd = str(ORCH / "convergence_detector.py")

    print("=== 0. 建立会话 ===")
    init = json.loads(run([py, sm, "init", "--topic", TOPIC, "--state", str(out / "state.json"),
                           "--session-id", "rt-demo"], args.quiet))
    state = init["state_path"]
    for p in SHARED_PREMISES:
        run([py, sm, "set", "--state", state, "--path", "shared_premises",
             "--append", "--value", json.dumps(p, ensure_ascii=False)], args.quiet)

    print("\n=== 1. R1 隔离立论 ===")
    run([py, sm, "begin-round", "--state", state, "--round", "1"], args.quiet)
    for payload in ROUND1:
        f = work / f"{payload['role']}-r1.json"
        f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        run([py, sm, "add-claims", "--state", state, "--file", str(f)], args.quiet)
        run([py, sm, "add-position", "--state", state, "--file", str(f)], args.quiet)

    print("\n=== 2. R1.5 元认知扫描 ===")
    for script in ("assumption_extractor.py", "divergence_classifier.py", "fallacy_detector.py"):
        run([py, str(META / script), "scan" if script != "divergence_classifier.py" else "suggest",
             "--state", state, "--write"], args.quiet)
    run([py, sm, "set", "--state", state, "--path", "injections", "--append", "--value",
         json.dumps({"round": 2, "must_respond": ["H1"], "must_resolve": ["C1"],
                     "forbidden": ["继续争论分配比例的具体数字"],
                     "note": "本轮所有角色必须正面回应 H1：竞赛必须拿奖才算成功"},
                    ensure_ascii=False)], args.quiet)

    print("\n=== 3. R2 自由交叉（含修正判定）===")
    run([py, rc, "plan", "--state", state, "--write"], args.quiet)
    run([py, sm, "begin-round", "--state", state, "--round", "2"], args.quiet)
    for payload in ROUND2:
        f = work / f"{payload['role']}-r2.json"
        f.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        run([py, sm, "add-claims", "--state", state, "--file", str(f)], args.quiet)
        run([py, sm, "add-position", "--state", state, "--file", str(f)], args.quiet)
        if "revision" in payload:
            run([py, str(EVO / "revision_tracker.py"), "record", "--state", state,
                 "--file", str(f), "--write"], args.quiet)

    print("\n=== 4. R2.5 元认知二次扫描 + 收敛检测 + 覆盖度 ===")
    for script in ("assumption_extractor.py", "divergence_classifier.py", "fallacy_detector.py"):
        run([py, str(META / script), "scan" if script != "divergence_classifier.py" else "suggest",
             "--state", state, "--write"], args.quiet)
    run([py, cd, "check", "--state", state, "--write"], args.quiet)
    run([py, rc, "coverage", "--state", state], args.quiet)

    print("\n=== 5. 交接摘要 ===")
    text = run([py, sm, "summary", "--state", state], args.quiet)
    print(text if args.quiet else "")

    # ---------------- P2 · 决策景观 ----------------
    print("\n=== 6. P2 决策景观报告 ===")
    dl = ROOT / "skills" / "decision-landscape" / "scripts" / "synthesis_generator.py"
    report_path = out / "decision-landscape.md"
    run([py, str(dl), "build", "--state", state, "--out", str(report_path)], args.quiet)
    run([py, str(dl), "check", "--state", state], args.quiet)
    print(f"决策景观报告已生成：{report_path}")

    # ---------------- P3 · 认知噪声（rigorous 模式应被脚本拒绝） ----------------
    print("\n=== 7. P3 认知噪声开关检查 ===")
    cn = ROOT / "skills" / "cognitive-noise" / "scripts" / "noise_injector.py"
    proc = subprocess.run([py, str(cn), "plan", "--state", state, "--role", "pg"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 3 and '"mode_ok": false' in proc.stdout:
        print("认知噪声在 rigorous 模式下被拒绝（符合预期：该层会降低严谨性，只允许 simulation 模式）")
    else:
        print(f"!! 预期被拒绝，实际 returncode={proc.returncode}")
        return 1

    # ---------------- P4 · 异构基座调用包 ----------------
    print("\n=== 8. P4 多基座调用包 ===")
    mm = ROOT / "skills" / "multi-model-adapter" / "scripts" / "runtime_manifest.py"
    bundle = out / "bundle-round3"
    run([py, str(mm), "emit", "--state", state, "--round", "3", "--out", str(bundle)], args.quiet)
    print(f"多基座调用包已生成（每角色一个 task.json，provider/model 未指定时为 unspecified）：{bundle}")

    print(f"\n演示完成。状态文件：{state}")
    print("注意：本演示的对话内容为虚构示例数据，不代表真实调研结论。")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

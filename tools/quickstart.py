#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一条命令跑通 quickstart.py

目标：让一个从没接触过这个仓库的人，在 **10 分钟内**看到一场完整的终极圆桌，
而不是先读 14 个 SKILL.md、装 Python、手写 5 个阶段 JSON。

它做四件事（按顺序，任一步失败会明确告诉你卡在哪、怎么修）：

  1. **体检**：Python 版本、仓库完整性、六个角色技能、脚本可执行性；
  2. **跑一场**：用内置示例数据走完 stage0→stage4，生成真实报告；
  3. **自检**：跑一遍仓库自检，确认你拿到的这份是好的；
  4. **下一步**：打印"接下来做什么"（换成你自己的议题 / 导入宿主 / 看文档）。

用法：
  python tools/quickstart.py                  # 完整流程（约 10 秒）
  python tools/quickstart.py --check          # 只体检，不跑演示
  python tools/quickstart.py --topic "你的议题"  # 用你的议题名跑示例流程
  python tools/quickstart.py --open           # 跑完尝试打开报告

设计原则：
  * **不伪造成功**：任何一步失败都如实报错并给修复建议，绝不"看起来跑通了"；
  * **不静默跳过**：缺什么就说缺什么，不用默认值糊弄；
  * **可重复**：跑多少次结果都一样，不污染仓库（产物写到 .quickstart/）。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".quickstart"
UR = ROOT / "skills" / "ultimate-roundtable" / "scripts"

MIN_PYTHON = (3, 9)
SIX_ROLES = ["role-musk", "role-feynman", "role-munger",
             "role-jobs", "role-karpathy", "role-pg"]

REQUIRED = [
    "skills/ultimate-roundtable/SKILL.md",
    "skills/ultimate-roundtable/scripts/ultimate_orchestrator.py",
    "skills/roundtable-orchestrator/scripts/state_manager.py",
    "tools/validate_repo.py",
    "docs/output-contract.md",
]

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _color_ok():
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if _color_ok() else text


def ok(msg: str):
    print(f"  {c('✓', GREEN)} {msg}")


def bad(msg: str):
    print(f"  {c('✗', RED)} {msg}")


def warn(msg: str):
    print(f"  {c('!', YELLOW)} {msg}")


def dim(msg: str):
    print(f"    {c(msg, DIM)}")


def section(title: str):
    print(f"\n{c(title, GREEN)}")
    print("─" * max(30, len(title) * 2))


# --------------------------------------------------------------------------- #
# 1. 体检
# --------------------------------------------------------------------------- #


def check_python() -> tuple:
    ver = sys.version_info[:2]
    if ver < MIN_PYTHON:
        bad(f"Python {ver[0]}.{ver[1]} 太旧，需要 {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")
        dim(f"当前解释器：{sys.executable}")
        dim("建议：升级 Python，或用 `python3.11 tools/quickstart.py` 指定版本")
        return False
    ok(f"Python {ver[0]}.{ver[1]}（{platform.system()}）")
    return True


def check_repo() -> tuple:
    missing = [r for r in REQUIRED if not (ROOT / r).is_file()]
    if missing:
        bad(f"仓库不完整，缺 {len(missing)} 个文件：")
        for m in missing[:5]:
            dim(f"缺失：{m}")
        dim("建议：重新 clone 整个仓库，不要只下载单个文件")
        return False
    ok(f"仓库结构完整（{len(REQUIRED)} 个关键文件都在）")
    return True


def check_roles() -> tuple:
    missing = [r for r in SIX_ROLES if not (ROOT / "skills" / r / "SKILL.md").is_file()]
    if missing:
        bad(f"六个角色技能缺 {len(missing)} 个：{', '.join(missing)}")
        dim("修复：python skills/host-bootstrap/scripts/bootstrap.py install")
        return False, missing
    ok("六个角色技能就绪（role-musk / feynman / munger / jobs / karpathy / pg）")

    # 社区角色是可选增强，缺失不算失败
    community = ROOT / "community-roles"
    extra = sorted(d.name for d in community.glob("role-*")) if community.exists() else []
    if extra:
        ok(f"社区角色 {len(extra)} 个：{', '.join(extra)}")
    else:
        warn("未发现社区角色（可选，不影响跑通）")
    return True, []


def check_scripts() -> tuple:
    if not UR.is_dir():
        bad("找不到 ultimate-roundtable 脚本目录")
        return False
    try:
        proc = subprocess.run([sys.executable, str(UR / "ultimate_orchestrator.py"), "--help"],
                              capture_output=True, text=True, timeout=30,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            bad("终极圆桌脚本无法执行")
            dim((proc.stderr or "")[-200:])
            return False
        ok("核心脚本可执行")
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        bad(f"脚本执行失败：{exc}")
        return False


def run_check(verbose: bool = True) -> bool:
    if verbose:
        section("① 体检")
    results = [check_python(), check_repo()]
    roles_ok, _ = check_roles()
    results.append(roles_ok)
    results.append(check_scripts())
    return all(results)


# --------------------------------------------------------------------------- #
# 2. 跑一场
# --------------------------------------------------------------------------- #


def build_demo(topic: str) -> dict:
    """内置示例：一段完整但精简的四阶段数据（全部标为 simulated）。"""
    north = "月活"
    confessions = []
    for i, role in enumerate(["musk", "feynman", "munger", "jobs", "karpathy", "pg"]):
        confessions.append({
            "role": role,
            "text": (f"{north} 是核心指标。[数据诉求: 需要第 {i} 项基准数据] "
                     f"[Tool Call: Search] 关键词：基准数据 {i}。"
                     f"基于此数据，我的观点是：第 {i} 条结论。"),
            "tool_result": {"source": "text", "simulated": True,
                            "tool": "simulated_search",
                            "query": f"基准数据 {i}",
                            "result": f"（示例数据）第 {i} 项基准值为 {i + 1}"},
        })
    return {
        "stage0": {"north_star": north},
        "stage1": {"confessions": confessions},
        "stage2": {
            "camps": {"blue": ["munger", "jobs", "pg"],
                      "red": ["musk", "feynman", "karpathy"]},
            "exchanges": [
                {"from": "munger", "target_claim": "M1-1", "interrupt": True,
                 "inner_thought": "他默认组织愿意改变，这条没人验证过",
                 "text": "[打断] 你的推演假设组织愿意承担额外协调成本，这个假设没被验证",
                 "evidence": "示例案例"},
                {"from": "jobs", "target_claim": "F1-1",
                 "inner_thought": "这堆环节没人真需要",
                 "text": "方案多出两个审批环节，砍掉后成本降 30%", "evidence": "减法清单"},
                {"from": "pg", "target_claim": "K1-1",
                 "inner_thought": "我只有两个案例，但必须顶住",
                 "text": "只改频次不改内容的两个案例都回到原状", "evidence": "示例案例"},
                {"from": "musk", "target_claim": "G2-1",
                 "inner_thought": "切换成本我确实漏了，但量级可能不够",
                 "text": "接受切换成本，但它占 9%，不改变结论；若超 25% 则结论反转",
                 "evidence": "示例估算"},
                {"from": "feynman", "target_claim": "J2-1",
                 "inner_thought": "他连谁不需要都答不上来",
                 "text": "「没人需要」需要一个可观测判据，否则无法检验",
                 "evidence": "可操作化要求"},
                {"from": "karpathy", "target_claim": "P2-1",
                 "inner_thought": "两个案例撑不起结论，但方向可试",
                 "text": "两个案例不足以支撑结论，但足以设计一个对照实验",
                 "evidence": "实验设计"},
            ],
        },
        "stage3": {
            "options": {
                "A": {"summary": "全量切换，三个月内完成"},
                "B": {"summary": "维持现状，只精简一个环节"},
                "C": {"summary": "改为触发式：指标跌破阈值才启动"},
            },
            "votes": {"musk": "A", "feynman": "C", "munger": "B",
                      "jobs": "C", "karpathy": "C", "pg": "B"},
            "vote_reasons": {
                "musk": "窗口只有三个月", "feynman": "触发式有可观测判据",
                "munger": "全量切换失败路径太多", "jobs": "固定流程本身冗余",
                "karpathy": "触发式可做对照实验", "pg": "见过全量切换失败",
            },
            "decision": "C",
            "decision_reason": "C 得 3 票且判据可观测；A 的下行风险未被防住",
        },
        "stage4": {
            "meta": {
                "shared_hidden_assumption": "流程的价值等于它拦下了多少事",
                "assumption_broken": ["频率是成本主项"],
                "ignored_dimension": "上下文切换成本",
                "memory": "流程优化的对象不是频率而是单次固定开销；"
                          "改频率前先问它承担了什么风险。",
                "memory_tags": ["流程", "成本"],
            },
            "action_plan": {
                "owner": "karpathy",
                "start": "本周在 2 个团队上线触发式流程，阈值设为指标跌破 8%",
                "kpi": "30 天内触发不超过 5 次，指标不低于 9%",
                "kill": "如果 30 天内触发超过 12 次，立刻停止并回滚",
                "need_info": ["过去两年的单次流程人时"],
            },
            "persist_memory": True,
        },
    }


def run_demo(topic: str) -> tuple:
    section("② 跑一场终极圆桌")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    payload = build_demo(topic)
    store = str(OUT / "memories.jsonl")
    payload["stage4"]["store"] = store
    payload["stage0"]["store"] = store

    orch = str(UR / "ultimate_orchestrator.py")
    t0 = time.time()

    def run(args: list, label: str, expect: int = 0) -> bool:
        proc = subprocess.run([sys.executable, orch, *args],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != expect:
            bad(f"{label} 失败（退出码 {proc.returncode}）")
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            for line in err[-4:]:
                dim(line)
            return False
        return True

    init = subprocess.run([sys.executable, orch, "init", "--topic", topic,
                           "--out", str(OUT)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if init.returncode != 0:
        bad("初始化失败")
        dim((init.stderr or "")[-300:])
        return False, None
    state = json.loads(init.stdout)["state_path"]

    steps = [
        ("stage0", "阶段零 · 记忆唤醒 + 北极星锚定"),
        ("stage1", "阶段一 · 极速交底（150 字 + 分舱 + 工具闭环）"),
        ("stage2", "阶段二 · 红蓝对抗（内心戏 + 打断）"),
        ("stage3", "阶段三 · 铁血裁决（A/B/C 三选一）"),
        ("stage4", "阶段四 · 战术级行动清单"),
    ]
    for name, label in steps:
        pf = OUT / f"{name}.json"
        pf.write_text(json.dumps(payload[name], ensure_ascii=False, indent=2),
                      encoding="utf-8")
        if not run([name, "--state", state, "--file", str(pf), "--write"], label):
            return False, None
        ok(label)

    report = OUT / "report.md"
    if not run(["report", "--state", state, "--out", str(report)], "生成报告"):
        return False, None
    ok(f"生成报告（{len(report.read_text(encoding='utf-8'))} 字符）")

    elapsed = time.time() - t0
    print(f"\n  {c('整场耗时', GREEN)} {elapsed:.1f} 秒　"
          f"{c('报告', GREEN)} {report.relative_to(ROOT)}")
    return True, report


# --------------------------------------------------------------------------- #
# 3. 自检
# --------------------------------------------------------------------------- #


def run_selftest(quick: bool = True) -> bool:
    section("③ 仓库自检" + ("（快速模式）" if quick else ""))
    cmd = [sys.executable, str(ROOT / "tools" / "validate_repo.py")]
    if quick:
        cmd.append("--no-scripts")
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = [l for l in (proc.stdout or "").splitlines() if l.strip()][-2:]
    for line in tail:
        dim(line.strip())
    if proc.returncode == 0:
        ok("自检通过")
        return True
    bad("自检未通过（不影响你跑通，但说明这份副本可能被改动过）")
    for line in (proc.stdout or "").splitlines():
        if "[" in line and "FAIL" in line:
            dim(line.strip()[:100])
    return False


# --------------------------------------------------------------------------- #
# 4. 下一步
# --------------------------------------------------------------------------- #


def next_steps(report: Path | None):
    section("④ 接下来做什么")
    print("  1) 看看刚才生成了什么")
    if report:
        dim(f"打开报告：{report}")
    dim(f"完整状态：{OUT / 'state.json'}")

    print("\n  2) 换成你自己的议题")
    dim('python tools/wizard.py            # 交互式引导，替你生成 5 个阶段的 payload')
    dim('或看模板：templates/ 目录下有可改的示例 JSON')

    print("\n  3) 在你的 AI 客户端里用")
    dim("python skills/host-bootstrap/scripts/bootstrap.py detect   # 我在什么宿主？")
    dim("python skills/host-bootstrap/scripts/bootstrap.py install  # 补齐六个角色技能")
    dim("然后把 skills/ 导入你的宿主（马维斯有原生导入，其他宿主读 AGENTS.md / CLAUDE.md）")

    print("\n  4) 想深入了解")
    dim("QUICKSTART.md          —— 10 分钟完整路径（含各宿主差异）")
    dim("docs/output-contract.md —— 所有字段的唯一来源")
    dim("skills/ultimate-roundtable/SKILL.md —— 机制全貌")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="10 分钟跑通：一条命令完成体检、跑一场、自检、给出下一步")
    ap.add_argument("--topic", default="【示例】要不要把年度流程改成季度",
                    help="议题名（默认用内置示例议题）")
    ap.add_argument("--check", action="store_true", help="只体检，不跑演示")
    ap.add_argument("--open", action="store_true", help="跑完尝试打开报告")
    ap.add_argument("--full-selftest", action="store_true", help="自检也跑全部脚本")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    if args.no_color:
        os.environ["NO_COLOR"] = "1"

    print(c("\n终极圆桌 · 快速跑通", GREEN))
    print(c(f"仓库：{ROOT}", DIM))

    if not run_check():
        print(f"\n{c('体检未通过，请按上面的提示修复后重试。', RED)}\n")
        return 1

    if args.check:
        print(f"\n{c('体检全部通过。加 --topic 跑一场看看：', GREEN)}")
        print("  python tools/quickstart.py\n")
        return 0

    demo_ok, report = run_demo(args.topic)
    if not demo_ok:
        print(f"\n{c('演示未跑通。上面的报错就是原因，修好后重跑本命令。', RED)}\n")
        return 1

    run_selftest(quick=not args.full_selftest)
    next_steps(report)

    if args.open and report and report.exists():
        try:
            if platform.system() == "Windows":
                os.startfile(str(report))       # noqa: S606
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(report)], check=False)
            else:
                subprocess.run(["xdg-open", str(report)], check=False)
        except OSError:
            warn("无法自动打开，请手动查看上面的路径")

    print(c("完成。", GREEN) + " 你刚刚跑完了一场完整的终极圆桌。\n")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

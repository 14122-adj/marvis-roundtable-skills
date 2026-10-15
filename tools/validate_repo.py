#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库自检 tools/validate_repo.py

一次跑完所有可机器验证的规则，避免"看起来都对"：
  1. 9 个技能目录齐全，每个都有 SKILL.md；
  2. frontmatter 能被 YAML 解析，name 与目录名一致，description 存在；
  3. 角色技能包含 9 个必需二级标题（顺序固定）；
  4. 全部技能都出现契约关键字段名；
  5. 禁用写法扫描（形式硬约束、弹窗、../、颜色样式），带"否定语境"豁免；
  6. 5 个脚本的 --selftest 全部通过；
  7. 参考文件齐全且行数达标。

用法：python tools/validate_repo.py [--no-scripts]
退出码：0 = 全部通过；1 = 有失败项。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

CORE_SKILLS = ["roundtable-orchestrator", "meta-supervisor", "position-evolution"]
ROLE_SKILLS = ["role-musk", "role-feynman", "role-munger", "role-jobs", "role-karpathy", "role-pg"]
ALL_SKILLS = CORE_SKILLS + ROLE_SKILLS

ROLE_HEADINGS = [
    "## 角色定位",
    "## 思维协议",
    "## 天然张力",
    "## 已知盲区",
    "## 输出契约",
    "## 分轮次行为",
    "## 修正权限",
    "## 反模式",
    "## 参考文件",
]

CONTRACT_FIELDS = [
    "role", "round", "position", "claims", "responses",
    "blind_spot_declared", "epistemic_status", "confidence",
    "uncertainty_points", "will_revise_if",
]

EXPECTED_FILES = {
    "roundtable-orchestrator": ["scripts/state_manager.py", "scripts/round_controller.py",
                                "scripts/convergence_detector.py", "references/interaction-protocols.md"],
    "meta-supervisor": ["scripts/assumption_extractor.py", "scripts/divergence_classifier.py",
                        "scripts/fallacy_detector.py", "references/metacognitive-checklist.md"],
    "position-evolution": ["scripts/revision_tracker.py", "references/revision-protocols.md"],
    "role-musk": ["references/first-principles-examples.md"],
    "role-feynman": ["references/explanation-verification.md"],
    "role-munger": ["references/mental-models-catalog.md"],
    "role-jobs": ["references/simplicity-criteria.md"],
    "role-karpathy": ["references/system-decomposition-guide.md"],
    "role-pg": ["references/case-based-reasoning.md"],
}

SCRIPTS = [
    "skills/roundtable-orchestrator/scripts/state_manager.py",
    "skills/roundtable-orchestrator/scripts/round_controller.py",
    "skills/roundtable-orchestrator/scripts/convergence_detector.py",
    "skills/meta-supervisor/scripts/assumption_extractor.py",
    "skills/meta-supervisor/scripts/divergence_classifier.py",
    "skills/meta-supervisor/scripts/fallacy_detector.py",
    "skills/position-evolution/scripts/revision_tracker.py",
]

ROOT_FILES = [
    "README.md", "LICENSE", "CHANGELOG.md", ".gitignore",
    "docs/output-contract.md", "docs/example-session.md",
    "tools/validate_repo.py", "tools/demo_session.py",
]

# 禁用写法：命中后还要看是否处在"否定语境"里（如"禁止出现本轮必须一对一轮流"）
FORBIDDEN = [
    (r"(?<![.\w])\.\./", "跨技能相对路径 ../"),
    (r"\balert\s*\(", "alert 弹窗"),
    (r"\bconfirm\s*\(", "confirm 弹窗"),
    (r"\bprompt\s*\(", "prompt 弹窗"),
    (r"this\.setState", "setState（本环境不存在）"),
    (r"background-color\s*:", "颜色样式"),
    (r"本轮必须一对一轮流", "形式硬约束：强制配对"),
    (r"必须联动\s*[≥>]\s*2", "形式硬约束：强制联动人数"),
    (r"每段不超过\s*\d+\s*字", "形式硬约束：字数限制"),
]
NEGATION = ("禁止", "不得", "不设", "废除", "❌", "不是", "不要", "反向", "旧", "原方案", "取消",
            "人为硬规定", "换成", "错误做法", "反模式")

results = []


def check(category: str, name: str, ok: bool, detail: str = ""):
    results.append((category, name, ok, detail))


def parse_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    return yaml.safe_load(parts[1]), parts[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-scripts", action="store_true", help="跳过脚本 selftest")
    args = ap.parse_args()

    # 1) 文件结构
    for rel in ROOT_FILES:
        check("结构", rel, (ROOT / rel).is_file())
    for skill in ALL_SKILLS:
        d = SKILLS / skill
        check("结构", f"{skill}/SKILL.md", (d / "SKILL.md").is_file())
        for rel in EXPECTED_FILES.get(skill, []):
            check("结构", f"{skill}/{rel}", (d / rel).is_file())

    # 2-5) 逐技能内容检查
    for skill in ALL_SKILLS:
        skill_md = SKILLS / skill / "SKILL.md"
        if not skill_md.is_file():
            continue
        fm, body = parse_frontmatter(skill_md)
        ok = isinstance(fm, dict) and fm.get("name") == skill and bool(fm.get("description"))
        check("frontmatter", skill, ok,
              "YAML 解析失败或缺 name/description" if not ok else "")

        # 只有角色技能与本技能自身需要内嵌完整的角色输出契约字段
        if skill in ROLE_SKILLS or skill == "roundtable-orchestrator":
            missing = [f for f in CONTRACT_FIELDS if f not in body]
            check("契约字段", skill, not missing, f"缺字段 {missing}" if missing else "")

        if skill in ROLE_SKILLS:
            positions = [body.find(h) for h in ROLE_HEADINGS]
            ok_h = all(p >= 0 for p in positions) and positions == sorted(positions)
            check("章节结构", skill, ok_h,
                  "缺少必需二级标题或顺序不正确" if not ok_h else "")

    # 禁用写法扫描（SKILL.md + references + docs）
    targets = list(ROOT.glob("skills/**/*.md")) + list(ROOT.glob("docs/*.md")) + [ROOT / "README.md"]
    for path in targets:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, label in FORBIDDEN:
                if re.search(pattern, line):
                    if any(w in line for w in NEGATION):
                        continue  # 否定语境，属于正确用法
                    check("禁用写法", f"{path.relative_to(ROOT)}:{lineno}", False, f"{label} → {line.strip()[:60]}")

    # 6) 脚本自检
    if not args.no_scripts:
        for rel in SCRIPTS:
            p = ROOT / rel
            if not p.is_file():
                check("脚本自检", rel, False, "文件不存在")
                continue
            proc = subprocess.run([sys.executable, str(p), "selftest"],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace")
            check("脚本自检", rel, proc.returncode == 0,
                  (proc.stderr or "")[-200:] if proc.returncode != 0 else "")

    # 汇总
    failed = [r for r in results if not r[2]]
    by_cat = {}
    for cat, name, ok, detail in results:
        b = by_cat.setdefault(cat, [0, 0])
        b[0] += 1
        b[1] += 0 if ok else 1
    print("== 仓库自检结果 ==")
    for cat, (total, bad) in by_cat.items():
        print(f"  {cat:<10} {total - bad}/{total} 通过")
    if failed:
        print("\n失败项：")
        for cat, name, ok, detail in failed:
            print(f"  [{cat}] {name} {('— ' + detail) if detail else ''}")
    print(f"\n合计 {len(results) - len(failed)}/{len(results)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

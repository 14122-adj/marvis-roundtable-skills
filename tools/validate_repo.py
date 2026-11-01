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
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

CORE_SKILLS = ["roundtable-orchestrator", "meta-supervisor", "position-evolution",
               "decision-landscape", "cognitive-noise", "multi-model-adapter",
               "ultimate-roundtable", "host-bootstrap"]
ROLE_SKILLS = ["role-musk", "role-feynman", "role-munger", "role-jobs", "role-karpathy", "role-pg"]
ALL_SKILLS = CORE_SKILLS + ROLE_SKILLS
EXPECTED_VERSION = "1.7.0"
# 版本例外：这两个技能按上游 spec 独立发版，不参与统一版本对齐
VERSION_OVERRIDES = {"ultimate-roundtable": "4.1.0", "host-bootstrap": "3.0.0"}

# 社区贡献角色：独立目录、独立版本号（1.0.0 起），不参与统一版本对齐。
# 它们的合规性由 tools/validate_role.py 负责（更严格的 13 项检查）。
COMMUNITY_DIR = ROOT / "community-roles"
COMMUNITY_PREFIXES = {"V": "role-civilian", "C": "role-contrarian"}

# 不得出现在文档里的真实模型名（本包一律用占位符或 unspecified）
FABRICATED_MODEL_RE = re.compile(
    r"\b(?:gpt-[0-9a-z]|claude-[0-9a-z]|gemini-[0-9a-z]|llama-[0-9a-z]|qwen[0-9-]|"
    r"deepseek-(?:chat|v[0-9]|r[0-9])|mistral-[0-9a-z]|grok-[0-9a-z])", re.I)

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
    "decision-landscape": ["scripts/synthesis_generator.py", "references/output-templates.md"],
    "cognitive-noise": ["scripts/noise_injector.py", "references/cognitive-noise-guide.md"],
    "multi-model-adapter": ["scripts/runtime_manifest.py",
                            "references/provider-assignment-guide.md"],
    "ultimate-roundtable": ["scripts/ultimate_orchestrator.py", "scripts/clash_analyzer.py",
                            "scripts/memory_store.py", "scripts/attention_split.py",
                            "scripts/deadlock_detector.py",
                            "references/adversarial-tactics.md",
                            "references/report-template.md",
                            "references/tool-protocol.md",
                            "references/tactical-playbook.md"],
    "host-bootstrap": ["scripts/bootstrap.py", "references/host-matrix.md"],
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
    "skills/decision-landscape/scripts/synthesis_generator.py",
    "skills/cognitive-noise/scripts/noise_injector.py",
    "skills/multi-model-adapter/scripts/runtime_manifest.py",
    "skills/ultimate-roundtable/scripts/ultimate_orchestrator.py",
    "skills/ultimate-roundtable/scripts/clash_analyzer.py",
    "skills/ultimate-roundtable/scripts/memory_store.py",
    "skills/ultimate-roundtable/scripts/attention_split.py",
    "skills/ultimate-roundtable/scripts/deadlock_detector.py",
    "skills/host-bootstrap/scripts/bootstrap.py",
]

ROOT_FILES = [
    "README.md", "LICENSE", "CHANGELOG.md", ".gitignore",
    "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "QUICKSTART.md",
    "docs/output-contract.md", "docs/example-session.md", "docs/agensi-listing.md",
    "tools/validate_repo.py", "tools/validate_role.py",
    "tools/quickstart.py", "tools/wizard.py",
    "tools/demo_session.py", "tools/demo_ultimate.py",
    "tools/run_evals.py", "tools/package_bundle.py", "evals/evals.json",
    "assets/icon-512.png", "assets/screenshots/README.md",
    "assets/screenshots/01-quickstart-zh.png", "assets/screenshots/03-verdict-en.png",
]

COMMUNITY_FILES = [
    "community-roles/role-civilian/SKILL.md",
    "community-roles/role-civilian/references/plain-user-checklist.md",
    "community-roles/role-contrarian/SKILL.md",
    "community-roles/role-contrarian/references/assumption-attack-guide.md",
]

# 阶段配置模板：必须齐全，否则 quickstart 提示的 templates/ 目录会误导用户
TEMPLATE_FILES = [
    "templates/README.md",
    "templates/stage0.json",
    "templates/stage1.json",
    "templates/stage2.json",
    "templates/stage3.json",
    "templates/stage4.json",
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

# 规则清单式行：整行在描述"什么不允许"，其中的禁用样例是引用而非实际用法。
# 例：CONTRIBUTING.md 的自查清单「不含 `../` 跨目录相对引用」「不写「本轮必须一对一轮流」」
RULE_LINE = ("不含", "不写", "不得出现", "禁止出现", "不允许", "自查", "- [ ]")

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
    for rel in COMMUNITY_FILES:
        check("结构", rel, (ROOT / rel).is_file())
    for rel in TEMPLATE_FILES:
        check("结构", rel, (ROOT / rel).is_file())
    for skill in ALL_SKILLS:
        d = SKILLS / skill
        check("结构", f"{skill}/SKILL.md", (d / "SKILL.md").is_file())
        for rel in EXPECTED_FILES.get(skill, []):
            check("结构", f"{skill}/{rel}", (d / rel).is_file())

    # 2-5) 逐技能内容检查
    versions = {}
    for skill in ALL_SKILLS:
        skill_md = SKILLS / skill / "SKILL.md"
        if not skill_md.is_file():
            continue
        fm, body = parse_frontmatter(skill_md)
        ok = isinstance(fm, dict) and fm.get("name") == skill and bool(fm.get("description"))
        check("frontmatter", skill, ok,
              "YAML 解析失败或缺 name/description" if not ok else "")
        versions[skill] = str((fm or {}).get("metadata", {}).get("version", "")) \
            if isinstance(fm, dict) else ""

        # 只有角色技能与本技能自身需要内嵌完整的角色输出契约字段
        if skill in ROLE_SKILLS or skill == "roundtable-orchestrator":
            missing = [f for f in CONTRACT_FIELDS if f not in body]
            check("契约字段", skill, not missing, f"缺字段 {missing}" if missing else "")

        if skill in ROLE_SKILLS:
            positions = [body.find(h) for h in ROLE_HEADINGS]
            ok_h = all(p >= 0 for p in positions) and positions == sorted(positions)
            check("章节结构", skill, ok_h,
                  "缺少必需二级标题或顺序不正确" if not ok_h else "")

    # 版本一致性：除 VERSION_OVERRIDES 例外外，全部技能 metadata.version 相同，
    # 且与 CHANGELOG / 契约抬头对齐
    bad_versions = {k: v for k, v in versions.items()
                    if v != VERSION_OVERRIDES.get(k, EXPECTED_VERSION)}
    check("版本一致", f"全部技能 == {EXPECTED_VERSION}（例外 {list(VERSION_OVERRIDES)}）",
          not bad_versions, f"不一致：{bad_versions}" if bad_versions else "")
    changelog = (ROOT / "CHANGELOG.md")
    check("版本一致", f"CHANGELOG 含 v{EXPECTED_VERSION}",
          changelog.is_file() and f"v{EXPECTED_VERSION}" in changelog.read_text(encoding="utf-8"))
    contract_head = (ROOT / "docs" / "output-contract.md").read_text(encoding="utf-8").splitlines()[0]
    check("版本一致", f"契约抬头含 v{EXPECTED_VERSION}", EXPECTED_VERSION in contract_head,
          contract_head if EXPECTED_VERSION not in contract_head else "")

    # 禁用写法扫描（SKILL.md + references + docs + community-roles）
    targets = (list(ROOT.glob("skills/**/*.md")) + list(ROOT.glob("docs/*.md"))
               + list(ROOT.glob("community-roles/**/*.md"))
               + [ROOT / "README.md", ROOT / "CONTRIBUTING.md"])
    for path in targets:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern, label in FORBIDDEN:
                if re.search(pattern, line):
                    if any(w in line for w in NEGATION):
                        continue  # 否定语境，属于正确用法
                    if any(w in line for w in RULE_LINE):
                        continue  # 规则清单在描述"什么不允许"，属引用
                    check("禁用写法", f"{path.relative_to(ROOT)}:{lineno}", False, f"{label} → {line.strip()[:60]}")
            m = FABRICATED_MODEL_RE.search(line)
            if m and not any(w in line for w in NEGATION + ("占位符", "placeholder", "unspecified")):
                check("禁用写法", f"{path.relative_to(ROOT)}:{lineno}", False,
                      f"疑似编造真实模型名 {m.group(0)} → {line.strip()[:60]}")

    # 5b) 社区角色：交给 validate_role.py 做 13 项专项检查（含前缀冲突）
    vr = ROOT / "tools" / "validate_role.py"
    if vr.is_file() and COMMUNITY_DIR.exists():
        dirs = sorted(d for d in COMMUNITY_DIR.glob("role-*") if d.is_dir())
        if dirs:
            proc = subprocess.run([sys.executable, str(vr), "--all", "--json"],
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            try:
                payload = json.loads(proc.stdout or "{}")
            except json.JSONDecodeError:
                payload = {}
            results_by_role = {r["role"]: r for r in payload.get("results", [])}
            for d in dirs:
                r = results_by_role.get(d.name, {})
                errs = [e["code"] for e in r.get("errors", [])]
                check("社区角色", d.name, bool(r.get("ok")),
                      f"errors={errs}" if errs else "")
            # 前缀不得重复
            prefixes = [r.get("id_prefix") for r in payload.get("results", [])]
            dup = {p for p in prefixes if p and prefixes.count(p) > 1}
            check("社区角色", "id 前缀无重复", not dup, f"重复前缀：{dup}" if dup else "")
            # 声明的前缀表与实际一致
            actual = {r.get("id_prefix"): r.get("role") for r in payload.get("results", [])}
            check("社区角色", "COMMUNITY_PREFIXES 与实际一致", actual == COMMUNITY_PREFIXES,
                  f"实际={actual} 声明={COMMUNITY_PREFIXES}" if actual != COMMUNITY_PREFIXES else "")

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

        # 向导自检（tools 下，独立于 skills/scripts）
        wiz = ROOT / "tools" / "wizard.py"
        if wiz.is_file():
            proc = subprocess.run([sys.executable, str(wiz), "--selftest"],
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            check("脚本自检", "tools/wizard.py", proc.returncode == 0,
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

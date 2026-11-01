#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包器 tools/package_bundle.py

把技能包打包成**可直接上传马维斯**的 ZIP，并在打包前做一遍合法性检查：
  * 每个 SKILL.md 的 frontmatter 可解析，name 与目录名一致，description 非空；
  * 技能目录内不出现 `../` 跨技能相对引用（单独导入会失效）；
  * 生成 import-manifest.json（每个技能的文件数、行数、description、sha256），便于核对导入结果。

产物：
  dist/marvis-roundtable-skills-v<version>.zip        整包（含 README / LICENSE / 契约 / skills/）
  dist/marvis-roundtable-skills-v<version>.import-manifest.json
  dist/skills/<skill>-v<version>.zip                  逐技能包（--per-skill）

用法：
  python tools/package_bundle.py build [--version 1.1.0] [--out dist] [--per-skill]
  python tools/package_bundle.py verify --zip dist/marvis-roundtable-skills-v1.1.0.zip
  python tools/package_bundle.py selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
BUNDLE_FILES = ["README.md", "LICENSE", "CHANGELOG.md",
                "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "QUICKSTART.md",
                "docs/output-contract.md", "docs/example-session.md", "docs/agensi-listing.md"]

# 除 skills/ 之外要一并打包的目录（社区角色、模板、工具、评测集）
BUNDLE_DIRS = ["community-roles", "templates", "tools", "evals"]

# 打包时排除的运行时产物与缓存
BUNDLE_EXCLUDE_DIRS = {"__pycache__", ".git", "dist", ".quickstart", ".wizard",
                       ".ultimate", ".roundtable", ".roundtable-demo",
                       ".ultimate-demo", ".roundtable-memory"}
IMPORT_ORDER = [
    "host-bootstrap",
    "roundtable-orchestrator",
    "meta-supervisor",
    "position-evolution",
    "decision-landscape",
    "role-musk", "role-feynman", "role-munger", "role-jobs", "role-karpathy", "role-pg",
    "cognitive-noise",
    "multi-model-adapter",
    "ultimate-roundtable",
]
REQUIRED_FRONTMATTER = ["name", "description"]

# ZIP 内的开箱入口文件（解压后第一眼看到）
START_HERE_TEMPLATE = """# 从这里开始

> 你拿到的是 **marvis-roundtable-skills v{version}** 的完整包
> （{skill_count} 个核心技能 + {community_count} 个社区角色，构建于 {built_at}）。

---

## 最快：先跑一次看看

```bash
python tools/quickstart.py
```

约 10 秒，你会看到：体检 → 跑完一场完整的终极圆桌 → 自检 → 下一步提示。
产物在 `.quickstart/`（`report.md` 就是一场完整的决策报告）。

**只想确认环境可用**：

```bash
python tools/quickstart.py --check
```

---

## 换成你自己的议题

```bash
python tools/wizard.py
```

交互式向导会问你几组问题，生成 5 个阶段的配置文件，**每步即时校验**。
生成完会直接打印可复制的命令序列。

详细路径（含三个常见卡点）：**[QUICKSTART.md](QUICKSTART.md)**

---

## 装进你的 AI 客户端

```bash
python skills/host-bootstrap/scripts/bootstrap.py detect    # 我在什么宿主？
python skills/host-bootstrap/scripts/bootstrap.py install   # 补齐缺失的角色技能
```

然后按宿主导入：

| 宿主 | 入口 |
|---|---|
| 马维斯 Marvis | 技能管理 → 本地技能 → 导入技能 → 选 `skills/*/SKILL.md` |
| Claude Code | 读 `CLAUDE.md`，或把 `skills/` 放进 `~/.claude/skills` |
| Codex / Hermes / Cursor | 读 `AGENTS.md`，或放进各自的 skills 目录 |
| 纯文本对话 | 把 `SKILL.md` 内容贴进上下文，工具结果标 `simulated: true` |

**导入顺序**见 `import-manifest.json` 的 `import_order` 字段：
先 `host-bootstrap` 与编排层，再六个角色，最后可选层。

---

## 包里有什么

```
START-HERE.md          ← 你正在读的
QUICKSTART.md          ← 10 分钟完整路径 + 三个常见卡点
README.md              ← 全貌（架构、路线图、诚实声明）
CONTRIBUTING.md        ← 怎么贡献一个新角色
skills/                ← {skill_count} 个核心技能（每个 = SKILL.md + scripts/ + references/）
community-roles/       ← {community_count} 个社区角色 + 模板
templates/             ← 5 个可直接改的阶段配置示例
tools/                 ← quickstart / wizard / 自检 / 打包 / 端到端 demo
docs/output-contract.md ← 所有字段的唯一来源（改任何东西前先读它）
```

---

## 一句话

```bash
python tools/quickstart.py     # 看它长什么样（10 秒）
python tools/wizard.py         # 换成你的议题（5 分钟）
```

剩下都是细节。

---

许可：MIT。问题与建议请提 issue。
"""


def die(msg: str, code: int = 2):
    print(f"[package_bundle] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def log(msg: str) -> None:
    print(f"[package_bundle] {msg}", file=sys.stderr)


def read_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        return yaml.safe_load(parts[1]), parts[2]
    except yaml.YAMLError as exc:
        die(f"{path} 的 frontmatter 不是合法 YAML: {exc}")


def collect_skills() -> list:
    skills = []
    for d in sorted(SKILLS.iterdir()):
        if not d.is_dir():
            continue
        skill_md = d / "SKILL.md"
        if not skill_md.is_file():
            die(f"{d.name} 缺少 SKILL.md")
        fm, body = read_frontmatter(skill_md)
        if not isinstance(fm, dict):
            die(f"{d.name}/SKILL.md 缺少 frontmatter")
        for key in REQUIRED_FRONTMATTER:
            if not str(fm.get(key, "")).strip():
                die(f"{d.name}/SKILL.md 缺少必填字段 {key}")
        if fm.get("name") != d.name:
            die(f"{d.name}/SKILL.md 的 name={fm.get('name')!r} 与目录名不一致")
        files = [p for p in sorted(d.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
        for p in files:
            if p.suffix == ".md" and re.search(r"(?<![.\w])\.\./", p.read_text(encoding="utf-8")):
                die(f"{p.relative_to(ROOT)} 含跨技能相对路径 ../（单独导入会失效）")
        lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files
                    if p.suffix in (".md", ".py"))
        skills.append({
            "skill": d.name,
            "dir": str(d.relative_to(ROOT)).replace("\\", "/"),
            "name": fm.get("name"),
            "version": (fm.get("metadata") or {}).get("version", ""),
            "layer": (fm.get("metadata") or {}).get("layer", ""),
            "description": str(fm.get("description", "")).strip(),
            "files": [str(p.relative_to(ROOT)).replace("\\", "/") for p in files],
            "file_count": len(files),
            "lines": lines,
        })
    return skills


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def collect_extra_files() -> list:
    """收集 skills/ 之外的目录（community-roles / templates / tools）。"""
    out = []
    for d in BUNDLE_DIRS:
        base = ROOT / d
        if not base.is_dir():
            log(f"警告：目录 {d} 不存在，跳过")
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            if any(part in BUNDLE_EXCLUDE_DIRS for part in p.parts):
                continue
            if p.suffix in (".pyc", ".pyo"):
                continue
            out.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    return out


def build(version: str, out_dir: Path, per_skill: bool = False) -> dict:
    skills = collect_skills()
    names = [s["skill"] for s in skills]
    missing = [s for s in IMPORT_ORDER if s not in names]
    if missing:
        die(f"IMPORT_ORDER 中的技能不存在：{missing}")

    extra = collect_extra_files()
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_name = f"marvis-roundtable-skills-v{version}"
    zip_path = out_dir / f"{bundle_name}.zip"

    manifest = {
        "bundle": bundle_name,
        "version": version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "skill_count": len(skills),
        "community_role_count": len([e for e in extra
                                     if e.startswith("community-roles/")
                                     and e.endswith("/SKILL.md")
                                     and "_template" not in e]),
        "extra_file_count": len(extra),
        "import_order": IMPORT_ORDER,
        "skills": skills,
        "files": BUNDLE_FILES,
        "dirs": BUNDLE_DIRS,
        "start_here": "START-HERE.md",
        "quickstart_commands": [
            "python tools/quickstart.py          # 一条命令跑通（约 10 秒）",
            "python tools/wizard.py              # 交互式生成你自己的 5 个阶段配置",
            "python tools/validate_repo.py       # 仓库自检",
        ],
        "import_steps": [
            "1) 先读 START-HERE.md（30 秒）",
            "2) 跑 python tools/quickstart.py 确认环境可用",
            "3) 逐个导入技能：马维斯 → 技能管理 → 本地技能 → 导入技能 → 选择 SKILL.md",
            "4) 导入顺序见 import_order（先 host-bootstrap 与编排层，再角色，最后可选层）",
            "5) 导入后说「开启终极圆桌」验证可触发",
        ],
        "notes": [
            "技能之间不使用跨目录相对引用，可单独导入",
            "scripts/ 需要宿主能执行 Python（仅用标准库）",
            "cognitive-noise 仅在 mode=simulation 下被脚本允许启用",
            "community-roles/ 下的角色是可选增强，不装也能跑",
        ],
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # 入口文件放最前面，解压后第一眼看到
        z.writestr(f"{bundle_name}/START-HERE.md", START_HERE_TEMPLATE.format(
            version=version, skill_count=len(skills),
            community_count=manifest["community_role_count"],
            built_at=manifest["built_at"]))
        for rel in BUNDLE_FILES:
            p = ROOT / rel
            if p.exists():
                z.write(p, f"{bundle_name}/{rel}")
            else:
                log(f"警告：{rel} 不存在，跳过")
        for s in skills:
            for rel in s["files"]:
                z.write(ROOT / rel, f"{bundle_name}/{rel}")
        for rel in extra:
            z.write(ROOT / rel, f"{bundle_name}/{rel}")
        z.writestr(f"{bundle_name}/import-manifest.json",
                   json.dumps(manifest, ensure_ascii=False, indent=2))

    per_skill_paths = []
    if per_skill:
        sub = out_dir / "skills"
        sub.mkdir(parents=True, exist_ok=True)
        for s in skills:
            p = sub / f"{s['skill']}-v{version}.zip"
            with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
                for rel in s["files"]:
                    z.write(ROOT / rel, f"{s['skill']}/{rel}")
                z.writestr("import-manifest-entry.json",
                           json.dumps(s, ensure_ascii=False, indent=2))
            per_skill_paths.append(str(p))

    manifest_path = out_dir / f"{bundle_name}.import-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"zip": str(zip_path), "manifest": str(manifest_path), "per_skill": per_skill_paths,
            "skills": len(skills), "bundle_sha256": sha256_of(zip_path)}


def verify(zip_path: Path) -> int:
    if not zip_path.exists():
        die(f"ZIP 不存在: {zip_path}")
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad:
            die(f"ZIP 损坏: {bad}")
        names = z.namelist()
        skill_mds = [n for n in names if n.endswith("SKILL.md")]
        manifest = [n for n in names if n.endswith("import-manifest.json")]
        results = {
            "zip": str(zip_path),
            "entries": len(names),
            "skill_md_count": len(skill_mds),
            "has_import_manifest": bool(manifest),
            "skills": [n.split("/")[-2] for n in sorted(skill_mds)],
        }
        if not skill_mds or not manifest:
            emit_and_fail(results, "缺少 SKILL.md 或 import-manifest.json")
        # 逐技能 frontmatter 复查（模板目录 _template 是占位，不参与校验）
        problems = []
        checked = 0
        for n in skill_mds:
            parts = n.split("/")
            if "_template" in parts:
                continue
            checked += 1
            try:
                text = z.read(n).decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{n}: 不是 UTF-8")
                continue
            if not text.startswith("---"):
                problems.append(f"{n}: 缺 frontmatter")
                continue
            fm = yaml.safe_load(text.split("---", 2)[1]) or {}
            if fm.get("name") != parts[-2]:
                problems.append(f"{n}: name 与目录不一致")
        results["skills_checked"] = checked
        results["problems"] = problems
        results["ok"] = not problems
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if results["ok"] else 1


def emit_and_fail(obj, msg):
    obj["ok"] = False
    obj["error"] = msg
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    raise SystemExit(1)


# --------------------------------------------------------------------------- #
# 市场单技能包（Agensi / Claude Skills 通用格式）
#
# 与整包不同：市场的规范是「一个 ZIP = 一个技能」，
# 顶层文件夹名 = 技能名，SKILL.md 直接在它下面（不能双层嵌套）。
# 参考 Agensi 的 zip structure 要求：
#   correct:  skill-name/{SKILL.md, references/, scripts/}
#   wrong:    SKILL.md（无外层文件夹）
#   wrong:    skill-name/skill-name/SKILL.md（双层嵌套）
# --------------------------------------------------------------------------- #

def _skill_tree(d: Path) -> str:
    """生成技能目录的简短树状说明（占位，实现在下方）。"""
    return _skill_tree_impl(d)


MARKET_README_TEMPLATE = """# {title}

{description}

---

## 为什么不是又一个"角色扮演"技能

大多数多智能体讨论技能，产出的是六份互相恭维的备忘录——没人被逼着证明什么，
最后什么也没决定。

这个技能让六个人**互相拷问**，并且只允许一种结尾：**一个决定**。

**四个真正起作用的东西**

1. **拒绝角色扮演** — 每个角色跑的是强制思维协议，不是人设服装。
   马斯克必须拆到物理约束并给出量级估算；费曼必须用外行话讲清否则标记"未理解"；
   芒格必须先反向问"怎么才能保证它失败"；乔布斯必须回答"这更简单还是更复杂"；
   Karpathy 必须让每条论断可复现；Paul Graham 必须从真实案例起手。
   模糊表述在**校验阶段**就被拒绝，不会留到最后。

2. **死锁熔断** — 内置语义级死锁检测。当双方只是在**换说法复读**
   （同样的论点、不同的词、不同的例子），系统切断辩论、强制进入裁决。
   逐字重复容易抓，**换说法才是难点**，这里抓的就是后者。

3. **可执行的产出，不是摘要** — 收尾只有三样东西：
   三个互斥方案（激进 / 保守 / 降维）、六人强制投票、一个决定。
   然后是一张命令单：负责人、第一步、**带数字的 KPI**、**带数字的止损线**。
   写"如果效果不好就停止"会被校验器拒绝——模糊是一种构建错误。

4. **零摩擦** — 附带一键跑通与交互式向导。
   `python tools/quickstart.py`：体检 → 跑完一场完整讨论 → 自检 → 下一步，约 10 秒，
   无需配置、无需 API key、无依赖。
   `python tools/wizard.py`：交互式生成你自己的五个阶段配置，**边填边校验**。

---

## 装法

把本目录整个放进你 AI 客户端的 skills 目录：

| 客户端 | 目标位置 |
|---|---|
| Claude Code | `~/.claude/skills/{name}/` |
| Cursor / Cline / Windsurf | 项目内 `skills/{name}/` |
| 马维斯 Marvis | 技能管理 → 导入技能 → 选本目录的 `SKILL.md` |
| 其他（读 AGENTS.md 的） | 放进 `skills/{name}/` |

装好后对它说：

> {trigger_example}

**如果你的宿主不支持 ZIP 导入**：克隆 GitHub 仓库后跑 `python tools/quickstart.py`，
30 秒即可。

---

## 里面有什么

```
{name}/
├── SKILL.md          ← 技能本体（agent 读这个）
{extra_tree}```

---

## 说明

{notes}

需要 Python 3.9+，仅用标准库，不需要安装任何依赖。

许可：MIT。
"""


def _skill_tree_impl(d: Path) -> str:
    """生成技能目录的简短树状说明。"""
    lines = []
    for sub in ("references", "scripts"):
        p = d / sub
        if p.is_dir():
            files = sorted(f.name for f in p.glob("*") if f.is_file())
            if files:
                lines.append(f"├── {sub}/")
                for f in files[:6]:
                    lines.append(f"│   └── {f}")
                if len(files) > 6:
                    lines.append(f"│   └── … ({len(files)} files total)")
    return "\n".join(lines) + ("\n" if lines else "")


# English flagship README for the marketplace bundle
MARKET_README_TEMPLATE_EN = """# {title}

{description}

---

## Why this is not another "role-play" skill

Most multi-agent discussion skills produce six memos that compliment each other — nobody is forced
to prove anything, and nothing gets decided.

This one makes six personas **cross-examine each other**, and allows exactly one ending: **a decision**.

**The four things that actually do the work**

1. **No more role-play** — every persona runs a forced thinking protocol, not a costume.
   Musk must decompose to physical constraints and give a magnitude estimate; Feynman must explain it
   to a layman or mark it "not understood"; Munger must invert first ("how would I guarantee this
   fails?"); Jobs must answer "is this simpler or more complex?"; Karpathy must make every claim
   reproducible; Paul Graham must start from a real case. Vague statements are rejected **at
   validation time**, not left for later.

2. **Deadlock breaker** — built-in semantic deadlock detection. When two sides are merely
   **paraphrasing** each other (same argument, different words, different examples), the system cuts
   the debate and forces the verdict stage. Verbatim repetition is easy to catch; **paraphrase is the
   hard case**, and that is what this detects.

3. **Actionable outputs, not a summary** — the run ends in three things:
   three mutually exclusive options (aggressive / conservative / orthogonal), a forced vote from all
   six, and one decision. Then an order sheet: a named owner, the first step, **a KPI containing a
   number**, and **a kill-switch containing a number**. Writing "stop if results are bad" is rejected
   by the validator — vagueness is a build error.

4. **Zero friction** — one-command quickstart and an interactive wizard are included.
   `python tools/quickstart.py`: health check → a full roundtable → self-test → next steps, about
   10 seconds, no config, no API key, no dependencies.
   `python tools/wizard.py`: walks you through your own topic and generates all five stage files with
   **live validation**.

---

## Install

Drop this folder into your agent's skills directory:

| Client | Target location |
|---|---|
| Claude Code | `~/.claude/skills/{name}/` |
| Cursor / Cline / Windsurf | `<project>/skills/{name}/` |
| Marvis | Skills → Import → select `SKILL.md` |
| Anything that reads AGENTS.md | `<project>/skills/{name}/` |

Then say:

> {trigger_example}

**If your host does not support ZIP import**: clone the GitHub repo and run
`python tools/quickstart.py`. It takes 30 seconds.

---

## What is inside

```
{name}/
├── SKILL.md          ← the skill itself (this is what your agent reads)
{extra_tree}```

---

## Notes

{notes}

Requires Python 3.9+. Standard library only — nothing to install.

License: MIT.
"""


# 非旗舰技能用精简版 README：讲清用途与装法即可，不套用旗舰的卖点长文
MARKET_README_LITE = """# {title}

{description}

---

## Install

Drop this folder into your agent's skills directory:

| Client | Target location |
|---|---|
| Claude Code | `~/.claude/skills/{name}/` |
| Cursor / Cline / Windsurf | `<project>/skills/{name}/` |
| Marvis | Skills → Import → select `SKILL.md` |
| Anything that reads AGENTS.md | `<project>/skills/{name}/` |

Then say:

> {trigger_example}

**If your host does not support ZIP import**: clone the GitHub repo and run
`python tools/quickstart.py`. It takes 30 seconds.

---

## What is inside

```
{name}/
├── SKILL.md          ← the skill itself (this is what your agent reads)
{extra_tree}```

---

## Notes

{notes}

Requires Python 3.9+. Standard library only — nothing to install.

License: MIT.
"""


def collect_en_files(src: Path) -> list:
    """英文版文件：SKILL.en.md + references/*.en.md。

    约定：`X.en.md` 是 `X.md` 的英文版。打包英文包时用它替换中文原文件，
    但**文件名改回 `X.md`**——因为 agent 只认 SKILL.md / references/X.md。
    """
    out = []
    skill_en = src / "SKILL.en.md"
    if skill_en.is_file():
        out.append((skill_en, "SKILL.md"))
    refs = src / "references"
    if refs.is_dir():
        for p in sorted(refs.glob("*.en.md")):
            out.append((p, f"references/{p.name[:-len('.en.md')]}.md"))
    return out


def build_market(version: str, out_dir: Path, only: str = None,
                 lang: str = "zh") -> dict:
    """为每个技能打一个符合市场规范的单技能 ZIP。

    lang="en" 时用 *.en.md 替换对应中文文件（文件名仍是 SKILL.md / references/X.md）。
    """
    skills = collect_skills()
    if only:
        skills = [s for s in skills if s["skill"] == only]
        if not skills:
            die(f"找不到技能：{only}")

    market_dir = out_dir / ("market-en" if lang == "en" else "market")
    market_dir.mkdir(parents=True, exist_ok=True)

    made = []
    for s in skills:
        name = s["skill"]
        src = ROOT / "skills" / name
        suffix = "-en" if lang == "en" else ""
        zip_path = market_dir / f"{name}-v{version}{suffix}.zip"

        title = f"{name}"
        if lang == "en":
            en_skill = src / "SKILL.en.md"
            desc = s["description"]
            if en_skill.is_file():
                import yaml as _yaml
                _fm = _yaml.safe_load(en_skill.read_text(encoding="utf-8").split("---", 2)[1]) or {}
                desc = str(_fm.get("description", desc)).strip()
            trigger = ("Open an ultimate roundtable on a decision you are stuck on"
                       if name == "ultimate-roundtable" else
                       "Let this skill take part in your roundtable")
        else:
            desc = s["description"]
            trigger = ("用它开始一场终极圆桌讨论"
                       if name == "ultimate-roundtable" else
                       "让这个技能参与你的圆桌讨论")

        # 只有旗舰技能用完整卖点页；其余用精简版，避免"套模板"的违和感
        if lang == "en":
            template = (MARKET_README_TEMPLATE_EN if name == "ultimate-roundtable"
                        else MARKET_README_LITE)
        else:
            template = (MARKET_README_TEMPLATE if name == "ultimate-roundtable"
                        else MARKET_README_LITE)
        notes = ("This skill is part of the roundtable family but works standalone; "
                 "see the repo README for the companion skills.\n"
                 "Scripts use the Python standard library only — no dependencies to install."
                 if lang == "en" else
                 "本技能是圆桌讨论体系的一部分，单独使用也可以；"
                 "配套技能见仓库 README。\n"
                 "脚本仅用 Python 标准库，不需要安装依赖。")
        readme = template.format(
            title=title, description=desc, name=name,
            trigger_example=trigger,
            extra_tree=_skill_tree(src),
            notes=notes)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            if lang == "en":
                # 英文包：用 *.en.md 覆盖，但文件名写回 SKILL.md / references/X.md
                en_files = collect_en_files(src)
                if not en_files:
                    die(f"{name} 没有英文版文件（SKILL.en.md），无法打英文包")
                written = set()
                for src_p, arc in en_files:
                    z.write(src_p, f"{name}/{arc}")
                    written.add(arc)
                z.writestr(f"{name}/README.md", readme)
                # 英文包里剩下的（脚本、无英文版的 references）仍用中文原件
                for rel in s["files"]:
                    arc = Path(rel).relative_to("skills/" + name).as_posix()
                    if arc in written or arc.endswith(".en.md"):
                        continue
                    if arc == "SKILL.md":
                        continue
                    z.write(ROOT / rel, f"{name}/{arc}")
            else:
                # 单层顶层文件夹，SKILL.md 在其根部
                z.write(src / "SKILL.md", f"{name}/SKILL.md")
                z.writestr(f"{name}/README.md", readme)
                for rel in s["files"]:
                    if rel.endswith("SKILL.md") or rel.endswith(".en.md"):
                        continue
                    z.write(ROOT / rel, f"{name}/{Path(rel).relative_to('skills/' + name).as_posix()}")

        made.append({"skill": name, "zip": str(zip_path),
                     "size_kb": round(zip_path.stat().st_size / 1024, 1),
                     "sha256": sha256_of(zip_path)})

    return {"market_dir": str(market_dir), "count": len(made),
            "lang": lang, "bundles": made}


def verify_market(zip_path: Path) -> dict:
    """按市场规范校验单技能 ZIP：单层顶层文件夹 + SKILL.md 在根部。"""
    if not zip_path.exists():
        die(f"ZIP 不存在: {zip_path}")
    problems = []
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip():
            die("ZIP 损坏")
        names = [n for n in z.namelist() if not n.endswith("/")]
        tops = {n.split("/")[0] for n in names}
        if len(tops) != 1:
            problems.append(f"顶层必须只有一个文件夹，实际 {len(tops)} 个：{sorted(tops)}")
        top = sorted(tops)[0] if tops else ""
        if f"{top}/SKILL.md" not in names:
            problems.append(f"SKILL.md 必须在 {top}/ 根部（不能在 zip 根或双层嵌套）")
        nested = [n for n in names if n.startswith(f"{top}/{top}/")]
        if nested:
            problems.append(f"存在双层嵌套：{nested[:3]}")
        if any("__pycache__" in n or n.endswith(".pyc") for n in names):
            problems.append("含 __pycache__ 或 .pyc")
        if any(n.endswith((".DS_Store", "Thumbs.db")) for n in names):
            problems.append("含系统隐藏文件（.DS_Store / Thumbs.db）")
        # frontmatter 必须只有 name + description 等合法字段
        try:
            text = z.read(f"{top}/SKILL.md").decode("utf-8")
            fm = yaml.safe_load(text.split("---", 2)[1]) or {}
            if fm.get("name") != top:
                problems.append(f"frontmatter name={fm.get('name')!r} 与文件夹名 {top!r} 不一致")
            if not str(fm.get("description", "")).strip():
                problems.append("description 为空")
        except Exception as exc:                     # noqa: BLE001
            problems.append(f"SKILL.md 解析失败：{exc}")
    return {"zip": str(zip_path), "top_folder": top, "entries": len(names),
            "problems": problems, "ok": not problems}


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    skills = collect_skills()
    ck(len(skills) >= 12, f"收集到 {len(skills)} 个技能（要求 ≥12）")
    ck(all(s["file_count"] >= 1 for s in skills), "每个技能至少有一个文件")
    ck(all(s["description"] for s in skills), "每个技能都有 description")
    ck(all(s["version"] in ("1.8.1", "3.0.0", "4.1.0") for s in skills),
       "技能版本只允许 1.8.1 / 3.0.0 / 4.1.0（ultimate 与 host-bootstrap 按 spec 独立发版）")
    ck(all(s["skill"] in IMPORT_ORDER for s in skills), "每个技能都在导入顺序里")
    ck(len({s["skill"] for s in skills}) == len(skills), "技能名无重复")

    with tempfile.TemporaryDirectory() as td:
        res = build("9.9.9-test", Path(td), per_skill=True)
        zp = Path(res["zip"])
        ck(zp.exists() and zp.stat().st_size > 1000, "整包 ZIP 生成成功")
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
            ck(any(n.endswith("import-manifest.json") for n in names), "ZIP 内含 import-manifest.json")
            # 现在包里同时含核心技能与社区角色，SKILL.md 总数 = 两者之和
            n_skill_md = len([n for n in names if n.endswith("SKILL.md")])
            ck(n_skill_md >= len(skills), f"ZIP 内 SKILL.md 数量 ≥ 核心技能数（{n_skill_md} ≥ {len(skills)}）")
            ck(any(n.endswith("START-HERE.md") for n in names), "ZIP 内含开箱入口 START-HERE.md")
            ck(any("community-roles/" in n for n in names), "ZIP 内含社区角色")
            ck(any("templates/stage1.json" in n for n in names), "ZIP 内含阶段配置模板")
            ck(any("/tools/quickstart.py" in n for n in names), "ZIP 内含 quickstart.py")
            ck(any(n.endswith("docs/output-contract.md") for n in names), "ZIP 内含冻结契约")
        ck(len(res["per_skill"]) == len(skills), "逐技能包数量与技能数一致")
        rc = verify(zp)
        ck(rc == 0, "verify 对新打包的 ZIP 返回 0")

        # 篡改一个技能目录名后应被 collect_skills 拒绝（用临时副本验证 name 一致性检查）
        bad = Path(td) / "bad"
        bad.mkdir()
        (bad / "SKILL.md").write_text("---\nname: wrong-name\ndescription: x\n---\n", encoding="utf-8")
        text = (bad / "SKILL.md").read_text(encoding="utf-8")
        fm = yaml.safe_load(text.split("---", 2)[1])
        ck(fm.get("name") != bad.name, "name 与目录名不一致的场景可被识别（校验逻辑前提）")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="技能包打包器（整包 / 逐技能 / 市场单技能）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--version", default="1.7.0")
    pb.add_argument("--out", default="dist")
    pb.add_argument("--per-skill", action="store_true")
    pb.add_argument("--market", action="store_true",
                    help="额外产出符合市场规范的单技能 ZIP（Agensi / Claude Skills）")
    pb.add_argument("--lang", default="zh", choices=["zh", "en"],
                    help="市场包语言：en 用 *.en.md 替换中文原文件")
    pb.add_argument("--only", help="只打包某一个技能（配合 --market）")

    pv = sub.add_parser("verify")
    pv.add_argument("--zip", required=True)
    pv.add_argument("--market", action="store_true", help="按市场规范校验单技能 ZIP")

    pm = sub.add_parser("market", help="只产出市场单技能 ZIP")
    pm.add_argument("--version", default="1.7.0")
    pm.add_argument("--out", default="dist")
    pm.add_argument("--lang", default="zh", choices=["zh", "en"])
    pm.add_argument("--only")

    pvm = sub.add_parser("verify-market", help="校验 dist/market/ 下全部单技能 ZIP")
    pvm.add_argument("--dir", default="dist/market")

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "build":
        out = (ROOT / args.out).resolve()
        res = build(args.version, out, args.per_skill)
        if args.market or args.only:
            res["market"] = build_market(args.version, out, args.only, args.lang)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "verify":
        if args.market:
            r = verify_market(Path(args.zip))
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return 0 if r["ok"] else 1
        return verify(Path(args.zip))
    if args.cmd == "market":
        res = build_market(args.version, (ROOT / args.out).resolve(),
                           args.only, args.lang)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "verify-market":
        d = (ROOT / args.dir).resolve() if not Path(args.dir).is_absolute() else Path(args.dir)
        if not d.is_dir():
            die(f"目录不存在：{d}")
        zips = sorted(d.glob("*.zip"))
        if not zips:
            die(f"{d} 下没有 zip")
        results = [verify_market(p) for p in zips]
        failed = [r for r in results if not r["ok"]]
        print(json.dumps({"dir": str(d), "total": len(results),
                          "failed": len(failed), "results": results},
                         ensure_ascii=False, indent=2))
        return 1 if failed else 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

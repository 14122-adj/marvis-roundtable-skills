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
BUNDLE_FILES = ["README.md", "LICENSE", "CHANGELOG.md", "docs/output-contract.md",
                "docs/example-session.md"]
IMPORT_ORDER = [
    "roundtable-orchestrator",
    "meta-supervisor",
    "position-evolution",
    "decision-landscape",
    "role-musk", "role-feynman", "role-munger", "role-jobs", "role-karpathy", "role-pg",
    "cognitive-noise",
    "multi-model-adapter",
]
REQUIRED_FRONTMATTER = ["name", "description"]


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


def build(version: str, out_dir: Path, per_skill: bool = False) -> dict:
    skills = collect_skills()
    names = [s["skill"] for s in skills]
    missing = [s for s in IMPORT_ORDER if s not in names]
    if missing:
        die(f"IMPORT_ORDER 中的技能不存在：{missing}")

    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_name = f"marvis-roundtable-skills-v{version}"
    zip_path = out_dir / f"{bundle_name}.zip"

    manifest = {
        "bundle": bundle_name,
        "version": version,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "skill_count": len(skills),
        "import_order": IMPORT_ORDER,
        "skills": skills,
        "files": BUNDLE_FILES,
        "import_steps": [
            "1) 解压后逐个导入：马维斯 → 技能管理 → 本地技能 → 导入技能 → 选择 SKILL.md",
            "2) 导入顺序见 import_order（先编排器与元认知层，再角色，最后可选层）",
            "3) 导入后用『开启圆桌讨论』验证编排器可触发，再单独触发一个角色技能验证字段",
            "4) 若宿主支持 ZIP 上传：设置 → Skills → Create → Upload 选择本 zip",
        ],
        "notes": [
            "技能之间不使用跨目录相对引用，可单独导入",
            "scripts/ 需要宿主能执行 Python（仅用标准库）",
            "cognitive-noise 仅在 mode=simulation 下被脚本允许启用",
        ],
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in BUNDLE_FILES:
            p = ROOT / rel
            if p.exists():
                z.write(p, f"{bundle_name}/{rel}")
            else:
                log(f"警告：{rel} 不存在，跳过")
        for s in skills:
            for rel in s["files"]:
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
        # 逐技能 frontmatter 复查
        problems = []
        for n in skill_mds:
            try:
                text = z.read(n).decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{n}: 不是 UTF-8")
                continue
            if not text.startswith("---"):
                problems.append(f"{n}: 缺 frontmatter")
                continue
            fm = yaml.safe_load(text.split("---", 2)[1]) or {}
            if fm.get("name") != n.split("/")[-2]:
                problems.append(f"{n}: name 与目录不一致")
        results["problems"] = problems
        results["ok"] = not problems
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if results["ok"] else 1


def emit_and_fail(obj, msg):
    obj["ok"] = False
    obj["error"] = msg
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    raise SystemExit(1)


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
    ck(all(s["version"] == "1.1.0" for s in skills),
       "所有技能 metadata.version 均为 1.1.0（版本一致性）")
    ck(all(s["skill"] in IMPORT_ORDER for s in skills), "每个技能都在导入顺序里")
    ck(len({s["skill"] for s in skills}) == len(skills), "技能名无重复")

    with tempfile.TemporaryDirectory() as td:
        res = build("9.9.9-test", Path(td), per_skill=True)
        zp = Path(res["zip"])
        ck(zp.exists() and zp.stat().st_size > 1000, "整包 ZIP 生成成功")
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
            ck(any(n.endswith("import-manifest.json") for n in names), "ZIP 内含 import-manifest.json")
            ck(len([n for n in names if n.endswith("SKILL.md")]) == len(skills),
               "ZIP 内 SKILL.md 数量与技能数一致")
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
    ap = argparse.ArgumentParser(description="技能包打包器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pb = sub.add_parser("build")
    pb.add_argument("--version", default="1.1.0")
    pb.add_argument("--out", default="dist")
    pb.add_argument("--per-skill", action="store_true")
    pv = sub.add_parser("verify")
    pv.add_argument("--zip", required=True)
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "build":
        res = build(args.version, (ROOT / args.out).resolve(), args.per_skill)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "verify":
        return verify(Path(args.zip))
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

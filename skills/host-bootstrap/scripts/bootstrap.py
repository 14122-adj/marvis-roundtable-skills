#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主检测与技能自动部署 bootstrap.py

解决的问题：这套技能原本是给马维斯用的。换到 Claude Code / Codex / Hermes 或任何
其他 AI 上时，**六个角色技能（role-*）不一定存在**，而终极圆桌依赖它们。

本脚本提供三件事：

  1. `detect`  —— 判断当前是什么宿主、技能装在哪、六个角色技能是否就绪；
  2. `install` —— 缺什么补什么：优先从本地仓库复制，其次从 GitHub 拉取，都不行就打印手工步骤；
  3. `verify`  —— 校验六个角色技能可用（frontmatter 合法、关键字段齐全）。

诚实边界：
  * 自动安装**只做文件复制/下载**，不修改宿主的配置或重启宿主；
  * 没有网络、没有 git 时，`install` 会退化为"打印手工部署清单"，不会假装成功；
  * 马维斯（Marvis）的技能目录如果找不到，会被明确报告为"未检测到"，不猜测路径。

用法：
  python bootstrap.py detect  [--repo PATH] [--json]
  python bootstrap.py install [--repo PATH] [--target DIR] [--source auto|local|github] [--dry-run]
  python bootstrap.py verify  [--repo PATH] [--target DIR]
  python bootstrap.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

SIX_ROLES = ["role-musk", "role-feynman", "role-munger",
             "role-jobs", "role-karpathy", "role-pg"]
REPO_URL = "https://github.com/14122-adj/marvis-roundtable-skills"
REPO_RAW = "https://raw.githubusercontent.com/14122-adj/marvis-roundtable-skills/main"
GIT_SSH = "git@github.com:14122-adj/marvis-roundtable-skills.git"
GIT_HTTPS = REPO_URL + ".git"

ROLE_FILES = {
    "role-musk": ["SKILL.md", "references/first-principles-examples.md"],
    "role-feynman": ["SKILL.md", "references/explanation-verification.md"],
    "role-munger": ["SKILL.md", "references/mental-models-catalog.md"],
    "role-jobs": ["SKILL.md", "references/simplicity-criteria.md"],
    "role-karpathy": ["SKILL.md", "references/system-decomposition-guide.md"],
    "role-pg": ["SKILL.md", "references/case-based-reasoning.md"],
}

# 宿主的技能目录候选（相对用户目录），顺序即优先级
HOST_HINTS = [
    ("claude", "Claude Code / Claude", [".claude/skills", ".config/claude/skills"]),
    ("codex", "Codex (ChatGPT)", [".codex/skills", ".config/codex/skills"]),
    ("hermes", "Hermes", [".hermes/skills", ".config/hermes/skills"]),
    ("marvis", "马维斯 Marvis", [".marvis/skills", ".config/marvis/skills",
                                 "AppData/Roaming/marvis/skills"]),
    ("dsh", "DeepSeek Harness", [".dsh/skills"]),
    ("agents", "通用 Agent Skills 约定", [".agent/skills", "skills"]),
]

MARKER_FILES = [
    ("claude", ["CLAUDE.md", ".claude", "claude_desktop_config.json"]),
    ("codex", ["AGENTS.md", ".codex", "codex.toml"]),
    ("hermes", [".hermes", "hermes.toml"]),
    ("marvis", [".marvis", "marvis.toml"]),
    ("dsh", [".dsh", "DSH.md"]),
]


def log(msg: str) -> None:
    print(f"[bootstrap] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[bootstrap] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- #
# 仓库定位
# --------------------------------------------------------------------------- #


def find_repo(explicit: str | None = None) -> Path | None:
    """定位技能仓库根目录（含 skills/ 的那一层）。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    here = Path(__file__).resolve()
    candidates.append(here.parents[3])          # skills/host-bootstrap/scripts → 仓库根
    candidates.append(here.parents[2])
    candidates.append(Path.cwd())
    for c in candidates:
        try:
            c = c.resolve()
        except OSError:
            continue
        if (c / "skills").is_dir() and (c / "skills" / "role-musk").is_dir():
            return c
    return None


# --------------------------------------------------------------------------- #
# 宿主检测
# --------------------------------------------------------------------------- #


def detect_host(repo: Path | None) -> dict:
    home = Path.home()
    found = []

    # 1) 环境变量线索
    env_marks = []
    for var, key in (("CLAUDE_CODE_ENTRYPOINT", "claude"), ("CLAUDECODE", "claude"),
                     ("CODEX_HOME", "codex"), ("HERMES_HOME", "hermes"),
                     ("MARVIS_HOME", "marvis"), ("DSH_ROOT", "dsh"),
                     ("TERM_PROGRAM", None)):
        val = os.environ.get(var)
        if val:
            if key:
                env_marks.append({"host": key, "evidence": f"env {var}={val}"})
            elif "vscode" in val.lower():
                env_marks.append({"host": "vscode", "evidence": f"env {var}={val}"})

    # 2) 文件线索
    file_marks = []
    for key, names in MARKER_FILES:
        for n in names:
            if (home / n).exists() or (Path.cwd() / n).exists():
                file_marks.append({"host": key, "evidence": f"找到 {n}"})
                break

    # 3) 技能目录
    skill_dirs = {}
    for key, label, rels in HOST_HINTS:
        for rel in rels:
            p = home / rel
            if p.is_dir():
                skill_dirs.setdefault(key, []).append(str(p))
        for rel in rels:
            p = Path.cwd() / rel
            if p.is_dir() and str(p) not in skill_dirs.get(key, []):
                skill_dirs.setdefault(key, []).append(str(p))

    # 4) 汇总
    seen = set()
    for m in env_marks + file_marks:
        if m["host"] not in seen:
            found.append({"host": m["host"], "evidence": m["evidence"]})
            seen.add(m["host"])

    primary = found[0]["host"] if found else "unknown"
    label = dict((k, l) for k, l, _ in HOST_HINTS).get(primary, "未知宿主 / 通用环境")

    return {
        "host": primary,
        "host_label": label,
        "evidence": found,
        "skill_dirs": skill_dirs,
        "recommended_target": (skill_dirs.get(primary) or
                               [str(Path.cwd() / "skills")])[0],
        "repo": str(repo) if repo else None,
        "repo_found": bool(repo),
    }


def check_roles(root: Path) -> dict:
    """检查某个目录下的六个角色技能是否就绪。"""
    status = {}
    for role in SIX_ROLES:
        d = root / role
        md = d / "SKILL.md"
        entry = {"installed": md.is_file(), "path": str(d), "missing_files": [],
                 "frontmatter_ok": False, "name_ok": False}
        if md.is_file():
            text = md.read_text(encoding="utf-8", errors="replace")
            if text.startswith("---") and text.count("---") >= 2:
                fm = text.split("---", 2)[1]
                entry["frontmatter_ok"] = "description:" in fm
                m = re.search(r"^name:\s*(\S+)", fm, re.M)
                entry["name_ok"] = bool(m and m.group(1) == role)
            for rel in ROLE_FILES.get(role, []):
                if not (d / rel).is_file():
                    entry["missing_files"].append(rel)
        status[role] = entry
    ready = [r for r, e in status.items()
             if e["installed"] and e["frontmatter_ok"] and e["name_ok"] and not e["missing_files"]]
    return {
        "root": str(root),
        "roles": status,
        "ready": ready,
        "missing": [r for r in SIX_ROLES if r not in ready],
        "all_ready": len(ready) == len(SIX_ROLES),
    }


# --------------------------------------------------------------------------- #
# 安装
# --------------------------------------------------------------------------- #


def _copy_role(repo: Path, role: str, target: Path) -> dict:
    src = repo / "skills" / role
    dst = target / role
    copied = []
    for rel in ROLE_FILES.get(role, []):
        s = src / rel
        if not s.is_file():
            return {"role": role, "ok": False, "error": f"源文件缺失：{s}"}
        d = dst / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        copied.append(rel)
    return {"role": role, "ok": True, "target": str(dst), "copied": copied}


def _download_role(role: str, target: Path, timeout: int = 20) -> dict:
    dst = target / role
    copied = []
    for rel in ROLE_FILES.get(role, []):
        url = f"{REPO_RAW}/skills/{role}/{rel}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {"role": role, "ok": False, "error": f"下载失败 {url}: {exc}"}
        d = dst / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(data)
        copied.append(rel)
    return {"role": role, "ok": True, "target": str(dst), "copied": copied}


def _git_clone(tmp: Path) -> tuple:
    """尝试 git clone（先 SSH 再 HTTPS），返回 (repo_path, 说明)。"""
    for url, name in ((GIT_SSH, "ssh"), (GIT_HTTPS, "https")):
        try:
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet", url, str(tmp / name)],
                capture_output=True, text=True, timeout=120)
            if proc.returncode == 0:
                return tmp / name, f"git clone（{name}）成功"
            err = (proc.stderr or "").strip().splitlines()
            log(f"git clone {name} 失败：{err[-1] if err else 'unknown'}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            log(f"git clone {name} 不可用：{exc}")
    return None, "git clone 失败（SSH 与 HTTPS 均不可用）"


def install(repo: Path | None, target: Path, source: str = "auto",
            dry_run: bool = False) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    before = check_roles(target)
    todo = before["missing"]
    actions = []

    if not todo:
        return {"ok": True, "target": str(target), "actions": [],
                "message": "六个角色技能已全部就绪，无需安装", "verified": before}

    def do_copy(src_repo: Path, how: str):
        for role in todo:
            if dry_run:
                actions.append({"role": role, "action": f"would copy from {src_repo}",
                                "ok": True})
            else:
                actions.append(_copy_role(src_repo, role, target))

    def do_download():
        for role in todo:
            if dry_run:
                actions.append({"role": role, "action": "would download from GitHub", "ok": True})
            else:
                actions.append(_download_role(role, target))

    if source in ("auto", "local") and repo:
        do_copy(repo, "local")
    elif source in ("auto", "github"):
        if source == "github":
            do_download()
        else:
            with tempfile.TemporaryDirectory() as td:
                cloned, note = _git_clone(Path(td))
                if cloned:
                    do_copy(cloned, "git")
                    actions.append({"action": note, "ok": True})
                else:
                    log("git clone 不可用，退回 HTTP 逐文件下载")
                    do_download()
                    actions.append({"action": note, "ok": False})

    if dry_run:
        return {"ok": True, "dry_run": True, "target": str(target),
                "todo": todo, "actions": actions,
                "message": "预演模式：未写入任何文件"}

    after = check_roles(target)
    ok = after["all_ready"]
    result = {"ok": ok, "target": str(target), "actions": actions,
              "installed": after["ready"], "still_missing": after["missing"],
              "verified": after}
    if not ok:
        result["manual_steps"] = manual_steps(target, after["missing"])
    return result


def manual_steps(target: Path, missing: list) -> list:
    steps = [
        f"目标目录：{target}",
        "方式一（有 git）：",
        f"  git clone {GIT_HTTPS} /tmp/mrs",
        f"  cp -r /tmp/mrs/skills/{'{' + ','.join(missing) + '}'} {target}/",
        "方式二（无 git，逐文件下载）：",
    ]
    for role in missing:
        for rel in ROLE_FILES.get(role, []):
            steps.append(f"  curl -L {REPO_RAW}/skills/{role}/{rel} "
                         f"-o {target}/{role}/{rel}")
    steps.append("方式三（宿主机支持 ZIP 上传）：下载仓库 dist/ 下的技能包直接导入")
    steps.append(f"仓库地址：{REPO_URL}")
    return steps


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def cmd_detect(args) -> int:
    repo = find_repo(args.repo)
    host = detect_host(repo)
    local = check_roles(repo / "skills") if repo else None
    installed_anywhere = {}
    for key, dirs in host["skill_dirs"].items():
        for d in dirs:
            installed_anywhere[d] = check_roles(Path(d))["ready"]

    payload = {
        "host": host,
        "repo_roles": local,
        "installed_roles_by_dir": installed_anywhere,
        "verdict": ("ok" if (local and local["all_ready"]) else "needs_install"),
        "next": ("可直接使用 ultimate-roundtable" if local and local["all_ready"]
                 else "运行 bootstrap.py install 部署六个角色技能"),
    }
    if args.json:
        emit(payload)
    else:
        print(f"宿主：{host['host_label']}（{host['host']}）")
        for e in host["evidence"]:
            print(f"  - 依据：{e['evidence']}")
        if not host["evidence"]:
            print("  - 依据：未发现明确宿主标识（按通用环境处理）")
        print(f"仓库：{host['repo'] or '未找到'}")
        if local:
            print(f"仓库内角色技能：{len(local['ready'])}/6 就绪")
            if local["missing"]:
                print(f"  缺失：{', '.join(local['missing'])}")
        if installed_anywhere:
            print("已安装目录：")
            for d, ready in installed_anywhere.items():
                print(f"  - {d}：{len(ready)}/6")
        print(f"建议目标目录：{host['recommended_target']}")
        print(f"结论：{payload['next']}")
    return 0 if payload["verdict"] == "ok" else 1


def cmd_install(args) -> int:
    repo = find_repo(args.repo)
    host = detect_host(repo)
    target = Path(args.target).expanduser() if args.target else Path(host["recommended_target"])
    if not repo and args.source == "local":
        die("--source local 需要能定位到仓库（用 --repo 指定）")
    result = install(repo, target, args.source, args.dry_run)
    emit(result)
    if not result["ok"] and not args.dry_run:
        print("\n手工部署步骤：", file=sys.stderr)
        for s in result.get("manual_steps", []):
            print(f"  {s}", file=sys.stderr)
        return 1
    return 0


def cmd_verify(args) -> int:
    repo = find_repo(args.repo)
    target = Path(args.target).expanduser() if args.target else (
        repo / "skills" if repo else Path.cwd() / "skills")
    res = check_roles(target)
    emit(res)
    if not res["all_ready"]:
        log(f"缺少：{', '.join(res['missing'])}　建议运行：bootstrap.py install")
    return 0 if res["all_ready"] else 1


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    repo = find_repo(None)
    ck(repo is not None, "能自动定位到仓库根目录")
    if repo:
        res = check_roles(repo / "skills")
        ck(res["all_ready"], "仓库内六个角色技能全部就绪")
        ck(len(res["ready"]) == 6, "六个角色技能都被识别")
        ck(all(res["roles"][r]["frontmatter_ok"] for r in SIX_ROLES),
           "每个角色技能 frontmatter 含 description")
        ck(all(res["roles"][r]["name_ok"] for r in SIX_ROLES),
           "每个角色技能 name 与目录名一致")

    host = detect_host(repo)
    ck("host" in host and "recommended_target" in host, "宿主检测返回必需字段")

    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "skills"
        empty.mkdir()
        before = check_roles(empty)
        ck(before["all_ready"] is False and len(before["missing"]) == 6,
           "空目录时判定六个全缺")

        dry = install(repo, empty, "local", dry_run=True)
        ck(dry["ok"] and dry["dry_run"], "dry-run 返回成功但未写入")
        ck(not (empty / "role-musk").exists(), "dry-run 确实没有创建目录")

        res = install(repo, empty, "local")
        ck(res["ok"] and not res["still_missing"], "本地复制安装成功")
        ck((empty / "role-musk" / "SKILL.md").is_file(), "role-musk/SKILL.md 已复制")
        ck((empty / "role-musk" / "references" / "first-principles-examples.md").is_file(),
           "role-musk 的 references 也被复制（不只是 SKILL.md）")
        after = check_roles(empty)
        ck(after["all_ready"], "安装后校验通过")

        again = install(repo, empty, "local")
        ck(again["ok"] and again["actions"] == [], "已就绪时幂等，不重复安装")

        # 破坏一个技能后应被检出
        (empty / "role-pg" / "SKILL.md").unlink()
        broken = check_roles(empty)
        ck(broken["missing"] == ["role-pg"], "删除 SKILL.md 后能被检出缺失")

        steps = manual_steps(empty, ["role-pg"])
        ck(any("curl" in s for s in steps), "手工步骤包含下载命令")
        ck(any(REPO_URL in s for s in steps), "手工步骤包含仓库地址")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="宿主检测与角色技能自动部署")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("detect")
    pd.add_argument("--repo")
    pd.add_argument("--json", action="store_true")

    pi = sub.add_parser("install")
    pi.add_argument("--repo")
    pi.add_argument("--target")
    pi.add_argument("--source", default="auto", choices=["auto", "local", "github"])
    pi.add_argument("--dry-run", action="store_true")

    pv = sub.add_parser("verify")
    pv.add_argument("--repo")
    pv.add_argument("--target")

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "detect":
        return cmd_detect(args)
    if args.cmd == "install":
        return cmd_install(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

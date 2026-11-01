#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社区角色协议校验器 validate_role.py

社区贡献的角色技能（community-roles/role-*）必须满足契约，否则接进圆桌就会污染状态文件。
本工具把"这个角色能不能用"变成可判定的检查，而不是维护者的个人口味。

检查项（分三级）：

  ERROR（必须修，否则不能合入）
    1. SKILL.md 存在且 frontmatter 可解析
    2. name 与目录名一致
    3. description 非空
    4. 9 个必需二级标题齐全且顺序正确
    5. 契约 §3 全部字段名出现（role/round/position/claims/responses/
       blind_spot_declared/epistemic_status/confidence/uncertainty_points/will_revise_if）
    6. 明确声明 claim id 前缀，且该前缀未被其他角色占用
    7. 7 个 basis 枚举全部出现
    8. 引用自己的 references/ 时文件真实存在
    9. 无跨技能相对路径 `../`

  WARN（建议修，不阻塞）
    10. references/ 下有参考手册（推荐但不是必须）
    11. 正文行数在 120–400 之间
    12. 有「已知盲区」章节且至少 3 条

  INFO
    13. 与现有角色的天然张力是否被提及

用法：
  python tools/validate_role.py community-roles/role-civilian
  python tools/validate_role.py --all                      # 校验所有社区角色
  python tools/validate_role.py --all --json
  python tools/validate_role.py selftest
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
COMMUNITY = ROOT / "community-roles"

REQUIRED_HEADINGS = [
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

BASIS_ENUM = [
    "physical_constraint", "empirical", "case", "mechanism",
    "analogy", "value_judgment", "intuition",
]

# 已被占用的 id 前缀（六个原始角色 + 社区角色）
RESERVED_PREFIXES = {
    "M": "musk", "F": "feynman", "G": "munger", "J": "jobs",
    "K": "karpathy", "P": "pg",
}

MIN_LINES, MAX_LINES = 120, 400
MIN_BLIND_SPOTS = 3


def die(msg: str, code: int = 2):
    print(f"[validate_role] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        return yaml.safe_load(parts[1]), parts[2]
    except yaml.YAMLError:
        return "INVALID", parts[2]


def collect_used_prefixes(exclude: str = None) -> dict:
    """扫描仓库内所有角色技能，收集已占用的 id 前缀。"""
    used = dict(RESERVED_PREFIXES)
    for base in (SKILLS, COMMUNITY):
        if not base.exists():
            continue
        for d in sorted(base.glob("role-*")):
            if exclude and d.name == exclude:
                continue
            md = d / "SKILL.md"
            if not md.is_file():
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            # 从前缀声明里抓，例如「claim id 前缀是 `V`」
            for m in re.finditer(r"前缀[是为：:\s]*[`\"']?([A-Z])[`\"']?", text):
                used.setdefault(m.group(1), d.name)
            # 从示例 id 里抓，例如 V1-1 / C2-3
            for m in re.finditer(r"\b([A-Z])(\d+)-\d+\b", text):
                used.setdefault(m.group(1), d.name)
    return used


def declared_prefix(body: str) -> str | None:
    for pat in (r"claim id 前缀[是为：:\s]*[`\"']?([A-Z])[`\"']?",
                r"前缀[是为：:\s]*[`\"']?([A-Z])[`\"']?",
                r"\bid_prefix[：:\s\"']+([A-Z])"):
        m = re.search(pat, body)
        if m:
            return m.group(1)
    return None


def validate(role_dir: Path, used_prefixes: dict = None) -> dict:
    errors, warnings, infos = [], [], []
    role_dir = Path(role_dir)
    name = role_dir.name

    if not role_dir.is_dir():
        return {"role": name, "ok": False,
                "errors": [{"code": "MISSING_DIR", "detail": f"目录不存在：{role_dir}"}],
                "warnings": [], "infos": []}

    skill_md = role_dir / "SKILL.md"
    if not skill_md.is_file():
        return {"role": name, "ok": False,
                "errors": [{"code": "MISSING_SKILL_MD", "detail": "缺少 SKILL.md"}],
                "warnings": [], "infos": []}

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)

    # ---- frontmatter ----
    if fm == "INVALID":
        errors.append({"code": "BAD_YAML", "detail": "frontmatter 不是合法 YAML"})
        fm = {}
    elif fm is None:
        errors.append({"code": "NO_FRONTMATTER", "detail": "缺少 frontmatter（--- 包裹的头部）"})
        fm = {}
    elif not isinstance(fm, dict):
        errors.append({"code": "BAD_FRONTMATTER", "detail": "frontmatter 不是键值对象"})
        fm = {}

    if fm.get("name") != name:
        errors.append({"code": "NAME_MISMATCH",
                       "detail": f"name={fm.get('name')!r} 与目录名 {name!r} 不一致"})
    if not str(fm.get("description", "")).strip():
        errors.append({"code": "NO_DESCRIPTION", "detail": "description 为空"})

    # ---- 章节结构 ----
    positions = [body.find(h) for h in REQUIRED_HEADINGS]
    missing = [h for h, p in zip(REQUIRED_HEADINGS, positions) if p < 0]
    if missing:
        errors.append({"code": "MISSING_HEADINGS", "detail": f"缺少章节：{missing}"})
    elif positions != sorted(positions):
        errors.append({"code": "HEADING_ORDER", "detail": "章节顺序不正确"})

    # ---- 契约字段 ----
    missing_fields = [f for f in CONTRACT_FIELDS if f not in body]
    if missing_fields:
        errors.append({"code": "MISSING_CONTRACT_FIELDS",
                       "detail": f"缺少契约字段：{missing_fields}"})

    # ---- basis 枚举 ----
    missing_basis = [b for b in BASIS_ENUM if b not in body]
    if missing_basis:
        errors.append({"code": "MISSING_BASIS_ENUM",
                       "detail": f"缺少 basis 枚举：{missing_basis}"})

    # ---- id 前缀 ----
    prefix = declared_prefix(body)
    if not prefix:
        errors.append({"code": "NO_ID_PREFIX",
                       "detail": "未声明 claim id 前缀（如「本角色 claim id 前缀是 V」）"})
    else:
        used = dict(used_prefixes or RESERVED_PREFIXES)
        owner = used.get(prefix)
        if owner and owner != name:
            errors.append({"code": "PREFIX_CONFLICT",
                           "detail": f"id 前缀 {prefix!r} 已被 {owner} 占用"})

    # ---- references 引用是否真实存在 ----
    refs = set(re.findall(r"references/([\w\-]+\.md)", body))
    for r in sorted(refs):
        if not (role_dir / "references" / r).is_file():
            errors.append({"code": "MISSING_REFERENCE",
                           "detail": f"正文引用了 references/{r}，但文件不存在"})
    if not (role_dir / "references").is_dir() or not list((role_dir / "references").glob("*.md")):
        warnings.append({"code": "NO_REFERENCES",
                         "detail": "没有 references/ 手册（推荐补充，但不是必须）"})

    # ---- 跨目录相对引用 ----
    if re.search(r"(?<![.\w])\.\./", body):
        errors.append({"code": "RELATIVE_PATH",
                       "detail": "含跨目录相对路径 ../（单独导入会失效）"})

    # ---- 行数 ----
    n_lines = len(text.splitlines())
    if not (MIN_LINES <= n_lines <= MAX_LINES):
        warnings.append({"code": "LINE_COUNT",
                         "detail": f"正文 {n_lines} 行，建议 {MIN_LINES}–{MAX_LINES} 行"})

    # ---- 盲区条数 ----
    m = re.search(r"## 已知盲区(.*?)(?=\n## |\Z)", body, re.S)
    if m:
        bullets = len(re.findall(r"^[-*]\s+\S", m.group(1), re.M))
        if bullets < MIN_BLIND_SPOTS:
            warnings.append({"code": "FEW_BLIND_SPOTS",
                             "detail": f"已知盲区只有 {bullets} 条，建议至少 {MIN_BLIND_SPOTS} 条"})
    else:
        warnings.append({"code": "NO_BLIND_SPOT_SECTION", "detail": "找不到已知盲区章节"})

    # ---- 与现有角色的张力 ----
    if "## 天然张力" in body:
        known = re.findall(r"\b(musk|feynman|munger|jobs|karpathy|pg)\b", body, re.I)
        if not known:
            infos.append({"code": "NO_TENSION",
                          "detail": "天然张力章节未提及任何现有角色（建议写明与谁冲突）"})

    return {
        "role": name,
        "ok": not errors,
        "lines": n_lines,
        "id_prefix": prefix,
        "references": sorted(refs),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }


def validate_all(as_json: bool = False) -> int:
    if not COMMUNITY.exists():
        die(f"社区角色目录不存在：{COMMUNITY}")
    dirs = sorted(d for d in COMMUNITY.glob("role-*") if d.is_dir())
    if not dirs:
        die("community-roles/ 下没有任何 role-* 目录")

    used = collect_used_prefixes()
    results = [validate(d, used) for d in dirs]
    failed = [r for r in results if not r["ok"]]

    if as_json:
        emit({"total": len(results), "failed": len(failed), "results": results})
    else:
        print(f"== 社区角色校验（{len(results)} 个）==")
        for r in results:
            status = "PASS" if r["ok"] else "FAIL"
            print(f"  [{status}] {r['role']:<22} 前缀={r.get('id_prefix') or '—'} "
                  f"行数={r.get('lines', 0)}")
            for e in r["errors"]:
                print(f"      ERROR {e['code']}: {e['detail']}")
            for w in r["warnings"]:
                print(f"      WARN  {w['code']}: {w['detail']}")
            for i in r["infos"]:
                print(f"      INFO  {i['code']}: {i['detail']}")
        print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
    return 1 if failed else 0


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    import tempfile

    good_body = """---
name: role-demo
description: "演示角色"
license: MIT
metadata:
  version: 1.0.0
---

# role-demo

## 角色定位
演示用。

## 思维协议
1. 做事。

## 天然张力
与 musk 冲突。

## 已知盲区
- 盲区一
- 盲区二
- 盲区三

## 输出契约
```yaml
role: demo
round: 1
position: 立场
claims: []
responses: []
blind_spot_declared: 无
epistemic_status:
  confidence: 50
  uncertainty_points: []
  will_revise_if: 证据
```
本角色 claim id 前缀是 `D`。
basis 可选：physical_constraint / empirical / case / mechanism / analogy / value_judgment / intuition

## 分轮次行为
R1 发言。

## 修正权限
引用契约 §5。

## 反模式
1. ❌ 无。

## 参考文件
- `references/demo.md`
"""

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        d = base / "role-demo"
        (d / "references").mkdir(parents=True)
        (d / "SKILL.md").write_text(good_body, encoding="utf-8")
        (d / "references" / "demo.md").write_text("# demo\n", encoding="utf-8")

        r = validate(d, {"M": "musk"})
        ck(r["ok"] is True, "合格角色通过校验")
        ck(r["id_prefix"] == "D", "识别出 id 前缀 D")
        ck(r["references"] == ["demo.md"], "识别出 references 引用")

        # name 不一致
        bad = base / "role-x"
        bad.mkdir()
        (bad / "SKILL.md").write_text(good_body, encoding="utf-8")
        r2 = validate(bad)
        ck(r2["ok"] is False and any(e["code"] == "NAME_MISMATCH" for e in r2["errors"]),
           "name 与目录名不一致被检出")

        # 缺章节
        short = base / "role-short"
        short.mkdir()
        (short / "SKILL.md").write_text(
            good_body.replace("## 已知盲区", "## 其他"), encoding="utf-8")
        r3 = validate(short)
        ck(any(e["code"] == "MISSING_HEADINGS" for e in r3["errors"]), "缺章节被检出")

        # 前缀冲突
        conflict = base / "role-conflict"
        conflict.mkdir()
        (conflict / "SKILL.md").write_text(
            good_body.replace("name: role-demo", "name: role-conflict")
                      .replace("前缀是 `D`", "前缀是 `M`"), encoding="utf-8")
        r4 = validate(conflict, {"M": "musk"})
        ck(any(e["code"] == "PREFIX_CONFLICT" for e in r4["errors"]), "前缀冲突被检出")

        # 引用了不存在的参考文件
        (d / "references" / "demo.md").unlink()
        r5 = validate(d)
        ck(any(e["code"] == "MISSING_REFERENCE" for e in r5["errors"]),
           "引用不存在的 references 文件被检出")
        (d / "references" / "demo.md").write_text("# demo\n", encoding="utf-8")

        # 跨目录相对引用
        (d / "SKILL.md").write_text(good_body + "\n见 ../role-musk/SKILL.md\n", encoding="utf-8")
        r6 = validate(d)
        ck(any(e["code"] == "RELATIVE_PATH" for e in r6["errors"]), "跨目录相对路径被检出")
        (d / "SKILL.md").write_text(good_body, encoding="utf-8")

        # 缺 description
        (d / "SKILL.md").write_text(
            good_body.replace('description: "演示角色"', "description: \"\""), encoding="utf-8")
        r7 = validate(d)
        ck(any(e["code"] == "NO_DESCRIPTION" for e in r7["errors"]), "空 description 被检出")

    # 真实仓库中的社区角色
    if COMMUNITY.exists() and list(COMMUNITY.glob("role-*")):
        used = collect_used_prefixes()
        ck("M" in used and used["M"] == "musk", "能从仓库里收集到已占用的前缀")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="社区角色协议校验器")
    ap.add_argument("path", nargs="?", help="角色目录，如 community-roles/role-civilian")
    ap.add_argument("--all", action="store_true", help="校验所有社区角色")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("selftest", nargs="?", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if argv and "selftest" in argv:
        return selftest()
    if args.all:
        return validate_all(args.json)
    if not args.path:
        ap.print_help()
        return 2

    p = Path(args.path)
    if not p.is_absolute():
        p = ROOT / p
    result = validate(p, collect_used_prefixes(exclude=p.name))
    emit(result)
    if not result["ok"]:
        log_lines = [f"ERROR {e['code']}: {e['detail']}" for e in result["errors"]]
        print("校验失败：\n  " + "\n  ".join(log_lines), file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main(sys.argv[1:]))

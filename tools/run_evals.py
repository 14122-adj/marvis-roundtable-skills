#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线评测 runner tools/run_evals.py

跑 `evals/evals.json` 里的四类评测，**不调用任何模型**：

  * `trigger`       —— 提示词与技能 description 的『关键词覆盖率』启发式检查，只作回归护栏
  * `command`       —— 真实执行脚本/演示，断言退出码与输出片段
  * `artifact`      —— 检查单个文件必须含/不得含的内容
  * `artifact_glob` —— 对一批文件逐个检查

诚实边界：覆盖率是**字符级启发式**，不是"这个技能该不该被触发"的语义判断。
真正的模型级评测需要在宿主里跑 LLM（`--live` 只说明这一点，不伪造结果）。

用法：
  python tools/run_evals.py [--json] [--live] [--filter PREFIX]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals" / "evals.json"

ASCII_WORD = re.compile(r"[a-z0-9_]+")


def tokens(text: str) -> set:
    t = unicodedata.normalize("NFKC", str(text)).lower()
    words = set(ASCII_WORD.findall(t))
    han = re.sub(r"[^\u4e00-\u9fff]+", "", t)
    bigrams = {han[i:i + 2] for i in range(len(han) - 1)} if len(han) >= 2 else ({han} if han else set())
    return words | bigrams


def coverage(prompt: str, description: str) -> float:
    pt = tokens(prompt)
    if not pt:
        return 0.0
    dt = tokens(description)
    return len(pt & dt) / len(pt)


def load_descriptions():
    out = {}
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"^description:\s*\"?(.*?)\"?\s*$", text.split("---")[1], re.M | re.S)
        desc = m.group(1) if m else ""
        out[skill_md.parent.name] = desc.replace("\n", " ")
    return out


def run_command(spec: list, tmp: str) -> tuple:
    cmd = [str(ROOT / c[len("{ROOT}/"):]) if c.startswith("{ROOT}/") else
           c.replace("{TMP}", tmp) for c in spec]
    if cmd and cmd[0] == "python":
        cmd[0] = sys.executable
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(ROOT))
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--filter", default="")
    args = ap.parse_args()

    if args.live:
        print("--live 需要在宿主环境里调用 LLM 逐条执行提示词；本仓库不提供模型调用，"
              "因此不产出任何'已通过'的结论。请把 evals/evals.json 的 prompt 交给宿主执行，"
              "并用本脚本的 trigger/command/artifact 三类做离线回归。")
        return 0

    spec = json.loads(EVALS.read_text(encoding="utf-8"))
    th = spec.get("thresholds", {})
    min_pos = th.get("trigger_min_coverage", 0.10)
    max_neg = th.get("trigger_negative_max_coverage", 0.08)
    descs = load_descriptions()

    results = []
    tmp = tempfile.mkdtemp(prefix="mrs-evals-")

    for ev in spec["evals"]:
        eid = ev["id"]
        if args.filter and not eid.startswith(args.filter):
            continue
        kind = ev["type"]
        detail, ok = "", False

        if kind == "trigger":
            prompt = ev["prompt"]
            if ev.get("skill"):
                target = ev["skill"]
                cov = coverage(prompt, descs.get(target, ""))
                ranked = sorted(((coverage(prompt, d), s) for s, d in descs.items()), reverse=True)
                rank = [s for _, s in ranked].index(target) + 1
                ok = cov >= min_pos and rank <= 3
                detail = (f"{target} coverage={cov:.3f} rank={rank}/{len(descs)} "
                          f"(阈值 {min_pos}，要求进前 3)；最高={ranked[0][1]}:{ranked[0][0]:.3f}")
            else:
                ranked = sorted(((coverage(prompt, d), s) for s, d in descs.items()), reverse=True)
                ok = ranked[0][0] < max_neg
                detail = f"最高覆盖率 {ranked[0][1]}={ranked[0][0]:.3f}（需 < {max_neg} 才不触发）"

        elif kind == "command":
            rc, out, err = run_command(ev["cmd"], tmp)
            miss = [p for p in ev.get("stdout_contains", []) if p not in out]
            miss_e = [p for p in ev.get("stderr_contains", []) if p not in err]
            ok = rc == ev.get("expect_exit", 0) and not miss and not miss_e
            detail = (f"exit={rc}（期望 {ev.get('expect_exit', 0)}）"
                      + (f"；stdout 缺 {miss}" if miss else "")
                      + (f"；stderr 缺 {miss_e}" if miss_e else ""))

        elif kind == "artifact":
            p = ROOT / ev["path"]
            text = p.read_text(encoding="utf-8") if p.exists() else ""
            miss = [s for s in ev.get("must_contain", []) if s not in text]
            bad = [s for s in ev.get("must_not_contain", []) if s in text]
            ok = p.exists() and not miss and not bad
            detail = (f"{ev['path']}" + (f"；缺 {miss}" if miss else "")
                      + (f"；出现禁止内容 {bad}" if bad else "")
                      + ("" if p.exists() else "；文件不存在"))

        elif kind == "artifact_glob":
            files = sorted(ROOT.glob(ev["glob"]))
            problems = []
            if not files:
                problems.append("未匹配到文件")
            for f in files:
                text = f.read_text(encoding="utf-8")
                miss = [s for s in ev.get("must_contain", []) if s not in text]
                bad = [s for s in ev.get("must_not_contain", []) if s in text]
                if miss or bad:
                    problems.append(f"{f.relative_to(ROOT)}: 缺{miss} 禁止{bad}")
            ok = not problems
            detail = f"{len(files)} 个文件" + ("；" + "；".join(problems) if problems else "")

        else:
            detail = f"未知评测类型 {kind}"
            ok = False

        results.append({"id": eid, "type": kind, "ok": ok, "detail": detail})

    failed = [r for r in results if not r["ok"]]
    if args.json:
        print(json.dumps({"total": len(results), "failed": len(failed), "results": results},
                         ensure_ascii=False, indent=2))
    else:
        print("== 离线评测结果（不调用模型）==")
        for r in results:
            print(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['id']:<38} {r['detail']}")
        print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
        if failed:
            print("失败项：" + ", ".join(r["id"] for r in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

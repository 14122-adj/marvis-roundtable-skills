#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨会话记忆库 memory_store.py

`ultimate-roundtable` V3.0 的阶段零与阶段四靠它落地：
会议开始前读取历史 `[MEMORY_UPDATE]`，会议结束后写入新记忆。

设计要点：

  * **纯文本可读**：记忆存成 JSONL（一行一条），可以直接用任何编辑器打开、grep、手工修正。
    不需要数据库，也不会因为脚本损坏而永久丢失。
  * **≤200 字硬门槛**：超长记忆在下次读取时会被截断，等于白写。所以写入时直接拒绝。
  * **可检索**：支持按关键词、标签、时间检索。检索是**字面匹配**，不是语义检索——
    脚本不假装懂语义（契约 §7）。
  * **可追溯**：每条记忆带 session_id、时间、标签、来源文件，能追到是哪场会议产生的。

存储位置（按优先级自动选择，可用 --store 覆盖）：

  1. `--store` 显式指定
  2. 环境变量 `ROUNDTABLE_MEMORY`
  3. 仓库内 `.roundtable-memory/memories.jsonl`（存在 .git 时优先，便于随仓库带走）
  4. 用户目录 `~/.marvis-roundtable/memories.jsonl`

用法：
  python memory_store.py remember --text "…" [--tags a,b] [--session id] [--store PATH]
  python memory_store.py recall   [--limit 5] [--query 关键词] [--tags a] [--json]
  python memory_store.py intro    [--limit 3]           # 阶段零开场白
  python memory_store.py stats
  python memory_store.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

MEMORY_LIMIT = 200
SCHEMA_VERSION = "3.0.0"
HERE = Path(__file__).resolve()
# skills/ultimate-roundtable/scripts/memory_store.py → 仓库根
REPO_ROOT = HERE.parents[3]


def log(msg: str) -> None:
    print(f"[memory_store] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[memory_store] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def resolve_store(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("ROUNDTABLE_MEMORY")
    if env:
        return Path(env).expanduser().resolve()
    if (REPO_ROOT / ".git").exists():
        return REPO_ROOT / ".roundtable-memory" / "memories.jsonl"
    return Path.home() / ".marvis-roundtable" / "memories.jsonl"


def load(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            log(f"跳过第 {i} 行：不是合法 JSON（记忆文件可手工修复）")
    return out


def char_len(text: str) -> int:
    return len(str(text))


def remember(path: Path, text: str, tags=None, session=None, topic=None,
             allow_long: bool = False) -> dict:
    text = str(text).strip()
    if not text:
        die("记忆内容为空")
    if char_len(text) > MEMORY_LIMIT and not allow_long:
        die(f"长期记忆 {char_len(text)} 字，超过 {MEMORY_LIMIT} 字上限。"
            f"请压缩成一条可复用的判断，而不是把会议纪要贴进来。", 3)

    entry = {
        "schema_version": SCHEMA_VERSION,
        "id": "M" + datetime.now().strftime("%Y%m%d%H%M%S"),
        "text": text,
        "chars": char_len(text),
        "tags": list(tags or []),
        "session_id": session or "",
        "topic": topic or "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def score(entry: dict, query: str) -> int:
    """字面匹配打分：命中查询里的任一词就加分。不做语义理解。"""
    if not query:
        return 0
    words = [w for w in re.split(r"[\s,，、;；]+", query) if w]
    blob = (entry.get("text", "") + " " + entry.get("topic", "")
            + " " + " ".join(entry.get("tags", [])))
    return sum(1 for w in words if w in blob)


def recall(path: Path, limit: int = 5, query: str = "", tags=None,
           session: str = "") -> list:
    items = load(path)
    if tags:
        want = set(tags)
        items = [e for e in items if want & set(e.get("tags", []))]
    if session:
        items = [e for e in items if e.get("session_id") == session]
    if query:
        scored = [(score(e, query), e) for e in items]
        items = [e for s, e in sorted(scored, key=lambda x: (-x[0], x[1].get("created_at", "")))
                 if s > 0]
    else:
        items = sorted(items, key=lambda e: e.get("created_at", ""), reverse=True)
    return items[:limit]


def intro(path: Path, limit: int = 3) -> str:
    items = recall(path, limit=limit)
    if not items:
        return "[会议启动] 已加载历史记忆：无记忆记录（这是本议题的第一次推演）"
    bullets = []
    for i, e in enumerate(items, 1):
        when = e.get("created_at", "")[:10]
        bullets.append(f"{i}. [{when}] {e.get('text', '')}")
    return "[会议启动] 已加载历史记忆：" + " ｜ ".join(bullets)


def stats(path: Path) -> dict:
    items = load(path)
    tags = {}
    for e in items:
        for t in e.get("tags", []):
            tags[t] = tags.get(t, 0) + 1
    return {
        "store": str(path),
        "exists": path.exists(),
        "count": len(items),
        "avg_chars": round(sum(e.get("chars", 0) for e in items) / len(items), 1) if items else 0,
        "max_chars": max((e.get("chars", 0) for e in items), default=0),
        "over_limit": [e.get("id") for e in items if e.get("chars", 0) > MEMORY_LIMIT],
        "tags": tags,
        "first": items[0].get("created_at") if items else None,
        "last": items[-1].get("created_at") if items else None,
        "limit": MEMORY_LIMIT,
    }


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    import io
    import contextlib
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        store = Path(td) / "mem.jsonl"

        ck(recall(store) == [], "空记忆库返回空列表而不是报错")
        ck("无记忆记录" in intro(store), "无记忆时开场白明确说没有")

        e1 = remember(store, "评审类流程的优化对象不是频次而是单次固定开销与切换成本",
                      tags=["评审", "流程"], session="ur-1", topic="季度评审")
        ck(e1["chars"] <= MEMORY_LIMIT, "正常记忆写入成功")
        ck(store.exists(), "记忆文件被创建")
        ck(len(store.read_text(encoding="utf-8").splitlines()) == 1, "JSONL 一行一条")

        e2 = remember(store, "单一可包装指标会催生为指标服务的成本", tags=["指标"], session="ur-2")
        ck(stats(store)["count"] == 2, "第二条记忆被追加")

        # 超长必须拒绝
        try:
            remember(store, "记" * 260)
            ck(False, "超过 200 字应被拒绝")
        except SystemExit as exc:
            ck(exc.code == 3, "超过 200 字以退出码 3 拒绝")

        # 检索
        ck(len(recall(store, query="评审")) == 1, "关键词检索命中正确条目")
        ck(len(recall(store, query="不存在的词")) == 0, "无关关键词不返回结果")
        ck(len(recall(store, tags=["指标"])) == 1, "标签检索生效")
        ck(len(recall(store, session="ur-1")) == 1, "会话检索生效")
        ck(len(recall(store, limit=1)) == 1, "limit 生效")

        # 开场白
        line = intro(store, limit=2)
        ck(line.startswith("[会议启动] 已加载历史记忆："), "开场白格式符合 spec")
        ck("评审" in line, "开场白包含历史记忆内容")

        st = stats(store)
        ck(st["max_chars"] <= MEMORY_LIMIT and st["over_limit"] == [], "统计显示无超长条目")
        ck(st["tags"].get("评审") == 1, "标签统计正确")

        # 损坏行应被跳过而不是崩溃
        with store.open("a", encoding="utf-8") as f:
            f.write("这不是 JSON\n")
        ck(len(load(store)) == 2, "损坏行被跳过，其余记忆仍可读")

        # CLI 端到端
        cli = Path(td) / "cli.jsonl"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = main(["remember", "--text", "CLI 写入测试", "--store", str(cli),
                       "--tags", "测试"])
        ck(rc == 0 and cli.exists(), "CLI remember 正常写入")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["recall", "--store", str(cli), "--json"])
        ck("CLI 写入测试" in buf.getvalue(), "CLI recall --json 能读回")
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            main(["intro", "--store", str(cli)])
        ck("[会议启动]" in buf2.getvalue(), "CLI intro 输出开场白")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="跨会话记忆库")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("remember")
    pr.add_argument("--text", required=True)
    pr.add_argument("--tags", default="")
    pr.add_argument("--session", default="")
    pr.add_argument("--topic", default="")
    pr.add_argument("--store")

    pc = sub.add_parser("recall")
    pc.add_argument("--limit", type=int, default=5)
    pc.add_argument("--query", default="")
    pc.add_argument("--tags", default="")
    pc.add_argument("--session", default="")
    pc.add_argument("--store")
    pc.add_argument("--json", action="store_true")

    pi = sub.add_parser("intro")
    pi.add_argument("--limit", type=int, default=3)
    pi.add_argument("--store")

    ps = sub.add_parser("stats")
    ps.add_argument("--store")

    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "remember":
        path = resolve_store(args.store)
        entry = remember(path, args.text,
                         tags=[t.strip() for t in args.tags.split(",") if t.strip()],
                         session=args.session, topic=args.topic)
        emit({"ok": True, "store": str(path), "entry": entry})
        return 0
    if args.cmd == "recall":
        path = resolve_store(args.store)
        items = recall(path, args.limit, args.query,
                       [t.strip() for t in args.tags.split(",") if t.strip()], args.session)
        if args.json:
            emit({"store": str(path), "count": len(items), "items": items})
        else:
            if not items:
                print("（无匹配记忆）")
            for e in items:
                print(f"- [{e.get('created_at','')[:10]}] {e.get('text','')}"
                      + (f"　tags={','.join(e.get('tags',[]))}" if e.get("tags") else ""))
        return 0
    if args.cmd == "intro":
        print(intro(resolve_store(args.store), args.limit))
        return 0
    if args.cmd == "stats":
        emit(stats(resolve_store(args.store)))
        return 0
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

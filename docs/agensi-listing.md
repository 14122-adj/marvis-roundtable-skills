# Agensi 上架材料

> 本文件是给**你**（账号持有人）用的。上架动作需要登录 Agensi 账号、走 `/sell` 流程、
> 绑定 Stripe Connect，这些我无法代你执行。这里提供的是**可以复制粘贴**的全部素材。

**写作原则**：不要一上来讲代码和架构。第一句打痛点，第二句说清它做什么，
架构放到最后一段——那是已经决定要买的人才看的东西。

---

## 一、可直接上传的包

`dist/market/` 下有 14 个单技能 ZIP，全部已按 Agensi 规范校验通过
（单层顶层文件夹、SKILL.md 在根部、无嵌套、无隐藏文件、无 `__pycache__`）：

```bash
python tools/package_bundle.py market --version 1.7.0
python tools/package_bundle.py verify-market --dir dist/market
```

**首个上架**：`ultimate-roundtable-v1.7.0.zip`

---

## 二、Listing 文案（英文）

### Title

```
Ultimate Roundtable — Turn 6 LLM Personas Into a Ruthless Decision Engine
```

### Short description（≤160 字符）

```
Turn 6 LLM personas (Musk, Feynman, Munger, etc.) into a ruthless, multi-agent decision-making engine.
```

> 这句是打痛点用的：不讲架构，只讲"把角色扮演变成决策引擎"。
> 下面是可选的补充句，放在短描述的第二行：

```
No more role-play. Forces first principles and inversion. Built-in deadlock breaker. Outputs strict KPI & kill criteria.
```

### Full description（复制这一段）

```
Stop asking one model to "think like a panel". Make six of them fight.

You already know the failure mode: you ask an LLM to debate a decision, and you get
six polite memos that agree with each other. Nobody is forced to prove anything.
Nothing gets decided.

Ultimate Roundtable turns six personas into a decision engine with teeth.

────────────────────────────────────────
THE FOUR THINGS IT ACTUALLY DOES
────────────────────────────────────────

1. NO MORE ROLE-PLAY.
   Every persona runs a forced thinking protocol, not a costume.
   Musk must decompose to first principles and show a magnitude estimate.
   Feynman must explain it to a layman in one sentence or mark it "not understood".
   Munger must invert first — "how would I guarantee this fails?" — then cross two
   disciplines. Jobs must answer "does this make it simpler or more complex?"
   Karpathy must make every claim reproducible. Paul Graham must start from a real
   case, not a principle. Vague statements are rejected at validation time.

2. DEADLOCK BREAKER.
   Built-in semantic deadlock detection. When two sides are merely paraphrasing each
   other — same argument, different words, different examples — the system cuts the
   debate and forces the verdict stage. Verbatim repetition is easy to catch;
   paraphrase is the hard case, and that is what this detects.
   You get a number, not a feeling: consecutive stalled rounds, similarity score,
   and an auditable REPEAT / PROGRESS verdict per exchange.

3. ACTIONABLE OUTPUTS. NOT A SUMMARY.
   The run ends in exactly one thing: three mutually exclusive options (aggressive /
   conservative / orthogonal), a forced vote from all six, and one decision.
   Then an order sheet with:
     • a named owner
     • the first step
     • a KPI containing a number
     • a kill-switch threshold containing a number
   "If results are bad, stop" is rejected by the validator. Vagueness is a build error.

4. ZERO FRICTION.
   One-command quickstart and an interactive wizard are included.
   `python tools/quickstart.py` — health check, a full roundtable, self-test, and
   next steps. ~10 seconds. No config, no API keys, no dependencies.
   `python tools/wizard.py` — walks you through your own topic and generates all five
   stage files with live validation, so you cannot submit a malformed payload.

────────────────────────────────────────
ALSO INCLUDED
────────────────────────────────────────

• Honest evidence labelling. Every data point is tagged real-tool or simulated, and
  the report header prints the ratio. Simulated data cannot masquerade as real —
  the run is rejected if the tag is missing.
• Attention compartmentalisation. Each persona only sees the history slice relevant
  to its lens, so context overload cannot turn the panel into mush.
• Minority protection. Unrefuted minority views are preserved in full, never
  averaged away by the majority.
• Civilian audit. Flags "elite consensus" — when all six agree, the blind spot is
  usually the person who actually has to use the thing.
• Cross-session memory. Lessons persist between runs in a plain JSONL file.

────────────────────────────────────────
INSTALL
────────────────────────────────────────

Drop the folder into your agent's skills directory:
  Claude Code            ~/.claude/skills/ultimate-roundtable/
  Cursor / Cline         <project>/skills/ultimate-roundtable/
  Marvis                 Skills → Import → select SKILL.md
  Anything that reads AGENTS.md    <project>/skills/ultimate-roundtable/

Then say: "open an ultimate roundtable on <your decision>"

────────────────────────────────────────
CUSTOM HOST ENVIRONMENTS
────────────────────────────────────────

For custom host environments, simply clone the GitHub repo and run
python tools/quickstart.py. It takes 30 seconds.

────────────────────────────────────────
REQUIREMENTS
────────────────────────────────────────

Python 3.9+. Standard library only — nothing to install.
Works in Claude Code, Codex, Cursor, Cline, Windsurf, and any agent that reads SKILL.md.
```

### Tags / category

- **Category**: `Agents & Orchestration`（备选 `Research & Analysis`）
- **Tags**: `decision-making`, `multi-agent`, `debate`, `red-team`, `orchestration`, `strategy`

### Trigger phrases（description 里已含）

```
opening an ultimate roundtable
stress-testing a decision with multiple expert perspectives
red-team vs blue-team debate
tactical decision review
forcing a decision out of endless debate
```

---

## 三、定价建议

| 方案 | 价格 | 适用 |
|---|---|---|
| 免费 + 引流 | $0 | 想要 star / 反馈优先 |
| **低价试水** | **$5–9** | **推荐先这个**：验证有没有人愿意付钱 |
| 正式定价 | $19–29 | 拿到 3–5 个好评后 |

Agensi 70/30 分成。先 $5 的目的不是赚钱，是拿真实反馈。

---

## 四、上架前检查清单

| 检查项 | 状态 |
|---|---|
| 单层顶层文件夹 | ✅ 14/14 |
| SKILL.md 在根部（非 zip 根、非双层嵌套） | ✅ |
| 无 `.DS_Store` / `Thumbs.db` / `__pycache__` | ✅ |
| 无二进制文件、无符号链接 | ✅ |
| frontmatter `name` 与文件夹名一致 | ✅ |
| `description` 非空且含触发短语 | ✅ |
| 无硬编码密钥/token | ✅ 全库扫描 |
| 每个技能至少一个 references 文件 | ✅ |
| 脚本只操作项目目录、不需提权、不装包 | ✅ 仅标准库 |
| 解压后脚本可执行 | ✅ 实测 `selftest OK` |
| 在至少一个 agent 内实测 | ⚠️ **你需要做这一步** |

---

## 五、你要做的三步

1. 登录 [agensi.io](https://www.agensi.io)，进 `/sell`
2. 上传 `dist/market/ultimate-roundtable-v1.7.0.zip`，粘贴上面的文案
3. 绑定 Stripe Connect（收款需要）

**上架后第一周只看两个数**：安装数、评价内容。
评价集中在"不会用" → 补一键安装；集中在"没什么用" → 调定位。

---

## 六、我没做的事（如实说明）

- **没有替你注册/登录 Agensi**，也没有代你提交 listing——需要你的账号与 Stripe 授权。
- **没有在真实 AI 客户端里装过**这个市场包。我验证的是：ZIP 结构合规、解压后脚本可执行、
  frontmatter 可解析。真实客户端行为需要你实测一次。
- **技能本体 SKILL.md 是中文**。上面的 listing 文案是英文；如果 Agensi 审核要求
  正文也英文，需要再做一版翻译（约 1 小时）。

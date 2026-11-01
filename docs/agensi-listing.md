# Agensi 上架材料

> 本文件是给**你**（账号持有人）用的。上架动作需要登录 Agensi 账号、走 `/sell` 流程、
> 绑定 Stripe Connect，这些我无法代你执行。这里提供的是**可以复制粘贴**的全部素材，
> 以及我这边已经验证过的产物。

---

## 一、可直接上传的包

`dist/market/` 下有 14 个单技能 ZIP，全部已按 Agensi 规范校验通过
（单层顶层文件夹、SKILL.md 在根部、无嵌套、无隐藏文件、无 `__pycache__`）：

```bash
python tools/package_bundle.py market --version 1.7.0
python tools/package_bundle.py verify-market --dir dist/market
```

**建议首个上架的**：`ultimate-roundtable-v1.7.0.zip`（最具差异化的那个）。

---

## 二、Listing 文案（英文，Agensi 是英文市场）

### Title

```
Ultimate Roundtable — 6-Expert Adversarial Decision Engine
```

### Short description（一句话，≤120 字符）

```
Six AI experts debate your decision, then force an A/B/C verdict with an owner, KPI and kill-switch.
```

### Full description

```
Most "multi-agent debate" skills produce six polite memos. This one produces a decision.

Ultimate Roundtable runs a fixed five-stage pipeline:

1. MEMORY — loads lessons from previous sessions and anchors ONE north-star metric.
   Every later statement must reference it, or it is rejected.
2. BRIEF — six experts speak in ≤150 characters each, every claim requiring a
   [data demand] + a [tool call] + a stated position. Vague claims are rejected.
3. ADVERSARIAL — 3 vs 3 red/blue teams with mandatory inner monologue, interruption
   tags, and on-the-spot fact-checking. If the two sides merely restate each other,
   a semantic deadlock detector cuts the debate and forces the verdict stage.
4. VERDICT — three mutually exclusive options (aggressive / conservative / orthogonal),
   all six experts cast a final vote with reasons, and one option is chosen.
5. ORDERS — an action plan with a named owner, first step, KPI with numbers,
   a kill-switch threshold, and the remaining unknowns.

WHAT MAKES IT DIFFERENT

• Refuses vagueness by construction. "If the effect is bad, stop" is rejected at
  validation time — the kill-switch must contain a number.
• Semantic deadlock detection. Paraphrasing is caught, not just verbatim repetition.
• Honest evidence labelling. Every data point is tagged real-tool or simulated,
  and the report header prints the ratio. Simulated data cannot masquerade as real.
• Attention compartmentalisation. Each expert only sees the slice of history
  relevant to their lens, to prevent context overload.
• Minority protection. Unrefuted minority views are preserved in full, never
  averaged away.

WHAT YOU GET

• 5-stage orchestrator with validation at every gate
• 6 expert thinking protocols (first principles, Feynman verification, inversion,
  product purity, system decomposition, case-based reasoning)
• Semantic deadlock detector + red/blue sparring analyser
• Cross-session memory store (plain JSONL, ≤200 chars per memory)
• Civilian-perspective audit — flags elite consensus as a blind spot
• Quickstart script: one command to see a full roundtable in ~10 seconds

REQUIREMENTS

Python 3.9+. Standard library only, no dependencies to install.
Works in Claude Code, Codex, Cursor, Cline, Windsurf and any agent that reads SKILL.md.
```

### Tags / category

- **Category**: `Agents & Orchestration`（备选 `Research & Analysis`）
- **Tags**: `decision-making`, `multi-agent`, `debate`, `red-team`, `strategy`, `orchestration`

### Trigger phrases（description 里要含 3–5 个）

```
opening a roundtable discussion
stress-testing a decision with multiple expert perspectives
red-team vs blue-team debate
tactical decision review
forcing a decision out of endless debate
```

---

## 三、定价建议

| 方案 | 价格 | 适用 |
|---|---|---|
| 免费 + 引流 | $0 | 想要 star / 反馈优先，先跑通流程 |
| 低价试水 | $5–9 | 验证有没有人愿意付钱（推荐先这个） |
| 正式定价 | $19–29 | 拿到 3–5 个好评后 |

Agensi 是 70/30 分成。**建议先 $5**——目的不是赚钱，是拿到真实反馈和第一批评价。

---

## 四、上架前我已完成的检查

| 检查项 | 状态 |
|---|---|
| 单层顶层文件夹 | ✅ 14/14 通过 |
| SKILL.md 在根部（非 zip 根、非双层嵌套） | ✅ |
| 无 `.DS_Store` / `Thumbs.db` / `__pycache__` | ✅ |
| 无二进制文件、无符号链接 | ✅ |
| frontmatter `name` 与文件夹名一致 | ✅ |
| `description` 非空且含触发短语 | ✅ |
| 无硬编码密钥/token | ✅ 已全库扫描 |
| 每个技能至少一个 references 文件 | ✅ |
| 脚本只操作项目目录、不需提权、不装包 | ✅ 仅标准库 |
| 解压后脚本可执行 | ✅ 实测 `selftest OK` |
| 至少一个 agent 内实测 | ⚠️ **你需要做这一步** |

---

## 五、你要做的三步

1. 登录 [agensi.io](https://www.agensi.io)，进 `/sell`
2. 上传 `dist/market/ultimate-roundtable-v1.7.0.zip`，粘贴上面的文案
3. 绑定 Stripe Connect（收款需要）

上架后第一周，重点看两个数：**安装数**和**评价内容**。
如果评价集中在"不会用"，说明要补的是一键安装；如果集中在"没什么用"，说明要调的是定位。

---

## 六、我没有做的事（如实说明）

- **没有替你注册/登录 Agensi 账号**，也没有代你提交 listing——这需要你的账号与 Stripe 授权。
- **没有在真实 AI 客户端里装过**这个市场包。我验证的是：ZIP 结构合规、解压后脚本可执行、
  frontmatter 可解析。真实客户端的行为需要你实测一次。
- **没有写英文版 SKILL.md**。上面提供的英文文案是给 listing 页面用的；
  技能本体的 SKILL.md 仍是中文。如果 Agensi 审核要求英文正文，需要再做一版翻译。

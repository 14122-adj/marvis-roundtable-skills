---
name: ultimate-roundtable
description: "终极专家圆桌机制 v2.0.0：通过动态召唤、红蓝对抗、内心戏外显和沙盘推演，把讨论从纸上谈兵升级为深度决策推演。当用户要求开启终极圆桌、深度推演讨论、红蓝对抗圆桌，或需要把一场多视角讨论压成可执行的 Do/Don't/Need Info 行动清单并给出存活率评估时，必须使用本技能。"
license: MIT
version: 2.0.0
trigger:
  - 开启终极圆桌
  - 深度推演讨论
  - 红蓝对抗圆桌
permission:
  - read_workspace
  - write_workspace
metadata:
  version: 2.0.0
  layer: "Layer 0+ · 高强度审议（ultimate）"
  extends: roundtable-orchestrator
---

# 终极圆桌

六个固定角色轮流发言，产出的是**六份独立报告**，不是决策。
本技能把同一批角色压进一条高密度流水线：**摊牌 → 对抗 → 沙盘 → 降维打击**，
每一步都有可检查的硬判据，最后只允许输出一种东西：带存活率的行动指令。

## 与 `roundtable-orchestrator` 的分工

| | `roundtable-orchestrator`（v1.x） | `ultimate-roundtable`（v2.0） |
|---|---|---|
| 目标 | 把讨论做深、挖到共享前提 | 把讨论压成**能执行的决策** |
| 交互 | 第一轮隔离、之后自由交叉 | 强制 3v3 红蓝对营，必须打出火花 |
| 表达 | 只要求论据与置信度 | 额外要求**内心戏**（没说出口的判断） |
| 数据 | 登记信息缺口 `G` 即可 | 必须给出 `[数据诉求]` 并真实调用工具或**明确标注模拟** |
| 结论 | 决策景观（分区呈现） | 存活率 + Do / Don't / Need Info |
| 失败处理 | 元认知介入 | **无火花强制重开**，行动栏有空即拒绝出报告 |

两者不冲突：需要挖前提用前者，需要做决策用本技能。

---

## 四个阶段（每次响应必须严格按此结构推进）

### 阶段一 · 极速摊牌与工具诉求

六个角色各发言一次，每条必须包含两样东西：

1. `[数据诉求: 需要……]` —— **我当前结论依赖的那一条最关键数据**（只准一条，逼他选出最要命的）
2. `tool_result` —— 这条数据从哪来：
   - 支持工具的环境：**真实调用**搜索/代码，`{"source": "tool", "tool": "web_search", "query": "...", "result": "..."}`
   - 纯文本环境：`{"source": "text", "simulated": true, "result": "..."}`

> **红线**：`source: tool` 与 `simulated: true` 不能同时出现；
> 两者都不标的数据会被判为"把模拟数据伪装成真实数据"，直接拒绝进入下一阶段。
> 报告头部会统计「真实工具调用 N 条 / 模拟数据 M 条」，让读者一眼看出证据的成色。

### 阶段二 · 幽灵干预与红蓝对抗

**内心戏**：每个角色发言前必须先写 `(Inner Thought: ...)`——他没说出口的真实想法
（鄙视、怀疑、妥协、试探）。内心戏不是心理描写，是**利益与顾虑的披露**：
它让"嘴上支持、心里反对"这件事变成可见信息。

**动态打断**：发现对方发言有逻辑漏洞或未验证假设，在自己发言开头加 `[打断]`，直接质问。

**红蓝分组**：由编排引擎指定 **3 人蓝军**（恶魔代言人，必须想尽办法证明方案会失败）
与 **3 人红军**（捍卫并修补方案）。

**火花检测（禁止和稀泥的量化判据）**：本阶段结束自动跑
`clash_analyzer.py spark`，六个计数决定是否算打出火花：

| 计数 | 含义 | 默认门槛 |
|---|---|---|
| `attack_count` | 蓝军有效攻击（有靶点 + 有内容） | ≥ 3 |
| `defense_count` | 红军有效防御/修补 | ≥ 2 |
| `target_spread` | 被攻击的不同 claim 数 | ≥ 2 |
| `signal_total` | 攻击+防御+立场修正+新论据 | ≥ 3 |
| `hollow_ratio` | 空洞发言占比（"我觉得挺好的""各有优劣"） | ≤ 34% |
| `unmet_must_respond` | 未回应的元认知强制条目 | 必须为空 |

**任一不达标 → 退出码 4，强制重开一轮**，并逐条打印重开理由。

### 阶段三 · 沙盘推演

选出现阶段最可行的综合方案，交给 **Karpathy + 马斯克** 做数字沙盘：

- `timeline` 至少 3 个月度节点，每个节点必须给出**可观测结果**（`metric` 数值或 `error` 报错），
  禁止只写"会遇到一些困难"；
- 必须登记 `risks`（severity × probability）、`key_assumptions`（有没有证据）、
  `attacks`（有没有被防住）；
- 遇到跨领域认知盲区（法律/政治/合规/供应链……）→ **`[召唤：法务专家]`** 临时角色，
  必须写清 `reason`（为什么这是盲区）与 `statement`（该角色说了什么）。

### 阶段四 · 元认知降维打击与记忆提炼

- 指出全场**始终没有跳出的共同隐性假设**（不是某个人漏了，是所有人都默认了）；
- 列出被沙盘证伪的前提、被忽略的成本维度；
- 提炼 `[长期记忆]`，**不超过 200 字**（超一个字都拒绝写入）。

---

## 量化模型（可复算，不是拍脑袋）

### 存活率

```
survival = 0.40 × risk_residual      # 100×(1-平均(severity×probability))
         + 0.25 × evidence_coverage  # 有关键假设中带证据的比例
         + 0.20 × defense_quality    # 攻击被有效防住的比例
         + 0.15 × plan_integrity     # Do/Don't/NeedInfo 三栏填充率
```

四舍五入到整数；`≥70 high`、`40–69 medium`、`<40 low`。
**没登记风险 → risk_residual 记 0**，不给同情分：没有风险识别本身就是最大风险。
`band=low` 时按纪律**不得直接交付**，必须先补 `Need Info` 或改设计。

公式写在 `clash_analyzer.py` 的 docstring 里，任何人都能手算复现——
这样"存活率 62%"才是一句能被讨论的话，而不是一个数字。

---

## 命令行

```bash
# 初始化
python scripts/ultimate_orchestrator.py init --topic "议题" [--out DIR]

# 四阶段（每个阶段 --write 才落盘；不写时只做校验预览）
python scripts/ultimate_orchestrator.py stage1 --state S --file roles.json    --write
python scripts/ultimate_orchestrator.py stage2 --state S --file clash.json    --write
python scripts/ultimate_orchestrator.py stage3 --state S --file sandbox.json  --write
python scripts/ultimate_orchestrator.py stage4 --state S --file meta.json     --write

# 报告与检查
python scripts/ultimate_orchestrator.py report --state S --out REPORT.md
python scripts/ultimate_orchestrator.py check  --state S

# 单独使用量化器官
python scripts/clash_analyzer.py spark    --state S [--round 2] [--write]
python scripts/clash_analyzer.py survival --state S [--write]

python scripts/ultimate_orchestrator.py selftest
python scripts/clash_analyzer.py selftest
```

**退出码约定**（可被上层脚本直接判定）：

| 码 | 含义 |
|---|---|
| 0 | 通过 |
| 2 | 参数/文件错误 |
| 3 | 阶段校验失败（缺字段、数据来源不诚实、顺序错误、报告不合格） |
| 4 | 红蓝对抗未打出火花，**必须重开一轮** |

---

## 输入格式

阶段一 `roles.json`：

```json
{
  "confessions": [
    {"role": "musk",
     "text": "我的结论依赖……[数据诉求: 需要 2024 年 Q3 的竞品营收数据]",
     "tool_result": {"source": "tool", "tool": "web_search",
                     "query": "……", "result": "……", "obtained_at": "2026-11-01"}},
    {"role": "pg",
     "text": "……[数据诉求: 需要至少 3 个同类项目的两年跟踪数据]",
     "tool_result": {"source": "text", "simulated": true, "result": "（模拟）……"}}
  ]
}
```

阶段二 `clash.json`：

```json
{
  "camps": {"blue": ["munger", "jobs", "pg"], "red": ["musk", "feynman", "karpathy"]},
  "exchanges": [
    {"from": "munger", "inner_thought": "他根本没算过失败率，我先把他按在地上",
     "interrupt": true, "target_claim": "M1-1",
     "text": "[打断] 你的推演假设组织愿意改考核，这个假设没被验证", "evidence": "历史案例"}
  ]
}
```

阶段三 `sandbox.json` 与阶段四 `meta.json` 的字段见
`references/report-template.md` 的完整示例。

---

## 输出格式（冻结，不可改动）

报告严格按五节输出，缺任何一节、任一行动栏为空、或出现"已达成共识 / 各有优劣"这类措辞，
`report` 会直接报错退出（退出码 3）：

```markdown
### 📊 终极圆桌决策报告

#### 1. 核心共识与分歧底牌
- **共识**：xxx
- **核心分歧（未被完全解决）**：xxx

#### 2. 击穿的隐性假设（元认知发现）
- 我们一开始默认了 xxx，但沙盘推演证明这是错的。
- 我们忽略了 xxx 维度的成本。

#### 3. 行动指令 (Action Items)
- ✅ **Do（立刻执行）**：xxx
- ❌ **Don't（绝对禁区）**：xxx
- 🔍 **Need Info（需要补充调研）**：xxx

#### 4. 沙盘推演存活率评估
- 当前方案的预估存活率：XX%（满分100%）
- 最致命的潜在风险点：xxx

#### 5. 长期记忆写入
- `[MEMORY_UPDATE]`：xxx
```

报告末尾附「过程留痕」（数据诉求、红蓝分组、火花计数、召唤记录），
让读者能追溯每一条结论的来源。

---

## 反模式

1. ❌ 六个角色各说一遍、互相不碰——这不是圆桌，是六份备忘录。
2. ❌ 红蓝对抗打成"你说得对，我再补充一点"——火花检测会直接判 `no_spark` 并强制重开。
3. ❌ 内心戏写成心理描写（"他感到压力很大"）。内心戏必须是**利益或顾虑的披露**（"这方案会砍掉我的预算"）。
4. ❌ 把模拟数据当真实数据用。要么真调工具，要么明写 `simulated: true`，没有第三种。
5. ❌ 沙盘只写"会遇到一些挑战"。必须给出第几个月、什么指标、变成多少。
6. ❌ 行动清单写"加强沟通""持续优化"——这类没有主语、没有判据的句子等于没写。
7. ❌ 存活率凑到 80% 让方案好看。分数由四项分项决定，改数字就要改对应事实。
8. ❌ 长期记忆写成会议纪要。它应该是**下次能直接复用的判断**，不是这次发生了什么。
9. ❌ 召唤临时角色凑数。只有在出现真正的跨领域盲区时才召唤，且必须写清 `reason`。
10. ❌ 为了让报告完整而编造 `[MEMORY_UPDATE]` 或风险数据。

---

## 边界声明

- 本技能**不替代** `roundtable-orchestrator`：它做决策压缩，不做前提挖掘。
  需要挖共享前提时先跑前者，再把结论交给本技能做沙盘。
- 六个角色的思维协议来自 `role-*` 技能；单独部署本技能时，按角色名做**降级执行**
  并在报告里标注"降级模式"，不要假装完整协议已生效。
- 红蓝分组由编排引擎指定，**不允许角色自选阵营**（自选会退化成"和自己吵得赢的人吵"）。
- 存活率是**算术结果**，不是判断结论：它可以被逐项挑战与重算。
  它回答的是"当前证据下方案有多稳"，不回答"这个方案该不该做"。

## 参考文件

- `references/adversarial-tactics.md`：红蓝双方的具体战术清单、内心戏的写法与禁忌、
  打断的触发条件、召唤临时角色的判据、火花阈值调参指南。**在组织阶段二时读它。**
- `references/report-template.md`：完整报告模板与合格/不合格对照、存活率手算示例、
  长期记忆的写法（≤200 字）与反例、阶段三/四的完整 JSON 字段说明。**在写报告或补数据时读它。**

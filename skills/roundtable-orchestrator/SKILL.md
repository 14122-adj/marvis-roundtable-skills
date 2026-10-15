---
name: roundtable-orchestrator
description: "多角色圆桌讨论的编排引擎：调度角色思维协议、元认知监督者与立场迭代，按目标驱动推进多轮讨论并产出决策景观素材。当用户要求组织多角色圆桌讨论、让不同视角就同一问题交叉论证，或说「开启圆桌讨论」「让几个角色辩一辩」「多视角会诊」「圆桌推演」「让马斯克/费曼/芒格/乔布斯/Karpathy/Paul Graham 一起讨论」时，必须使用本技能。"
license: MIT
metadata:
  version: 1.0.0
  layer: "Layer 0 · 编排引擎"
---

# 圆桌编排引擎

本技能**不参与讨论**。它只做四件事：调度、记状态、控轮次、聚合产出。
六个角色各自的思维协议在 `role-*` 技能里；底层前提挖掘在 `meta-supervisor`；
立场修正的合法性判定在 `position-evolution`。

## 为什么这样设计（三个被点名的短板与回应）

| 原方案的短板 | 本编排层的回应 |
|---|---|
| 问题的根本藏在**所有人共享的隐性预设**里，角色互相辩论挖不到 | 每轮结束强制插入元认知层（`meta-supervisor`），其输出是下一轮的**强制输入**，角色必须正面回应 |
| 角色**立场写死**，被说服也不改 | 第 2 轮起开放立场修正（`position-evolution`），并记录 from/to/trigger，历史不删除 |
| 交互形式**人为硬规定**（必须一对一、必须联动≥2 人） | 只保留"轮次目标"，形式由角色自选；唯一的硬约束是**第一轮隔离发言**（防锚定） |

一句话：**把"讨论机制"从角色提示词里抽出来，交给编排层**。角色只管自己的思维协议。

## 契约（字段速查）

完整契约随仓库提供：`docs/output-contract.md`。单独部署本技能时以下字段即全部所需。

角色每次发言的输出块（YAML，可被脚本解析）：

```yaml
role: musk            # musk | feynman | munger | jobs | karpathy | pg
round: 2
position: 一句话立场（本轮基线）
claims:
  - id: M2-1          # 前缀：M=musk F=feynman G=munger J=jobs K=karpathy P=pg，格式 <前缀><轮次>-<序号>
    text: 论断正文
    basis: physical_constraint   # physical_constraint|empirical|case|mechanism|analogy|value_judgment|intuition
    evidence: 证据或推理链
    falsifiable_by: 什么观察能推翻它
responses:
  - to: P1-2          # 对方 claim id，或 H1/D1/G1/F1/C1（元认知条目）
    type: challenge   # support|challenge|refine|adopt|ignore_with_reason
    text: 回应内容
blind_spot_declared: 我这个视角看不见什么（必填）
epistemic_status:
  confidence: 65                # 0-100
  uncertainty_points: []        # 至少一条
  will_revise_if: 什么条件下愿意修正
revision:                       # 可选：出现即表示立场变化，交给 position-evolution 判定
  trigger: 引用 claim id 或 H/D/G/F/C 编号
  level: micro                  # micro|local|foundational
  from: 原立场摘要
  to: 新立场摘要
  reason: 修正理由
  remaining_doubt: 修正后仍不确定的地方
```

元认知条目编号：`H`=隐性假设　`D`=分歧　`G`=信息缺口　`F`=谬误　`C`=质疑。

## 状态文件与脚本

状态文件默认 `./.roundtable/<session_id>/state.json`（由脚本创建）。
四个脚本仅依赖 Python 标准库，全部通过 `--selftest` 自检：

```bash
# Layer 0（本技能）
python scripts/state_manager.py init --topic "议题" [--mode rigorous|simulation] [--max-rounds 3]
python scripts/state_manager.py begin-round --state S --round 2
python scripts/state_manager.py add-claims --state S --file musk-round2.json
python scripts/state_manager.py add-position --state S --file musk-round2.json
python scripts/state_manager.py summary --state S            # 文本摘要
python scripts/state_manager.py summary --state S --json     # 交接块
python scripts/state_manager.py get|set --state S --path meta.reviews
python scripts/round_controller.py plan --state S [--write]  # 下一轮目标与覆盖缺口
python scripts/round_controller.py coverage --state S
python scripts/convergence_detector.py check --state S [--write]

# Layer 2（meta-supervisor 技能）
python scripts/assumption_extractor.py scan --state S --write
python scripts/divergence_classifier.py suggest --state S --write
python scripts/fallacy_detector.py scan --state S --write

# Layer 3（position-evolution 技能）
python scripts/revision_tracker.py record --state S --file role-round2.json --write
python scripts/revision_tracker.py baseline --state S --role pg
```

脚本产出的是**候选**（`needs_judgment: true`）。它们不会替你判断"这是不是真的隐性假设"，只负责把值得复核的原文摆到桌面上。

## 工作流

### Step 0 · 建会话
1. `state_manager.py init` 创建状态文件。
2. 从议题里提取：**要做的决定是什么**、**谁受影响**、**什么算讨论成功**。写进 `topic` 与 R0 的 `shared_premises`。
3. 选模式：`rigorous`（严谨论证，默认）或 `simulation`（真人质感，允许保留更多不确定性表达）。
4. 角色裁剪：与议题无关的角色可以裁掉，但至少在记录里说明裁掉了谁、为什么。少于 3 个角色时告知用户"这已经不是圆桌，是两人对话"。

### Step 1 · R0 准备（不发言）
`round_controller.py plan --state S --write` 给出 R1 目标。同时把"大家默认接受但没论证过的前提"显式写下来：

```bash
python scripts/state_manager.py set --state S --path shared_premises \
  --append --value '"竞赛必须拿奖才算成功"'
```

这一步是**成本最低、收益最高**的动作：把共享前提提前摆到桌面上，胜过事后补救。

### Step 2 · R1 隔离发言
- 交互模式固定 `parallel_isolated`：**六份发言互不可见**。
- 这是唯一保留的形式约束，目的是防锚定：如果先让一个人长篇发言，后面的人会被拖进他的框架。工程做法是把六个角色分别调用（或分批生成但禁止互相引用），再一起登记。
- 每个角色 2–4 条 claim，必须带 `epistemic_status` 与 `blind_spot_declared`。
- 登记：`add-claims` + `add-position`。

### Step 3 · 元认知第 1 轮（必须执行，不可省略）
1. 跑三个 meta 脚本（`assumption_extractor` → `divergence_classifier` → `fallacy_detector`），`--write` 写回状态。
2. **模型侧**再补一轮脚本抓不到的隐性假设（没有标记词的、所有人默认的成败标准、默认的受益方等等），按契约 §4 的六段格式产出 META REVIEW。
3. 写回：把 META 报告 append 到 `meta.reviews`，并用 `set --append` 写 `injections`：

```bash
python scripts/state_manager.py set --state S --path injections --append \
  --value '{"round":2,"must_respond":["H1","H3"],"must_resolve":["C1"],"forbidden":["继续争论资源怎么分直到得出比例"]}'
```

`must_respond` 是**下一轮唯一强制的东西**：每个角色必须至少正面回应其中一条。

### Step 4 · R2 目标驱动交叉
- 交互模式 `cross_exam`，但**不做配对**。角色自行决定追问谁、追问几个人、或只补自己的证据。
- 提供建议而非命令：把 `round_controller.py plan` 输出的 `advisory.prioritize_untested_claims`（从未被任何人检验的论断）和 `unanswered_challenges` 交给角色，措辞是"建议优先处理"，不是"必须回应某某"。
- 角色回应元认知条目时，`responses[].to` 直接写 `H1`/`G2`/`C1`——脚本会把它们记进 `meta_engagement`。
- 允许修正：出现 `revision` 块就交给 `revision_tracker.py record --write`；有效修正会改写该角色下一轮的立场基线。
- 每轮结束跑 `convergence_detector.py check --write`。

### Step 5 · 元认知第 2 轮 + 收敛判定
重复 Step 3，并做三选一的决策：

- `recommendation = continue|deepen` → 进入 R3（或按 `max_rounds` 加轮）。
- `recommendation = meta_intervene` → 连续两轮无新增关键论据：本轮元认知报告必须**点名**在重复什么、并给出一个"换问题"的注入。
- `recommendation = close` → 进入 Step 6，但在关闭前必须明确回答：**哪些分歧是事实分歧（缺什么信息）、哪些是价值分歧（不可调和）**。这两类混在一起关闭是最常见的偷懒。

### Step 6 · 收尾与交接
1. `round_controller.py plan` 返回 `close` 时，跑 `state_manager.py summary --state S --json` 得到交接块。
2. 交接块里的 `minority_views` 中 `refuted: false` 的条目**必须**完整保留论证，不允许被多数票淹没。
3. `decision-landscape`（Layer 4，P2，本版本未实现）尚未提供时，直接用交接块 + 元认知报告向用户汇报，并注明"少数派观点未被有效反驳"。

### Step 7 · 向用户展示什么
每轮结束给一段**短**汇报，不要倾倒全文：

```
第 2 轮 · 目标：探究存疑前提
必须回应的隐性假设：H1（竞赛必须拿奖才算成功）→ 已回应 4/6
新增关键论据：2 条（少于上一轮的 5 条）
立场修正：pg 局部修正（R1，基于 M1-1）；jobs 检测到 1 次从众漂移，基线未变
悬空质疑：C1
收敛信号：跨轮重复表述 M1-1 ≈ P2-3（相似度 0.78）
下一步：R3 或提前收敛（原因）
```

## 轮次目标表（取代硬性交互规则）

| 阶段 | 轮次 | 目标 | 交互 |
|---|---|---|---|
| 准备 | R0 | 定义边界与成功判据，列出共享前提 | — |
| 立论 | R1 | 亮判断、论据、认知边界 | 隔离（防锚定） |
| 元认知 | R1.5 | 挖隐性假设、分类分歧、标信息缺口、查谬误 | 独立运行 |
| 深挖 | R2 | 探究对方的前提/证据/边界，回应注入条目 | 自由交叉，自主选对象 |
| 元认知 | R2.5 | 二次扫描 + 收敛判定 | 独立运行 |
| 综合 | R3 | 整合视角、识别矛盾根源、区分不可调和的价值观分歧 | 自由交叉 |

**明令禁止的写法**：本轮必须一对一轮流、必须联动 ≥2 人、每段不超过 N 字、必须按顺序发言。

## 终止条件（满足其一）

1. `round >= max_rounds`；
2. 连续 2 轮无新增关键论据，且已识别候选根因；
3. 元认知判定当前主要分歧是伪分歧或术语分歧——继续讨论无增量，提前关闭并说明原因；
4. 用户叫停。

关闭时**不得**声称"已达成共识"或"已挖到根本"——只能说"提供了 N 条待确认的根因候选"和"哪些信息补上后判断可能改变"。

## 反模式

1. ❌ 跳过元认知层直接开第 2 轮——整个设计的意义就在于那一步。
2. ❌ 让六个角色互相看见第一轮发言（破坏隔离，后面的人会被锚定）。
3. ❌ 把 `advisory` 清单当成命令，硬性指派"你去质疑他"——退回到被废弃的形式约束。
4. ❌ 把脚本的候选当成结论（"检测到 jobs 犯了稻草人谬误"）。正确说法是"规则命中一处转述偏差，需复核"。
5. ❌ 为了产出好看的报告，把没被回应的质疑悄悄标成 resolved。
6. ❌ 角色重复表述时继续加轮次。重复=没增量，应该换问题或收敛。
7. ❌ 在 `simulation` 模式下关闭严谨检查（模式只影响表达质感，不豁免逻辑要求）。
8. ❌ 讨论过程中编造数据、案例或"研究显示"。缺数据就登记为信息缺口 `G`。

## 参考文件

- `references/interaction-protocols.md`：交互模式细则、防锚定工程做法、追问策略、覆盖度诊断、三个完整流程示例。**在切换交互模式或判断"该不该追问"时读它。**

## 边界声明

- 本版本实现 P0（编排 + 元认知）与 P1（立场演化 + 六个角色协议）。Layer 4 `decision-landscape` 属 P2，未实现，但 Step 6 已预留交接字段。
- 六个角色技能可以**单独调用**（不经过编排器）：它们自带输出契约，此时相当于"单角色顾问"。
- 缺少某个角色技能时不要伪装成有该角色：要么跳过并说明，要么按 `role-*` 的协议摘要降级执行并标注"降级模式"。
- 所有 agent 共享同一底座模型时，底层偏见是共通的——本系统能暴露前提、能减少单视角盲区，但**不能保证跳出模型自身的偏见**。输出里不要暗示相反的意思。

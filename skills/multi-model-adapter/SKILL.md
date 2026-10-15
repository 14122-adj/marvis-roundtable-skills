---
name: multi-model-adapter
description: "异构基座适配层：同一底座模型的认知偏见是共通的，本技能把每个角色编译成独立的调用包（提示骨架 + 上下文 + 输出契约 + 隔离要求），交给支持多 provider 的宿主分别执行，再把结果合回同一个讨论状态。当用户要求用不同模型跑同一个圆桌、担心多角色共享同一基座而盲区一致、需要跨模型交叉验证，或 roundtable-orchestrator 要把角色分发到不同模型时，必须使用本技能。"
license: MIT
metadata:
  version: 1.1.0
  layer: "Layer 6 · 异构基座（可选）"
---

# 异构基座适配

角色技能规定"这个视角该怎么想"，编排层规定"讨论怎么推进"，本技能只规定**由谁执行**。
默认情况下所有角色跑在同一底座模型上：提示词差异能减少单视角盲区，但跳不出共享的训练偏差。
把角色分发到不同基座是缓解这一点的手段之一。本技能负责让分发这件事变得**可执行、可校验、可复现**。

## 定位与适用场景

**解决什么**

- 多角色共享同一底座模型时，底层认知偏见共通（`README.md` 第 6 节已如实声明）；本技能把这条声明推进为一个可尝试的工程动作。
- 把每个角色编译成独立调用包：提示骨架 + 上下文 + 输出契约 + 隔离要求，四样缺一不可，否则分发出去的结果合不回来。
- 跨模型交叉验证：同一议题由不同基座的角色各自立论，用来观察"某个结论是不是基座自身的产物"。
- 服务编排层：`roundtable-orchestrator` 需要把角色分发到不同模型时，走本技能的 emit / merge 两端。

**不解决什么**

- **不解决"多模型一定更好"**。异构会引入三类新成本：风格不一致（同一条判据在 A 模型上是克制、在 B 模型上是武断）、成本上升（多家计费、异常重试）、可复现性下降（参数、版本、截断行为都更难固定）。
- 不解决语义判断。合并校验只查结构（ID 前缀、轮次、basis 枚举、必填字段），"这算不算新增视角"仍由模型或人复核。
- 不改契约。字段名、枚举值、ID 规则一律以 `docs/output-contract.md` 为准，本技能只做搬运与校验。

## 核心概念：调用包

调用包（task bundle）是"一次可分发的最小执行单元"：**一个角色 × 一个轮次**。它必须自带足够的上下文，
使接收方在不看其他角色发言的前提下也能完成本轮任务——这正是隔离能够成立的前提。

| 字段 | 含义 |
|---|---|
| `role` | 角色标识（`musk` / `feynman` / `munger` / `jobs` / `karpathy` / `pg`） |
| `round` | 轮次号；必须与状态文件 `state.round` 推进后的目标轮次一致 |
| `phase` | 阶段标签（`opening` / `probing` / `synthesis` 等），取自状态文件 |
| `interaction_mode` | `parallel_isolated` 或 `cross_exam`；决定能否把他人发言放进上下文 |
| `isolation` | 本包的隔离要求：`parallel_isolated` 时禁止携带其他角色的原始发言，只允许携带元认知条目编号 |
| `goals` | 本轮认知目标（来自 `next_round.goals`），不是"必须说几句"这类形式约束 |
| `must_respond` | 必须正面回应的元认知条目编号（`H` / `D` / `G` / `C`），来源是 `injections` |
| `forbidden` | 本轮禁止重复的争论路线，原样搬运，不得由本技能增删 |
| `contract_summary` | 输出契约摘要：ID 规则、`basis` 枚举、必填字段；接收方不需要读仓库才能合规 |
| `payload_schema` | 期望的返回结构（与角色输出契约一致：`position` / `claims[]` / `responses[]` / `blind_spot_declared` / `epistemic_status`，可选 `revision`） |
| `provider` | 目标 provider 标识；未指定时为 `"unspecified"` |
| `model` | 目标模型标识；未指定时为 `"unspecified"` |
| `prompt_skeleton` | 提示骨架：角色协议要点 + 本轮目标 + 输出契约 + 隔离要求拼接成的可投递文本 |

`emit` 的子命令按角色逐个写出 `DIR/roles/<role>.task.json`，并写一份 `DIR/manifest.json`。
manifest 是这一轮分发的**唯一凭据**：它记录 provider 分配、隔离要求、契约摘要、每角色 payload schema、
生成时间、状态文件路径与轮次。事后想复现，看的是 manifest，不是聊天记录。

## 输入与输出

**输入**

- 状态文件 `S`：由 `roundtable-orchestrator/scripts/state_manager.py` 维护，提供 `roles`、`round`、`phase`、`interaction_mode`、`injections`、`next_round`。
- 轮次号：本轮要分发的目标轮次。
- 可选 `assignment.json`：provider 分配配置（见下一节）。
- 宿主回执（人工或宿主写入）：`DIR/roles/<role>.result.json`，以及实际使用的 provider / model / 采样参数。

**输出**

- `DIR/roles/<role>.task.json`：每个角色一个调用包。
- `DIR/manifest.json`：本轮分发凭据（含 `unspecified` 的诚实标注）。
- `merge` 的校验结论：

```jsonc
{
  "accepted": ["M2-1", "P2-3"],
  "rejected": [{"role": "feynman", "errors": ["BASIS_INVALID"]}],
  "missing_roles": ["jobs"]
}
```

- 给了 `--state-manager PATH`：把通过校验的结果登记回状态文件；否则只写 `DIR/validated/` 并打印应当执行的命令。`--dry-run` 只校验、不写任何文件。

## 工作流

```bash
python scripts/runtime_manifest.py emit --state S --round 2 --out DIR [--assignment assignment.json]
python scripts/runtime_manifest.py merge --state S --dir DIR [--state-manager PATH] [--dry-run]
python scripts/runtime_manifest.py selftest
```

1. **emit**（编排层调用）：读状态文件与轮次，按分配策略决定每个角色的 provider / model，写出 `DIR/roles/*.task.json` 与 `DIR/manifest.json`。`parallel_isolated` 轮次里，调用包**只**包含本角色协议、共享前提、元认知条目编号，不含其他角色的原始发言。
2. **宿主执行**：由宿主把每个调用包投递给对应 provider。本技能不发起任何网络请求，也不持有凭据。执行方必须保持隔离：隔离轮次不得让角色互相看到对方输出。
3. **回执落盘**：把每个角色的返回写成 `DIR/roles/<role>.result.json`，并记下**实际**使用的 provider、model、采样参数、时间与是否截断。请求值与实际值不一致时，以实际值入档。
4. **merge（先 `--dry-run`）**：只看校验结论，确认 `rejected` 与 `missing_roles` 是否为空，再决定是否落盘。
5. **merge**：正式校验并写 `DIR/validated/`；给了 `--state-manager` 才登记回状态文件。命令由本技能打印，也可以由编排层自己执行。
6. **回到编排层继续**：登记完成后跑一次 `convergence_detector.py check --write`，再由 `roundtable-orchestrator` 决定进入下一轮、深挖还是收敛。
7. **失败处理**：`rejected` / `missing_roles` 非空时，如实汇报给用户并保留原始回执；不得手工改写结果文件，也不得把缺失角色当成"无意见"。

## provider 分配策略

`assignment.json` 支持两种形态：显式映射，或 provider 列表 + 策略。

| 策略 | 配置形态 | 说明 |
|---|---|---|
| `explicit` | `{"<角色>": {"provider": "<provider-id>", "model": "<model-id>"}}` | 逐个角色指定；未出现在映射里的角色写 `unspecified` |
| `round_robin` | `{"providers": ["<provider-id>", "<provider-id>"], "strategy": "round_robin"}` | 按角色顺序轮流分配，适合"只想分散、不在乎谁跑谁" |
| `single_host` | 不传 `assignment.json`，或只给一个 provider | 全部角色落在同一基座；作为对照实验的基线组 |

规则：

1. **显式映射优先**：某个角色同时命中显式映射与 `round_robin` 时，以显式映射为准，并在 manifest 里标出分配来源。
2. **必须记录实际值**：manifest 要写清该角色**实际**使用的 provider 与 model（来自宿主回执），而不是只写请求值；只写请求值的分发不可复现。
3. **未指定一律写 `unspecified`**：`provider` 与 `model` 都未指定时，两个字段都写 `"unspecified"`，**不得**填入任何猜测或"常见默认值"的模型名。宁可让记录看起来不完整，也不允许伪造。
4. **本技能不解释模型能力**：不评估哪家更强、不给价格与性能判断。选择依据由用户或 `decision-landscape` 层面的讨论提供。
5. **轮间稳定**：同一角色在同一场讨论中若换了基座，manifest 必须标出换点（否则轮间差异会与模型差异混在一起）。

## 合并纪律

以下六条是硬约束，任一不满足就不是"合并完成"：

1. **ID 前缀与轮次必须匹配**：`<角色首字母大写><轮次>-<序号>`，费曼=F、芒格=G、乔布斯=J、马斯克=M、Karpathy=K、Paul Graham=P。前缀不是该角色，或 ID 里的轮次与本次合并轮次不一致，一律拒绝。
2. **basis 必须在枚举内**：`physical_constraint` / `empirical` / `case` / `mechanism` / `analogy` / `value_judgment` / `intuition`。枚举外的值不猜、不映射、不降级，直接拒绝。
3. **重复 ID 必须拒绝**：同一批次内 ID 重复，或与状态文件里已有 claim ID 冲突，整条拒绝并报 `DUPLICATE_ID`；轮内序号不得跳号、不得复用。
4. **角色缺失必须显式报告**：manifest 里有角色但没有对应 `result.json`，写进 `missing_roles`。静默跳过、当成空发言、或按"其他角色差不多"补写，都是伪造。
5. **必填字段缺一不可**：`role` / `round` / `position` / `claims[].id|text|basis|evidence` / `blind_spot_declared` / `epistemic_status.confidence` / `uncertainty_points`。缺失即 `MISSING_FIELD`。
6. **合并后必须跑一次收敛检测**：`convergence_detector.py check --write`，无论本轮结果是否全部通过校验都要跑。没有这一步，"合并完成"只是文件写完了。

校验只做结构判断，`accepted` 不等于"这条论断成立"。关键论据判定、`is_new_key_argument` 等语义字段仍由编排层与模型处理。

## 诚实边界

- **本环境未验证真实多 provider 调用**。本机没有可用的多 provider 路由、鉴权与计费通道，因此"真的用不同模型跑起来"这件事**没有被执行过**。
- **可运行的部分**：调用包的生成（`emit`）、结果的契约校验与合并（`merge`）、以及 `selftest`。这些只依赖 Python 标准库，操作的是本地 JSON 文件。
- **取决于宿主的部分**：宿主是否支持多 provider、如何路由、是否允许并发、是否有上下文长度与超时限制。宿主不支持时，`single_host` 是唯一诚实的降级选择——此时应如实说明"本轮仍是同基座讨论，共享偏见未缓解"。
- **未验证不等于可以编造**：不知道的模型标识就写 `unspecified`，没有回执就写 `missing_roles`。
- **异构不保证新增视角**：多个模型可能在同一批训练语料的偏差上同时出错，模型一致不构成结论正确的证据。判别方法见参考文件第 6 节。

## 反模式

1. ❌ 在 manifest 里编造 model 名称。未指定就写 `unspecified`；写"某个常见模型"比留空更糟，它会让整场讨论的复现记录变成假的。
2. ❌ 把结果当作已合并却不校验：跳过 `merge` 直接写状态文件，或把 `rejected` 手工改成 `accepted`。
3. ❌ 用不同模型掩盖同一错误结论：几个基座都指向同一个可疑结论，就被当成"交叉验证通过"。基座数量不构成证据强度。
4. ❌ 跳过隔离导致跨模型互相锚定：在 `parallel_isolated` 轮次把已发言角色的原文塞进后续调用包，等于让隔离形同虚设。
5. ❌ 用"不同模型风格本来就不同"解释契约违规。风格差异可以解释措辞，解释不了缺字段、basis 越界、ID 前缀不符。
6. ❌ 在合并前按"多数基座一致"淘汰少数派。契约规定：没被有效反驳的少数派观点必须完整保留（`refuted: false`）。
7. ❌ 只换模型、不改提示骨架，指望模型自动带来新视角。调用包不携带目标与契约时，换基座的收益会被格式混乱吃掉。
8. ❌ 只记 provider 不记实际 model / 采样参数 / 时间。缺这些字段的记录，无法与单基座基线做对照。

## 参考文件

- `references/provider-assignment-guide.md`：三种分配策略的场景与取舍表、调用包字段清单与抽象示例、合并校验错误码表、跨模型讨论的六类质量陷阱、可复现性清单、"同一议题单基座 vs 异构基座"对照实验模板。**在配置 provider 分配、判读 `merge` 的拒绝原因、或要判断异构是否真的带来新增视角时读它。**

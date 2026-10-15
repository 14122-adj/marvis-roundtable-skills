# provider 分配与异构合并指南

`multi-model-adapter` 的操作手册。回答四个问题：角色该分给谁、调用包怎么装、合并失败怎么判、
以及**异构到底有没有带来新增视角**。

## 目录

1. 三种分配策略的适用场景与取舍
2. 调用包字段清单与示例
3. 合并校验的错误码表
4. 跨模型讨论的质量陷阱
5. 可复现性清单
6. "同一议题单基座 vs 异构基座"对照实验模板

---

## 1. 三种分配策略的适用场景与取舍

| 策略 | 配置形态 | 适用场景 | 成本 | 可比性 | 偏见分散度 | 主要风险 |
|---|---|---|---|---|---|---|
| `round_robin` | `{"providers":["provider-a","provider-b"],"strategy":"round_robin"}` | 只想让角色分散到不同基座，不关心谁跑谁；探索性讨论 | 中（各 provider 计费口径不同，本技能不做估算） | 低：分到谁就靠谁，轮间可能换基座 | 中高 | 分配结果与角色协议不一定匹配；同一角色跨轮换基座会混入模型差异 |
| `explicit` | `{"<角色>":{"provider":"<provider-id>","model":"<model-id>"}}` | 已知某角色在某基座上表现更稳；需要把实验写死以便复现 | 可控（可预先算清调用量） | 高：逐轮一致，可写成配置文件入库 | 取决于映射本身 | 映射写死，provider 或 model 下线即失效，需人工维护 |
| `single_host` | 不传 `assignment.json`，或只给一个 provider | 复用同一流程做基线；对照实验的 A 组；宿主不支持多 provider 时的唯一选择 | 低 | 最高 | 无（就是单基座） | 不缓解共享偏见，不能声称"已做异构验证" |

取舍要点：

- **可比性 vs 偏见分散度**是一对反向指标。把角色固定在同一基座（可比性高）就无法分散偏见；把角色随机分散（分散度高）就牺牲了轮间可比性。对照实验通常两者都要：A 组固定，B 组分散。
- 混合策略是允许的：显式映射优先，未命中的角色走策略分配，再未命中的写 `unspecified`。manifest 必须能看出每个角色走了哪条路径。
- `unspecified` 不是配置错误，而是一种**诚实状态**：说明该角色的基座未知或未指定。它比"随便填一个常见模型名"有用得多。

## 2. 调用包字段清单与示例

字段清单（以 `docs/output-contract.md` 为契约来源，本技能不新增字段）：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `role` | string | 是 | 角色标识 |
| `round` | int | 是 | 目标轮次，需与状态文件推进后的轮次一致 |
| `phase` | string | 是 | `opening` / `probing` / `synthesis` 等 |
| `interaction_mode` | string | 是 | `parallel_isolated` 或 `cross_exam` |
| `isolation` | string | 是 | `isolated`（对应 `parallel_isolated`）或 `cross_visible`（对应 `cross_exam`；只允许引用他方 claim id，不得整段搬运） |
| `goals` | array | 是 | 本轮认知目标，原样搬运 |
| `must_respond` | array | 是 | 必须回应的 `H` / `D` / `G` / `C` 编号，可为空数组 |
| `forbidden` | array | 是 | 本轮禁止重复的争论路线，可空 |
| `contract_summary` | object | 是 | ID 规则 + `basis` 枚举 + 必填字段，使接收方无需读仓库即可合规 |
| `payload_schema` | object | 是 | 期望返回结构 |
| `provider` | string | 是 | 目标 provider；未指定写 `"unspecified"` |
| `model` | string | 是 | 目标模型；未指定写 `"unspecified"` |
| `prompt_skeleton` | string | 是 | 可直接投递的提示骨架（角色协议要点 + 目标 + 契约 + 隔离要求） |

示例（**`provider-a` / `model-x` 是占位符，不是任何真实产品或模型**）：

```jsonc
{
  "role": "musk",
  "round": 2,
  "phase": "probing",
  "interaction_mode": "cross_exam",
  "isolation": "cross_visible",
  "goals": ["探究对方论据中存疑的前提与边界条件"],
  "must_respond": ["H1", "H3"],
  "forbidden": ["继续在资源分配比例上争论"],
  "contract_summary": {
    "claim_id": "<角色首字母大写><轮次>-<序号>",
    "basis_enum": ["physical_constraint", "empirical", "case", "mechanism",
                   "analogy", "value_judgment", "intuition"],
    "required": ["role", "round", "position", "claims", "blind_spot_declared", "epistemic_status"]
  },
  "payload_schema": {
    "position": "string",
    "claims": [{"id": "string", "text": "string", "basis": "enum",
                "evidence": "string", "falsifiable_by": "string"}],
    "responses": [{"to": "string", "type": "support|challenge|refine|adopt|ignore_with_reason", "text": "string"}],
    "blind_spot_declared": "string",
    "epistemic_status": {"confidence": "int 0-100", "uncertainty_points": "array", "will_revise_if": "string"},
    "revision": "optional object"
  },
  "provider": "provider-a",
  "model": "model-x",
  "prompt_skeleton": "<角色思维协议要点> + <本轮目标> + <输出契约> + <隔离要求>"
}
```

manifest（`DIR/manifest.json`）至少要能回答：**这轮谁跑了什么、谁没指定、隔离要求是什么、什么时候生成的、状态文件在哪、轮次是多少。**

## 3. 合并校验的错误码表

`merge` 的 `rejected[].errors` 只使用下列错误码，不做模糊归类：

| 错误码 | 触发条件 | 处理动作 | 是否阻断 |
|---|---|---|---|
| `ID_PREFIX_MISMATCH` | claim id 前缀与该角色不符（例：feynman 提交 `M2-1`） | 拒绝该条 claim，保留原报文供核对 | 是（该条） |
| `ROUND_MISMATCH` | id 内轮次或报文 `round` 与本次合并轮次不一致 | 拒绝该条；提示可能是轮次错配或复用旧回执 | 是（该条） |
| `BASIS_INVALID` | `basis` 不在七值枚举内 | 拒绝该条；不猜测、不映射、不降级 | 是（该条） |
| `DUPLICATE_ID` | 批次内 id 重复，或与状态文件已有 claim id 冲突 | 拒绝重复条目，保留首次出现者 | 是（重复项） |
| `MISSING_FIELD` | 缺 `role` / `round` / `position` / `claims[].id|text|basis|evidence` / `blind_spot_declared` / `epistemic_status.confidence` / `uncertainty_points` | 拒绝该角色本次提交中不合规的部分 | 是（该条） |
| `UNKNOWN_ROLE` | 提交的角色不在本轮 manifest 的角色列表内 | 拒绝整个文件；不自动扩员 | 是（整文件） |
| `MISSING_ROLE` | manifest 中的角色没有 `result.json` | 写入 `missing_roles`，继续合并其余角色 | 否（但必须汇报） |

纪律：

- `rejected` 与 `missing_roles` 必须原样汇报，**不得**为了"看起来完整"而补写或改为 `accepted`。
- 校验通过（`accepted`）只表示结构合规，不表示论断成立；语义判定仍由编排层与模型完成。
- 错误码只是定位工具，报告用户时要说清具体是哪一条、原文长什么样。

## 4. 跨模型讨论的质量陷阱

| 陷阱 | 现象 | 后果 | 处置 |
|---|---|---|---|
| 风格差异被误读为分歧 | A 模型写得克制、B 模型写得武断，读起来像两种立场 | 元认知把措辞差异登记成"分歧"，凭空多出 `D` 条目 | 分类前先对齐语义，不是对齐语气；同一语义只保留一条 |
| 拒答策略不同 | 某模型拒绝角色化表态，返回一段元评论或空内容 | 被当成"该角色沉默"或"弃权"，实际是执行失败 | 记为缺失（`missing_roles` 或整条 `MISSING_FIELD`），不要当成观点 |
| 采样参数影响可复现性 | 温度、`top_p`、种子不同，同一调用包产出不同 | 轮间差异无法归因到"视角"还是"随机性" | 固定参数并入档；改动参数视为新实验 |
| 上下文截断差异 | 长状态文件在不同 provider 上被截断的位置不同 | 有的角色看不到 `must_respond`，回应率统计失真 | 记录是否截断；截断即标注，不得计入"未回应" |
| 同基座同错被当成共识 | 多个基座都指向同一个可疑结论 | 一致性被误当作证据强度 | 多模型一致不是证据；仍走 `basis` 与 `falsifiable_by` 检验 |
| 判定口径漂移 | 同一份 META 分类在不同模型上标准不同 | 跨轮次的 `H` / `D` / `G` 计数不可比 | 判定口径写在项目约定里；口径变更要留痕 |

前两条最容易被忽略：它们不会报错，只会让讨论看起来"更丰富"。

## 5. 可复现性清单

每轮分发完成后逐项核对，缺项就写 `unsupported` 或 `unknown`，不留空：

- [ ] `provider` 标识（实际值，不是请求值）
- [ ] `model` 标识（宿主回执里的实际值；请求值与实际值不同时两者都记）
- [ ] 采样参数：温度、`top_p`、最大输出长度
- [ ] 随机种子（宿主不支持则写 `unsupported`）
- [ ] 每次调用的时间戳（含时区）
- [ ] 调用包哈希（对规范化后的 `task.json` 求哈希；注明哈希算法）
- [ ] `manifest.json` 的路径与生成时间
- [ ] 状态文件路径、`schema_version` 与轮次
- [ ] 本轮 `interaction_mode` 与 `isolation`
- [ ] 重试次数与失败原因（若发生）
- [ ] 是否发生上下文截断
- [ ] 契约版本（`docs/output-contract.md` 的版本号）
- [ ] 角色到基座的映射来源（`explicit` / `round_robin` / `unspecified`）

判断标准很简单：**换一个人拿着这份记录，能不能在没有聊天历史的情况下重跑出同一批调用包。** 做不到就不算可复现。

## 6. "同一议题单基座 vs 异构基座"对照实验模板

目的：判断异构是否真的带来**新增视角**，而不是只带来措辞差异。这是一个需要人工复核的判断，
脚本只能把材料摆齐（`needs_judgment: true`）。

**固定项（两组必须完全一致）**

1. 议题原文、角色集合、`max_rounds`、轮次目标与 `injections`；
2. 输出契约版本与提示骨架结构（除 provider / model 字段外逐字相同）;
3. 采样参数口径（尽量固定；无法固定则两组一致地记录）；
4. 元认知的判定口径。

**两组设置**

- A 组：`single_host`，全部角色落在同一个 provider / model。
- B 组：`explicit` 或 `round_robin`，角色分散到多个 provider / model，映射入档。

**正判据（满足其一才算可能的新增视角）**

1. B 组出现了 A 组完全没有的 `basis` 类型或论据链，而不只是同一论断换措辞；
2. B 组产生了新的元认知条目（新的 `H` / `D` / `G`），且该条目确实触及 A 组的共享前提；
3. B 组有论断收窄或推翻了 A 组某条 claim 的适用范围（即发生了实质性 `revision` 条件）。

**反判据（出现即视为假增益）**

1. B 组新增内容只是 A 组的同义改写（可用跨轮重复度工具比对措辞相似度）；
2. B 组新增条目没有任何角色引用（既不进 `responses[].to`，也不改变任何立场基线）；
3. B 组新增条目 `basis` 全是 `intuition` / `value_judgment` 且没有 `evidence`。

**记录表模板**

| 项 | A 组（单基座） | B 组（异构） |
|---|---|---|
| 角色 → provider/model | 全部同一基座 | 逐角色记录 |
| 新增关键论据数 |  |  |
| 新增 `H` / `D` / `G` 条目 |  |  |
| 与对方论断的引用次数 |  |  |
| 有效修正次数（含 `remaining_doubt`） |  |  |
| 正判据命中 | — |  |
| 反判据命中 | — |  |
| 结论 | — | 需人工复核 |

**读表方式**：若 B 组只在"措辞/篇幅"上更丰富，而新增论据数、元认知条目数、引用次数与 A 组接近，
那么这轮异构的收益没有证据支持，应当如实写"未观察到新增视角"。
反过来，B 组更丰富也可能来自成本更高的调用或更长的上下文，不能自动归因于"多基座"。

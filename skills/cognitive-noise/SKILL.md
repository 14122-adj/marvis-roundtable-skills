---
name: cognitive-noise
description: "轻量认知噪声层（默认关闭）：为圆桌角色注入三种可控的不完美——选择性注意（只看见部分历史并必须声明忽略了什么）、表达偏好（先说结论/先说顾虑/保守/冒险四档）、置信度传导（低置信度必须带保留语气，高置信度必须自陈可能错在哪）。当用户觉得讨论太干净太理性、要求模拟真人的表达质感与不确定性，或 roundtable-orchestrator 在 mode=simulation 下需要注入噪声时，必须使用本技能。仅在 simulation 模式下可用。"
license: MIT
metadata:
  version: 1.1.0
  layer: "Layer 5 · 认知噪声（可选）"
---

# 轻量认知噪声层

本层是 Layer 5 的**可选**组件，默认关闭。
它不给讨论增加任何新论据，只改变角色"看得见什么"和"怎么说"。

## 定位与代价提示

- 本层不是质量层，是**质感层**：它的全部作用是让发言更像真人，而不是更接近真相。
- **本层会降低严谨性**，这是设计选择而不是副作用：注意力被削弱、表述被风格化、语气被置信度绑定。
- 需要高质量结论时用 `rigorous` 模式并保持本层关闭；只有在"模拟真人讨论"本身就是交付物时才开启。
- 开启本层不会提升讨论质量，也不得在报告里暗示它提升了讨论质量。噪声之后的产物，仍然要靠元认知层与立场演化层来兜底。
- 代价可量化也可回滚：注意力比例、种子、风格档位都必须写进状态，关闭后可用同一参数复跑同一议题。

## 开关条件

- **仅 `mode=simulation` 可用**。状态文件里 `mode` 字段不是 `simulation` 时，`plan` 必须直接拒绝执行并给出理由，不得降级执行、不得"先跑再看"。
- `mode=rigorous` 下调用本层必须直接拒绝，理由固定为：严谨模式的目标是论证质量，噪声会削弱论据覆盖与前提回应，二者目标冲突。
- 模式在会话中途从 `simulation` 改回 `rigorous` 时，噪声立即停用；已写入的 `attention_manifests` 与 `style_profile` 保留但不再生效，并在下轮汇报中注明"本轮起噪声已关闭"。
- 本层**不能自行开启**。它只在用户明确要求，或 `roundtable-orchestrator` 在 `simulation` 流程中显式调用时生效。
- 三层噪声可以单独开启其中一项（例如只要表达偏好），但开启项必须在状态里记录，不能隐式生效。

## 三类噪声的定义与边界

### 1. 选择性注意

- **做什么**：按确定性种子从状态历史中选取部分条目（默认比例 0.6，可由 `--attention` 调整）作为本轮"看得见"的历史；未被选中的条目写入 `ignored` 清单。
- **不许做什么**：角色不得引用 `ignored` 里的内容；也不得假装它不存在——被问到时必须承认"我这轮没注意到"，而不是声称该条不存在、不成立或已被处理。
- 条目本身**一字不改**：可见与不可见的分割只发生在条目层面，不发生在句子层面。

### 2. 表达偏好

- **做什么**：四档 `conclusion_first`（先说结论）/ `concern_first`（先说顾虑）/ `conservative`（倾向保守估计、主动加安全边界）/ `adventurous`（倾向激进方案，但必须自己写出最大下行风险）。
- **不许做什么**：风格**只影响语序与措辞**，不改变论据类型、不做无证据的断言；不得因为档位是 `adventurous` 就省略下行风险，也不得因为档位是 `conservative` 就把 `basis` 从 `mechanism` 改写成 `empirical`。

### 3. 置信度传导

- **做什么**：按本轮 `epistemic_status.confidence` 强制语气档位——`confidence < 40` 必须使用保留语气（"我倾向…""这可能是错的"）；`confidence >= 90` 必须写出"我可能错在哪"；`40–69` 正常表述但必须给出 `will_revise_if`。
- **不许做什么**：语气档位不得反过来倒改置信度数值；不得用 `>= 90` 的强断言语气配一个低置信度数值，也不得用保留语气包装一个 `95` 的自信结论。

## 可控性红线

噪声**只能改变"看见什么"和"怎么说"，绝不能改变论断内容、证据、ID、枚举值**。具体红线：

1. 选择性注意只影响可见历史范围，**不得改写原文**：`noticed` 条目的文本必须与状态中原文逐字一致。
2. 表达档位只管语序与措辞，不管论断类型、证据强度、`basis` 枚举与 `falsifiable_by`。
3. 置信度传导只管语气，不管 `confidence` 数值本身。
4. `claims[].id`、`responses[].to`、`H/D/G/F/C` 编号一律不得因噪声而增删或改号；不得为"没注意到"的条目编造一个 id。
5. 不得事后用噪声解释结论变化：噪声不构成修正理由，`revision.trigger` 里引用噪声不成立。
6. 噪声不得用于规避 `must_respond`、`must_resolve` 等元认知注入项——"这轮没注意到"不是豁免理由，元认知层会核查。

## 声明义务

每一轮开启噪声的发言，**必须**输出 `attention_manifest`，含三部分：

- `noticed`：本轮可见条目的 id 列表；
- `ignored`：本轮不可见条目的 id 列表；
- `attention_ratio`：实际比例，以及被忽略条目数占历史总量的比例。

纪律要求：

1. 忽略清单必须完整、可枚举，**必须可被元认知层核查**：元认知层用 `check` 逐条比对 id 是否真实存在于状态中。
2. 只写"看见了相关历史"不算声明，必须给出 id。
3. 角色在正文里被追问 `ignored` 中的内容时，标准回答是"我这轮没注意到它"，并说明是否要在下一轮补看；**不得**临时声称该条已被回应、已被推翻或无关紧要。
4. `attention_manifest` 缺失时，本轮发言标记为不合格，不得进入收敛统计。

## 输出契约

噪声元数据是附加字段，**不替代任何既有字段**。契约 §3 的角色输出块一个字段都不能少，噪声信息按以下结构追加：

```yaml
noise:
  attention_manifest:
    noticed: [M1-1, P1-2, H1]
    ignored: [J1-3, G1-2]
    attention_ratio: 0.6
  style_profile: conclusion_first
  tone_rules:
    band: high
    requirement: 必须写出"我可能错在哪"
  seed: 7
```

与契约 §3 的关系：

- §3 的 `claims` / `responses` / `blind_spot_declared` / `epistemic_status` 仍是**主体**，噪声块只是在同一轮发言上附加的来源标注。
- 状态文件层面只允许新增两个顶层附加字段：`attention_manifests`（数组，`--write` 写入）与 `style_profile`（对象）。不得自创其他输出字段。
- `attention_manifests` 记录：角色、轮次、种子、比例、`noticed`、`ignored`、`style_profile`、`warnings`。
  （本仓库实现里 `style_profile` 记录在**每条 manifest 内部**，便于逐轮复现；顶层 `style_profile` 字段保留给宿主自用，脚本不写入。）
- 元认知层读 `attention_manifests` 的方式与读 `positions` / `claims` 一致：只做核查与标注，不代替模型判断。

## 工作流

### Step 1 · 确认模式
读状态文件 `mode`。不是 `simulation` 就停止，向用户说明"噪声层仅在仿真模式可用，当前为严谨模式"，并给出两个选项：保持严谨模式不注入噪声，或显式改用仿真模式。

### Step 2 · plan · 生成注意力清单与表达档位
```bash
python scripts/noise_injector.py plan --state S --role pg [--seed 7] [--attention 0.6] [--style auto|conclusion_first|concern_first|conservative|adventurous] [--write]
```
- `plan` 输出：角色、轮次、模式检查结果（mode_ok）、种子、比例、`noticed`（可见条目 id 列表）、`ignored`（不可见条目 id 列表）、`style_profile`、`tone_rules`（按置信度分档的语气要求）、`warnings`。
- `--write` 把注意力清单写入状态的 `attention_manifests` 数组；不写时只在 stdout 展示，供人工确认。
- 同一会话同一轮必须是同一份清单：种子固定后不得重掷。重新抽样等于换了一份历史，必须记为新的轮次或新的会话。

### Step 3 · 角色按档位发言
角色拿到 `noticed` 清单与 `style_profile` 后正常发言：论点、论据、回应照 §3 契约写；只调整语序、措辞与语气；同时在 `noise` 块里如实回填 `noticed` 与 `ignored`。

### Step 4 · check · 校验
```bash
python scripts/noise_injector.py check --state S
```
- `check` 输出：模式合法性（rigorous 模式出现噪声记录则报警）、声明完整性（有 plan 但无 manifest 则报警）、**是否篡改事实**（noticed 条目的 id 必须真实存在于状态中）。
- `check` 还比对风格档位与实际发言语气是否一致，不一致给出 `warnings`。
- 所有 `needs_judgment: true` 的字段都表示需模型或人工复核；脚本只摆事实，不判断语义。

### Step 5 · 元认知层核查忽略清单
把 `attention_manifests` 交给元认知层，逐条核查两件事：① `ignored` 里是否有本轮必须回应的 `must_respond` / `must_resolve` 项（若有，"没注意到"不构成豁免）；② `ignored` 是否集中在最近一轮的关键质疑上（若集中出现，说明选择性注意正在替代直面论证，应点名）。核查结论写入 META 报告，不写进噪声块。

### Step 6 · selftest 与收尾
```bash
python scripts/noise_injector.py selftest
```
退出码 0 表示脚本可用。会话结束时在汇报里列出：本会话哪些轮次开了噪声、种子与比例、以及"噪声未提升论证质量，结论仍需按严谨口径复核"。

## 反模式

1. ❌ 用噪声掩盖没有论据：论据不足是论据问题，加噪声只是让发言读起来更像真人，不会凭空补出证据。
2. ❌ 在 `rigorous` 模式下偷偷启用，或把模式检查失败当成"脚本太严"绕过——模式就是开关，绕过等于篡改模式声明。
3. ❌ 选择性忽略关键质疑后声称"没看到"。被问到时必须承认"我这轮没注意到"；把没看到当成没发生是欺骗。
4. ❌ 把风格档位当成降低论据要求的借口：档位是 `adventurous` 就可以只讲上行、不写下行风险，这是违规而不是风格。
5. ❌ 用噪声块替代 §3 契约字段：以为写了 `attention_manifest` 就能省略 `uncertainty_points` 或 `blind_spot_declared`。
6. ❌ 事后为了让结论好看而重掷种子、改比例，或把 `ignored` 清单缩减后再报"全部看见了"。
7. ❌ 用保留语气包装高置信度结论（语气说"我倾向"，数值写 95），或用强断言语气配低置信度数值。
8. ❌ 开启噪声后把汇报口径也放松：噪声只改发言质感，不改汇报口径与严谨检查项。

## 参考文件

- `references/cognitive-noise-guide.md`：三类噪声的量化参数建议、四档表达偏好的正反例、置信度分档措辞库、误用清单、与元认知层的配合方式、关闭噪声后的复跑规则。**在设参数、选档位、写保留语气或判断"这轮该不该开噪声"时读它。**

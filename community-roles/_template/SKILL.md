---
name: role-YOURNAME
description: "一句话说清这个角色强制执行的思维动作，以及什么时候该用它。写成「以 X 为硬约束的圆桌角色技能：……。当用户……，或 roundtable-orchestrator 调用 <role> 角色发言时，必须使用本技能。」"
license: MIT
version: 1.0.0
metadata:
  version: 1.0.0
  layer: "Community · 你的视角分类"
  role: yourname
  contributed: true
---

# role-YOURNAME · 一句话概括

> 复制这个目录后，请把 `role-YOURNAME` 改成 `role-<你的角色名>`，
> 并把 `name:` 改成同一个名字（校验器会检查一致性）。

## 角色定位

3–5 行，写清三件事：

1. 这个视角**只做**什么（一句话）；
2. 它**不做**什么（划清边界，避免和现有角色重叠）；
3. 不做名人扮演、不编造原话、不虚构私人事件。

## 思维协议

5 步。每步必须写「做什么 / 产出什么 / 不通过的判据」。
这是整个角色的核心——**没有判据的步骤等于没有步骤**。

**步骤 1 · 名称**

- 做什么：
- 产出什么：
- 不通过的判据：

**步骤 2 · 名称**

- 做什么：
- 产出什么：
- 不通过的判据：

**步骤 3 · 名称**

- 做什么：
- 产出什么：
- 不通过的判据：

**步骤 4 · 名称**

- 做什么：
- 产出什么：
- 不通过的判据：

**步骤 5 · 名称**

- 做什么：
- 产出什么：
- 不通过的判据：

## 天然张力

必须写明与**至少一个现有角色**的冲突点。说不出冲突，说明这个角色是冗余的。

- **与 musk**：……冲突点是什么。
- **与 feynman**：……
- **与 munger**：……
- **与 jobs**：……
- **与 karpathy**：……
- **与 pg**：……

## 已知盲区

至少 3 条。**这一节最能看出作者是否真的想清楚了。**

- 盲区一：……（表现：……；自查信号：……）
- 盲区二：……
- 盲区三：……

## 输出契约

每轮发言必须给出以下 YAML 块（字段名原样引自 `docs/output-contract.md` §3，不得改名）：

```yaml
role: yourname
round: 1
position: 一句话立场

claims:
  - id: X1-1
    text: 论断正文
    basis: empirical
    evidence: 证据
    falsifiable_by: 什么观察能推翻它

responses:
  - to: M1-1
    type: challenge
    text: 回应内容

blind_spot_declared: 我这个视角看不见什么（必填）

epistemic_status:
  confidence: 60
  uncertainty_points: []
  will_revise_if: 什么条件下愿意修正
```

**本角色 claim id 前缀是 `X`**（请改成你选的、未被占用的字母）。

已被占用：`M` musk、`F` feynman、`G` munger、`J` jobs、`K` karpathy、
`P` pg、`V` civilian、`C` contrarian。

`basis` 只能取：`physical_constraint`、`empirical`、`case`、`mechanism`、
`analogy`、`value_judgment`、`intuition`。

## 分轮次行为

**R1（opening，`parallel_isolated`）**：……

> 注意：R1 是隔离轮次，看不见其他角色发言。
> 引用对象只能是**议题原文**与 **R0 的 `shared_premises`**（见契约 §2）。

**R2（probing，`cross_exam`）**：必须回应注入的 H/G 条目。……

**R3（synthesis）**：……

## 修正权限

依据契约 §5，修正必须至少满足一条触发条件且可被引用：
收到此前未考虑的事实证据（新 claim 或 G 编号）；对方提出本角色思维协议无法反驳的论证；
元认知标记了某条隐性假设且本角色认可其值得质疑；发现自己的论据类型本身失效。

**禁止从众漂移**：无新信息、仅因"多数人这样认为"而改变立场会被判为 `compliance_drift`。

本角色特有的修正条件：……（可选）

## 反模式

至少 5 条，写清"这个角色最容易犯的错"：

1. ❌ ……
2. ❌ ……
3. ❌ ……
4. ❌ ……
5. ❌ ……

## 参考文件

- `references/your-topic.md`：……（120–200 行，含目录，写可操作的方法而不是角色简介）。

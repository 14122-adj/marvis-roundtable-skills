---
name: ultimate-roundtable
description: "终极专家圆桌机制 V3.0：在红蓝对抗与沙盘推演之上，加入跨会话记忆锚点、强制工具调用闭环与数据交叉验真，让讨论从内部推演走向现实验证。当用户要求开启终极圆桌、深度推演讨论、红蓝对抗圆桌，或需要把多视角讨论压成 Do/Don't/Need Info 行动清单并给出存活率评估时，必须使用本技能。"
license: MIT
version: 3.0.0
trigger:
  - 开启终极圆桌
  - 深度推演讨论
  - 红蓝对抗圆桌
permission:
  - read_workspace
  - write_workspace
  - execute_tools
metadata:
  version: 3.0.0
  layer: "Layer 0+ · 高强度审议（ultimate）"
  extends: roundtable-orchestrator
---

# 终极圆桌 V3.0

V2 把六个人的观点压成了一条流水线。V3 要解决的是另一件事：
**这条流水线跑完之后，结论到底有没有接触过真实世界。**

三个新增的硬约束：

1. **记忆**——开会前先读历史教训，开完必须写回，否则每次都在从零开始；
2. **工具**——每个 `[数据诉求]` 必须有 `[Tool Call]` 闭环，不允许抛了问题就跑；
3. **验真**——辩论中可以直接 `[打断并验真]`，当场查证对方的未验证前提。

## 与 V2 / `roundtable-orchestrator` 的分工

| | roundtable-orchestrator | ultimate V2 | **ultimate V3** |
|---|---|---|---|
| 目标 | 挖到共享前提 | 压成决策 | 压成**经过外部验证**的决策 |
| 数据 | 登记缺口即可 | 必须标真实/模拟 | 必须标 + **必须有 Tool Call 闭环** |
| 记忆 | 无 | 单次 | **跨会话读写** |
| 辩论 | 自由交叉 | 红蓝 3v3 | 红蓝 3v3 + **打断并验真** |
| 沙盘 | 决策景观 | 逐月推演 | 逐月推演 + **工具验证假设** |

---

## 五个阶段（每次响应必须严格按此结构推进）

### 阶段零 · 记忆唤醒（新会话第一轮）

```bash
python scripts/memory_store.py intro            # 生成开场白
python scripts/ultimate_orchestrator.py stage0 --state S --write
```

输出一句开场白，格式固定：

```
[会议启动] 已加载历史记忆：1. [2026-11-01] … ｜ 2. …
```

没有历史记录时写：`[会议启动] 已加载历史记忆：无记忆记录（这是本议题的第一次推演）`。
**不允许跳过**——跳过就意味着每次讨论都从零开始，这正是 V3 要消灭的东西。

### 阶段一 · 数据诉求与外部调用

每条角色发言必须同时具备三样：

1. `[数据诉求: …]` —— 结论依赖的关键数据；
2. `[Tool Call: Search] 关键词：…` 或 `[Tool Call: Code] 目的：…` —— **对应的调用**；
3. `基于此数据，我的观点是…` —— 拿到结果后的**明确表态**。

缺任一样，阶段一整体拒绝（退出码 3）。这就是 spec 说的「闭环要求：
所有 `[数据诉求]` 必须在本次会话中有 `[Tool Call]` 的对应结果，不允许抛出问题就跑」。

数据来源仍必须二选一标注：`source: "tool"`（真实调用）或 `simulated: true`（模拟）。
两者都不标 = 把模拟数据伪装成真实数据 = 拒绝。

### 阶段二 · 幽灵干预与红蓝对抗

**内心戏**：发言前必须 `(Inner Thought: ...)`——没说出口的利益与顾虑。

**交叉验真**：发现对方引用未验证前提时，用 `[打断并验真]`，并且**必须给出验真结果**
（`[Tool Call]` 或 `verify_result`）。只打断不查证 = 拒绝。

**红蓝 3v3**：编排引擎指定阵营，不允许自选。

**火花检测**：六个计数任一不达标 → 退出码 4，强制重开（判据见 §「量化」）。

### 阶段三 · 终极沙盘与动态召唤

- `timeline` ≥ 3 个月度节点，每节点必须给 `metric` 或 `error`；
- 主推必须是 Karpathy + 马斯克；
- **`tool_calls` 至少 1 条**：沙盘必须用代码执行或搜索验证假设（V3 新增硬要求）；
- 跨领域盲区 → `[召唤：金融风控]`，必须写清 `reason` 与 `statement`。

### 阶段四 · 记忆沉淀

- 共同隐性假设 + 被证伪前提 + 被忽略的成本维度；
- `[MEMORY_UPDATE]` ≤200 字，**并真正写入记忆库**（默认 `persist_memory: true`）。

---

## 量化模型（可复算）

### 火花判据

| 计数 | 含义 | 默认门槛 |
|---|---|---|
| `attack_count` | 蓝军有效攻击（有靶点 + 有内容） | ≥ 3 |
| `defense_count` | 红军有效防御/修补 | ≥ 2 |
| `target_spread` | 被攻击的不同 claim 数 | ≥ 2 |
| `signal_total` | 攻击+防御+立场修正+新论据 | ≥ 3 |
| `hollow_ratio` | 空洞发言占比 | ≤ 0.34 |
| `unmet_must_respond` | 未回应的元认知强制条目 | 空 |

### 存活率

```
survival = 0.40 × risk_residual      # 100×(1-平均(severity×probability))；无风险记 0
         + 0.25 × evidence_coverage  # 关键假设中带证据的比例
         + 0.20 × defense_quality    # attacks 中被 defended 的比例
         + 0.15 × plan_integrity     # Do/Don't/NeedInfo 三栏填充率
```

`≥70 high`｜`40–69 medium`｜`<40 low`。`low` 不得直接交付。

---

## 命令行

```bash
UR=scripts

# 阶段零：记忆
python $UR/memory_store.py stats                       # 看记忆库现状
python $UR/memory_store.py recall --query 评审          # 检索相关历史
python $UR/ultimate_orchestrator.py stage0 --state S --write

# 阶段一~四
python $UR/ultimate_orchestrator.py init   --topic "议题" --out DIR
python $UR/ultimate_orchestrator.py stage1 --state S --file roles.json   --write
python $UR/ultimate_orchestrator.py stage2 --state S --file clash.json   --write
python $UR/ultimate_orchestrator.py stage3 --state S --file sandbox.json --write
python $UR/ultimate_orchestrator.py stage4 --state S --file meta.json    --write

# 报告与检查
python $UR/ultimate_orchestrator.py check  --state S
python $UR/ultimate_orchestrator.py report --state S --out REPORT.md

# 单独使用量化器官
python $UR/clash_analyzer.py spark    --state S --round 2
python $UR/clash_analyzer.py survival --state S
```

**退出码**：0 通过｜2 参数错误｜3 阶段校验失败｜**4 红蓝对抗无火花，必须重开一轮**。

---

## 输入格式

阶段一 `roles.json`（三个要素缺一不可）：

```json
{
  "confessions": [
    {"role": "musk",
     "text": "评审的固定开销才是主项。[数据诉求: 需要过去两年每次评审的平均参与人时] "
             "[Tool Call: Search] 关键词：评审 平均人时 统计。"
             "基于此数据，我的观点是：频次不是主变量。",
     "tool_result": {"source": "tool", "tool": "web_search", "query": "…",
                     "result": "…", "obtained_at": "2026-11-01"}}
  ]
}
```

阶段二 `clash.json`（含验真）：

```json
{
  "camps": {"blue": ["munger", "jobs", "pg"], "red": ["musk", "feynman", "karpathy"]},
  "exchanges": [
    {"from": "pg", "target_claim": "M1-1",
     "inner_thought": "我只有一个案例，但我必须用它顶住",
     "text": "[打断并验真] 你说按获奖概率分配有效，我要现场查证。"
             "[Tool Call: Search] 关键词：按获奖概率分配 失效案例。"
             "基于此数据，我的观点是：该做法已失效。",
     "verify": true,
     "verify_result": {"result": "模拟检索：2 个案例显示失效",
                       "simulated": true, "verdict": "supported"}}
  ]
}
```

阶段三 `sandbox.json`（V3 新增 `tool_calls`）：

```json
{
  "sandbox": {
    "plan": "方案 A", "runners": ["karpathy", "musk"],
    "timeline": [{"month": 1, "event": "…", "metric": "…"}],
    "risks": [{"name": "…", "severity": 0.8, "probability": 0.6}],
    "key_assumptions": [{"text": "…", "evidence": ""}],
    "attacks": [{"text": "…", "defended": true}],
    "action_plan": {"do": ["…"], "dont": ["…"], "need_info": ["…"]},
    "tool_calls": [
      {"kind": "Code", "source": "tool", "purpose": "验证包装成本占比是否会让结论反转",
       "code": "rate = 0.12\nprint('反转' if rate > 0.15 else '不变')",
       "result": "不变"}
    ]
  }
}
```

---

## 输出格式（V3.0 冻结，不可改动）

```markdown
### 📊 终极圆桌决策报告 V3.0

#### 🔗 1. 本次会议引入的外部数据 / 工具结果
- 数据 1：…（来源：真实工具 / 模拟）
  - 调用：[Search] 关键词：…
  - 结果：…
- 沙盘工具 1（真实 · Code）：…
  - 运行结果：…
- **打断并验真 N 次**：…

#### 🧠 2. 击穿的隐性假设（元认知发现）
- 我们一开始默认了 xxx，但外部数据证明这是错的。
- 我们忽略了 xxx 维度的成本。

#### 🎯 3. 行动指令 (Action Items)
- ✅ **Do（立刻执行）**：xxx
- ❌ **Don't（绝对禁区）**：xxx
- 🔍 **Need Info（需要补充调研）**：xxx

#### 🛡️ 4. 沙盘存活率评估
- 当前方案预估存活率：XX%
- 最致命的潜在风险点：xxx

#### 🧠 5. 长期记忆写入
- `[MEMORY_UPDATE]`：xxx
  - 已写入记忆库：`M20261101…`（N 字）
```

报告头部会打印两行：数据来源统计（阶段一真实/模拟、沙盘真实/模拟）与阶段零的**开场白**。
共识与分歧移到末尾「过程留痕」，不再占正文五节之一（V3 相对 V2 的格式变化）。

出现以下任一情况 `report` 直接报错（退出码 3）：
行动栏为空、缺存活率、缺长期记忆、记忆超 200 字、
出现 `已达成共识` / `已验证` / `已挖到根本` / `我觉得挺好的` / `各有优劣` 等禁止措辞。

---

## 反模式

1. ❌ 跳过阶段零直接开会——没有记忆锚点，等于每次从零开始。
2. ❌ 抛出 `[数据诉求]` 却没有 `[Tool Call]`——这是 V3 最不能容忍的行为，直接判阶段一失败。
3. ❌ 拿到工具结果不作表态（只贴数据不说结论）——数据本身不构成观点。
4. ❌ `[打断并验真]` 之后不给验真结果——只打断不查证，比不打断更糟。
5. ❌ 沙盘不用工具、只靠嘴说"大概会掉到 30%"——V3 要求至少一条真实代码/搜索验证。
6. ❌ 内心戏写成心理描写（"他感到压力很大"），必须是利益或顾虑的披露。
7. ❌ 红蓝打成"你说得对，我再补充一点"——火花检测会判 `no_spark` 并强制重开。
8. ❌ 行动清单写"加强沟通""持续优化"——没有主语、没有判据的句子等于没写。
9. ❌ 长期记忆写成会议纪要或超过 200 字——下次读取会被截断，等于白写。
10. ❌ 把模拟数据当真实数据用。要么真调工具，要么明写 `simulated: true`。

---

## 边界声明

- 本技能**不替代** `roundtable-orchestrator`：它做决策压缩，不做前提挖掘。
- 六个角色的思维协议来自 `role-*` 技能；**若这些技能尚未安装**，
  先用 `host-bootstrap` 技能检测并部署（见下），不要假装完整协议已生效。
- 红蓝分组由编排引擎指定，不允许角色自选。
- 存活率是**算术结果**，不是判断结论：它回答"当前证据下方案有多稳"，不回答"该不该做"。
- 记忆检索是**字面匹配**，不是语义检索——脚本不假装懂语义。

---

## 跨 AI 宿主（Claude / Codex / Hermes / 其他）

本技能可以被任意支持「读取本地文件 + 执行命令」的 AI 使用，不依赖马维斯：

| 宿主 | 加载方式 |
|---|---|
| **Claude Code / Claude** | 读取仓库根 `CLAUDE.md`，或 `claude` 的 skills 目录 |
| **Codex (ChatGPT)** | 读取仓库根 `AGENTS.md` |
| **Hermes / 其他** | 读取仓库根 `AGENTS.md`（通用约定）或直接把本 SKILL.md 内容贴进上下文 |

**六个角色技能没有预装时**，先运行：

```bash
python skills/host-bootstrap/scripts/bootstrap.py detect    # 检测宿主与已安装技能
python skills/host-bootstrap/scripts/bootstrap.py install   # 缺什么补什么（本地优先，其次 GitHub）
python skills/host-bootstrap/scripts/bootstrap.py verify    # 校验六个角色技能可用
```

`bootstrap.py` 会告诉你当前宿主是什么、六个 `role-*` 是否就绪、缺的从哪里拉。
详见 `host-bootstrap` 技能。

## 参考文件

- `references/adversarial-tactics.md`：红蓝战术、内心戏写法、打断触发条件、召唤判据、阈值调参。
- `references/report-template.md`：V3 报告模板、存活率手算示例、各阶段 JSON 字段说明。
- `references/tool-protocol.md`：工具调用协议细则（Search/Code 的写法、真实与模拟的边界、
  闭环校验规则、验真结果的三种 verdict）。**在阶段一/二需要调用工具时读它。**

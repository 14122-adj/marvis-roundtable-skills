---
name: ultimate-roundtable
description: "终极专家圆桌机制 V4.0：引入注意力分舱、死锁检测强制收敛与颗粒度执行指标，从深度推演走向绝对落地的战术指挥部。当用户要求开启终极圆桌、深度推演讨论、红蓝对抗圆桌、战术推演圆桌，或需要在一场高冲突讨论后拿到带负责人/KPI/止损点的战术级行动清单时，必须使用本技能。"
license: MIT
version: 4.0.0
trigger:
  - 开启终极圆桌
  - 深度推演讨论
  - 红蓝对抗圆桌
  - 战术推演圆桌
permission:
  - read_workspace
  - write_workspace
  - execute_tools
metadata:
  version: 4.0.0
  layer: "Layer 0+ · 高强度审议（ultimate）"
  extends: roundtable-orchestrator
---

# 终极圆桌 V4.0 · 战术指挥部

V3 解决了"结论有没有接触过真实世界"。V4 解决的是另一个更硬的问题：
**这场讨论能不能在有限轮次内停下来，并且停在一个可以直接执行的地方。**

三个新增机制：

1. **注意力分舱**——每个角色只记得自己镜头内的历史，拒绝上下文超载导致的"脑雾"；
2. **死锁熔断**——连续两轮复读就切断发言权，交给独裁裁决，不许无限发散；
3. **颗粒度下探**——最终产出必须有负责人、KPI、时间线、止损点，禁止"大概、也许、建议"。

## 版本演进

| 版本 | 解决什么 | 关键机制 |
|---|---|---|
| V2 | 从"轮流发言"到"红蓝对抗" | 内心戏、打断、3v3、沙盘、存活率 |
| V3 | 从"内部推演"到"现实验证" | 记忆唤醒、工具闭环、交叉验真、沙盘工具验证 |
| **V4** | **从"深度推演"到"绝对落地"** | **注意力分舱、死锁熔断、三选一裁决、战术级清单** |

---

## 五个阶段（每次响应必须严格按此结构推进）

### 阶段零 · 记忆唤醒与焦点锚定

```bash
python scripts/ultimate_orchestrator.py stage0 --state S --file mem.json --write
# mem.json: {"store": "...", "north_star": "月活"}
```

- 加载历史 `[MEMORY_UPDATE]`，输出固定开场白 `[会议启动] 已加载历史记忆：…`；
- **必须指定唯一的北极星指标**（月活 / 利润率 / 存活率…）。缺 `north_star` 直接拒绝（退出码 3）。
- 焦点规则：`本轮起所有发言必须围绕「月活」，偏离即视为无效发言`。

### 阶段一 · 极速交底与工具查证

**分舱机制**：每个角色最多 **150 字**（去标点计数），超一个字都拒绝。
同时为六个角色各生成一份**注意力分舱声明**——每个角色只看得到与自己镜头相关的历史。

| 角色 | 镜头 | 关注什么 |
|---|---|---|
| musk | 物理与成本 | 约束、量级、下界、成本结构 |
| feynman | 可检验性 | 定义、可观测判据、反例 |
| munger | 风险与激励 | 失败路径、激励错位、二阶效应 |
| jobs | 复杂度 | 减法、冗余、环节、使用者 |
| karpathy | 可复现 | 指标、证据链、基线、实验设计 |
| pg | 案例 | 真实案例、n=1、模式、反例 |

保留 V3 的 `[数据诉求]` + `[Tool Call]` + 表态句三要素；
无工具支撑的发言直接标记为 **低置信度发言**（`low_confidence`）。

### 阶段二 · 红蓝绞肉机与死锁检测

保留 `(Inner Thought)`、`[打断]`、`[打断并验真]`、3v3 分营。

**死锁熔断**（V4 新增）：连续两轮同时满足以下四项即判定死锁：

| 判据 | 说明 |
|---|---|
| 复读 | 与上一轮最大相似度 ≥ 0.55 |
| 无新事实 | 本轮无新增关键论据、无新工具结果 |
| 立场未动 | 本轮无有效立场修正 |
| 靶点未变 | 攻击的 claim 集合与上一轮相同 |

触发后输出固定话术并**切断发言权**：

```
[系统强制熔断] 双方无法说服彼此，此议题直接交由最终裁决阶段处理。
```

熔断后任何再提交的 stage2 都会被拒绝（退出码 3），只能进入阶段三。

### 阶段三 · 铁血裁决与三选一

**禁止和稀泥**：必须给出三个互斥方案，描述不能是同一句话的换皮。

| 方案 | 定位 |
|---|---|
| A | 激进派：高收益高风险 |
| B | 保守派：低收益低风险 |
| C | 奇招：跳出当前框架的物理/降维解法 |

六人**全部**投出最后一票并陈述理由（不再互相辩论）。主持人拍板 A/B/C 之一；
若拍板与票数最高方案不一致，必须记录 `decision_reason`（否则告警）。

### 阶段四 · 战术级行动清单 + 记忆沉淀

四要素缺一即拒绝，且 KPI 与 Kill **必须含具体数字**：

```json
{
  "owner": "karpathy",
  "start": "本周在 2 个团队上线触发式评审，阈值设为月活跌破 8%",
  "kpi": "30 天内触发 5 次以内，月活不低于 9%",
  "kill": "如果 30 天内触发超过 12 次，立刻停止并回滚到年度评审",
  "need_info": ["过去两年每次评审的平均人时"]
}
```

含"大概 / 也许 / 酌情 / 视情况 / 建议进一步"等模糊措辞 → 直接拒绝。

---

## 量化模型

### 火花判据（沿用 V2/V3）

`attack_count ≥ 3`、`defense_count ≥ 2`、`target_spread ≥ 2`、`signal_total ≥ 3`、
`hollow_ratio ≤ 0.34`、`unmet_must_respond` 为空。任一不达标 → 退出码 4。

### 死锁判据（V4 新增）

见阶段二表格。`deadlock_detector.py check` 输出 `consecutive_stalled`，
≥2 即 `deadlock: true`。

### 存活率（可选，降级为过程留痕）

```
survival = 0.40×risk_residual + 0.25×evidence_coverage
         + 0.20×defense_quality + 0.15×plan_integrity
```

V4 关注落地，存活率只在跑过 `sandbox` 子命令时才出现在过程留痕里。

---

## 命令行

```bash
UR=scripts

# 阶段零（必须带 north_star）
python $UR/ultimate_orchestrator.py init   --topic "议题" --out DIR
python $UR/ultimate_orchestrator.py stage0 --state S --file mem.json     --write

# 阶段一~四
python $UR/ultimate_orchestrator.py stage1 --state S --file roles.json   --write
python $UR/ultimate_orchestrator.py stage2 --state S --file clash.json   --write
python $UR/ultimate_orchestrator.py stage3 --state S --file vote.json    --write   # 三选一
python $UR/ultimate_orchestrator.py stage4 --state S --file action.json  --write   # 战术清单

# 可选：沙盘推演（不覆盖三选一裁决）
python $UR/ultimate_orchestrator.py sandbox --state S --file sandbox.json --write

# 报告与检查
python $UR/ultimate_orchestrator.py check  --state S
python $UR/ultimate_orchestrator.py report --state S --out REPORT.md

# 独立工具
python $UR/attention_split.py  plan --state S --role pg --write    # 分舱
python $UR/attention_split.py  check --state S                     # 分舱与 150 字闸门校验
python $UR/attention_split.py  lenses                              # 打印六个镜头
python $UR/deadlock_detector.py check --state S [--write]          # 死锁检测
python $UR/deadlock_detector.py fuse  --state S                    # 手动熔断
python $UR/clash_analyzer.py spark    --state S --round 2
python $UR/memory_store.py recall --query 评审
```

**退出码**：0 通过｜2 参数错误｜3 阶段校验失败｜**4 红蓝对抗无火花，必须重开**。

---

## 输入格式

阶段零 `mem.json`：

```json
{"store": ".ultimate/memories.jsonl", "north_star": "月活"}
```

阶段一 `roles.json`（150 字内 + 提及北极星 + 三要素闭环）：

```json
{"confessions": [
  {"role": "musk",
   "text": "月活增长的主约束是获客成本。[数据诉求: 需要过去 6 个月 CAC] "
           "[Tool Call: Search] 关键词：SaaS CAC 基准。基于此数据，我的观点是：CAC 已接近上限。",
   "tool_result": {"source": "tool", "tool": "web_search", "query": "…", "result": "…"}}
]}
```

阶段三 `vote.json`：

```json
{
  "options": {
    "A": {"summary": "全量改为季度评审，三个月内切换完毕"},
    "B": {"summary": "维持年度评审，只把材料准备流程精简一半"},
    "C": {"summary": "取消固定评审，改为触发式评审：指标跌破阈值才开"}
  },
  "votes": {"musk": "A", "feynman": "C", "munger": "B",
            "jobs": "C", "karpathy": "C", "pg": "B"},
  "vote_reasons": {"musk": "月活窗口只有三个月", "feynman": "触发式有可观测判据", "...": "..."},
  "decision": "C",
  "decision_reason": "C 拿 3 票且判据可观测；A 的下行风险未被防住"
}
```

---

## 输出格式（V4.0 冻结，不可改动）

```markdown
### ⚔️ 终极圆桌决策报告 V4.0

#### 📌 1. 北极星指标与底线假设
- 本次推演的核心指标：xxx
- 我们击穿的隐性假设：xxx

#### 🔗 2. 证据链与外部验证
- 采纳的外部数据/工具结果：xxx

#### 🚦 3. 铁血裁决（三选一）
- **激进方案 A**：[简述]（投票支持：xxx）
- **保守方案 B**：[简述]（投票支持：xxx）
- **降维方案 C**：[简述]（投票支持：xxx）
- 🏆 **最终拍板结论**：采用方案 [X]

#### 🎯 4. 战术级行动清单 (Action Items)
- **负责人**：[指定角色]
- **第一步（Start）**：xxx
- **关键指标（KPI）**：xxx
- **止损红线（Kill）**：xxx
- **补充调研（Need Info）**：xxx

#### 🧠 5. 长期记忆写入
- `[MEMORY_UPDATE]`：xxx
```

出现以下任一情况 `report` 直接报错（退出码 3）：
缺北极星、缺拍板结论、战术清单缺 owner/start/kpi/kill、KPI 或 Kill 无数字、
出现禁止措辞（`已达成共识`/`已验证`/`我觉得挺好的`/`各有优劣`）或
**咨询体**（`一方面`/`另一方面`/`视具体情况而定`/`综合考虑`/`大概`/`也许`）。

---

## 反模式

1. ❌ 没有北极星指标就开会——V4 要求全场唯一焦点，缺了直接拒绝。
2. ❌ 角色发言超 150 字——分舱机制就是要过滤铺陈，只留底线逻辑。
3. ❌ 发言不提及北极星——视为无效发言，直接拒绝。
4. ❌ 红蓝连续两轮复读还继续辩——死锁检测会熔断并切断发言权。
5. ❌ 熔断后又偷偷提交 stage2——直接拒绝，只能进入三选一。
6. ❌ 三个方案是同一句话换皮——互斥性检查会拒绝。
7. ❌ 行动清单写"加强沟通""持续优化"——没有负责人、没有数字等于没写。
8. ❌ Kill 写"如果效果不好就停止"——必须给出可判定的阈值。
9. ❌ 报告里出现"一方面…另一方面…"——咨询体一律报错。
10. ❌ 拍板与多数票不一致却不写理由——会告警，且必须可追溯。

---

## 边界声明

- 本技能**不替代** `roundtable-orchestrator`：它做决策压缩，不做前提挖掘。
- 六个角色的思维协议来自 `role-*` 技能；**若未安装**，先用 `host-bootstrap` 检测并部署，
  否则必须在输出中声明「⚠ 降级模式」。
- **死锁检测只抓"明显复读"**：字符二元组相似度不懂语义，换了说法但意思相同的复读抓不到，
  这部分要靠元认知层的模型判断。
- **分舱只影响"看见什么"**，不改写任何原文；`muted` 里的内容不得被引用，
  被追问时应承认"这不在我的镜头里"。
- 存活率在 V4 中降级为参考指标，因为"能落地的方案"比"存活率 80% 的方案"更重要。

## 参考文件

- `references/adversarial-tactics.md`：红蓝战术、内心戏写法、打断触发条件、召唤判据、阈值调参。
- `references/report-template.md`：报告模板、存活率手算示例、各阶段 JSON 字段说明。
- `references/tool-protocol.md`：工具调用协议（Search/Code 写法、真实与模拟边界、闭环校验、验真 verdict）。
- `references/tactical-playbook.md`：**V4 新增**——北极星选取、分舱镜头调参、死锁判定细则、
  三选一方案的互斥性设计、战术清单的颗粒度标准（负责人/KPI/Kill 的合格写法与反例）。
  **在组织阶段三/四时读它。**

# 10 分钟跑通

这份文档只回答一个问题：**怎么最快看到一场完整的终极圆桌。**

---

## 最快路径（1 条命令）

```bash
git clone https://github.com/14122-adj/marvis-roundtable-skills.git
cd marvis-roundtable-skills
python tools/quickstart.py
```

大约 10 秒后你会看到：

```
① 体检          Python / 仓库 / 六个角色技能 / 脚本
② 跑一场终极圆桌  阶段零 → 一 → 二 → 三 → 四 → 生成报告
③ 仓库自检       确认这份副本是好的
④ 接下来做什么
```

产物在 `.quickstart/`：

| 文件 | 是什么 |
|---|---|
| `report.md` | 一场完整的决策报告（V4.1 五节） |
| `state.json` | 完整讨论状态，可追溯每一步 |
| `memories.jsonl` | 记忆库，下次开会会读到它 |

**只想体检不跑演示**：

```bash
python tools/quickstart.py --check
```

---

## 换成你自己的议题

`quickstart.py` 用的是内置示例数据。换成你自己的，用交互式向导：

```bash
python tools/wizard.py
```

它会问几组问题，然后生成 5 个阶段的配置文件。**每步即时校验**——
比如你的发言漏了 `[数据诉求]`，它会当场让你重填，而不是等你跑到阶段一才报错。

生成完会直接打印可复制的命令序列：

```bash
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py init --topic "你的议题" --out .myrun
# 把输出的 state_path 填进下面的命令
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py stage0 --state <state> --file .wizard/stage0.json --write
... （共 5 步）
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py report --state <state> --out 我的决策报告.md
```

**不想交互**：`python tools/wizard.py --demo` 直接生成一份示例。

---

## 在 AI 客户端里用

这套技能不是只能命令行跑。它同时是 **Agent Skills 格式**，可以装进各种宿主。

### 第一步：确认你在哪个宿主

```bash
python skills/host-bootstrap/scripts/bootstrap.py detect
```

输出会告诉你：当前宿主、技能目录在哪、六个角色技能是否就绪。

### 第二步：补齐缺失的角色技能

```bash
python skills/host-bootstrap/scripts/bootstrap.py install --target <你的技能目录>
python skills/host-bootstrap/scripts/bootstrap.py verify  --target <你的技能目录>
```

`install` 有四级回退：**本地复制 → git clone → HTTP 下载 → 打印手工步骤**。
无网络无 git 时它会如实告诉你需要手工做什么，不会假装成功。

### 第三步：按宿主导入

| 宿主 | 怎么做 |
|---|---|
| **马维斯 Marvis** | 技能管理 → 本地技能 → 导入技能 → 选 `SKILL.md`。导入顺序：`host-bootstrap` → `roundtable-orchestrator` → `meta-supervisor` → `position-evolution` → `decision-landscape` → 6 个 `role-*` → `cognitive-noise` → `multi-model-adapter` → `ultimate-roundtable` |
| **Claude Code** | 读仓库根 `CLAUDE.md`；或把 `skills/` 放进 `~/.claude/skills` |
| **Codex / Hermes / Cursor** | 读仓库根 `AGENTS.md`；或放进各自的 skills 目录 |
| **纯文本对话** | 把 `SKILL.md` 内容贴进上下文，所有工具结果标 `simulated: true` |

### 第四步：说一句话触发

```
开启终极圆桌：要不要把年度评审改成季度评审
```

---

## 三个常见卡点

### 卡点 1：`no_spark`（退出码 4）

**现象**：阶段二报 `no_spark`，强制重开。

**原因**：红蓝对抗没有打出火花。判据是六个计数（有效攻击 ≥3、有效防御 ≥2、
靶点 ≥2、信号总量 ≥3、空洞发言 ≤34%、强制条目已回应）。

**修复**：至少让蓝军打 3 个不同的靶点，红军给 2 条有效防御。
不要写「我觉得挺好的」「各有优劣」——这些会被计为空洞发言。

### 卡点 2：阶段一被拒（退出码 3）

**现象**：`阶段一校验失败`，列出若干条。

**常见原因**：

| 报错 | 修复 |
|---|---|
| 缺少 `[数据诉求]` | 每条发言必须有 |
| 缺少 `[Tool Call]` | V3 要求闭环，写了诉求就要有调用 |
| 没有表态句 | 必须出现「基于此数据，我的观点是…」 |
| 发言未提及北极星 | V4 要求全场围绕唯一焦点指标 |
| 超过 150 字 | 分舱机制过滤铺陈，只留底线逻辑 |
| `tool_result` 既非 `source:tool` 也非 `simulated:true` | 不允许把模拟数据伪装成真实数据 |

### 卡点 3：战术清单被拒（退出码 3）

**现象**：`action_plan.kill 没有具体数字`。

**原因**：V4 拒绝咨询体。KPI 与 Kill **必须含数字**。

```diff
- kill: 如果效果不好就停止
+ kill: 如果 30 天内触发超过 12 次，立刻停止并回滚
```

---

## 跑通之后看什么

| 你想了解 | 读这个 |
|---|---|
| 所有字段的唯一来源 | `docs/output-contract.md` |
| 终极圆桌的完整机制 | `skills/ultimate-roundtable/SKILL.md` |
| 怎么组织红蓝对抗 | `skills/ultimate-roundtable/references/adversarial-tactics.md` |
| 北极星怎么选、KPI 怎么写 | `skills/ultimate-roundtable/references/tactical-playbook.md` |
| 一次完整讨论的实录 | `docs/example-session.md` |
| 怎么贡献一个新角色 | `CONTRIBUTING.md` |

---

## 一句话总结

```bash
python tools/quickstart.py     # 看它长什么样（10 秒）
python tools/wizard.py         # 换成你的议题（5 分钟）
```

剩下的都是细节。

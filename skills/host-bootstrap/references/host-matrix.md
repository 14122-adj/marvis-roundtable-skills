# 宿主能力矩阵与接入手册

`host-bootstrap` 的参考手册。回答：这套技能在哪些 AI 上能跑、怎么装、能力差异在哪、坏了怎么查。

## 目录

1. 宿主能力矩阵
2. 各宿主接入步骤
3. 目录约定对照
4. 能力降级路径
5. 故障排查
6. 新增一个宿主时要改什么

---

## 1. 宿主能力矩阵

三个能力维度决定这套技能能跑到什么程度：

| 宿主 | 文件系统 | 执行命令 | 网络 | 能跑到的上限 |
|---|---|---|---|---|
| **马维斯 Marvis** | ✅ | ✅ | ✅ | 全功能（原生技能导入） |
| **Claude Code** | ✅ | ✅ | ✅ | 全功能 |
| **Codex (ChatGPT)** | ✅（沙箱内） | ✅ | 视配置 | 全功能（沙盘工具可能受限） |
| **Hermes** | ✅ | ✅ | 视配置 | 全功能 |
| **Cursor / Cline / Windsurf** | ✅ | ✅ | ✅ | 全功能（读 AGENTS.md） |
| **纯网页对话（无文件系统）** | ❌ | ❌ | ❌ | 仅对话层：所有工具调用必须标 `simulated: true` |
| **移动端 / 语音助手** | ❌ | ❌ | ❌ | 同纯网页，且建议只跑 `role-*` 单角色 |

**判据**：能读 `SKILL.md` 就能用；能执行 `python` 就能用完整闭环；
两样都不能，就退到"贴文本 + 全模拟"模式，但**必须如实标注**。

---

## 2. 各宿主接入步骤

### Claude Code / Claude

```bash
# 方式 A：仓库内直接使用（推荐）
cd marvis-roundtable-skills
claude          # 会自动读取仓库根 CLAUDE.md

# 方式 B：装到全局技能目录
python skills/host-bootstrap/scripts/bootstrap.py install --target ~/.claude/skills
python skills/host-bootstrap/scripts/bootstrap.py verify  --target ~/.claude/skills
```

### Codex (ChatGPT)

```bash
python skills/host-bootstrap/scripts/bootstrap.py install --target ~/.codex/skills
# Codex 会读取仓库根 AGENTS.md
```

Codex 的沙箱可能限制网络，此时阶段一的 `[Tool Call: Search]` 会退化为模拟，
报告头部会显示「真实 0 条」——这是正常且诚实的结果。

### Hermes

```bash
python skills/host-bootstrap/scripts/bootstrap.py install --target ~/.hermes/skills
```

Hermes 读 `AGENTS.md`，不需要额外配置。

### 马维斯 Marvis

```bash
# 马维斯有原生技能管理，推荐用它自己的导入功能：
#   技能管理 → 本地技能 → 导入技能 → 选择 SKILL.md
# 也可以用脚本预检目录：
python skills/host-bootstrap/scripts/bootstrap.py detect
```

马维斯的技能目录在不同版本下位置不同，脚本**不会猜测**；
如果 `detect` 显示"未检测到"，用马维斯自己的导入界面即可。

### Cursor / Cline / Windsurf

把仓库根 `AGENTS.md` 保留在项目里即可（多数这类工具会自动读取）。
或复制到对应规则目录。

---

## 3. 目录约定对照

| 宿主 | 默认技能目录（脚本会探测） |
|---|---|
| Claude | `~/.claude/skills`、`~/.config/claude/skills` |
| Codex | `~/.codex/skills`、`~/.config/codex/skills` |
| Hermes | `~/.hermes/skills`、`~/.config/hermes/skills` |
| Marvis | `~/.marvis/skills`、`~/.config/marvis/skills`、`AppData/Roaming/marvis/skills` |
| DSH | `~/.dsh/skills` |
| 通用 | `~/.agent/skills`、`./skills` |

**脚本只读不写这些目录**，除非你显式给 `install --target`。

---

## 4. 能力降级路径

按能力缺失逐级降级，每级都要在报告里声明：

| 缺失能力 | 降级方式 | 报告里怎么写 |
|---|---|---|
| 无网络搜索 | `[Tool Call: Search]` 照写，结果标 `simulated: true` | 「真实 0 条 / 模拟 N 条」 |
| 无代码执行 | `[Tool Call: Code]` 照写，结果标 `simulated: true` | 同上，并进 `Need Info` |
| 无文件系统 | 不写状态文件，全部在对话里推进 | 「本次未落盘，结论不可跨会话复用」 |
| 角色技能未装 | 编排引擎按摘要执行协议 | 「⚠ 降级模式：role-* 未安装」 |
| 全部缺失 | 只跑单角色或纯讨论 | 不产出决策报告，只产出讨论纪要 |

**降级不等于失败**，但不声明降级等于欺骗。

---

## 5. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `detect` 显示未知宿主 | 环境无标识文件 | 正常，用 `--target ./skills` 手动指定 |
| `install` 返回 1 且打印手工步骤 | 无 git 且无网络 | 按步骤 curl 或 ZIP 导入 |
| `verify` 显示 `name_ok: false` | 复制串台（目录名与 name 不符） | 删掉该目录重装 |
| `verify` 显示 `missing_files` | 只复制了 SKILL.md | 重跑 `install`（会补齐 references） |
| 技能装了但不触发 | 宿主未重新加载 | 重启宿主或重新打开项目 |
| 六个都在但仍报缺失 | 目标目录不是宿主实际读取的目录 | `detect` 看"已安装目录"与"建议目标"是否一致 |
| Windows 下路径报错 | 使用了 `~` 但 shell 未展开 | 用绝对路径，或 PowerShell 里用 `$env:USERPROFILE` |

---

## 6. 新增一个宿主时要改什么

只有两处：

1. `bootstrap.py` 的 `HOST_HINTS`（技能目录候选）与 `MARKER_FILES`（标记文件）；
2. 本手册的能力矩阵与接入步骤。

**不需要改**任何技能正文——所有 SKILL.md 都不含宿主特定路径，
这正是"技能之间不用跨目录相对引用"的收益。

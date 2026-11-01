---
name: host-bootstrap
description: "跨 AI 宿主的技能自检与自动部署：检测当前运行在 Claude Code / Codex / Hermes / 马维斯 / 其他环境，校验六个角色技能（role-musk/feynman/munger/jobs/karpathy/pg）是否就绪，缺失时从本地仓库或 GitHub 自动补齐。当用户要求把圆桌技能接入别的 AI、换一个客户端使用、或某个角色技能报缺失/不生效时，必须使用本技能。"
license: MIT
version: 3.0.0
trigger:
  - 接入 Claude
  - 接入 Codex
  - 接入其他 AI
  - 技能缺失
  - 部署圆桌技能
permission:
  - read_workspace
  - write_workspace
metadata:
  version: 3.0.0
  layer: "Layer -1 · 宿主适配（前置）"
---

# 宿主自检与自动部署

这套技能原本为马维斯编写。换到 Claude Code、Codex（ChatGPT）、Hermes 或任何其他
支持「读本地文件 + 执行命令」的 AI 上时，最大的风险不是机制失效，而是
**六个角色技能根本不存在，而编排引擎却假装它们在**。

本技能解决这件事：先检测，再补齐，最后校验。

## 三个命令

```bash
B=skills/host-bootstrap/scripts/bootstrap.py

python $B detect    # 我是什么宿主？技能装在哪？六个角色技能就绪吗？
python $B install   # 缺什么补什么（本地优先 → GitHub 兜底 → 打印手工步骤）
python $B verify    # 校验六个角色技能是否真的可用
```

退出码：`0` 就绪｜`1` 需要安装｜`2` 参数错误。

---

## 一、detect：先搞清楚自己在哪

检测依据（按可靠性排序）：

1. **环境变量**：`CLAUDE_CODE_ENTRYPOINT` / `CODEX_HOME` / `HERMES_HOME` /
   `MARVIS_HOME` / `DSH_ROOT`；
2. **标记文件**：`CLAUDE.md`、`AGENTS.md`、`.claude/`、`.codex/`、`.hermes/`、`.marvis/`、`.dsh/`；
3. **技能目录**：在用户目录与当前目录下探测各宿主的约定路径。

输出示例：

```
宿主：Claude Code / Claude（claude）
  - 依据：找到 CLAUDE.md
仓库：/path/to/marvis-roundtable-skills
仓库内角色技能：6/6 就绪
已安装目录：
  - ~/.claude/skills：0/6
建议目标目录：~/.claude/skills
结论：可直接使用 ultimate-roundtable
```

**找不到宿主时不会猜**：输出 `未知宿主 / 通用环境`，并建议装到 `./skills`。
猜错的路径比不猜更糟——它会让用户以为装好了。

---

## 二、install：缺什么补什么

三级回退，每级都真实执行：

| 级别 | 条件 | 动作 |
|---|---|---|
| 1 | 能定位到本仓库 | 从 `skills/role-*` **复制**（含 references，不只 SKILL.md） |
| 2 | 有网络与 git | `git clone`（先 SSH 后 HTTPS），再复制 |
| 3 | 都没有 | **打印手工步骤**（curl 逐文件 / ZIP 导入 / 仓库地址），并返回退出码 1 |

```bash
python $B install --target ~/.claude/skills          # 装到 Claude
python $B install --target ~/.codex/skills --source local
python $B install --dry-run                          # 只预演，不写文件
```

**幂等**：已就绪的技能不会被重复覆盖；六个都在时 `actions` 为空数组。

**它不做什么**（诚实边界）：

- 不修改宿主的配置文件（`claude_desktop_config.json` 之类）；
- 不重启宿主；
- 不猜测马维斯的技能目录——找不到就报"未检测到"。

装完之后**必须重启或重新加载宿主**，这一步只能由用户做。

---

## 三、verify：校验到字段级

`verify` 不是只看目录存在，它逐项检查：

| 检查项 | 判据 |
|---|---|
| `installed` | `SKILL.md` 存在 |
| `frontmatter_ok` | frontmatter 里含 `description:` |
| `name_ok` | `name:` 与目录名一致（防止复制串台） |
| `missing_files` | references 下的手册是否齐全 |

只有四项全过才算 `ready`。任一不过就进 `missing`，`install` 会重新补它。

---

## 四、各宿主的接入方式

| 宿主 | 怎么让它读到这套技能 |
|---|---|
| **Claude Code / Claude** | 仓库根有 `CLAUDE.md`（已提供）；或把 `skills/` 放进 `~/.claude/skills` |
| **Codex (ChatGPT)** | 仓库根有 `AGENTS.md`（已提供，通用约定） |
| **Hermes** | 读 `AGENTS.md`；或把 `skills/` 放进 `~/.hermes/skills` |
| **Cursor / Cline / Windsurf** | 读 `AGENTS.md` 或 `.cursor/rules` |
| **马维斯 Marvis** | 技能管理 → 本地技能 → 导入 SKILL.md（原生支持） |
| **纯文本对话（无文件系统）** | 把 `SKILL.md` 内容直接贴进上下文；工具调用全部标 `simulated: true` |

> 没有文件系统的宿主仍然可以跑终极圆桌，只是所有工具调用必须标为模拟——
> `ultimate-roundtable` 的报告头部会如实印出「真实 0 条 / 模拟 N 条」。

---

## 五、六个角色技能清单

| 技能 | 仓库地址 |
|---|---|
| `role-musk` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-musk |
| `role-feynman` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-feynman |
| `role-munger` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-munger |
| `role-jobs` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-jobs |
| `role-karpathy` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-karpathy |
| `role-pg` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-pg |

每个技能都包含 `SKILL.md` + 一份 `references/` 手册，两者都要复制。

---

## 六、降级策略（没装角色技能时怎么办）

如果用户拒绝安装、或环境确实无法写入：

1. 在讨论开始时**明确声明**："六个角色技能未安装，本场为降级模式"；
2. 降级模式下，角色的思维协议由编排引擎按摘要执行（`ultimate-roundtable` 的
   SKILL.md 里有每个角色的一句话判据）；
3. 报告末尾必须写：`⚠ 降级模式：role-* 技能未安装，角色协议为摘要级`。

**不允许**：假装完整协议已生效。这会让用户高估结论质量。

---

## 反模式

1. ❌ 检测不到宿主就猜一个路径装进去——装错地方等于没装。
2. ❌ `install` 只复制 `SKILL.md`，漏掉 `references/`——角色手册是协议的一部分。
3. ❌ 装完不 `verify` 就宣布成功。
4. ❌ 修改宿主的配置文件（超出本技能权限，且容易弄坏用户环境）。
5. ❌ 在无网络、无 git 时静默失败——必须打印手工步骤并返回非零退出码。
6. ❌ 角色技能缺失却继续跑终极圆桌而不声明降级模式。

---

## 参考文件

- `references/host-matrix.md`：各宿主的目录约定、能力差异（有无工具/文件系统/网络）、
  接入步骤与常见故障排查。**在给新宿主做适配时读它。**

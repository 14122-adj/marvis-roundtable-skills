# AGENTS.md

> 本文件面向所有支持「读取仓库内约定文件」的 AI 编码/对话工具
> （Codex、Hermes、Cursor、Cline、Windsurf、以及任何遵循 AGENTS.md 约定的宿主）。
>
> Claude Code 请优先读 `CLAUDE.md`（内容等价）。

## 这是什么仓库

`marvis-roundtable-skills` —— 一套**多角色圆桌讨论与决策推演**技能包。
它把"六个人各说一遍"升级为一条有硬判据的流水线：挖前提 → 红蓝对抗 → 沙盘 → 决策景观。

- 13 个独立技能，12+ 个零依赖 Python 脚本（全部带 `--selftest`）
- 中文正文，字段名英文
- 只依赖 Python 3.9+ 标准库（打包器另需 PyYAML）

## 你可以直接用的入口

| 你想做什么 | 读这个 | 跑这个 |
|---|---|---|
| 把一场讨论做深、挖共享前提 | `skills/roundtable-orchestrator/SKILL.md` | `scripts/state_manager.py` 等 |
| 把讨论压成**可执行决策** | `skills/ultimate-roundtable/SKILL.md` | `scripts/ultimate_orchestrator.py` |
| 检测/安装六个角色技能 | `skills/host-bootstrap/SKILL.md` | `scripts/bootstrap.py` |
| 汇总成决策报告 | `skills/decision-landscape/SKILL.md` | `scripts/synthesis_generator.py` |

**首次使用请先跑自检**：

```bash
python skills/host-bootstrap/scripts/bootstrap.py detect   # 我在什么环境？技能齐吗？
python tools/validate_repo.py                              # 仓库本身是否健康
```

## 六个角色技能（可能尚未安装）

`role-musk` / `role-feynman` / `role-munger` / `role-jobs` / `role-karpathy` / `role-pg`

若 `bootstrap.py detect` 显示缺失：

```bash
python skills/host-bootstrap/scripts/bootstrap.py install
```

无网络无 git 时，脚本会打印 curl 与 ZIP 两种手工步骤，**不会假装装好了**。
在技能确实缺失的情况下跑终极圆桌，必须在输出里声明「⚠ 降级模式」。

## 硬性纪律（违反会让结论失去可信度）

1. **数据诚实**：真实调用标 `source: "tool"`，构造的数据标 `simulated: true`。
   两者都不标 = 伪造数据 = 禁止。
2. **数据诉求必须闭环**：写了 `[数据诉求]` 就必须有对应的 `[Tool Call]` 和表态句。
3. **禁止和稀泥**：红蓝对抗无火花（判据见 `clash_analyzer.py`）必须重开一轮，
   不允许"各有优劣、综合考虑"。
4. **不许伪造完成状态**：不能写"已验证""已达成共识""已挖到根本"，
   除非确实有对应的证据或脚本输出。
5. **记忆 ≤200 字**：长期记忆超长会在下次读取时被截断，等于白写。
6. **不编造模型名/数据源**：不知道就写 `unspecified` 或进 `Need Info`。

## 目录导航

```
skills/                     13 个技能，每个 = SKILL.md + scripts/ + references/
  roundtable-orchestrator/  编排引擎（状态、轮次、收敛）
  meta-supervisor/          元认知监督（隐性假设、分歧分类、谬误）
  position-evolution/       立场演化与反从众
  decision-landscape/       决策景观聚合
  cognitive-noise/          轻量认知噪声（仅 simulation 模式）
  multi-model-adapter/      异构基座调用包
  ultimate-roundtable/      终极圆桌 V3（四阶段 + 记忆 + 工具闭环）
  host-bootstrap/           宿主检测与技能自动部署
  role-*/                   六个角色的思维协议
docs/output-contract.md     冻结契约：所有字段的唯一来源
evals/evals.json            离线评测（不调用模型）
tools/                      自检、评测、打包、端到端演示
```

## 常用命令

```bash
python tools/validate_repo.py                        # 91+ 项仓库自检
python tools/run_evals.py                            # 离线评测
python tools/demo_session.py --quiet                 # 圆桌主线端到端
python tools/demo_ultimate.py --quiet                # 终极圆桌端到端
python tools/package_bundle.py build --per-skill     # 打包 ZIP
```

## 在无工具环境里

如果当前宿主不能执行命令或访问网络：

- 仍然按 SKILL.md 的流程推进，但所有工具结果标 `simulated: true`；
- 在输出中明确写「本次无真实工具调用，结论未经过外部验证」；
- 不要因为"跑不了脚本"就跳过阶段——阶段结构本身仍然有效。

## 许可

MIT。

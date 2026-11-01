# CLAUDE.md

> Claude Code / Claude 的仓库级约定文件。内容与 `AGENTS.md` 等价，
> 针对 Claude 的使用习惯做了调整（更强调"先读契约再动手"）。

## 项目性质

`marvis-roundtable-skills`：多角色圆桌讨论与决策推演技能包。
13 个技能 + 零依赖 Python 脚本，中文正文、英文字段名。

## 开始任何圆桌任务前

```bash
python skills/host-bootstrap/scripts/bootstrap.py detect
```

这一步会告诉你：当前宿主、六个角色技能（`role-musk` 等）是否就绪、
缺失的从哪里补。**不要跳过**——如果角色技能不存在而直接开会，
产出的结论会缺协议支撑。

需要补装时：

```bash
python skills/host-bootstrap/scripts/bootstrap.py install --target ~/.claude/skills
python skills/host-bootstrap/scripts/bootstrap.py verify  --target ~/.claude/skills
```

## 先读契约，再动手

`docs/output-contract.md` 是所有字段的唯一来源（v1.2.0）。
新增或修改任何技能前，先确认字段名、枚举、ID 规则没有偏离它。

改契约 = 改所有技能 = 必须同步跑：

```bash
python tools/validate_repo.py      # 结构 / 契约字段 / 版本一致 / 禁用写法 / 12 个脚本自检
python tools/run_evals.py          # 28 条离线评测
```

## 两条主流程

**A. 圆桌主线**（把讨论做深）

```bash
python skills/roundtable-orchestrator/scripts/state_manager.py init --topic "议题"
python skills/roundtable-orchestrator/scripts/round_controller.py plan --state S --write
# → R1 隔离立论 → 元认知扫描 → R2 交叉 → 收敛检测 → 决策景观
```

**B. 终极圆桌 V3**（把讨论压成决策）

```bash
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py stage0 --state S --write  # 记忆唤醒
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py stage1 --state S --file roles.json --write
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py stage2 --state S --file clash.json --write
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py stage3 --state S --file sandbox.json --write
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py stage4 --state S --file meta.json --write
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py report --state S --out REPORT.md
```

退出码：`0` 通过｜`3` 阶段校验失败｜**`4` 红蓝对抗无火花，必须重开**。

## 我会替你守住的纪律

1. **不伪造数据**：真实调用 `source: "tool"`，构造数据 `simulated: true`，两者都不标会被脚本拒绝。
2. **不跳过阶段**：阶段之间有硬顺序校验，跳步直接退出码 3。
3. **不和稀泥**：行动清单三栏（Do / Don't / Need Info）有空栏就拒绝出报告。
4. **不伪造完成**：不写"已验证""已达成共识"，除非有脚本输出或真实工具结果支撑。
5. **不编造模型名**：未知写 `unspecified`。

## 代码风格

- 脚本仅用标准库，每个脚本必须有 `--selftest` 且退出码 0；
- 语义判断一律标 `needs_judgment: true`，脚本只做结构化工件；
- 输出 JSON 到 stdout，日志走 stderr。

## 常用命令

```bash
python tools/validate_repo.py
python tools/run_evals.py
python tools/demo_session.py --quiet
python tools/demo_ultimate.py --quiet
python tools/package_bundle.py build --per-skill
```

## 许可

MIT。

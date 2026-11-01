# marvis-roundtable-skills

马维斯（Marvis / Agent Skills 兼容）圆桌讨论技能包：把"多角色辩论"从**人设扮演**升级为一套**可执行的审议机制**。

一句话：**讨论机制从角色提示词里抽出来交给编排层；角色只负责自己的思维协议。**

> ### 🚀 第一次来？先看 **[QUICKSTART.md](QUICKSTART.md)** —— 10 分钟跑通
>
> ```bash
> git clone https://github.com/14122-adj/marvis-roundtable-skills.git
> cd marvis-roundtable-skills
> python tools/quickstart.py
> ```
>
> 约 10 秒：体检 → 跑完一场完整的终极圆桌 → 自检 → 告诉你下一步。
> 换成你自己的议题：`python tools/wizard.py`（交互式，替你生成 5 个阶段的配置）。

### 想直接下载？

去 [**Releases**](https://github.com/14122-adj/marvis-roundtable-skills/releases/latest) 下载 `marvis-roundtable-skills-v1.7.0.zip`，
解压后先读里面的 `START-HERE.md`。

---

| 你想做什么 | 去哪 |
|---|---|
| **10 分钟跑通** | **[QUICKSTART.md](QUICKSTART.md)** |
| 看一场完整讨论长什么样 | [`docs/example-session.md`](docs/example-session.md) |
| 了解全部字段 | [`docs/output-contract.md`](docs/output-contract.md) |
| 贡献一个新角色 | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| 在 AI 客户端里用 | `python skills/host-bootstrap/scripts/bootstrap.py detect` |

---

- 版本：**v1.7.0**（P0–P11）；`ultimate-roundtable` **v4.1.0**、`host-bootstrap` **v3.0.0** 按上游 spec 独立发版
- 形态：**14 个核心技能** ＋ **2 个社区角色**（`community-roles/`）＋ **18 个零依赖 Python 脚本**（全部带 `--selftest`）
- 跨宿主：马维斯 / **Claude Code** / **Codex (ChatGPT)** / **Hermes** / Cursor / 纯文本对话
- 验收：`tools/validate_repo.py` 127 项、`tools/run_evals.py` 38 条离线评测、两套端到端 demo
- 语言：中文正文，字段名英文

> **欢迎贡献角色**：六个人覆盖不了所有思考方式。
> 提交新的思维协议请看 [CONTRIBUTING.md](CONTRIBUTING.md)，用 `tools/validate_role.py` 本地校验。
> 已收录：`role-civilian`（平民视角）、`role-contrarian`（职业杠精）。

---

## 1. 它解决什么问题

单角色或多角色"各说各话"的讨论有三个固有短板，本技能包逐条给出工程回应：

| 短板 | 现象 | 本包的机制 |
|---|---|---|
| 挖不到根本 | 所有人默认"竞赛必须拿奖才算成功"，六个人在这个前提里争资源怎么分，辩再久也碰不到前提 | **元认知监督者**每轮独立扫描隐性假设，其输出是下一轮的**强制输入** |
| 立场写死 | 角色被说服也不改，或"为了共识"集体投降 | **立场演化层**：允许修正，但无新证据的修正**不改变立场基线**，只记 `compliance_drift` |
| 形式僵化 | "第二轮必须一对一""第三轮必须联动≥2 人"——仿真的是形式，不是思考动机 | **目标驱动**：只规定本轮认知目标；唯一保留的硬约束是第一轮隔离发言（防锚定） |

此外还有三个**可选**层，用来处理"结论怎么交付"与"视角同源"的问题：

- **决策景观**：把讨论聚合成分区报告，而不是按轮次拼接发言；少数派观点只要没被有效反驳就必须完整保留；
- **轻量认知噪声**：用严谨性换真人质感（默认关闭，`rigorous` 模式下脚本直接拒绝启用）；
- **异构基座适配**：同一底座模型的偏见是共通的，该层把角色编译成独立调用包，交给支持多 provider 的宿主分别执行。

---

## 2. 架构

```
Layer -1 host-bootstrap            宿主检测 + 六个角色技能自动部署（跨 AI 接入前置）
Layer 0  roundtable-orchestrator   调度、状态、轮次、聚合（不参与讨论）
Layer 1  role-musk / feynman / munger / jobs / karpathy / pg   角色思维协议 ×6
Layer 2  meta-supervisor           隐性假设、分歧分类、信息缺口、谬误、质量评分
Layer 3  position-evolution        修正判定、反从众、基线更新
Layer 4  decision-landscape        决策景观报告（共识/分歧/假设/建议/缺口/少数派）
Layer 5  cognitive-noise           轻量认知噪声（可选，仅 simulation 模式）
Layer 6  multi-model-adapter       异构基座调用包与结果合并（可选）

Layer 0+ ultimate-roundtable V4    战术指挥部：北极星锚定 → 分舱交底(150字+工具闭环)
                                   → 红蓝对抗(验真+死锁熔断) → 三选一铁血裁决
                                   → 战术级行动清单(负责人/KPI/Kill) → V4 五节报告
```

数据流：

```
R0 列共享前提 → R1 六角色隔离立论 → R1.5 元认知扫描并注入
   → R2 自由交叉（必须回应注入项，可修正立场）→ R2.5 收敛检测
   → R3 综合 / 或提前收敛 → 交接块 → Layer 4 决策景观报告
                    ↑                          ↑
          Layer 5 噪声（仅 simulation）    Layer 6 多基座分发（可选）

需要把讨论压成决策时，另起一条流水线：
   终极圆桌 V4
     stage0 记忆唤醒 + 北极星锚定（全场唯一焦点）
     stage1 极速交底：≤150 字 + 分舱 + [数据诉求]/[Tool Call]/表态 三要素
     stage2 红蓝对抗：内心戏 + 打断 + [打断并验真] + 死锁熔断
     stage3 铁血裁决：A/B/C 三选一 + 六人最后一票 + 主持人拍板
     stage4 战术级清单：负责人 / Start / KPI / Kill / Need Info
     report V4 五节报告（北极星 / 证据链 / 裁决 / 战术清单 / 记忆）
```

### 两套流程怎么选

| | `roundtable-orchestrator` | `ultimate-roundtable` V4 |
|---|---|---|
| 目标 | 把讨论做深、挖到共享前提 | 把讨论压成**能立刻执行**的决策 |
| 输出 | 决策景观（分区呈现） | 存活率 + Do / Don't / Need Info |
| 记忆 | 无 | 跨会话读写 |
| 何时用 | 议题还不清楚、需要先想明白 | 方案已成型、需要压力测试并拍板 |

### 角色思维协议一览

| 角色 | 强制思维协议 | 一句话判据 |
|---|---|---|
| `role-musk` | 第一性原理拆解 | 区分物理约束 / 成本约束 / 社会约定，禁止类比起手 |
| `role-feynman` | 费曼技巧验证 | 说不成外行话，就标"未理解的伪理解"并降置信度 |
| `role-munger` | 逆向 + 多元模型 | 先答"怎么才能彻底失败"，再跨两个学科模型交叉 |
| `role-jobs` | 产品纯粹性追问 | 回答"更简单还是更复杂"，拒绝"因为一直这样做" |
| `role-karpathy` | 系统分解 + 可复现性 | 拆成可独立验证子模块，证据链不可复现标 `unverified` |
| `role-pg` | 从具体案例归纳 | 拒绝抽象原则起手，先给案例并标 `n=1` 警告 |

每个角色输出都带 `epistemic_status`：`confidence` / `uncertainty_points` / `will_revise_if`，
以及 `blind_spot_declared`（自曝视角盲区，供元认知层使用）。

---

## 3. 目录结构

```
marvis-roundtable-skills/
├── README.md  LICENSE  CHANGELOG.md  .gitignore  .gitattributes
├── AGENTS.md                     ← Codex / Hermes / Cursor 等宿主的仓库级入口
├── CLAUDE.md                     ← Claude Code 的仓库级入口
├── CONTRIBUTING.md               ← 如何贡献一个新角色
├── docs/
│   ├── output-contract.md        ← 冻结契约 v1.7.0（含 §8 §9 §10 §11 §12 §13）
│   └── example-session.md        ← 一次完整讨论的实录（示例数据，含脚本误报说明）
├── evals/
│   └── evals.json                ← 36 条离线评测（trigger / command / artifact）
├── community-roles/              ← 社区贡献角色（独立目录、独立版本号）
│   ├── _template/                ← 复制这个目录开始写你的角色
│   ├── role-civilian/            平民视角（前缀 V）
│   └── role-contrarian/          职业杠精（前缀 C）
├── tools/
│   ├── quickstart.py             ← ★ 一条命令跑通（体检 + 跑一场 + 自检 + 下一步）
│   ├── wizard.py                 ← ★ 交互式向导，替你生成 5 个阶段配置
│   ├── validate_repo.py          ← 121 项仓库自检（结构/契约/版本/禁用写法/社区角色/17 个脚本自检）
│   ├── validate_role.py          ← 社区角色协议校验器（13 项检查）
│   ├── run_evals.py              ← 离线评测 runner（不调用模型，--live 会明确说明）
│   ├── package_bundle.py         ← 打包 ZIP（整包 + 逐技能），打包前校验
│   ├── demo_session.py           ← 圆桌主线端到端演示
│   └── demo_ultimate.py          ← 终极圆桌 V4 端到端（北极星/分舱/熔断/三选一/战术清单）
└── skills/
    ├── host-bootstrap/           scripts/bootstrap.py（宿主检测 + 角色技能自动部署）
    ├── roundtable-orchestrator/  scripts/{state_manager,round_controller,convergence_detector}.py
    ├── meta-supervisor/          scripts/{assumption_extractor,divergence_classifier,fallacy_detector}.py
    ├── position-evolution/       scripts/revision_tracker.py
    ├── decision-landscape/       scripts/synthesis_generator.py
    ├── cognitive-noise/          scripts/noise_injector.py
    ├── multi-model-adapter/      scripts/runtime_manifest.py
    ├── ultimate-roundtable/      scripts/{ultimate_orchestrator,clash_analyzer,memory_store,
    │                                      attention_split,deadlock_detector}.py
    └── role-{musk,feynman,munger,jobs,karpathy,pg}/
```

每个技能都是 `SKILL.md + scripts/ + references/`，**技能之间不使用跨目录相对引用**，可单独导入、单独使用。

---

## 4. 快速开始（本地）

```bash
cd marvis-roundtable-skills

# 一键验收（107 项 + 16 个脚本自检）
python tools/validate_repo.py

# 离线评测（36 条，不调用模型）
python tools/run_evals.py

# 宿主检测：我在什么环境？六个角色技能齐了吗？
python skills/host-bootstrap/scripts/bootstrap.py detect

# 8 步端到端演示：R0→R1→元认知→R2（含一次有效修正 + 一次从众漂移）→收敛→交接→决策景观→噪声拒绝→多基座调用包
python tools/demo_session.py --quiet --out .roundtable-demo

# 终极圆桌四阶段演示：摊牌→红蓝对抗（含空洞发言被拒的反例）→沙盘→降维打击→五节报告
python tools/demo_ultimate.py --quiet --out .ultimate-demo
```

最小手工流程（先设好脚本目录变量）：

```bash
ORCH=skills/roundtable-orchestrator/scripts
META=skills/meta-supervisor/scripts
DL=skills/decision-landscape/scripts

python $ORCH/state_manager.py init --topic "自建还是采购"        # → 记住输出的 state_path
python $ORCH/round_controller.py plan --state <state> --write    # 第 1 轮目标与并行批次
python $ORCH/state_manager.py add-claims   --state <state> --file musk-round1.json
python $ORCH/state_manager.py add-position --state <state> --file musk-round1.json
python $META/assumption_extractor.py  scan    --state <state> --write
python $META/divergence_classifier.py suggest --state <state> --write
python $META/fallacy_detector.py      scan    --state <state> --write
python $ORCH/convergence_detector.py  check   --state <state> --write
python $ORCH/state_manager.py summary --state <state> --json     # 交接块
python $DL/synthesis_generator.py build --state <state> --out 决策景观.md
python $DL/synthesis_generator.py check --state <state>          # 完整性检查
```

可选层：

```bash
# P3 认知噪声（只有 simulation 模式允许；rigorous 会被脚本拒绝并返回退出码 3）
python skills/cognitive-noise/scripts/noise_injector.py plan --state S --role pg --seed 7 --write
python skills/cognitive-noise/scripts/noise_injector.py check --state S

# P4 异构基座：分发调用包 → 宿主执行 → 合并校验
python skills/multi-model-adapter/scripts/runtime_manifest.py emit --state S --round 2 --out bundle \
  --assignment assignment.json
python skills/multi-model-adapter/scripts/runtime_manifest.py merge --state S --dir bundle \
  --state-manager skills/roundtable-orchestrator/scripts/state_manager.py
```

终极圆桌（独立状态文件，四阶段硬顺序）：

```bash
UR=skills/ultimate-roundtable/scripts

python $UR/ultimate_orchestrator.py init   --topic "议题" --out .ultimate/run1
python $UR/ultimate_orchestrator.py stage0 --state S --file mem.json     --write   # 记忆唤醒 + 北极星
python $UR/ultimate_orchestrator.py stage1 --state S --file roles.json   --write   # 150字+分舱+工具闭环
python $UR/ultimate_orchestrator.py stage2 --state S --file clash.json   --write   # 内心戏+验真+死锁熔断
python $UR/ultimate_orchestrator.py stage3 --state S --file vote.json    --write   # A/B/C 三选一裁决
python $UR/ultimate_orchestrator.py stage4 --state S --file action.json  --write   # 战术级清单+记忆
python $UR/ultimate_orchestrator.py check  --state S
python $UR/ultimate_orchestrator.py report --state S --out REPORT.md               # V4 五节报告

# 可选：沙盘推演（不覆盖三选一裁决）
python $UR/ultimate_orchestrator.py sandbox --state S --file sandbox.json --write

# V4 独立工具
python $UR/attention_split.py   plan --state S --role pg --write   # 生成分舱声明
python $UR/attention_split.py   check --state S                    # 分舱 + 150 字闸门校验
python $UR/attention_split.py   lenses                             # 打印六个镜头
python $UR/deadlock_detector.py check --state S [--write]          # 死锁检测（自动熔断）
python $UR/deadlock_detector.py fuse  --state S                    # 手动熔断

# 记忆库与量化器官
python $UR/memory_store.py stats                       # 看记忆库现状
python $UR/memory_store.py recall --query 评审          # 检索相关历史
python $UR/clash_analyzer.py spark    --state S --round 2    # 无火花 → 退出码 4，强制重开
python $UR/clash_analyzer.py survival --state S              # 存活率四项加权（V4 降为参考）
```

**退出码**：0 通过｜2 参数错误｜3 阶段校验失败｜**4 红蓝对抗无火花，必须重开一轮**。

需要 Python 3.9+，脚本仅用标准库；`tools/package_bundle.py` 另需 PyYAML（仅打包时用）。

### 触发方式

- 自然语言："开启圆桌讨论：要不要把年度评审改成季度"、"这场讨论的底层前提是什么"、
  "把这些讨论汇总成一份决策报告"、"担心多角色共享同一个模型导致盲区一致"
- 终极圆桌："**开启终极圆桌**"、"深度推演讨论"、"红蓝对抗圆桌"、"**战术推演圆桌**"
- 跨宿主接入："**接入 Claude**"、"接入 Codex"、"技能缺失"、"部署圆桌技能"
- 显式调用：`@roundtable-orchestrator`、`@ultimate-roundtable`、`@host-bootstrap` 等

---

## 5. 部署

### 5.1 马维斯 Marvis

两种方式，二选一：

**方式 A · 逐个导入 SKILL.md**（推荐先做，便于定位问题）

```
马维斯 → 技能管理 → 本地技能 → 导入技能 → 选择 SKILL.md
导入顺序：host-bootstrap → roundtable-orchestrator → meta-supervisor → position-evolution
        → decision-landscape → 6 个 role-* → cognitive-noise → multi-model-adapter
        → ultimate-roundtable
```

**方式 B · ZIP 上传**

```bash
python tools/package_bundle.py build --version 1.3.0 --per-skill
# 产物：
#   dist/marvis-roundtable-skills-v1.3.0.zip                  整包（含契约、AGENTS/CLAUDE 与 import-manifest.json）
#   dist/marvis-roundtable-skills-v1.3.0.import-manifest.json 导入清单（文件数/行数/描述/哈希）
#   dist/skills/<skill>-v1.3.0.zip                            逐技能包
python tools/package_bundle.py verify --zip dist/marvis-roundtable-skills-v1.3.0.zip
```

### 5.2 其他 AI 宿主（Claude / Codex / Hermes / Cursor）

**先检测，再部署**——六个角色技能在你那边可能根本不存在：

```bash
B=skills/host-bootstrap/scripts/bootstrap.py

python $B detect                                  # 我是什么宿主？六个角色技能齐吗？
python $B install --target ~/.claude/skills       # Claude Code
python $B install --target ~/.codex/skills        # Codex (ChatGPT)
python $B install --target ~/.hermes/skills       # Hermes
python $B verify  --target ~/.claude/skills       # 逐字段校验
```

`install` 有四级回退：**本地复制 → git clone → HTTP 逐文件下载 → 打印手工步骤**。
无网络无 git 时会打印 curl 与 ZIP 两种手工方案并返回退出码 1，**不会假装成功**。

仓库根已提供宿主入口文件：

| 文件 | 面向 |
|---|---|
| `AGENTS.md` | Codex / Hermes / Cursor / Cline / Windsurf |
| `CLAUDE.md` | Claude Code / Claude |

**六个角色技能仓库地址**：

| 技能 | 地址 |
|---|---|
| `role-musk` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-musk |
| `role-feynman` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-feynman |
| `role-munger` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-munger |
| `role-jobs` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-jobs |
| `role-karpathy` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-karpathy |
| `role-pg` | https://github.com/14122-adj/marvis-roundtable-skills/tree/main/skills/role-pg |

**降级契约**：角色技能确实缺失时，必须在输出里写
`⚠ 降级模式：role-* 技能未安装，角色协议为摘要级`，不允许假装完整协议已生效。

然后在马维斯里 `设置 → Skills → Create → Upload` 选择 ZIP。

**导入后的验收三步**：① 说"开启圆桌讨论"确认编排器可触发；② 单独触发一个角色技能确认字段一致；
③ 跑一场 3 轮讨论，确认最终产出决策景观报告且少数派观点被保留。

---

## 6. 验收结果（本次交付实测）

| 项目 | 结果 |
|---|---|
| `tools/validate_repo.py` | **107/107** 通过（结构 / frontmatter / 契约字段 / 章节 / 版本一致 / 禁用写法 / **16 个脚本自检**） |
| `tools/run_evals.py` | **36/36** 通过（含 14 条技能可触发性、2 条负例、12 条命令、6 条产物检查） |
| `tools/demo_session.py` | 圆桌主线 8 步通过：抓出 H1「竞赛必须拿奖才算成功」、4 角色回应、1 次有效修正 + 1 次从众漂移被拦、决策景观报告生成 |
| `tools/demo_ultimate.py` | 终极圆桌 V4 全流程通过：北极星锚定「月活」→ 6 条 ≤150 字交底（**2 条真实本地测量** + 4 条标注模拟）+ 分舱 + 工具闭环 → 3v3 sparked + 1 次验真 → **死锁判定与熔断话术** → 三选一（C 得 3 票，拍板 C）→ 战术清单（KPI/Kill 均带数字）→ 记忆写入 → V4 五节报告 |
| `tools/demo_ultimate.py` 反例 | 四条全部命中：空洞发言 `no_spark`（退出码 4）、缺 `[Tool Call]`（3）、**超 150 字**（3）、**Kill 无数字**（3） |
| `tools/package_bundle.py` | 14 个技能打包成功，`verify` 通过 |
| `bootstrap.py detect` | 在本机正确识别出 Claude / Codex / Marvis / DSH 四处技能目录，仓库内角色技能 6/6 就绪 |

### 终极圆桌 V4 的实测产物

`demo_ultimate.py` 的真实测量部分：本仓库 `.md`/`.py` 文件数与总行数
（以 `source: tool` 记入阶段一，可被任何人重跑复现）；
沙盘的 `Code` 调用也是**真实可运行的 Python 代码**。

V4 关注的是"落地"而不是"概率"，所以存活率降为过程留痕里的参考值（52%，medium）。
真正的主产出是这三样，且都被脚本强制校验：

```
北极星：月活
拍板：方案 C（触发式评审）—— 票数 A:1 / B:2 / C:3
战术清单：
  负责人   karpathy
  Start    本周在 2 个团队上线触发式评审，阈值设为月活跌破 8%
  KPI      30 天内触发不超过 5 次，月活不低于 9%
  Kill     如果 30 天内触发超过 12 次，立刻停止并回滚到年度评审
```

注意 KPI 与 Kill 都带具体数字——这是 V4 的硬门槛，
写"如果效果不好就停止"会被脚本以退出码 3 拒绝。

---

## 7. 诚实声明（重要）

1. **脚本不做语义判断。** `scripts/` 只做解析、登记、去重、计数、规则扫描，输出一律是
   `candidates` / `signals` + `needs_judgment: true`。隐性假设、根本矛盾的最终判定必须由模型或人完成。
2. **不能保证"触达根本"。** 本包能显著提高挖到共享前提的概率（每轮强制扫描 + 强制回应），
   但"根本"是开放判断，不存在可验证的收敛证明。
3. **同基座偏见是共通的。** 六个角色共享同一底座模型时，底层认知偏见共通；
   Layer 6 提供了分发到不同 provider 的调用包与合并校验，但**真实多 provider 调用在本环境未验证**，
   需要宿主支持；未指定模型时一律写 `unspecified`，绝不编造模型名。
4. **不是真人仿真。** 产出是**结构化理性审议**，不是生活化对话。
   Layer 5 只放宽表达质感，**会降低严谨性**，因此默认关闭且 `rigorous` 模式下被脚本拒绝。
5. **反从众机制是硬约束。** 无新证据的"立场修正"不会改变基线。这条会让人觉得"讨论不够顺滑"，
   但顺滑的共识往往是假共识。
6. **评测不调用模型。** `evals/` 是离线回归护栏，`trigger` 类只是关键词覆盖率启发式，
   不等于"技能该不该被触发"的语义判断；真正的模型级评测需要宿主提供 LLM（`--live` 会明确说明）。
7. **终极圆桌的数据诚实性由脚本强制。** 阶段一每条数据必须标 `source: tool`（真实调用）
   或 `simulated: true`（明确模拟）；两者都不标会被判为"把模拟数据伪装成真实数据"并拒绝。
   演示中只有 2 条是真实本地测量，其余 4 条明确标注为模拟——**报告头部会直接印出这个比例**。
8. **火花检测与存活率都是规则/算术，不是判断。** "打出火花"只说明结构上有交锋，
   不说明交锋质量；"存活率 52%"是可以被逐项挑战重算的算术结果，不是"这个方案该不该做"的结论。
9. **跨宿主适配只做文件层面。** `bootstrap.py` 会复制/下载技能文件并校验，但
   **不修改宿主配置、不重启宿主**；找不到马维斯技能目录时如实报"未检测到"，不猜路径。
10. **记忆库是本地 JSONL。** 不加密、不同步、不做语义检索（只有字面匹配）；
    跨机器使用需要自己同步 `.roundtable-memory/memories.jsonl`。
11. **V3/V4 的工具闭环只校验"有没有写"，不校验"结果真不真"。** 脚本能强制你写
    `[Tool Call]` 和表态句，但无法判断工具结果是否真实——这部分靠 `source`/`simulated`
    标注 + 报告头部的条数统计来约束，最终仍需人复核。
12. **语义判定由主持人（模型）完成，脚本只组织材料与记录判定。**
    `deadlock_detector.py` 调不了 LLM：`judge` 输出待判材料、`record` 收标签、`check` 据此判定。
    所以"语义级"的准确度取决于执行判定的模型——脚本保证的是**过程可审计**
    （每条判定都有 `from`/`to`/`label`/`reason`），不是判定本身绝对正确。
    结构路径（字符相似度）仍保留为兜底：它只抓逐字重复，抓不到换说法。
13. **分舱只影响"看见什么"，不改写原文。** `muted` 里只有 id，被屏蔽的内容在报告里可追溯；
    被追问时角色应承认"这不在我的镜头里"，而不是假装没发生。
14. **"颗粒度"校验是形式化的。** 脚本能查 KPI/Kill 里有没有数字、有没有咨询体措辞，
    但**判断不了那个数字是否合理**——一个荒谬的阈值同样能通过校验。数字的合理性靠人审。

---

## 8. 路线图

| 优先级 | 模块 | 状态 |
|---|---|---|
| P0 | `roundtable-orchestrator`、`meta-supervisor` | ✅ v1.0.0 |
| P1 | `position-evolution`、6 个角色思维协议 | ✅ v1.0.0 |
| P2 | `decision-landscape`（决策景观报告） | ✅ v1.1.0 |
| P3 | 轻量认知噪声（选择性注意 / 表达偏好 / 置信度传导） | ✅ v1.1.0（默认关闭） |
| P4 | 异构基座适配（调用包 + 合并校验） | ✅ v1.1.0（真实多 provider 调用待宿主支持） |
| P5 | 离线评测集与一键打包 | ✅ v1.1.0 |
| **P6** | **`ultimate-roundtable` V2**（红蓝对抗 / 内心戏 / 沙盘 / 存活率） | ✅ v1.2.0（技能本体 v2.0.0） |
| **P7** | **终极圆桌 V3**（跨会话记忆 + 工具闭环 + 交叉验真） | ✅ v1.3.0（技能本体 v3.0.0） |
| **P8** | **跨 AI 宿主适配**（`host-bootstrap` + AGENTS.md / CLAUDE.md） | ✅ v1.3.0（技能本体 v3.0.0） |
| **P9** | **终极圆桌 V4 战术指挥部**（北极星 / 注意力分舱 / 死锁熔断 / 三选一 / 战术清单） | ✅ v1.4.0（技能本体 v4.0.0） |
| **P10** | **语义级死锁检测**（REPEAT/PROGRESS/UNCERTAIN 三标签 + 双路径熔断） | ✅ **v1.5.0（技能本体 v4.1.0）** |
| P11 | 完整认知噪声模块（记忆衰减、情绪状态） | ⏳ 暂不做（性价比低，会显著降低严谨性） |
| P12 | 真实多 provider 联调 | ⏳ 待宿主具备多模型能力 |
| P13 | 记忆库云端同步 / 语义检索 | ⏳ 当前为本地 JSONL + 字面匹配 |
| P14 | 战术清单的"数字合理性"审查（如 KPI 是否与历史基线匹配） | ⏳ 当前只校验形式，不校验数值合理性 |

---

## 9. 许可

MIT，见 `LICENSE`。

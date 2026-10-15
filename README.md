# marvis-roundtable-skills

马维斯（Marvis / Agent Skills 兼容）圆桌讨论技能包：把"多角色辩论"从**人设扮演**升级为一套**可执行的审议机制**。

一句话：**讨论机制从角色提示词里抽出来交给编排层；角色只负责自己的思维协议。**

- 版本：**v1.1.0**（P0–P5 全部落地）
- 形态：**12 个独立技能**（每个可单独导入）＋ **10 个零依赖 Python 脚本**（全部带 `--selftest`）
- 验收：`tools/validate_repo.py` 83 项、`tools/run_evals.py` 23 条离线评测、8 步端到端 demo
- 语言：中文正文，字段名英文

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

## 2. 七层架构

```
Layer 0  roundtable-orchestrator   调度、状态、轮次、聚合（不参与讨论）
Layer 1  role-musk / feynman / munger / jobs / karpathy / pg   角色思维协议 ×6
Layer 2  meta-supervisor           隐性假设、分歧分类、信息缺口、谬误、质量评分
Layer 3  position-evolution        修正判定、反从众、基线更新
Layer 4  decision-landscape        决策景观报告（共识/分歧/假设/建议/缺口/少数派）
Layer 5  cognitive-noise           轻量认知噪声（可选，仅 simulation 模式）
Layer 6  multi-model-adapter       异构基座调用包与结果合并（可选）
```

数据流：

```
R0 列共享前提 → R1 六角色隔离立论 → R1.5 元认知扫描并注入
   → R2 自由交叉（必须回应注入项，可修正立场）→ R2.5 收敛检测
   → R3 综合 / 或提前收敛 → 交接块 → Layer 4 决策景观报告
                    ↑                          ↑
          Layer 5 噪声（仅 simulation）    Layer 6 多基座分发（可选）
```

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
├── docs/
│   ├── output-contract.md        ← 冻结契约 v1.1.0：所有字段的唯一来源（含 §8 §9 §10）
│   └── example-session.md        ← 一次完整讨论的实录（示例数据，含脚本误报说明）
├── evals/
│   └── evals.json                ← 23 条离线评测（trigger / command / artifact）
├── tools/
│   ├── validate_repo.py          ← 83 项仓库自检（结构/契约/版本/禁用写法/脚本自检）
│   ├── run_evals.py              ← 离线评测 runner（不调用模型，--live 会明确说明）
│   ├── package_bundle.py         ← 打包 ZIP（整包 + 逐技能），打包前校验
│   └── demo_session.py           ← 8 步端到端演示 = 集成测试
└── skills/
    ├── roundtable-orchestrator/  scripts/{state_manager,round_controller,convergence_detector}.py
    ├── meta-supervisor/          scripts/{assumption_extractor,divergence_classifier,fallacy_detector}.py
    ├── position-evolution/       scripts/revision_tracker.py
    ├── decision-landscape/       scripts/synthesis_generator.py
    ├── cognitive-noise/          scripts/noise_injector.py
    ├── multi-model-adapter/      scripts/runtime_manifest.py
    └── role-{musk,feynman,munger,jobs,karpathy,pg}/
```

每个技能都是 `SKILL.md + scripts/ + references/`，**技能之间不使用跨目录相对引用**，可单独导入、单独使用。

---

## 4. 快速开始（本地）

```bash
cd marvis-roundtable-skills

# 一键验收（83 项 + 10 个脚本自检）
python tools/validate_repo.py

# 离线评测（23 条，不调用模型）
python tools/run_evals.py

# 8 步端到端演示：R0→R1→元认知→R2（含一次有效修正 + 一次从众漂移）→收敛→交接→决策景观→噪声拒绝→多基座调用包
python tools/demo_session.py --quiet --out .roundtable-demo
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

需要 Python 3.9+，脚本仅用标准库；`tools/package_bundle.py` 另需 PyYAML（仅打包时用）。

### 触发方式

- 自然语言："开启圆桌讨论：要不要把年度评审改成季度"、"这场讨论的底层前提是什么"、
  "把这些讨论汇总成一份决策报告"、"担心多角色共享同一个模型导致盲区一致"
- 显式调用：`@roundtable-orchestrator`、`@decision-landscape` 等

---

## 5. 部署到马维斯

两种方式，二选一：

**方式 A · 逐个导入 SKILL.md**（推荐先做，便于定位问题）

```
马维斯 → 技能管理 → 本地技能 → 导入技能 → 选择 SKILL.md
导入顺序：roundtable-orchestrator → meta-supervisor → position-evolution → decision-landscape
        → 6 个 role-* → cognitive-noise → multi-model-adapter
```

**方式 B · ZIP 上传**

```bash
python tools/package_bundle.py build --version 1.1.0 --per-skill
# 产物：
#   dist/marvis-roundtable-skills-v1.1.0.zip                  整包（含契约与 import-manifest.json）
#   dist/marvis-roundtable-skills-v1.1.0.import-manifest.json 导入清单（文件数/行数/描述/哈希）
#   dist/skills/<skill>-v1.1.0.zip                            逐技能包
python tools/package_bundle.py verify --zip dist/marvis-roundtable-skills-v1.1.0.zip
```

然后在马维斯里 `设置 → Skills → Create → Upload` 选择 ZIP。

**导入后的验收三步**：① 说"开启圆桌讨论"确认编排器可触发；② 单独触发一个角色技能确认字段一致；
③ 跑一场 3 轮讨论，确认最终产出决策景观报告且少数派观点被保留。

---

## 6. 验收结果（本次交付实测）

| 项目 | 结果 |
|---|---|
| `tools/validate_repo.py` | 83/83 通过（结构 / frontmatter / 契约字段 / 章节 / 版本一致 / 禁用写法 / 10 个脚本自检） |
| `tools/run_evals.py` | 23/23 通过（含 12 条技能可触发性、2 条负例、6 条命令、3 条产物检查） |
| `tools/demo_session.py` | 端到端 8 步通过：抓出 H1「竞赛必须拿奖才算成功」、4 角色回应、1 次有效修正 + 1 次从众漂移被拦、报告生成 |
| `tools/package_bundle.py` | 12 个技能打包成功，`verify` 通过 |

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
| P6 | 完整认知噪声模块（记忆衰减、情绪状态） | ⏳ 暂不做（性价比低，会显著降低严谨性） |

---

## 9. 许可

MIT，见 `LICENSE`。

# marvis-roundtable-skills

马维斯（Marvis / Agent Skills 兼容）圆桌讨论技能包：把"多角色辩论"从**人设扮演**升级为一套**可执行的审议机制**。

一句话：**讨论机制从角色提示词里抽出来交给编排层；角色只负责自己的思维协议。**

- 版本：v1.0.0（P0 + P1 全量落地；P2 见路线图）
- 形态：9 个独立技能（每个可单独导入），7 个零依赖 Python 脚本，全部带 `--selftest`
- 语言：中文正文，字段名英文

---

## 1. 它解决什么问题

单角色或多角色"各说各话"的讨论有三个固有短板，本技能包逐条给出工程回应：

| 短板 | 现象 | 本包的机制 |
|---|---|---|
| 挖不到根本 | 所有人默认"竞赛必须拿奖才算成功"，六个人在这个前提里争资源怎么分，辩再久也碰不到前提 | **Layer 2 元认知监督者**每轮独立扫描隐性假设，其输出是下一轮的**强制输入** |
| 立场写死 | 角色被说服也不改，或"为了共识"集体投降 | **Layer 3 立场演化**：允许修正，但无新证据的修正**不改变立场基线**，只记 `compliance_drift` |
| 形式僵化 | "第二轮必须一对一""第三轮必须联动≥2 人"——仿真的是形式，不是思考动机 | **目标驱动**：只规定本轮认知目标；唯一保留的硬约束是第一轮隔离发言（防锚定） |

---

## 2. 五层架构

```
Layer 0  roundtable-orchestrator   调度、状态、轮次、聚合（不参与讨论）
Layer 1  role-musk / feynman / munger / jobs / karpathy / pg   角色思维协议 ×6
Layer 2  meta-supervisor           隐性假设、分歧分类、信息缺口、谬误、质量评分
Layer 3  position-evolution        修正判定、反从众、基线更新
Layer 4  decision-landscape        决策景观（P2，本版本未实现，接口已预留）
```

数据流：

```
R0 列共享前提 → R1 六角色隔离立论 → R1.5 元认知扫描并注入
   → R2 自由交叉（必须回应注入项，可修正立场）→ R2.5 收敛检测
   → R3 综合 / 或提前收敛 → 交接块 → （P2）决策景观报告
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

每个角色输出都带 `epistemic_status`：`confidence` / `uncertainty_points` / `will_revise_if`。
这是**轻量级的不确定性注入**——保留"说不准在哪"，但不引入完整认知噪声模块（那会显著降低严谨性）。

---

## 3. 目录结构

```
marvis-roundtable-skills/
├── README.md  LICENSE  CHANGELOG.md
├── docs/
│   ├── output-contract.md        ← 冻结契约：所有字段的唯一来源
│   └── example-session.md        ← 一次完整讨论的状态与元认知报告样例
├── tools/
│   └── validate_repo.py          ← 一键自检（54+ 项）
└── skills/
    ├── roundtable-orchestrator/  SKILL.md + scripts/{state_manager,round_controller,convergence_detector}.py
    │                             + references/interaction-protocols.md
    ├── role-musk/                SKILL.md + references/first-principles-examples.md
    ├── role-feynman/             SKILL.md + references/explanation-verification.md
    ├── role-munger/              SKILL.md + references/mental-models-catalog.md
    ├── role-jobs/                SKILL.md + references/simplicity-criteria.md
    ├── role-karpathy/            SKILL.md + references/system-decomposition-guide.md
    ├── role-pg/                  SKILL.md + references/case-based-reasoning.md
    ├── meta-supervisor/          SKILL.md + scripts/{assumption_extractor,divergence_classifier,fallacy_detector}.py
    │                             + references/metacognitive-checklist.md
    └── position-evolution/       SKILL.md + scripts/revision_tracker.py
                                  + references/revision-protocols.md
```

**技能之间不使用相对路径跨目录引用**：每个 SKILL.md 自带所需的字段说明，因此可以单独导入、单独使用。

---

## 4. 快速开始（本地）

```bash
cd marvis-roundtable-skills
python tools/validate_repo.py          # 全部自检（含 7 个脚本的 --selftest）

# 一次最小可运行的会话（先设好两个脚本目录变量）
ORCH=skills/roundtable-orchestrator/scripts
META=skills/meta-supervisor/scripts

python $ORCH/state_manager.py init --topic "自建还是采购"
# → 输出 state_path，例如 .roundtable/rt-20260601-101500-a1b2/state.json

python $ORCH/round_controller.py plan --state <state> --write
# → 第 1 轮目标与并行批次（隔离发言）

# 角色发言（JSON 形态见 SKILL.md 的字段速查）写回状态
python $ORCH/state_manager.py add-claims   --state <state> --file musk-round1.json
python $ORCH/state_manager.py add-position --state <state> --file musk-round1.json

# 元认知层
python $META/assumption_extractor.py  scan    --state <state> --write
python $META/divergence_classifier.py suggest --state <state> --write
python $META/fallacy_detector.py      scan    --state <state> --write

# 收敛检测与摘要
python $ORCH/convergence_detector.py check --state <state> --write
python $ORCH/state_manager.py summary --state <state>          # 文本
python $ORCH/state_manager.py summary --state <state> --json   # 交接块
```

需要 Python 3.9+，仅用标准库。

### 触发方式

- 自然语言："开启圆桌讨论：要不要把年度评审改成季度"、"让几个角色就这个方案辩一辩"、"这场讨论的底层前提是什么"
- 显式调用：`@roundtable-orchestrator`

---

## 5. 部署到马维斯

本地开发已就绪，**GitHub 上传与马维斯导入尚未执行**（需要你的账号环境）：

1. **本地技能导入测试**：马维斯 → 技能管理 → 本地技能 → 导入技能 → 选择任一 `SKILL.md`
   （建议顺序：先 `roundtable-orchestrator`，再 `meta-supervisor`，再 6 个角色）
2. **上传 GitHub**：`git init && git add -A && git commit && git tag v1.0.0 && git push`
3. **从仓库导入**：马维斯 → 导入外部技能（拉取仓库）或打包 ZIP 后
   设置 → Skills → Create → Upload
4. **验证**：导入后先单独触发一个角色技能（"用费曼的视角看看这个说法"），
   确认字段与输出契约一致，再跑完整编排流程

SKILL.md 使用标准 YAML frontmatter（`name` / `description` / `license` / `metadata`），
与 Claude Agent Skills 及本机 `.dsh/skills/` 现有技能格式一致。

---

## 6. 诚实声明（重要）

1. **脚本不做语义判断。** `scripts/` 只做解析、登记、去重、计数、规则扫描，输出一律是
   `candidates` + `needs_judgment: true`。隐性假设、根本矛盾的最终判定必须由模型或人来完成。
2. **不能保证"触达根本"。** 本包能显著提高挖到共享前提的概率（每轮强制扫描 + 强制回应），
   但"根本"是开放判断，不存在可验证的收敛证明。
3. **同基座偏见是共通的。** 六个角色共享同一底座模型时，底层认知偏见是共通的；
   角色视角差异化只能减少单视角盲区，不能跳出模型自身的盲区。真正突破需要异构基座协同（工程成本更高）。
4. **不是真人仿真。** 产出是**结构化理性审议**，不是生活化对话。`simulation` 模式只放宽表达质感，
   不豁免逻辑要求。
5. **反从众机制是硬约束。** 无新证据的"立场修正"不会改变基线。这条会让人觉得"讨论不够顺滑"，
   但顺滑的共识往往是假共识。

---

## 7. 路线图

| 优先级 | 模块 | 状态 |
|---|---|---|
| P0 | `roundtable-orchestrator`、`meta-supervisor` | ✅ v1.0.0 |
| P1 | `position-evolution`、6 个角色思维协议 | ✅ v1.0.0 |
| P2 | `decision-landscape`（决策景观报告） | ⏳ 未实现，交接字段已由 `summary --json` 预留 |
| P3 | 轻量认知噪声（选择性注意、表达偏好） | ⏳ 仅实现 `epistemic_status` 三个字段；完整噪声模块暂不做 |
| P3 | 异构基座多模型讨论 | ⏳ 概念阶段 |

---

## 8. 许可

MIT，见 `LICENSE`。

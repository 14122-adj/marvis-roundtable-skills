# 变更日志

遵循语义化版本。字段与枚举的改动一律同步 `docs/output-contract.md` 并提升契约版本号。

## v1.7.1 — 2026-11-01

上架准备：把打包器做到能直接产出符合 **Agensi / Claude Skills 市场规范**的单技能 ZIP。

> 本次只改工具与文档，**技能版本号保持 1.7.0 不变**（契约未变）。

**`package_bundle.py` 新增市场模式**
- `market` / `--market` / `--only`：为每个技能打一个**单技能 ZIP**
- 严格遵循市场 zip structure 规范：
  - 单层顶层文件夹（文件夹名 = 技能名）
  - `SKILL.md` 在该文件夹根部（不能是 zip 根，也不能双层嵌套）
  - 无 `.DS_Store` / `Thumbs.db` / `__pycache__` / `.pyc`
- 每个市场包自动附带一份**面向买家的 README.md**（含装法、触发示例、目录说明）
- `verify-market`：一次校验整个 `dist/market/`，逐包检查结构与 frontmatter
- 整包同时补齐了此前遗漏的 `community-roles/`、`templates/`、`tools/`、`evals/`
- 整包新增 **`START-HERE.md`**（解压后第一眼看到的入口）

**修复**
- `render_report` 硬编码报告标题为「V4.0」，但 schema 已是 4.1.0 → 改为 V4.1
- `verify()` 把 `community-roles/_template` 当成正式角色校验 → 模板不参与校验
- 打包清单统计社区角色时把 `_template` 计入 → 已排除

**新增 `docs/agensi-listing.md`**
- 可直接复制粘贴的英文 listing 文案（标题 / 简介 / 完整描述 / tags / 触发短语）
- 定价建议（$5 试水 → 拿到评价后再涨）
- 上架前检查清单（12 项，含哪些我已完成、哪些必须你来做）

**README 顶部**
- 新增显眼的 QUICKSTART 入口区块与 Releases 下载指引
- 新增「你想做什么 → 去哪」导航表

**验收**
- 127/127 仓库自检、38/38 离线评测
- 14 个市场包 `verify-market` 全部通过
- 解压市场包后脚本实测 `selftest OK`
- 全库密钥扫描：未发现硬编码密钥

## v1.7.0 — 2026-11-01

**10 分钟首次跑通**：把「导入 14 个技能 + 装 Python + 手写 5 个 JSON」压成一条命令。
契约升到 v1.7.0（新增 §14），其余 12 个技能对齐 1.7.0。

**新增 `tools/quickstart.py`**
- 一条命令做四件事：体检 → 跑一场完整终极圆桌 → 仓库自检 → 打印下一步
- 体检覆盖 Python 版本、仓库完整性、六个角色技能、社区角色、脚本可执行性
- 内置示例 **0.9 秒**跑完五阶段并生成报告（实测）
- 任一步失败都明确报出卡在哪、怎么修，不静默降级

**新增 `tools/wizard.py`**
- 交互式采集，替用户生成 5 个阶段配置，**每步即时校验**
- 例如发言漏了 `[数据诉求]` 会当场让重填，而不是等跑到阶段一才报错
- `--demo` 可直接生成示例；非交互环境会明确提示改用 `--demo`

**新增 `QUICKSTART.md`**
- 三条路径：跑通 / 换成自己的议题 / 装进 AI 客户端
- 三个常见卡点及修复：`no_spark`（退出码 4）、阶段一被拒（3）、战术清单被拒（3）

**修复两个真实可用性问题**
1. `stage3` 的 `kind` 字段被当作必填，但它只是展示标签、可由 `OPTION_DEFS` 自动补齐。
   新手会被这条无意义的校验卡住 → 改为自动补全。
2. 向导示例只给 2 条交锋，阶段二直接 `no_spark`（退出码 4）——
   **新手第一课就是失败**。已补齐到火花检测下限（3 攻 2 防 2 靶点），
   并把「示例必须真能跑」写进契约 §14。

**工程**
- `validate_repo.py` 扩到 **121 项**（新增 `QUICKSTART.md`、两个新工具、向导自检）
- `package_bundle.py` 打包纳入 `CONTRIBUTING.md` 与 `QUICKSTART.md`
- README 顶部新增「30 秒跑通」段

## v1.6.0 — 2026-11-01

社区角色机制 + 平民视角审计；契约升到 v1.6.0（新增 §13），其余 12 个技能对齐 1.6.0。

**平民视角审计（`clash_analyzer.py` 新增 `civilian` 子命令）**
- 六个角色全是精英视角，他们**全票通过**时往往意味着共享同一盲区
- 检测三类信号：精英共识（全票 / 零分歧）、"用户应该会……"式以假设代验证、
  平民角色是否已被召唤
- 召唤建议：小白用户 / 愤怒的客户 / 一线执行者 / 一线客服
- **平民角色的三条硬约束**：必须具体、必须带数字、不许提"加个引导"这类零成本建议
- `ultimate_orchestrator.check()` 已接入，出现精英共识时在 warnings 里提示

**社区角色机制（`community-roles/`）**
- 新增目录 `community-roles/`，独立版本号，不参与统一版本对齐
- 两个官方示例：
  - `role-civilian`（前缀 `V`）平民视角：只问能不能用、要不要填这么多、出错找谁
  - `role-contrarian`（前缀 `C`）职业杠精：逐句盘问"凭什么"，并明确写出与芒格的分工
- `community-roles/_template/` 提供可复制的模板（SKILL.md + references）
- `CONTRIBUTING.md`：贡献标准、13 项校验、审核尺度

**新增工具 `tools/validate_role.py`**
- 13 项检查，分 ERROR / WARN / INFO 三级
- 关键检查：id 前缀冲突、references 引用是否真实存在、跨目录相对引用、盲区条数
- `validate_repo.py` 自动调用它，社区角色与核心技能同一道门禁

**修复：社区角色前缀未注册（真 bug）**
- `state_manager.py` 与 `runtime_manifest.py` 的正则写死为 `[MFGJKP]`，
  社区角色的 `V`/`C` 前缀 claim 会被直接拒绝
- 改为从 `ROLE_PREFIX` 动态生成，新增角色只需改映射表
- 澄清 `C` 前缀与 `open_challenges` 编号 `C1` 的命名空间差异（claim 带短横 `C1-1`，challenge 不带）

**契约补充**
- §2 新增「R1 隔离轮的引用规则」：R1 只能引用议题原文与 R0 的 `shared_premises`，
  不得引用其他角色 R1 的发言（它们还不存在）
- §3 新增「前缀注册表」与命名空间澄清
- 新增 §13 社区角色契约（目录约定、前缀登记、13 项准入、R1 引用规则）

**工程**
- `validate_repo.py` 扩到 **118 项**（新增社区角色专项检查 + CONTRIBUTING.md 结构检查）
- 禁用写法扫描新增"规则清单豁免"：整行在描述"什么不允许"时，其中的禁用样例算引用不算违规

## v1.5.0 — 2026-11-01

`ultimate-roundtable` 升到 **V4.1**：阶段二死锁检测从「字符相似度」升级为**语义级判定**；
契约升到 v1.5.0，其余 12 个技能版本号对齐 1.5.0。

**语义级死锁检测（`deadlock_detector.py` 重写）**
- 主持人每轮结束**在内心完成判定**（不输出过程），对比本轮与上一轮发言
- 三标签：`[REPEAT]`（换说法/同义词/换例子但核心论点与支撑数据未变）/
  `[PROGRESS]`（新证据、改观点、针对性反驳特定词句、**反问质疑要数据**）/ `[UNCERTAIN]`
- **放行规则**：本轮出现 `PROGRESS` 即放行，哪怕结构相似度 1.0
- **熔断规则**：`REPEAT > 0 且 PROGRESS == 0` 连续 2 轮 → 熔断
- **结构路径保留为兜底**：无语义判定时退回「相似度 ≥0.55 + 无新事实 + 无修正 + 靶点未变」
- 新增三个子命令：`judge`（生成待判材料）/ `record`（写回标签，归一化 `[repeat]`→`REPEAT`）/
  `check`（双路径判定，`trigger` 标明 `semantic`/`structural`）
- 每条判定必须带 `reason`，写入 `semantic_verdicts`，**可审计**
- `stage2` 支持直接携带 `semantic_verdicts` 数组，一次提交完成「对抗 + 语义判定」
- **熔断话术更新**：`[系统强制熔断] 双方已陷入实质重复，此议题直接交由最终裁决阶段处理。`
  （旧话术「双方无法说服彼此」保留为常量，供历史状态兼容）

**为什么需要这层**：实测两段意思相同的话换个说法后，字符相似度只有 0.0x，
结构路径完全抓不到。而"我觉得他们在重复"若不落成带理由的记录，就只是主观感觉。

**工程**
- `validate_repo.py` / `package_bundle.py` 版本口径更新到 1.5.0 / 4.1.0
- `deadlock_detector.py` selftest 扩到 22 条断言：逐字重复（结构路径）、换说法（语义路径）、
  `PROGRESS` 放行、单轮不熔断、连续两轮熔断、`UNCERTAIN` 不定论、judge 材料、record 归一化
- `ultimate_orchestrator.py` selftest 增加语义路径断言（结构抓不到 → 语义 REPEAT 触发）

## v1.4.0 — 2026-11-01

`ultimate-roundtable` 升到 **V4.0**（战术指挥部）；契约升到 v1.4.0（§11 重写），
其余 12 个技能版本号对齐 1.4.0。

**`ultimate-roundtable` V4.0**
- **北极星锚定**（阶段零）：必须指定唯一焦点指标（`north_star`），缺则拒绝；
  阶段一每条发言必须提及该指标，偏离即判无效发言
- **注意力分舱**（新增 `attention_split.py`）：
  - 每个角色只看见与自己镜头相关的历史，六个镜头（物理成本/可检验性/风险激励/复杂度/可复现/案例）
  - **150 字闸门**：阶段一发言去标点计数超限直接拒绝
  - 红线：只记录 id 不改写原文；北极星与 `must_respond` 永不被屏蔽
- **死锁熔断**（新增 `deadlock_detector.py`）：
  - 四项判据（复读相似度 ≥0.55 / 无新事实 / 无立场修正 / 靶点未变）
  - 连续 2 轮全中 → 输出 `[系统强制熔断]` 并置 `debate_closed`，此后拒绝任何 stage2 提交
- **铁血裁决**（阶段三重写）：强制 A/B/C 三选一（互斥性校验，换皮拒绝）+ 六人最后一票
  + 主持人拍板；拍板与多数票不一致时必须记录 `decision_reason`
- **战术级行动清单**（阶段四重写）：负责人 / Start / KPI / Kill / Need Info 五要素，
  KPI 与 Kill **必须含数字**，出现"大概/也许/酌情/视情况"直接拒绝
- **报告升级为 V4 五节**：北极星与底线假设 / 证据链 / 铁血裁决 / 战术级清单 / 记忆
- 沙盘降级为可选的 `sandbox` 子命令，写入 `stage3.sandbox`，**不覆盖**三选一裁决

**工程**
- `validate_repo.py` 扩到 **107 项**（16 个脚本自检，新增 `tactical-playbook.md` 与两个新脚本）
- `evals/evals.json` 扩到 **36 条**
- `tools/demo_ultimate.py` 升级为 V4 全流程，含四条反例验证：
  空洞发言（退出码 4）、缺 Tool Call（3）、超 150 字（3）、Kill 无数字（3），
  并演示死锁判定与熔断话术
- 契约 §11 重写为 V4（11.5 报告格式、11.5b 三条硬约束、11.5c 三选一、11.5d 战术清单、11.7 新脚本）

## v1.3.0 — 2026-11-01

`ultimate-roundtable` 升到 **V3.0**，新增 **`host-bootstrap` v3.0.0**（跨 AI 宿主适配）；
契约升到 v1.3.0（§11 重写 + 新增 §12），其余 12 个技能版本号对齐 1.3.0。

**`ultimate-roundtable` V3.0**
- **阶段零 · 记忆唤醒**：新增 `memory_store.py`（JSONL 跨会话记忆库，≤200 字硬门槛、字面检索、
  可手工修复）；`stage0` 输出固定开场白 `[会议启动] 已加载历史记忆：…`
- **工具调用闭环**：每条发言必须同时具备 `[数据诉求]` + `[Tool Call: Search|Code]` +
  `基于此数据，我的观点是…` 三要素，缺一即整体拒绝（退出码 3）
- **交叉验真**：`[打断并验真]` 必须给出 `[Tool Call]` 或 `verify_result`，
  `verdict ∈ {supported, refuted, inconclusive}`；只打断不查证直接拒绝
- **沙盘工具验证**：`sandbox.tool_calls` ≥1 条，`Code` 类型必须有可运行 `code`
- **记忆沉淀**：阶段四默认 `persist_memory: true`，真正写入记忆库并回报记忆 id
- **报告升级为 V3 五节**：第 1 节改为「本次会议引入的外部数据 / 工具结果」，
  共识与分歧移入「过程留痕」；头部打印阶段一/沙盘的真实与模拟条数

**`host-bootstrap` v3.0.0（跨 AI 接入）**
- `bootstrap.py detect`：识别 Claude / Codex / Hermes / 马维斯 / DSH / 通用环境，
  探测技能目录，检查六个角色技能是否就绪
- `bootstrap.py install`：四级回退（本地复制 → git clone → HTTP 逐文件下载 → 打印手工步骤），
  幂等、支持 `--dry-run`、含 references 不只 SKILL.md
- `bootstrap.py verify`：逐字段校验 `installed / frontmatter_ok / name_ok / missing_files`
- 新增仓库级入口文件 `AGENTS.md`（Codex/Hermes/Cursor 等）与 `CLAUDE.md`（Claude Code）
- 降级契约：角色技能缺失时必须声明「⚠ 降级模式」，不得假装完整协议生效

**工程**
- `validate_repo.py` 扩到 **102 项**（14 个技能、14 个脚本自检、新增两个入口文件检查）
- `evals/evals.json` 扩到 **33 条**（新增 host-bootstrap 可触发性、两个脚本命令、两个入口产物检查）
- `package_bundle.py`：导入顺序把 `host-bootstrap` 提到最前，打包纳入 `AGENTS.md` / `CLAUDE.md`
- `tools/demo_ultimate.py` 升级为 V3 全流程：阶段零记忆唤醒 → 工具闭环 → 交叉验真 →
  沙盘 Code 验证 → 记忆写入，并新增两条反例验证（空洞发言退出码 4、无 Tool Call 退出码 3）

## v1.2.0 — 2026-11-01

新增 `ultimate-roundtable` v2.0.0（上游 spec 独立发版），契约升到 v1.2.0（新增 §11），
其余 12 个技能版本号对齐到 1.2.0。

**`ultimate-roundtable`（Layer 0+ · 高强度审议）**
- `ultimate_orchestrator.py`：四阶段推进（摊牌 → 对抗 → 沙盘 → 降维打击），阶段间硬顺序校验
- 阶段一强制 `[数据诉求]` + `tool_result`，**区分真实工具调用与模拟数据**，伪装数据直接拒绝
- 阶段二强制内心戏 `(Inner Thought: ...)`、`[打断]` 标签、3v3 红蓝分营
- 阶段三沙盘：≥3 月度节点、每节点必须给 `metric` 或 `error`、必须由 Karpathy + 马斯克主推、
  `[召唤：…]` 临时角色需写清 reason/statement
- 阶段四：共同隐性假设 + 被证伪前提 + `[MEMORY_UPDATE]`（≤200 字硬门槛）
- `clash_analyzer.py`：**火花检测**（六个计数，任一不达标 → 退出码 4 强制重开）与
  **存活率模型**（四项加权，公式公开可手算复现）
- 报告格式冻结为五节；行动栏有空、缺存活率、缺记忆、出现"已达成共识/各有优劣"等措辞一律报错退出
- `tools/demo_ultimate.py`：端到端演示，含两条**真实本地测量**（仓库文件数/行数）与四条明确标注的模拟数据

**工程**
- `validate_repo.py` 扩到 91 项：新增 `ultimate-roundtable` 结构与两个脚本自检，
  版本一致性支持 `VERSION_OVERRIDES`（ultimate 独立发版）
- `evals/evals.json` 扩到 27 条：新增 ultimate 可触发性、两个脚本命令、报告结构产物检查
- `package_bundle.py`：导入顺序追加 `ultimate-roundtable`
- 全部 12 个脚本通过 `--selftest`

## v1.1.0 — 2026-06-01

路线图 P2–P5 落地：新增 3 个技能、3 个脚本、3 份参考手册、离线评测集与打包器；契约升到 v1.1.0。

**Layer 4 · `decision-landscape`（P2，决策景观）**
- `synthesis_generator.py`：把讨论状态聚合成分区报告（共识区 / 分歧区 / 隐性假设 / 决策建议 / 信息缺口 / 少数派保护 + 未检验主张附录）
- 共识强度三档口径（剔除 `compliance_drift` 后的有效支持数）：`unanimous` / `majority` / `weak`
- `check` 完整性检查：少数派是否被保留、弱共识、≥3 角色漂移时的"假共识"告警、事实分歧是否缺 `G` 缺口
- 禁止断言护栏：报告出现"已达成共识 / 已验证 / 已挖到根本"等字样时脚本直接报错退出

**Layer 5 · `cognitive-noise`（P3，轻量认知噪声，默认关闭）**
- `noise_injector.py`：选择性注意（确定性种子 + 必须声明忽略清单）、表达偏好四档、置信度传导
- **脚本级开关**：`mode=rigorous` 时 `plan` 直接以退出码 3 拒绝（不靠文档纪律）
- 可控性红线：manifest 只记录 id，出现任何文本即判定"改写原文"违规；`must_respond` 不受注意力筛选影响

**Layer 6 · `multi-model-adapter`（P4，异构基座适配，可选）**
- `runtime_manifest.py emit`：为每个角色生成独立调用包（含契约摘要、payload schema、隔离要求、调用包哈希）
- `merge`：按契约校验跨模型结果（8 个固定错误码），可调用 `state_manager.py` 回写状态
- `unspecified` 纪律：未指定 provider/model 一律写 `unspecified`，禁止编造模型名（仓库自检含此项扫描）

**P5 · 评测与打包**
- `evals/evals.json` + `tools/run_evals.py`：23 条离线评测（trigger 覆盖率回归护栏 / command 真实执行 / artifact 结构检查），明确不调用模型
- `tools/package_bundle.py`：打包整包 ZIP 与逐技能 ZIP，打包前校验 frontmatter、name 一致性与跨目录相对引用
- `tools/demo_session.py` 扩展为 8 步端到端：新增决策景观生成、噪声开关拒绝验证、多基座调用包生成

**工程**
- `tools/validate_repo.py` 扩到 83 项：新增版本一致性（技能 / CHANGELOG / 契约三方对齐）与"疑似编造真实模型名"扫描
- 全部 10 个脚本通过 `--selftest`；`.gitignore` 增加 `dist/`

## v1.0.0 — 2026-06-01

P0 + P1 全量落地。9 个技能、7 个脚本、3 份参考手册、1 份冻结契约。

**Layer 0 · roundtable-orchestrator**
- 状态管理器 `state_manager.py`：会话初始化、claim/response 登记、立场基线更新、轮次推进、交接块生成
- 轮次控制器 `round_controller.py`：目标驱动的下一轮计划、覆盖度统计、前置阻塞检查
- 收敛检测器 `convergence_detector.py`：新增关键论据计数、跨轮重复度、分歧类型分布、根因候选
- 明确废除"一对一轮流 / 联动≥2 人 / 字数限制"等硬性形式约束，仅保留第一轮隔离发言

**Layer 1 · 六个角色思维协议**
- `role-musk` 第一性原理拆解；`role-feynman` 费曼技巧验证；`role-munger` 逆向 + 多元模型；
  `role-jobs` 产品纯粹性追问；`role-karpathy` 系统分解 + 可复现性；`role-pg` 从案例归纳
- 每个角色统一输出 `epistemic_status`（confidence / uncertainty_points / will_revise_if）
  与 `blind_spot_declared`（自曝视角盲区）
- 每个角色附独立参考手册（正反例均为抽象化工作场景，不含名人原话）

**Layer 2 · meta-supervisor**
- 隐性假设提取器 `assumption_extractor.py`：句式信号 + 跨角色共现聚类 + 启发式评分（候选级）
- 分歧分类器 `divergence_classifier.py`：事实 / 价值 / 术语 / 伪分歧的规则建议 + 与模型分类的一致性核对
- 谬误检测器 `fallacy_detector.py`：稻草人、循环论证、偷换概念、诉诸权威、以偏概全、假二分（候选级）
- 六段式 META REVIEW 输出规范 + 四项讨论质量评分口径 + 元反思注入（must_respond / must_resolve / forbidden）

**Layer 3 · position-evolution**
- 修正追踪器 `revision_tracker.py`：引用校验、三级幅度判定、`foundational` 自动降级、
  横跳识别、**无新证据的修正不改变立场基线**（compliance_drift）

**工程**
- `tools/validate_repo.py`：结构 / frontmatter / 章节 / 契约字段 / 禁用写法 / 脚本自检 六类一次性校验
- 7 个脚本全部通过 `--selftest`（`py -3 tools/validate_repo.py` 可复现）
- 所有脚本仅依赖标准库；语义判断交给模型，脚本输出一律带 `needs_judgment`

**未实现（P2/P3）**
- `decision-landscape`（决策景观报告）：交接字段已由 `state_manager.py summary --json` 预留
- 完整认知噪声模块（选择性注意、表达偏好）：仅实现 `epistemic_status` 三个轻量字段

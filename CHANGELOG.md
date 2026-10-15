# 变更日志

遵循语义化版本。字段与枚举的改动一律同步 `docs/output-contract.md` 并提升契约版本号。

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

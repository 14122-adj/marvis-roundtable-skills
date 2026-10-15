# 变更日志

遵循语义化版本。字段与枚举的改动一律同步 `docs/output-contract.md` 并提升契约版本号。

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

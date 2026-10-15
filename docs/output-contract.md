# 圆桌技能输出契约 v1.0（冻结版）

> 本文件是 9 个技能的**唯一契约来源**。任何 SKILL.md 中的字段名、枚举值、ID 规则都必须与本文件一致。
> 修改本文件 = 修改契约 = 必须同步全部角色技能。改动请在 CHANGELOG 中记录版本号。

---

## 0. 设计原则（先读这一节，再看字段）

1. **目标驱动，不锁形式**：轮次规定的是「本轮要达成什么认知目标」，不是「必须和谁说话、必须说几句」。
   交互形式由角色根据目标自行选择。禁止在技能里写「本轮必须一对一轮流」「必须联动 ≥2 人」这类硬约束。
2. **第一轮隔离**：唯一保留的形式约束，目的是防锚定（避免后发言者被先发言者带偏）。
3. **底层前提优先**：表层的观点冲突可以无限循环，隐性假设不解决就挖不到根本。元认知层的输出是**下一轮的强制输入**。
4. **允许修正，但反对从众**：立场可以改，前提是要有新证据/新论证；没有新信息就跟着多数走的修正被标记为 `compliance_drift`，不计入有效修正。
5. **诚实标注**：置信度、不确定性、信息缺口必须显式写出，宁可说「我不知道」也不允许为了发言完整而编造论据。

---

## 1. 讨论状态文件（state.json）

由 `roundtable-orchestrator/scripts/state_manager.py` 维护，路径默认 `./.roundtable/<session_id>/state.json`。

```jsonc
{
  "schema_version": "1.0",
  "session_id": "rt-20260601-101500-a1b2",
  "topic": "议题原文",
  "mode": "rigorous",                  // rigorous(严谨论证) | simulation(真人仿真)
  "round": 0,                          // 当前轮次，0 表示尚未开始
  "max_rounds": 3,
  "phase": "prepare",                  // prepare | opening | meta_1 | probing | meta_2 | synthesis | closed
  "roles": ["musk", "feynman", "munger", "jobs", "karpathy", "pg"],
  "interaction_mode": "parallel_isolated", // parallel_isolated | cross_exam
  "shared_premises": [],               // R0 由编排层显式列出、大家默认接受但未论证的前提（候选隐性假设）
  "positions": {
    "musk": {
      "stance_summary": "",
      "confidence": 70,
      "key_claims": [],                // claim id 列表
      "uncertainty_points": [],
      "will_revise_if": "",
      "blind_spot_declared": "",
      "revision_count": 0,
      "compliance_drift_count": 0
    }
  },
  "claims": [                          // 所有角色提出的论断，全局登记
    {
      "id": "M1-1",                    // 见 §3 ID 规则
      "role": "musk",
      "round": 1,
      "text": "……",
      "basis": "physical_constraint",  // 见 §3 basis 枚举
      "evidence": "……",
      "is_new_key_argument": true,     // 新增关键论据判定，由编排层写回
      "responses_received": []         // 收到的回应 id，如 ["P2-2", "H3"]
    }
  ],
  "open_challenges": [
    {
      "id": "C1",
      "from": "pg",
      "to": "musk",
      "target_claim": "M1-1",
      "question": "……",
      "status": "open"                 // open | answered | dropped | resolved_by_revision
    }
  ],
  "meta": {
    "reviews": [],                     // 每轮的元认知报告（见 §4）
    "hidden_assumptions": [            // 汇总后的隐性假设清单，跨轮去重
      {"id": "H1", "content": "……", "scope": "all", "first_seen_round": 1, "challenge_effect": "……", "status": "open"}
    ],
    "divergences": [
      {"id": "D1", "type": "fact", "topic": "……", "sides": {"musk": "……", "pg": "……"}, "resolution_path": "……", "status": "open"}
    ],
    "information_gaps": [
      {"id": "G1", "missing": "……", "would_flip": "……", "cost": "low", "status": "open"}
    ],
    "fallacies": [
      {"id": "F1", "type": "strawman", "role": "jobs", "quote": "……", "note": "……"}
    ]
  },
  "injections": [                      // 元认知注入给下一轮的强制输入
    {"round": 2, "must_respond": ["H1", "H3"], "must_resolve": ["C1"], "forbidden": ["继续争论X直到Y"], "note": "……"}
  ],
  "argument_log": [                    // 每轮新增关键论据计数，供收敛检测
    {"round": 1, "role": "musk", "claim_id": "M1-1", "is_new_key_argument": true}
  ],
  "revisions": [                       // 见 §5，由 position-evolution 写入
    {
      "id": "R1", "role": "pg", "round": 2, "level": "local",
      "trigger": "……", "from": "……", "to": "……", "reason": "……", "remaining_doubt": "……",
      "valid": true, "invalid_reason": null
    }
  ],
  "convergence": {
    "rounds_without_new_argument": 0,
    "root_cause_reached": false,
    "root_cause_note": "",
    "signals": [],
    "recommendation": "continue"       // continue | deepen | meta_intervene | close
  },
  "next_round": {
    "round": 1,
    "interaction_mode": "parallel_isolated",
    "goals": ["……"],
    "must_respond": [],
    "may_revise": true,
    "notes": ""
  }
}
```

**写回规则**：角色发言 → 编排层解析成 claims / open_challenges 写回；元认知报告 → 写回 `meta.*` 与 `injections`；修正记录 → 写回 `revisions` 并更新 `positions[role]` 基线。

---

## 2. 轮次目标（goal-driven）

| 阶段 | 轮次 | 本轮唯一目标 | 交互模式 | 交付物 |
|------|------|--------------|----------|--------|
| prepare | R0 | 定义议题边界、成功判据，并**显式列出大家默认接受但未论证的前提** | — | `shared_premises`、`next_round.goals` |
| opening | R1 | 充分亮出各自判断、论据、**认知边界** | `parallel_isolated`（防锚定） | 每个角色 2–4 条 claim + epistemic_status |
| meta_1 | R1.5 | 扫描 R1，挖隐性假设、判分歧类型、标信息缺口 | 独立运行 | META 报告 + 注入指令 |
| probing | R2 | 探究对方论据中存疑的**前提 / 证据 / 边界条件**；必须回应 ≥1 条注入的隐性假设 | `cross_exam`（自主选择追问对象，1 人或多人都可） | responses + 可选 revision |
| meta_2 | R2.5 | 第二轮扫描 + 收敛检测 | 独立运行 | META 报告 + `convergence.recommendation` |
| synthesis | R3 | 整合视角，识别**矛盾根源**，判断哪些分歧不可调和 | `cross_exam` | 待交接给 decision-landscape 的字段 |

**明确禁止的写法**（豆包方案已论证过的失真点）：

- ❌ 「第二轮必须一对一轮流」「第三轮必须联动 ≥2 人」
- ❌ 「每段发言不超过 N 字」这类形式约束
- ✅ 换成：「本轮目标是 X；你可以追问 1 人也可以追问多人，也可以只补充自己的证据」

**终止条件**（满足其一即可）：

1. `round >= max_rounds`；
2. 收敛检测：连续 2 轮无新增关键论据，且已识别出至少 1 条根本矛盾；
3. 元认知判定当前分歧为「伪分歧 / 术语分歧」，继续讨论无增量 → 提前关闭并说明原因。

---

## 3. 角色发言输出契约（Layer 1 通用）

每个角色每次发言**必须**输出以下结构的 YAML 块（块外用自然语言展开论述，块内保证机器可解析）：

```yaml
role: musk
round: 2
position: 一句话立场（本轮基线，若已修正则为修正后立场）

claims:
  - id: M2-1
    text: 论断正文
    basis: physical_constraint     # 枚举见下
    evidence: 证据 / 推理链 / 案例来源
    falsifiable_by: 什么观察能推翻它（没有则写 unknown）

responses:
  - to: P1-2                       # 对方 claim id，或 H1 / D1 / G1（元认知条目）
    type: challenge                # support | challenge | refine | adopt | ignore_with_reason
    text: 回应内容

blind_spot_declared: 我这个视角天然看不见什么（必填，禁止写「没有」）

epistemic_status:
  confidence: 65                   # 0-100，整数
  uncertainty_points: []           # 至少 1 条，写不出来说明还没想清楚
  will_revise_if: 在什么条件下愿意修正
```

**ID 规则**：`<角色首字母大写><轮次>-<序号>`，例如 `M2-1`（musk 第 2 轮第 1 条）、`P1-3`（pg 第 1 轮第 3 条）、`K2-2`（karpathy）。费曼=F、芒格=G、乔布斯=J、马斯克=M、Karpathy=K、Paul Graham=P。
轮内序号从 1 连续递增，不得跳号、不得复用。

**basis 枚举**（必须选一个，用于元认知分类）：

| 值 | 含义 |
|----|------|
| `physical_constraint` | 物理/数学/资源约束，不能靠意愿改变 |
| `empirical` | 实测数据、公开统计、可复现实验 |
| `case` | 具体案例（此时 `evidence` 必须写清案例来源） |
| `mechanism` | 机制推演（为什么这样会那样） |
| `analogy` | 类比推理（**必须**同时写出类比在何处失效） |
| `value_judgment` | 价值判断（标注后不得再用逻辑论证伪装成事实） |
| `intuition` | 直觉（必须降低 confidence） |

**修正记录**（可选字段，出现即代表立场变化，规则见 §5）：

```yaml
revision:
  trigger: 受到了谁/什么信息的触发（须引用 claim id 或 H/G 编号）
  level: local                     # micro | local | foundational
  from: 原立场摘要
  to: 新立场摘要
  reason: 修正理由
  remaining_doubt: 修正后仍不确定的地方
```

`trigger` 的引用对象：claim id（如 `M1-1`）或元认知条目 `H`/`D`/`G`/`F`/`C` 编号。
`position-evolution/scripts/revision_tracker.py` 接受这五类编号，其中 `H`/`G` 是最常见的形式。

---

## 4. 元认知报告契约（Layer 2）

`meta-supervisor` 每轮独立运行，输出**固定六段**，同时写成结构化 JSON 交回编排层：

```markdown
[META REVIEW — Round N]

A. 隐性假设
[H1] 内容：……
     涉及角色：全部 | 多数 | 特定角色(musk, jobs)
     若被挑战，讨论走向可能变化：……
     证伪成本：low | medium | high
     建议问法：……（一句话，可直接放进下一轮）

B. 分歧类型
[D1] 议题：……
     类型：事实 | 价值 | 术语 | 伪分歧
     各方立场：musk=…… / pg=……
     判定依据：……
     消解路径：需要什么证据（事实）| 承认不可调和（价值）| 统一术语定义（术语）| 指出表述差异（伪分歧）

C. 信息缺口
[G1] 缺失信息：……
     补上后可能翻转的判断：……
     获取成本：low | medium | high

D. 逻辑谬误
[F1] 类型：稻草人 | 循环论证 | 偷换概念 | 诉诸权威 | 以偏概全 | 假二分
     出处：角色 + 原文片段
     修正建议：……

E. 讨论质量
     论据密度：0-100（有效论据数 / 发言量）
     前提触及度：0-100（是否触及共享前提，而非只在表层吵架）
     回应率：0-100（质疑被实际回应的比例）
     循环度：0-100（重复观点占比，越高说明在原地打转）
     一句话诊断：……

F. 注入指令（下一轮强制输入）
     must_respond: [H1, H3]
     must_resolve: [C1]
     forbidden: ["继续在X上争论直到Y"]
```

**纪律**：元认知角色**不站队**、不提出自己的议题立场、不评价角色人格，只评价论证质量。允许多次自我修正（若上一轮标记的隐性假设被证明不成立，下一轮须显式撤回）。

---

## 5. 立场演化契约（Layer 3）

**允许修正的触发条件**（至少满足一条，且必须能被引用）：

1. 收到此前未考虑过的**事实证据**（新 claim 或 G 编号）；
2. 对方提出了本角色思维协议**无法反驳**的论证；
3. 元认知标记了某条隐性假设，角色认可它确实值得质疑；
4. 发现自己的论据属于 `analogy` 且类比已失效。

**修正幅度分级**：`micro`（保留核心立场，调整论据/边界条件）｜`local`（某个子问题上改变立场）｜`foundational`（承认初始前提有问题；罕见，必须给出为什么初始前提错了，而不是「为了达成共识」）。

**有效性判定**（由 `position-evolution/scripts/revision_tracker.py` 执行）：

| 判定 | 条件 | 结果 |
|------|------|------|
| 有效修正 | 引用了新的 claim id / G 编号 / 元认知条目，且 `reason` 说明推理如何变化 | `valid: true` |
| 从众漂移 | 无新信息，仅因「多数人这样认为」「为推进讨论」而修正 | `valid: false`, `compliance_drift` 计数 +1 |
| 反复横跳 | 同一议题上修正 ≥3 次 | 标记 `unstable`，提示元认知介入 |
| 底层修正 | `foundational` 级修正 | 强制要求写出「初始前提错在哪」，否则降级为 `local` |

**接口**：编排层在每轮开始前读取 `revisions`，把修正后的 `to` 字段作为该角色本轮 `position` 的新基线。修正不删除历史，`from` 永远保留在记录里。

---

## 6. 交接字段（预留 Layer 4 `decision-landscape`）

讨论结束时，编排层必须整理出可供聚合层直接消费的中间产物：

```jsonc
{
  "consensus_candidates": [{"text": "……", "supporters": ["musk","jobs"], "strength": "unanimous|majority|weak"}],
  "divergence_map": ["D1", "D2"],
  "hidden_assumption_list": ["H1", "H2"],
  "information_gaps": ["G1"],
  "minority_views": [{"role": "pg", "claim_id": "P3-1", "text": "……", "refuted": false}],
  "confidence_weighted_advice": [{"text": "……", "confidence": "high|medium|needs_info"}]
}
```

`minority_views` 中 `refuted: false` 的条目**必须**在最终报告里完整保留论证——少数派观点只要没被有效反驳，就不允许被多数票淹没。

---

## 7. 脚本与模型的职责边界（诚实声明）

`scripts/` 下的 Python 只做**结构化工件**：解析、登记、去重、计数、规则扫描、生成提示片段。
**语义判断（什么叫「隐性假设」、什么算「不可调和」）由模型完成**，脚本不得伪装成能自动判定语义。

因此各脚本的输出一律使用 `candidates` / `signals` 这类措辞，并附带 `needs_judgment: true` 字段，交由模型或人工复核。

所有脚本：

- 仅依赖 Python 标准库；
- 支持 `--selftest` 自检（退出码 0 = 通过）；
- 以 JSON 输出到 stdout，日志走 stderr。

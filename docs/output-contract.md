# 圆桌技能输出契约 v1.5.0（冻结版）

> 本文件是 14 个技能的**唯一契约来源**。任何 SKILL.md 中的字段名、枚举值、ID 规则都必须与本文件一致。
> 修改本文件 = 修改契约 = 必须同步全部角色技能。改动请在 CHANGELOG 中记录版本号。
>
> v1.1 变更：新增 §8 决策景观契约（Layer 4）、§9 认知噪声附加契约（Layer 5，可选）、
> §10 异构基座调用包契约（Layer 6，可选）；§1 的 `meta_engagement` 与 `attention_manifests` 转正。
>
> v1.2 变更：新增 §11 终极圆桌契约（`ultimate-roundtable`，四阶段 + 火花判据 + 存活率模型）。
>
> v1.3 变更：§11 升级到 **V3.0**（阶段零记忆唤醒、工具调用闭环、交叉验真、沙盘工具验证、
> 记忆沉淀），新增 §12 跨宿主适配契约（`host-bootstrap`）。
>
> v1.4 变更：§11 升级到 **V4.0**（北极星锚定、注意力分舱 + 150 字闸门、死锁熔断、
> 三选一铁血裁决、战术级行动清单），报告格式改为 V4 五节。
>
> v1.5 变更：§11.5b 第 3 条重写为**语义级死锁检测**（REPEAT/PROGRESS/UNCERTAIN 三标签 +
> 双路径熔断），熔断话术更新为「双方已陷入实质重复」。
> `ultimate-roundtable` v4.1.0 与 `host-bootstrap` v3.0.0 按上游 spec 独立发版，不参与统一版本对齐。

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
  "meta_engagement": [                 // 角色对元认知条目（H/D/G/F/C）的正面回应
    {"meta_id": "H1", "from": "pg", "round": 2, "type": "adopt", "text": "……"}
  ],
  "attention_manifests": [],           // 可选，见 §9：仅在 mode=simulation 下由 cognitive-noise 写入
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

## 6. 交接字段（`decision-landscape` 的输入）

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

> 该结构由 `state_manager.py summary --json` 产出；`decision-landscape` 的 `synthesis_generator.py build`
> 在此基础上直接读状态文件做完整聚合（见 §8），两者字段保持兼容。

---

## 7. 脚本与模型的职责边界（诚实声明）

`scripts/` 下的 Python 只做**结构化工件**：解析、登记、去重、计数、规则扫描、生成提示片段。
**语义判断（什么叫「隐性假设」、什么算「不可调和」）由模型完成**，脚本不得伪装成能自动判定语义。

因此各脚本的输出一律使用 `candidates` / `signals` 这类措辞，并附带 `needs_judgment: true` 字段，交由模型或人工复核。

所有脚本：

- 仅依赖 Python 标准库；
- 支持 `--selftest` 自检（退出码 0 = 通过）；
- 以 JSON 输出到 stdout，日志走 stderr；
- 共 10 个：`state_manager` / `round_controller` / `convergence_detector`（Layer 0）、
  `assumption_extractor` / `divergence_classifier` / `fallacy_detector`（Layer 2）、
  `revision_tracker`（Layer 3）、`synthesis_generator`（Layer 4）、
  `noise_injector`（Layer 5）、`runtime_manifest`（Layer 6）。

---

## 8. 决策景观契约（Layer 4 `decision-landscape`）

`decision-landscape` 的 `synthesis_generator.py build` 读取 §1 的状态文件，输出**分区**报告
（不按轮次拼接发言）。报告 HTML 级标题固定为六个板块，顺序不可调换：

```
## 一、共识区（候选，需复核）
## 二、分歧区
## 三、隐性假设清单
## 四、决策建议（按置信度分级）
## 五、信息缺口清单
## 六、少数派观点保护
## 附录 A · 未被检验的主张
```

机器可读结构（`--json` 输出，字段名固定）：

```jsonc
{
  "schema_version": "1.1", "generated_at": "…", "needs_judgment": true,
  "topic": "…", "session_id": "…", "mode": "rigorous", "rounds_completed": 2,
  "phase": "closed", "min_support": 2, "roles": ["musk", "…"],
  "consensus": [{"claim_id": "M1-1", "text": "…", "basis": "…",
                 "supporters_raw": ["pg","jobs"], "supporters_effective": ["pg"],
                 "excluded_by_drift": ["jobs"], "strength": "unanimous|majority|weak",
                 "counts_toward_consensus": true, "needs_judgment": true}],
  "divergences": [{"id": "D1", "type": "fact|value|term|pseudo|unclear",
                   "topic": "…", "sides": {"musk": "…"}, "resolution_path": "…",
                   "related_gap": "G1|null", "needs_gap": true, "status": "open"}],
  "divergence_by_type": {"fact": ["D1"]},
  "hidden_assumptions": [{"id": "H1", "content": "…", "scope": "…", "status": "open",
                          "responded_by": ["pg"], "response_types": ["adopt"],
                          "challenge_effect": "…", "suggested_question": "…"}],
  "unregistered_shared_premises": ["…"],
  "advice": [{"role": "musk", "text": "…", "confidence": "high|medium|needs_info|unknown",
              "confidence_raw": 70, "will_revise_if": "…", "revision_count": 1,
              "compliance_drift_count": 0,
              "evolution": [{"id": "R1", "from": "…", "to": "…", "trigger": "…"}]}],
  "information_gaps": [{"id": "G1", "missing": "…", "would_flip": "…", "cost": "low"}],
  "minority_views": [{"role": "pg", "claim_id": "P3-1", "text": "…", "evidence": "…",
                      "falsifiable_by": "…", "challenges": [{"from": "musk", "text": "…"}],
                      "refuted": false, "protection": "…"}],
  "untested_claims": [{"claim_id": "J1-1", "role": "jobs", "text": "…"}],
  "convergence": {}, "quality_reviews": [], "roles_without_claims": []
}
```

**共识强度口径**（必须先剔除漂移者再分档）：

| strength | 条件 |
|---|---|
| `unanimous` | 有效支持者数 ≥ 在册角色数 |
| `majority` | 有效支持者数 ≥ `--min-support`（默认 2） |
| `weak` | 有效支持者数 < `--min-support`：仅供观察，不计入共识区 |

「有效支持」= 明确写了 `support`/`adopt` 的角色，且该角色 `compliance_drift_count == 0`。

**禁止断言**：报告文本中不得出现 `已达成共识`、`已验证`、`已挖到根本`、`已确认根因`、`结论已确定`。
脚本在渲染时检测这些字符串并直接报错退出（退出码 3），避免"报告很好看但没有依据"。

`check` 子命令的完整性检查字段：

```jsonc
{"minority_preserved": true, "minority_count": 2,
 "weak_consensus": ["M1-3"], "drift_roles": ["jobs"], "consensus_suspect": false,
 "gaps_missing_for_fact_divergence": ["D1"], "untested_claims": 7,
 "warnings": ["…"], "verdict": "pass_with_review|needs_attention"}
```

`consensus_suspect` 为真时（≥3 个角色发生从众漂移），报告必须显式写出"当前共识可能是假共识"。

---

## 9. 认知噪声附加契约（Layer 5 `cognitive-noise`，可选）

**开关条件**：仅 `mode == "simulation"` 可用。`mode == "rigorous"` 时 `noise_injector.py plan`
直接以退出码 3 拒绝并输出 `{"mode_ok": false, ...}`——这是脚本级强制，不只是文档纪律。

状态文件新增（可选字段，仅该层写入）：

```jsonc
"attention_manifests": [
  {
    "id": "AM1", "role": "pg", "round": 2, "seed": 7, "attention_ratio": 0.6,
    "noticed": ["M1-1", "H1"],            // 本轮可见的条目 id
    "ignored": ["F1-1", "K1-1"],          // 本轮不可见，必须如实承认"没注意到"
    "style_profile": "conclusion_first",  // conclusion_first|concern_first|conservative|adventurous
    "tone_rules": ["…"], "created_at": "…"
  }
]
```

红线（由 `noise_injector.py check` 校验，违反即 `verdict: "reject"`）：

1. `noticed` / `ignored` **只能是 id 字符串**——写入任何文本内容即视为"改写原文"，判定违规；
2. 两个列表不得重叠，引用的 id 必须真实存在于状态中；
3. 编排层注入的 `must_respond` / `must_resolve` **不受注意力筛选影响**：若被选入 `ignored`，
   脚本会把它拉回 `noticed` 并给出告警；
4. 被忽略的质疑若被追问，角色必须承认"本轮没有注意到"，不得假装已回应。

`plan` 输出字段：`role`、`round`、`seed`、`attention_ratio`、`history_total`、`noticed`、
`ignored`、`style_profile`、`confidence_raw`、`tone_rules`、`warnings`、`note`。
**本层会降低严谨性**：它不提升讨论质量，只换取真人质感；决策选型与对外交付场景应保持关闭。

---

## 10. 异构基座调用包契约（Layer 6 `multi-model-adapter`，可选）

`runtime_manifest.py emit` 为每个角色生成一个**调用包** `roles/<role>.task.json`：

```jsonc
{
  "schema_version": "1.1", "role": "musk", "round": 2,
  "phase": "probing", "interaction_mode": "cross_exam", "isolation": false,
  "goals": ["…"], "must_respond": ["H1"], "forbidden": ["…"], "may_revise": true,
  "provider": "unspecified", "model": "unspecified",
  "contract_summary": {"fields": ["role","round","position","claims","responses",
                                  "blind_spot_declared","epistemic_status","confidence",
                                  "uncertainty_points","will_revise_if"],
                       "id_prefix": "M", "id_pattern": "M2-<序号>",
                       "basis_enum": ["physical_constraint","empirical","case","mechanism",
                                      "analogy","value_judgment","intuition"],
                       "response_types": ["support","challenge","refine","adopt","ignore_with_reason"]},
  "payload_schema": {"…": "本轮结果的 JSON Schema 约束（含 ID 正则）"},
  "prompt_skeleton": "…", "result_file": "roles/musk.result.json"
}
```

`manifest.json` 记录 `provider_assignment`（角色 → provider/model）、`strategy`
（`single_host` / `round_robin` / `explicit`）、`isolation_required`、`bundle_sha256`（每角色调用包哈希）与
`unspecified` 诚实标注。

**`unspecified` 纪律**：未在 assignment 中指定的角色，`provider` 与 `model` 一律写 `"unspecified"`，
**禁止**填入任何猜测或"常见默认值"的模型名——伪造模型标识会让整场讨论的复现记录变成假的。

`merge` 的错误码（固定枚举）：

| 错误码 | 含义 |
|---|---|
| `ID_PREFIX_MISMATCH` | claim id 形如 `PG2-1` 或前缀与角色不符 |
| `ROUND_MISMATCH` | payload 轮次或 id 内轮次与任务包不一致 |
| `BASIS_INVALID` | `basis` 不在枚举内，或 `responses.type` 不在允许集合内 |
| `DUPLICATE_ID` | 与本批或既有状态中的 claim id 重复 |
| `MISSING_FIELD` | 缺少 `text` / `to` / `type`，或 `claims` 与 `responses` 同时为空 |
| `UNKNOWN_ROLE` | 文件名角色与 `payload.role` 不一致 |
| `MISSING_ROLE` | 该角色未提交结果（写入 `missing_roles`，不得静默跳过） |
| `INVALID_JSON` | 结果文件不是合法 JSON |

合并输出：`accepted` / `rejected[{role, errors, warnings}]` / `missing_roles` / `merge_errors`。
存在任何 `rejected` 或 `merge_errors` 时退出码为 1。合并之后**必须**再跑一次
`convergence_detector.py check`——跨模型结果同样需要收敛判定，模型不同不等于结论更对。

---

## 11. 终极圆桌契约（`ultimate-roundtable` v4.0.0）

高强度决策压缩流程：**摊牌 → 对抗 → 沙盘 → 降维打击**。
它与 §1–§10 的圆桌状态文件**并存但独立**（有自己的 `state.json` 结构），
两者通过 `roundtable-orchestrator` 的交接块衔接。

### 11.1 阶段与退出码

| 阶段 | 命令 | 必须产出 | 失败退出码 |
|---|---|---|---|
| init | `init --topic` | `state.json` | 2 |
| 零 | `stage0` | 加载历史记忆 + 输出开场白 | 3 |
| 一 | `stage1 --file roles.json` | 6 条 `[数据诉求]` + `[Tool Call]` + 表态句 + `tool_result` | 3 |
| 二 | `stage2 --file clash.json` | 3v3 分营 + 内心戏 + `[打断并验真]`结果 + 火花检测通过 | 3（校验）/ **4（无火花，强制重开）** |
| 三 | `stage3 --file sandbox.json` | ≥3 月度节点 + risks/assumptions/attacks + action_plan + **≥1 条 `tool_calls`** | 3 |
| 四 | `stage4 --file meta.json` | 共同隐性假设 + 被证伪前提 + ≤200 字记忆 + **写入记忆库** | 3 |
| 报告 | `report --state --out` | 冻结五节报告（V3 格式） | 3 |

阶段之间有硬顺序：跳过前一阶段一律退出码 3。

### 11.1b V3 新增的三条硬约束

1. **阶段零记忆唤醒**：`stage0` 读取历史 `[MEMORY_UPDATE]`，输出固定格式开场白
   `[会议启动] 已加载历史记忆：…`；无历史时写明"无记忆记录"。重复执行只更新、不重复登记。
2. **工具调用闭环**（阶段一）：每条发言必须同时具备三要素，缺一即整体拒绝：
   - `[数据诉求: …]`
   - `[Tool Call: Search|Code] …`
   - `基于(此|该|这)(数据|结果|查证)` 表态句
3. **交叉验真**（阶段二）：`[打断并验真]` 必须给出 `[Tool Call]` 或 `verify_result`，
   否则阶段二拒绝。`verdict ∈ {supported, refuted, inconclusive}`。

沙盘（阶段三）另需 ≥1 条 `tool_calls`，每条含 `kind`（Search/Code）、`purpose`、`result`，
`Code` 类型还必须有 `code` 字段，且遵守真实/模拟标注。

### 11.2 数据诚实性（强制）

阶段一每条 `tool_result` 必须二选一：

```jsonc
{"source": "tool", "tool": "web_search", "query": "...", "result": "...", "obtained_at": "..."}  // 真实调用
{"source": "text", "simulated": true, "tool": "...", "query": "...", "result": "..."}            // 明确模拟
```

| 情形 | 判定 |
|---|---|
| `source: tool` 且 `simulated: true` | 标注矛盾 → 拒绝 |
| 既非 `tool` 也未标 `simulated: true` | **把模拟数据伪装成真实数据** → 拒绝 |
| 报告头部 | 必须打印「阶段一 真实 N / 模拟 M；沙盘 真实 X / 模拟 Y」 |

### 11.3 火花判据（禁止和稀泥的可执行版本）

`clash_analyzer.py spark` 的六个计数，任一不达标即 `sparked: false` → 退出码 4：

| 字段 | 含义 | 默认阈值 |
|---|---|---|
| `attack_count` | 蓝军有效攻击（有靶点 + 有内容） | ≥ 3 |
| `defense_count` | 红军有效防御/修补 | ≥ 2 |
| `target_spread` | 被攻击的不同 claim 数 | ≥ 2 |
| `signal_total` | 攻击+防御+立场修正+新论据 | ≥ 3 |
| `hollow_ratio` | 空洞发言占比（"我觉得挺好的""各有优劣"） | ≤ 0.34 |
| `unmet_must_respond` | 未回应的元认知强制条目 | 必须为空 |

阈值可在 `state.clash_thresholds` 覆盖；**不允许调到 0**（等于关掉这条规则）。

### 11.4 存活率模型（算术，可手算复现）

```
survival = 0.40 × risk_residual      # 100 × (1 − 平均(severity × probability))；无风险记 0
         + 0.25 × evidence_coverage  # 有关键假设中带 evidence 的比例
         + 0.20 × defense_quality    # attacks 中 defended=true 的比例
         + 0.15 × plan_integrity     # Do/Don't/NeedInfo 三栏填充率
```

`≥70 high`｜`40–69 medium`｜`<40 low`。`band=low` 时**不得直接交付**，
必须先补 `Need Info` 或改设计。

### 11.5 报告格式（V4.0 冻结）

```markdown
### ⚔️ 终极圆桌决策报告 V4.0
#### 📌 1. 北极星指标与底线假设
#### 🔗 2. 证据链与外部验证
#### 🚦 3. 铁血裁决（三选一）      ← A/B/C + 投票支持 + 拍板结论
#### 🎯 4. 战术级行动清单         ← 负责人 / Start / KPI / Kill / Need Info
#### 🧠 5. 长期记忆写入           ← [MEMORY_UPDATE]，≤200 字
```

出现下列任一情况时 `report` 直接报错（退出码 3）：
缺北极星指标；缺拍板结论（A/B/C）；战术清单缺 `owner`/`start`/`kpi`/`kill`；
`kpi` 或 `kill` 不含数字；缺长期记忆；记忆超 200 字；
文本中出现禁止措辞 `已达成共识` / `已验证` / `已挖到根本` / `结论已确定` /
`我觉得挺好的` / `各有优劣` / `见仁见智` / `综合考虑吧`，
或**咨询体** `一方面` / `另一方面` / `视具体情况而定` / `综合考虑` /
`权衡利弊` / `大概` / `也许` / `或许` / `酌情` / `看情况` / `建议进一步`。

### 11.5b V4 新增的三条硬约束

1. **北极星锚定**（阶段零）：`stage0` 必须传 `north_star`，缺失直接拒绝（退出码 3）；
   阶段一每条发言必须出现该指标字样，否则判为无效发言。
2. **注意力分舱 + 150 字闸门**（阶段一）：
   - 发言去标点计数 > 150 → 拒绝；
   - 六份分舱声明写入 `attention_splits`，每份只含 `visible`/`muted` 的 **id**，
     出现任何文本内容即判"改写原文"违规；
   - 北极星相关条目与 `must_respond`/`must_resolve` **永不被屏蔽**。
3. **语义级死锁检测**（阶段二，V4.1）：
   - 主持人**每轮结束在内心完成判定**（不输出过程），对比本轮与上一轮发言；
   - 判定标准：只是换说法/同义词/换例子，但**核心论点、支撑数据、推导逻辑**未变 → 语义复读；
   - 三标签写回 `semantic_verdicts`：`REPEAT` / `PROGRESS` / `UNCERTAIN`；
   - **放行规则**：本轮有 `PROGRESS`（新证据 / 改观点 / 针对性反驳 / 反问 / 要数据）→ 放行；
   - **熔断规则**：`REPEAT > 0 且 PROGRESS == 0` 连续 2 轮 → 熔断；
   - **结构兜底**：无语义判定时退回「相似度 ≥0.55 + 无新事实 + 无立场修正 + 靶点未变」；
   - 熔断话术固定为 `[系统强制熔断] 双方已陷入实质重复，此议题直接交由最终裁决阶段处理。`
     并置 `debate_closed = true`；此后任何 `stage2` 提交一律拒绝（退出码 3），只能进入阶段三。

   `semantic_verdicts` 字段：

   ```jsonc
   [{"round": 3, "from": "munger", "to": "munger", "label": "REPEAT",
     "reason": "换了说法，核心论点仍是切换成本被低估",
     "pair_id": "2->3#1", "judged_by": "host-judge"}]
   ```

   `check` 输出的 `trigger` 标明命中路径（`semantic` / `structural`），
   `semantic_coverage` 给出被判定的配对数——**每条判定都必须带 `reason`，否则无法复核**。

   CLI 三件套：`judge`（生成待判材料）→ `record`（写回标签）→ `check --write`（判定并熔断）。
   `stage2` 也支持直接携带 `semantic_verdicts` 数组，一次提交完成「对抗 + 语义判定」。

### 11.5c 三选一裁决（阶段三）

```jsonc
{
  "options": {
    "A": {"summary": "全量改为季度评审，三个月内切换完毕"},
    "B": {"summary": "维持年度评审，只把材料准备流程精简一半"},
    "C": {"summary": "取消固定评审，改为触发式评审：月活跌破阈值才开"}
  },
  "votes": {"musk":"A","feynman":"C","munger":"B","jobs":"C","karpathy":"C","pg":"B"},
  "vote_reasons": {"musk":"…", "…": "…"},
  "decision": "C",
  "decision_reason": "C 拿 3 票且判据可观测；A 的下行风险未被防住"
}
```

校验：A/B/C 三个方案必须齐全且 `summary` 互不相同（换皮拒绝）；六人必须全部投票且
每人给出 `vote_reasons`；票只能投给 A/B/C；`decision` 必须是 A/B/C 之一。
若 `decision` 与票数最高方案不一致，输出告警（需记录否决理由）。

### 11.5d 战术级行动清单（阶段四）

```jsonc
{
  "action_plan": {
    "owner": "karpathy",                        // 必须是六人之一，或标注的召唤角色
    "start": "本周在 2 个团队上线触发式评审，阈值设为月活跌破 8%",
    "kpi": "30 天内触发不超过 5 次，月活不低于 9%",   // 必须含数字
    "kill": "如果 30 天内触发超过 12 次，立刻停止并回滚到年度评审",  // 必须含数字
    "need_info": ["过去两年每次评审的平均参与人时"]     // 至少一条
  }
}
```

`kpi` / `kill` 不含数字 → 拒绝；含"大概/也许/酌情/视情况/建议进一步" → 拒绝。

### 11.6 状态字段（V4.0）

```jsonc
{
  "schema_version": "4.0.0", "session_id": "ur-20261101-012900",
  "topic": "…", "stage": "stage4_done", "north_star": "月活",
  "stages_done": ["stage0","stage1","stage2","stage3","stage4"],
  "roles": ["musk","feynman","munger","jobs","karpathy","pg"],
  "stage0": {"memory_loaded": [{"id":"M…","text":"…"}], "opening_line":"[会议启动] …",
             "store":"…", "memory_count":1, "north_star":"月活", "loaded_at":"…"},
  "stage1": {"confessions": [], "data_demands": [{"role":"musk","demand":"…"}],
             "tool_results": [{"role":"musk","source":"tool","simulated":false,
                               "tool_calls":[{"kind":"Search","detail":"…"}],
                               "closure_ok":true,"result":"…"}],
             "low_confidence": [{"role":"jobs","reason":"缺少工具闭环"}]},
  "attention_splits": [{"role":"musk","round":1,"lens":"物理与成本","north_star":"月活",
                        "visible":["M1-1"],"muted":["F1-1","J1-1"],
                        "visible_ratio":0.17,"speech_limit":150}],
  "fused": false, "debate_closed": false,
  "stage2": {"exchanges": [{"from":"munger","camp":"blue","inner_thought":"…",
                            "interrupt":true,"verify":true,"target_claim":"M1-1","text":"…"}],
             "camps": {"blue":["…"],"red":["…"]}, "spark": {},
             "verifications": [{"from":"pg","target_claim":"K1-1","result":"…",
                                "simulated":true,"verdict":"refuted"}],
             "deadlock": {"deadlock":false,"consecutive_stalled":0}},
  "stage3": {"options": {"A":{},"B":{},"C":{}}, "votes": {"musk":"A"},
             "vote_reasons": {"musk":"…"}, "tally": {"A":["musk"],"B":[],"C":[]},
             "decision": "C", "decision_reason": "…",
             "sandbox": {"plan":"…","timeline":[],"tool_calls":[],
                         "evaluation":{"survival_rate":52,"band":"medium"}},
             "summons": [{"role":"法务专家","reason":"…","statement":"…"}]},
  "stage4": {"meta": {"shared_hidden_assumption":"…","assumption_broken":["…"],
                      "ignored_dimension":"…"},
             "action_plan": {"owner":"karpathy","start":"…","kpi":"…","kill":"…",
                             "need_info":["…"]},
             "memory": "≤200 字", "memory_written": true,
             "memory_entry": {"id":"M20261101121635","chars":48}},
  "camps": {}, "clash_exchanges": [], "sandbox": {}, "clash_spark": {}
}
```

`stage2` 与顶层的 `camps` / `clash_exchanges` 保持同步，因为 `clash_analyzer.py`
读的是顶层字段（便于单独调用）；沙盘（`sandbox` 子命令）写入 `stage3.sandbox`，
**不覆盖**三选一裁决结果。

### 11.7 新增脚本（V4 / V4.1）

| 脚本 | 作用 | 关键纪律 |
|---|---|---|
| `attention_split.py` | 分舱声明生成、150 字闸门、违规校验 | 只记录 id，绝不改写原文；北极星与强制条目永不屏蔽 |
| `deadlock_detector.py` | **语义级**复读判定、双路径死锁、强制熔断 | 语义路径优先（REPEAT 且无 PROGRESS），结构路径兜底；每条判定必须带 `reason`；熔断后 `debate_closed=true` |

`deadlock_detector.py` 的四个子命令：

| 子命令 | 作用 | 说明 |
|---|---|---|
| `judge` | 生成待判材料 | 按"上一轮 vs 本轮"配对，附判定标准；支持 `--pair 2-3` |
| `record` | 写回语义判定 | 标签归一化（`[repeat]` → `REPEAT`），非法标签拒绝 |
| `check` | 双路径判定 | `trigger` 标明 `semantic`/`structural`；`--write` 自动熔断 |
| `fuse` | 手动熔断 | 用于主持人主动止损 |

---

## 12. 跨宿主适配契约（`host-bootstrap` v3.0.0）

这套技能原本为马维斯编写。换到 Claude Code / Codex / Hermes / Cursor / 纯文本宿主时，
**六个角色技能不一定存在**。`host-bootstrap` 负责检测与补齐，并规定降级行为。

### 12.1 三个命令与退出码

| 命令 | 作用 | 退出码 |
|---|---|---|
| `bootstrap.py detect` | 判断宿主、技能目录、六个角色技能是否就绪 | 0 就绪 / 1 需安装 |
| `bootstrap.py install` | 本地复制 → git clone → HTTP 下载 → 打印手工步骤（四级回退） | 0 成功 / 1 需人工 |
| `bootstrap.py verify` | 逐字段校验（installed / frontmatter_ok / name_ok / missing_files） | 0 全就绪 / 1 有缺失 |

`install` 支持 `--dry-run`（只预演不写盘）与 `--source auto|local|github`。
**幂等**：已就绪的技能不会被重复覆盖。

### 12.2 角色技能就绪的判定

一个角色技能只有四项全过才算 `ready`：

```jsonc
{"installed": true,                 // SKILL.md 存在
 "frontmatter_ok": true,            // frontmatter 含 description:
 "name_ok": true,                   // name: 与目录名一致
 "missing_files": []}               // references/ 下的手册齐全
```

任一不过即进入 `missing`，`install` 会重新补齐（含 references，不只 SKILL.md）。

### 12.3 降级契约（必须声明）

角色技能缺失时**不得假装完整协议已生效**。降级时必须在输出中写明：

```
⚠ 降级模式：role-* 技能未安装，角色协议为摘要级
```

工具能力缺失时（纯文本宿主）：

- `[Tool Call]` 照写，但所有结果标 `simulated: true`；
- 报告头部如实显示「真实 0 条 / 模拟 N 条」；
- 依赖模拟数据的结论必须进入 `Need Info`。

### 12.4 宿主的接入文件

| 文件 | 面向宿主 | 约定 |
|---|---|---|
| `AGENTS.md` | Codex / Hermes / Cursor / Cline / Windsurf | 通用入口：入口表、纪律、目录导航、常用命令 |
| `CLAUDE.md` | Claude Code / Claude | 与 AGENTS 等价，强调"先读契约再动手" |
| `skills/*/SKILL.md` | 所有支持 Agent Skills 的宿主 | 单个技能的自描述，不含宿主特定路径 |

**技能之间不使用跨目录相对引用**，因此可以单独复制到任意宿主的技能目录。

### 12.5 诚实边界

- `install` **不修改**宿主配置文件，**不重启**宿主；
- 找不到马维斯的技能目录时**不猜测**，如实报告"未检测到"；
- 无网络且无 git 时打印 curl/ZIP 手工步骤并返回非零，不假装成功。

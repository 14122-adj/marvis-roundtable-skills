# 一次完整讨论的实录（示例数据）

> **声明**：本文所有对话内容均为**虚构示例数据**，用于演示机制如何运转，不代表任何真实调研结论。
> 议题刻意选了豆包方案里举过的那类例子——"科创竞赛资源怎么分"，因为它的根因恰好藏在一句所有人都默认的话里。
>
> 全部数据由 `python tools/demo_session.py` 一次性生成，可复现（见文末）。

## 目录

1. R0 建立会话与共享前提
2. R1 六角色隔离立论
3. R1.5 元认知扫描与强制注入
4. R2 自由交叉：一次有效修正 + 一次从众漂移
5. R2.5 二次扫描、覆盖度与收敛判定
6. 交接摘要原文
7. 这个例子暴露了什么（含脚本的误报）

---

## 1. R0 建立会话与共享前提

```
议题：【示例数据】科创竞赛资源应该怎么分配
shared_premises:
  - 竞赛必须拿奖才算成功
  - 资源总量固定，不讨论外部争取
```

第一条就是**这场讨论的根因候选**：六个人可以在"怎么分"上争到天荒地老，
而"必须拿奖才算成功"从未被任何人论证过。第二条是范围约定，属于正常的边界设定。

## 2. R1 六角色隔离立论

| 角色 | 立场摘要 | 论断 | 论据类型 | 置信度 |
|---|---|---|---|---|
| musk | 先算单位获奖产出的成本下界 | M1-1、M1-2 | mechanism / value_judgment | 70 |
| feynman | 先定义"获奖"和"资源"，否则在答两道题 | F1-1 | mechanism | 60 |
| munger | 想让它失败：按获奖概率分钱 + 只考核一年 | G1-1 | mechanism | 65 |
| jobs | 先砍掉两级评审 | J1-1 | value_judgment | 50 |
| karpathy | 先拆成可独立验证的模块 | K1-1 | mechanism | 75 |
| pg | 案例：按能力覆盖分配后获奖反升 | P1-1 | case | 40 |

注意两件事：

- 六个角色的 `blind_spot_declared` 各不相同（马斯克"看不到组织政治"、乔布斯"会把必要冗余当复杂度"），
  这是给元认知层的输入，让盲区互相可见；
- pg 只有 40 分置信度并主动写了"n=1，不能当统计证据"——**低置信度是合法输出**，不是失败。

## 3. R1.5 元认知扫描与强制注入

```json
hidden_assumptions:
  [{"id":"H1","scope":"explicit(编排层 R0 列出的共享前提)","heuristic_score":0.25,
    "content":"竞赛必须拿奖才算成功","status":"open"},
   {"id":"H2","scope":"explicit(...)","heuristic_score":0.25,
    "content":"资源总量固定，不讨论外部争取","status":"open"}]

injections:
  [{"round":2,"must_respond":["H1"],"must_resolve":["C1"],
    "forbidden":["继续争论分配比例的具体数字"],
    "note":"本轮所有角色必须正面回应 H1：竞赛必须拿奖才算成功"}]
```

`forbidden` 那一行的作用：把讨论从"比例是多少"这个表层循环里拔出来。

**诚实标注**：本演示只跑了脚本，H1/H2 都是 R0 显式列出、被脚本直接接管的。
脚本**抓不到**没有标记词的前提——那部分必须由模型侧按
`meta-supervisor/references/metacognitive-checklist.md` 的四个结构性问句补上
（例如"谁承担成本、有没有从未被提起的受损方"）。

## 4. R2 自由交叉：一次有效修正 + 一次从众漂移

**回应 H1 的分布**（写入 `meta_engagement`）：

```
pg       -> H1 [adopt]      承认结论依赖该前提
musk     -> H1 [refine]     指出 H1 决定 M1-2 是否成立
feynman  -> H1 [challenge]  要求先给出可操作的成败定义
jobs     -> H1 [support]    同意该前提值得质疑
```

同一轮里针对 H1 出现了三种不同处理方式（接受、收窄、质疑）——这正是"强制回应"想要的：
不是逼大家同意，而是逼大家**表态**。

### 修正 R1（有效）

```yaml
revision:
  role: musk   level: local   valid: true   action: baseline_updated
  trigger: P2-1 提出的包装成本，以及元认知登记的 H1
  from: 单位获奖产出的成本是唯一可优化量
  to:   单位有效产出的成本才是可优化量，其中必须计入为迎合口径产生的包装成本
  reason: 原结论把「产出」默认为获奖数，而包装成本说明该口径本身会制造额外成本；范围需要收窄
  remaining_doubt: 有效产出的口径由谁定义，这是价值问题不是事实问题
```

它引用了新的 claim（P2-1）与元认知条目（H1），说明了**哪条结论变了**，
并留下了余疑——三项齐备，因此基线被更新：

```
musk.stance_summary = "单位有效产出的成本才是可优化量，其中必须计入为迎合口径产生的包装成本"
```

### 修正 R2（从众漂移，基线不变）

```yaml
revision:
  role: jobs   level: local   valid: false   action: baseline_unchanged(compliance_drift)
  trigger: 大家都觉得减少评审是共识，为了推进讨论我也同意
  from: 先砍掉两级评审
  to:   砍掉一级评审
  reason: 为了达成共识，与多数人保持一致
  invalid_reason: trigger 未引用任何新证据/新论证（claim id 或 H/D/G/F/C 编号），疑似从众漂移
```

处理结果：`jobs.compliance_drift_count = 1`，**立场基线一个字没改**。
这正是反从众机制的作用点——角色可以说"我被说服了"，但拿不出新理由时，系统不认。
（元认知层在下一轮应点名这件事：`meta_engagement` 里可以看到 jobs 对 H1 是 `support`，
但它的修正是唯一没有引用的一条。）

## 5. R2.5 二次扫描、覆盖度与收敛判定

```json
divergences:
  D1 type=fact    conf=0.5  单位获奖产出的成本 vs 良率/包装成本 → 双方都用实质性论据，是事实认定冲突
  D2 type=unclear conf=0.25 评审该不该砍 → 一方价值判断、一方实质论据，规则判不了，交模型

fallacies:
  F1 type=strawman role=pg      相似度 0.04
  F2 type=strawman role=feynman 相似度 0.05
```

**F1/F2 很可能是误报**，正好用来说明脚本的定位：规则只看"质疑与原文相似度过低"，
而这两条实际上是**补充信息**与**要求定义**，不是曲解。脚本因此给每条候选都标了
`needs_judgment: true`，并把 `target_text` 一起输出供人对照。
真正的稻草人应该是"把对方观点换成更容易反驳的版本"，这一步判断必须由模型完成。

覆盖度（结构计数，不评价质量）：

```
untested_total: 7   （M1-2, M2-1, F1-1, G1-1, J2-1, K1-1, P1-1 从未被任何人检验）
open_challenges_total: 2   （C1: pg→musk；C2: feynman→jobs）
response_attention: {musk:1, jobs:1, pg:1, feynman:1}   （没有出现"全员围攻一人"）
```

`untested_total = 7` 说明：六个人各自发表了主张，**真正被检验的只有两条**。
这正是多角色讨论最常见的假象——看起来很热闹，交叉验证却很少。

收敛判定：

```json
{
  "per_round_new_key_arguments": {"1": {"claims": 7, "new_key": 5}, "2": {"claims": 4, "new_key": 3}},
  "rounds_without_new_argument": 0,
  "divergence_type_counts": {"fact": 1, "unclear": 1},
  "root_cause_candidate": true,
  "recommendation": "continue",
  "signals": [
    "隐性假设已被角色回应：H1（可判断它是否仍然成立）",
    "存在事实分歧但未登记任何信息缺口：事实分歧的消解路径不明",
    "候选根因：已登记隐性假设并已分类分歧，可进入根因确认（需模型判断）"
  ]
}
```

第 2 轮仍有 3 条新增关键论据，所以**不收敛**，建议继续 R3。
第二条信号是脚本真正有用的地方：既然 D1 是事实分歧，就必须登记一条 `G`
（例如"包装成本占总投入的比例"），否则这个分歧会一直悬着。

## 6. 交接摘要原文

```
# 圆桌讨论摘要  rt-demo
议题：【示例数据】科创竞赛资源应该怎么分配
进度：第 2/3 轮 · 阶段 probing · 交互模式 cross_exam

## 各轮论据统计
- 第 1 轮：论断 7 条，其中新增关键论据 5 条，参与角色 feynman, jobs, karpathy, munger, musk, pg
- 第 2 轮：论断 4 条，其中新增关键论据 3 条，参与角色 feynman, jobs, musk, pg

## 未决质疑（2）
- C1: pg → musk，指向 M1-1：你的成本下界推演只算了直接投入，忽略了为迎合评审口径产生的包装成本
- C2: feynman → jobs，指向 J1-1：砍掉评审要能说清「没人需要」是谁的判断；使用者包含未来的人，他们没法投票

## 共识候选（0，需人工/模型复核）
- 无

## 少数派观点（2，未被脚本判定为已反驳，必须完整保留）
- [musk] M1-1：固定预算下真正可优化的是单位获奖产出的成本，而不是获奖数量
- [jobs] J1-1：若只能保留一件事，就是让资源跟着使用者的实际需求走，而不是跟着评审表走

## 讨论质量信号
- 连续无新增关键论据轮数：0
- 根因触及：False　建议：continue
  · 隐性假设已被角色回应：H1（可判断它是否仍然成立）
```

两点值得注意：

- **共识候选为 0** 是正常且诚实的结果。讨论到第 2 轮还没有任何一条主张被两个以上角色明确支持，
  脚本不会为了好看而编造共识；
- **少数派观点被强制保留**：M1-1 与 J1-1 都收到了质疑且没有支持者，因此进入
  `minority_views`（`refuted: false`）。它们不允许被多数票淹没。

## 7. 这个例子暴露了什么

1. **机制确实能碰到前提**：H1 被登记、被注入、被四个角色正面回应——这是纯脚本部分就能做到的。
2. **前提被"回应"不等于被"解决"**：H1 回应率 4/4，但它是被接受、被收窄还是被推翻，仍需模型判断；
   脚本只报"已被回应"。
3. **反从众机制有效**：jobs 的漂移被拦下，基线未变。若没有这一步，这场讨论会呈现出
   "五人同意砍评审"的假共识。
4. **规则检测会误报**：F1/F2 就是例子。`needs_judgment` 不是免责声明，而是**强制的人工复核入口**。
5. **最容易被忽略的指标**：`untested_total`。多角色讨论的质量瓶颈通常不在"说得多不多"，
   而在"有多少主张真的被检查过"。

## 如何复现

```bash
cd marvis-roundtable-skills
python tools/demo_session.py              # 完整流程与关键输出
python tools/demo_session.py --quiet      # 只跑流程，最后打印摘要
# 状态文件：.roundtable-demo/state.json
python skills/roundtable-orchestrator/scripts/state_manager.py summary \
  --state .roundtable-demo/state.json --json     # 交接块（预留给 decision-landscape）
```

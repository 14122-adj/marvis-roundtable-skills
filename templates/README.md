# 阶段配置模板

这五个 JSON 是终极圆桌五个阶段的输入。**不要手写，用向导生成**：

```bash
python tools/wizard.py            # 交互式，替你生成
python tools/wizard.py --demo     # 或者直接生成一份示例看看
```

本目录里的文件是**示例**，可以直接改。

---

## 怎么用

```bash
# 1. 初始化（会输出一个 state_path，记住它）
python skills/ultimate-roundtable/scripts/ultimate_orchestrator.py init \
  --topic "你的议题" --out .myrun

# 2. 按顺序提交五个阶段
ORCH=skills/ultimate-roundtable/scripts/ultimate_orchestrator.py
STATE=.myrun/<你的会话id>/state.json

python $ORCH stage0 --state $STATE --file templates/stage0.json --write
python $ORCH stage1 --state $STATE --file templates/stage1.json --write
python $ORCH stage2 --state $STATE --file templates/stage2.json --write
python $ORCH stage3 --state $STATE --file templates/stage3.json --write
python $ORCH stage4 --state $STATE --file templates/stage4.json --write

# 3. 出报告
python $ORCH check  --state $STATE
python $ORCH report --state $STATE --out 我的决策报告.md
```

---

## 各阶段要点

| 文件 | 关键要求 | 不满足会怎样 |
|---|---|---|
| `stage0.json` | 必须有 `north_star`（唯一焦点指标） | 退出码 3 |
| `stage1.json` | 六人齐全；每条含 `[数据诉求]` + `[Tool Call]` + 表态句；都提及北极星；≤150 字 | 退出码 3 |
| `stage2.json` | 3v3 分营；每条有 `inner_thought`；**火花检测通过** | 退出码 4（强制重开） |
| `stage3.json` | A/B/C 三方案互斥；六人全投票带理由 | 退出码 3 |
| `stage4.json` | `owner`/`start`/`kpi`/`kill` 齐全；KPI 与 Kill **含数字** | 退出码 3 |

---

## 一个容易被忽略的点

`stage4.json` 里的 `persist_memory` 默认为 `true`，会把记忆写进记忆库。
如果你只是试跑，建议改成 `false`，否则会污染真实记忆。

示例文件里已经设为 `false`。

---

## 想看更完整的示例

`tools/quickstart.py` 内置的示例比这里的更完整（六人各有真实感的立场），
跑完可以在 `.quickstart/` 下看到它生成的全部文件。

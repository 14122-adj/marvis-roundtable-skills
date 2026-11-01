# 商品截图

Agensi 官方建议：**带截图的 listing 安装量明显更高**，20 秒演示视频更好。
这里是可直接上传的截图，全部由 `quickstart.py` 的**真实输出**渲染而成，不是编的。

---

## 上传顺序（建议）

| 顺序 | 文件 | 内容 | 用途 |
|---|---|---|---|
| 1 | `03-verdict-en.png` | 英文版裁决 + 战术清单 | **首图**。最直接回答「我买它得到什么」 |
| 2 | `01-quickstart-zh.png` | 一键跑通终端输出 | 证明零摩擦、10 秒出结果 |
| 3 | `03-verdict-zh.png` | 中文版裁决 + 清单 | 中文买家 |
| 4 | `02-report-zh.png` | 完整报告全文 | 展示产出完整度 |

**如果只能传一张**：传 `03-verdict-en.png`。

---

## 各图说明

### `03-verdict-en.png`（首图，英文）

展示 A/B/C 三选一、拍板理由、以及带数字的 KPI 与 Kill-switch。
底部有两行灰字点明差异化：

```
Note: 'if results are bad, stop' is rejected at validation time.
The kill-switch must contain a number.
```

这句话比任何形容词都有效——它证明「拒绝模糊」是**校验器强制的**，不是文案。

### `01-quickstart-zh.png`

终端截图，展示体检 → 五阶段全绿 → 0.9 秒出报告 → 自检通过。
直接回应买家最担心的问题：**要配多久才能跑起来。**

### `03-verdict-zh.png` / `02-report-zh.png`

中文买家版本。`02` 是完整报告，篇幅较长，建议放最后。

---

## 制作方式（可复现）

这些图由 Python 脚本渲染，不是手绘：

- 内容来源：`python tools/quickstart.py` 的真实输出 + `.quickstart/report.md`
- 字体：`msyh.ttc`（中文）、`consola.ttf`（ASCII）、`seguisym.ttf`（✓ 符号）
- 配色：深色终端主题，绿色表示成功/结论，青紫橙区分三个方案

> 踩过的坑：`✓` 只有 `seguisym.ttf` 真含字形，其他字体会画成方框；
> emoji 在 PIL 下是单色剪影，所以报告截图**去掉了 emoji** 只留文字。

---

## 还缺什么

**演示视频**（官方更推荐，转化率更高）。

20 秒能讲完的脚本：

```
0-3s   终端：python tools/quickstart.py
3-8s   五阶段逐条变绿
8-12s  报告生成，滚到「铁塔裁决」段
12-18s 停在 KPI / Kill-switch 两行
18-20s 字幕：No role-play. One verdict. With a number.
```

我无法录制视频（需要你的屏幕录制 + 编辑），但上面这个脚本可以直接照做。

---

## 如实说明

- 截图里的内容是**示例数据**（议题是"要不要把年度流程改成季度"），不是真实客户的讨论。
- 报告头部的「真实工具调用 0 条 / 模拟 6 条」是真实显示的——这恰恰是诚实标注的证明，
  我没有为了好看而隐藏它。

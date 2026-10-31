#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对抗火花检测与存活率评估 clash_analyzer.py

终极圆桌（ultimate-roundtable v2.0.0）的两个量化器官：

  1. **火花检测**（`spark`）——回答"红蓝对抗到底有没有打出火花"。
     spec 里写了"禁止和稀泥：如果红蓝对抗没有打出火花，元认知监督者必须强制重开一轮"，
     但"有没有火花"如果只靠感觉，这条规则就等于没有。这里给出可计数的判据：

       进攻量 attack_count     蓝军发出的有效攻击（有靶点 + 有内容）条数
       防御量 defense_count    红军给出的有效防御/修补条数
       靶点分散 targets_hit    被攻击的 claim 数量（全员围攻同一条 = 视野窄）
       立场变动 position_shift 本轮发生的有效立场修正次数
       新论据 new_arguments    本轮新增关键论据条数
       空洞发言 hollow         无靶点、无证据、纯表态的发言条数

     火花判定是**规则+阈值**，不是语义判断：它只能说明"结构上有没有交锋"，
     不能说明"交锋得好不好"。因此输出一律带 needs_judgment。

  2. **存活率模型**（`survival`）——把沙盘推演的结果折算成 0–100 的存活率。
     公式公开、可复算、可反驳：它不是"AI 感觉"，而是一份可以被审计的算术。
     见 `survival_score()` 的注释。

用法：
  python clash_analyzer.py spark --state S [--round 2] [--write]
  python clash_analyzer.py survival --state S [--scenario sandbox.json] [--write]
  python clash_analyzer.py selftest
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BLUE = "blue"   # 恶魔代言人：必须想尽办法证明方案会失败
RED = "red"     # 捍卫并修补方案

# 火花判定阈值（可在 state.clash_thresholds 里覆盖）
DEFAULT_THRESHOLDS = {
    "min_attack": 3,          # 至少 3 条有效攻击
    "min_defense": 2,         # 至少 2 条有效防御
    "min_targets": 2,         # 至少打到 2 个不同的 claim
    "min_signal": 3,          # attack+defense+position_shift+new_arguments 的总和下限
    "max_hollow_ratio": 0.34,  # 空洞发言占比上限
}

# 存活率权重（合计 1.0）
SURVIVAL_WEIGHTS = {
    "risk_residual": 0.40,    # 未缓解风险的残值（越少越好）
    "evidence_coverage": 0.25, # 关键假设被证据覆盖的比例
    "defense_quality": 0.20,   # 攻击是否被有效回应
    "plan_integrity": 0.15,    # 方案完整性：是否有明确的 Do/Don't/Need Info 支撑
}


def log(msg: str) -> None:
    print(f"[clash_analyzer] {msg}", file=sys.stderr)


def die(msg: str, code: int = 2):
    print(f"[clash_analyzer] ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def load_state(path) -> dict:
    p = Path(path)
    if not p.exists():
        die(f"状态文件不存在: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path, state) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)


# --------------------------------------------------------------------------- #
# 火花检测
# --------------------------------------------------------------------------- #

HOLLOW_MARKERS = ["我觉得挺好的", "大家都很努力", "都有道理", "各有优劣", "见仁见智",
                  "综合考虑", "权衡一下", "没有对错", "因人而异"]


def _is_hollow(entry: dict) -> bool:
    text = str(entry.get("text", "")).strip()
    if not text:
        return True
    if any(m in text for m in HOLLOW_MARKERS):
        return True
    # 无靶点、无证据、且很短 → 视为纯表态
    return (not entry.get("target_claim") and not entry.get("evidence")
            and len(text) < 12)


def spark(state: dict, round_no: int = None) -> dict:
    """统计某一轮（或全部轮次）的对抗结构。"""
    round_no = round_no if round_no is not None else state.get("round", 0)
    th = dict(DEFAULT_THRESHOLDS)
    th.update(state.get("clash_thresholds") or {})

    camps = state.get("camps", {}) or {}
    camp_of = {}
    for role in camps.get(BLUE, []) or []:
        camp_of[role] = BLUE
    for role in camps.get(RED, []) or []:
        camp_of[role] = RED

    exchanges = [e for e in (state.get("clash_exchanges") or [])
                 if round_no in (None, 0) or int(e.get("round", -1)) == int(round_no)]

    attack, defense, hollow, targets = [], [], [], set()
    for e in exchanges:
        role = e.get("from")
        camp = camp_of.get(role, e.get("camp"))
        if _is_hollow(e):
            hollow.append(e)
            continue
        if camp == BLUE:
            attack.append(e)
            if e.get("target_claim"):
                targets.add(e["target_claim"])
        elif camp == RED:
            defense.append(e)
        else:
            # 未分营的发言只计空洞检查，不计攻防
            pass

    position_shift = len([r for r in (state.get("revisions") or [])
                          if int(r.get("round", -1)) == int(round_no) and r.get("valid")])
    new_arguments = len([a for a in (state.get("argument_log") or [])
                         if int(a.get("round", -1)) == int(round_no) and a.get("is_new_key_argument")])
    injections = [i for i in (state.get("injections") or [])
                  if int(i.get("round", -1)) == int(round_no)]
    must_respond = sorted({m for i in injections for m in i.get("must_respond", [])})
    responded = sorted({m.get("meta_id") for m in (state.get("meta_engagement") or [])
                        if int(m.get("round", -1)) == int(round_no)})
    unmet = [m for m in must_respond if m not in responded]

    total_utterances = len(exchanges)
    hollow_ratio = round(len(hollow) / total_utterances, 3) if total_utterances else 0.0
    signal = len(attack) + len(defense) + position_shift + new_arguments

    reasons = []
    if len(attack) < th["min_attack"]:
        reasons.append(f"有效攻击只有 {len(attack)} 条（需 ≥{th['min_attack']}）")
    if len(defense) < th["min_defense"]:
        reasons.append(f"有效防御只有 {len(defense)} 条（需 ≥{th['min_defense']}）")
    if len(targets) < th["min_targets"]:
        reasons.append(f"只打到 {len(targets)} 个靶点（需 ≥{th['min_targets']}，说明攻击集中或没有靶点）")
    if signal < th["min_signal"]:
        reasons.append(f"对抗信号总量 {signal} 偏低（需 ≥{th['min_signal']}）")
    if hollow_ratio > th["max_hollow_ratio"]:
        reasons.append(f"空洞发言占比 {hollow_ratio:.0%} 超过上限 {th['max_hollow_ratio']:.0%}")
    if unmet:
        reasons.append(f"本轮必须回应的元认知条目未回应：{', '.join(unmet)}")
    if not camps:
        reasons.append("尚未分营：红蓝分组未建立，对抗不成立")

    sparked = not reasons
    return {
        "needs_judgment": True,
        "round": round_no,
        "camps_established": bool(camps),
        "blue": camps.get(BLUE, []),
        "red": camps.get(RED, []),
        "attack_count": len(attack),
        "defense_count": len(defense),
        "targets_hit": sorted(targets),
        "target_spread": len(targets),
        "position_shift": position_shift,
        "new_arguments": new_arguments,
        "hollow_count": len(hollow),
        "hollow_ratio": hollow_ratio,
        "unmet_must_respond": unmet,
        "signal_total": signal,
        "thresholds": th,
        "sparked": sparked,
        "verdict": "sparked" if sparked else "no_spark",
        "reopen_required": not sparked,
        "reasons": reasons,
        "note": ("这是结构计数：它只能说明有没有交锋，不能说明交锋得好不好。"
                 "sparked=false 时按 spec 必须强制重开一轮，并针对 reasons 逐条补强。"),
    }


# --------------------------------------------------------------------------- #
# 存活率模型
# --------------------------------------------------------------------------- #


def normalize_scenario(raw: dict) -> dict:
    """把状态里的 sandbox 结构转成 survival_score 需要的形态。

    注意区分两个都叫 "plan" 的东西：
      * sandbox.plan        —— 被推演方案的**名字**（字符串）
      * sandbox.action_plan —— Do / Don't / Need Info 三栏（dict）
    survival_score 要的是后者。直接传整个 sandbox 会把名字当成清单，导致 AttributeError。
    """
    if not isinstance(raw, dict):
        return {}
    action = raw.get("action_plan")
    if not isinstance(action, dict):
        action = raw.get("plan") if isinstance(raw.get("plan"), dict) else {}
    return {
        "risks": raw.get("risks") or [],
        "key_assumptions": raw.get("key_assumptions") or [],
        "attacks": raw.get("attacks") or [],
        "plan": action,
    }


def survival_score(scenario: dict) -> dict:
    """把沙盘推演折算成 0–100 的存活率。公式完全公开，可手算复现：

      risk_residual     = 100 × (1 - Σ(risk.severity × risk.probability) / 风险数)   [截断到 0–100]
      evidence_coverage = 100 × 已被证据覆盖的关键假设数 / 关键假设总数
      defense_quality   = 100 × 已被有效回应的攻击数 / 攻击总数
      plan_integrity    = 100 × (Do/Don't/NeedInfo 三栏是否齐备且非空) 的加权

      survival = Σ(weight × 分项)  → 四舍五入到整数

    为什么这样设计：它把"感觉能行"拆成四个可反驳的量。任何一个分项都能被单独挑战，
    从而让"存活率 62%"变成一句可以被讨论的话，而不是一个拍脑袋的数字。
    """
    risks = scenario.get("risks") or []
    assumptions = scenario.get("key_assumptions") or []
    attacks = scenario.get("attacks") or []
    plan = scenario.get("plan") or {}

    if risks:
        per = [max(0.0, min(1.0, float(r.get("severity", 0.5)) * float(r.get("probability", 0.5))))
               for r in risks]
        mean_risk = sum(per) / len(per)
        risk_residual = round(100 * (1 - mean_risk), 1)
    else:
        risk_residual = 0.0   # 没做风险识别 → 不给分（这才是诚实的）

    if assumptions:
        covered = [a for a in assumptions if a.get("evidence")]
        evidence_coverage = round(100 * len(covered) / len(assumptions), 1)
    else:
        evidence_coverage = 0.0

    if attacks:
        defended = [a for a in attacks if a.get("defended")]
        defense_quality = round(100 * len(defended) / len(attacks), 1)
    else:
        defense_quality = 0.0

    slots = {"do": plan.get("do") or [], "dont": plan.get("dont") or [],
             "need_info": plan.get("need_info") or []}
    filled = sum(1 for v in slots.values() if v)
    plan_integrity = round(100 * filled / 3, 1)

    parts = {
        "risk_residual": {"score": risk_residual, "weight": SURVIVAL_WEIGHTS["risk_residual"]},
        "evidence_coverage": {"score": evidence_coverage, "weight": SURVIVAL_WEIGHTS["evidence_coverage"]},
        "defense_quality": {"score": defense_quality, "weight": SURVIVAL_WEIGHTS["defense_quality"]},
        "plan_integrity": {"score": plan_integrity, "weight": SURVIVAL_WEIGHTS["plan_integrity"]},
    }
    total = sum(p["score"] * p["weight"] for p in parts.values())

    worst = None
    if risks:
        worst = max(risks, key=lambda r: float(r.get("severity", 0.5)) * float(r.get("probability", 0.5)))

    deductions = []
    if not risks:
        deductions.append("未登记任何风险：risk_residual 直接记 0（没有风险识别本身就是最大风险）")
    if not assumptions:
        deductions.append("未登记关键假设：evidence_coverage 记 0")
    if not attacks:
        deductions.append("未登记攻击记录：defense_quality 记 0")
    if filled < 3:
        deductions.append(f"行动清单只填了 {filled}/3 栏（Do / Don't / Need Info）")

    band = "high" if total >= 70 else ("medium" if total >= 40 else "low")
    return {
        "needs_judgment": True,
        "survival_rate": int(round(total)),
        "band": band,
        "components": parts,
        "weights": SURVIVAL_WEIGHTS,
        "worst_risk": worst,
        "risk_count": len(risks),
        "assumption_count": len(assumptions),
        "attack_count": len(attacks),
        "plan_slots_filled": filled,
        "deductions": deductions,
        "formula": ("survival = 0.40×risk_residual + 0.25×evidence_coverage "
                    "+ 0.20×defense_quality + 0.15×plan_integrity"),
        "note": ("存活率是**算术结果**，不是判断结论：它可以被逐项挑战与重算。"
                 "band=low 时不得直接交付方案，应先补 Need Info 或改设计。"),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def cmd_spark(args) -> int:
    st = load_state(args.state)
    result = spark(st, args.round)
    if args.write:
        st.setdefault("clash_spark", {})[str(result["round"])] = result
        save_state(args.state, st)
        log(f"已写回 clash_spark[{result['round']}]: {result['verdict']}")
    emit(result)
    return 0 if result["sparked"] or args.no_fail else 1


def cmd_survival(args) -> int:
    if args.scenario:
        raw = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
        st = None
    else:
        st = load_state(args.state) if args.state else die("需要 --state 或 --scenario")
        raw = st.get("sandbox") or {}
        if not raw:
            die("状态里没有 sandbox 数据（先执行 ultimate_orchestrator.py stage3 --write）")
    result = survival_score(normalize_scenario(raw))
    if args.write:
        if not st:
            die("--write 需要 --state")
        st.setdefault("sandbox", {}).setdefault("evaluation", {}).update(result)
        save_state(args.state, st)
    emit(result)
    return 0


def selftest() -> int:
    ok = True

    def ck(cond, msg):
        nonlocal ok
        if cond:
            print(f"  ok: {msg}", file=sys.stderr)
        else:
            ok = False
            print(f"  FAIL: {msg}", file=sys.stderr)

    def base_state():
        return {
            "round": 2, "roles": ["musk", "pg", "jobs"],
            "camps": {BLUE: ["pg", "jobs"], RED: ["musk"]},
            "clash_exchanges": [
                {"from": "pg", "round": 2, "target_claim": "M1-1",
                 "text": "你的下界推演漏了包装成本，这一项可能吃掉全部收益", "evidence": "示例数据"},
                {"from": "jobs", "round": 2, "target_claim": "M1-2",
                 "text": "这套流程有两个环节没人需要，先砍掉再谈成本", "evidence": "减法清单"},
                {"from": "pg", "round": 2, "target_claim": "M1-1",
                 "text": "如果良率低于 70%，你的单位成本结论直接反转"},
                {"from": "musk", "round": 2, "target_claim": "P2-1",
                 "text": "接受包装成本，但量级只有 3%，不足以推翻下界结论", "evidence": "量级估算"},
                {"from": "musk", "round": 2, "target_claim": "J2-1",
                 "text": "砍流程前先给出拦截损失的记录，否则无法验证"},
            ],
            "revisions": [{"round": 2, "valid": True, "role": "musk"}],
            "argument_log": [{"round": 2, "is_new_key_argument": True, "role": "musk"}],
            "injections": [{"round": 2, "must_respond": ["H1"]}],
            "meta_engagement": [{"meta_id": "H1", "round": 2, "from": "pg"}],
        }

    r = spark(base_state())
    ck(r["sparked"] is True and r["verdict"] == "sparked", "攻防充足时判定为有火花")
    ck(r["attack_count"] == 3 and r["defense_count"] == 2, "攻防计数正确（蓝3/红2）")
    ck(r["targets_hit"] == ["M1-1", "M1-2"], "靶点去重正确（M1-1 被攻两次只算一个靶点）")
    ck(r["target_spread"] == 2, "靶点分散度统计正确")
    ck(r["unmet_must_respond"] == [], "已回应的元认知条目不进未回应清单")

    # 无火花：攻击不足 + 空洞发言
    weak = base_state()
    weak["clash_exchanges"] = [
        {"from": "pg", "round": 2, "text": "我觉得挺好的"},
        {"from": "jobs", "round": 2, "text": "大家都很努力"},
        {"from": "musk", "round": 2, "text": "各有优劣"},
    ]
    weak["revisions"] = []
    weak["argument_log"] = []
    r2 = spark(weak)
    ck(r2["sparked"] is False and r2["reopen_required"] is True, "空洞发言导致判定为无火花并要求重开")
    ck(r2["hollow_count"] == 3 and r2["hollow_ratio"] == 1.0, "空洞发言被识别并计入比例")
    ck(any("空洞" in x for x in r2["reasons"]), "重开理由里点名了空洞发言")

    # 未回应强制项 → 不算火花
    un = base_state()
    un["meta_engagement"] = []
    r3 = spark(un)
    ck(r3["sparked"] is False and "H1" in r3["unmet_must_respond"], "未回应 must_respond 时不算打出火花")

    # 未分营 → 对抗不成立
    nc = base_state()
    nc["camps"] = {}
    r4 = spark(nc)
    ck(r4["sparked"] is False and any("未分营" in x for x in r4["reasons"]), "未分营时判定对抗不成立")

    # 阈值可覆盖
    custom = base_state()
    custom["clash_thresholds"] = {"min_attack": 10}
    r5 = spark(custom)
    ck(r5["sparked"] is False and r5["thresholds"]["min_attack"] == 10, "自定义阈值生效")

    # ---------- 存活率 ----------
    sc = {
        "risks": [{"name": "留存下滑", "severity": 0.8, "probability": 0.5},
                  {"name": "合规", "severity": 0.3, "probability": 0.4}],
        "key_assumptions": [{"text": "需求真实", "evidence": "访谈 12 人"},
                            {"text": "成本可控", "evidence": ""}],
        "attacks": [{"text": "留存风险", "defended": True}, {"text": "合规风险", "defended": False}],
        "plan": {"do": ["先做最小试点"], "dont": ["不要一次全量"], "need_info": ["留存基线"]},
    }
    s = survival_score(sc)
    # 手算：risk = 1 - mean(0.4, 0.12) = 1-0.26 = 0.74 → 74.0
    ck(s["components"]["risk_residual"]["score"] == 74.0, "风险残值分项可手算复现（74.0）")
    ck(s["components"]["evidence_coverage"]["score"] == 50.0, "证据覆盖率 = 1/2 = 50")
    ck(s["components"]["defense_quality"]["score"] == 50.0, "防御质量 = 1/2 = 50")
    ck(s["components"]["plan_integrity"]["score"] == 100.0, "三栏齐全 → 完整性 100")
    expect = round(74.0 * 0.40 + 50.0 * 0.25 + 50.0 * 0.20 + 100.0 * 0.15)
    ck(s["survival_rate"] == expect, f"加权总分正确（{s['survival_rate']} == {expect}）")
    ck(s["band"] in ("high", "medium", "low"), "给出高/中/低分档")
    ck(s["worst_risk"]["name"] == "留存下滑", "最致命风险点被识别")

    empty = survival_score({})
    ck(empty["survival_rate"] == 0, "空方案存活率为 0（没有风险识别/证据/防御/清单，不给同情分）")
    ck(empty["band"] == "low", "空方案落在 low 分档")
    ck(len(empty["deductions"]) == 4, "空方案列出 4 条扣分理由（风险/假设/攻击/清单）")

    low = survival_score({"risks": [{"severity": 0.95, "probability": 0.9}],
                          "key_assumptions": [{"text": "x", "evidence": ""}],
                          "attacks": [{"text": "y", "defended": False}],
                          "plan": {"do": [], "dont": [], "need_info": []}})
    ck(low["band"] == "low", "高风险低覆盖时判定为 low 分档")
    ck(low["survival_rate"] < 40, "低分档分数确实低于 40")

    # normalize_scenario：区分"方案名（字符串）"与"行动清单（dict）"
    sandbox = {"plan": "方案 A：季度评审", "risks": [{"severity": 0.5, "probability": 0.5}],
               "key_assumptions": [{"text": "a", "evidence": "e"}],
               "attacks": [{"text": "b", "defended": True}],
               "action_plan": {"do": ["x"], "dont": ["y"], "need_info": ["z"]}}
    norm = normalize_scenario(sandbox)
    ck(norm["plan"] == {"do": ["x"], "dont": ["y"], "need_info": ["z"]},
       "normalize 取 action_plan 作为清单，而不是把方案名当清单")
    s2 = survival_score(norm)
    ck(s2["plan_slots_filled"] == 3, "从 sandbox 结构算出的清单填充率为 3/3")
    ck(survival_score(normalize_scenario({"plan": "只有名字"}))["survival_rate"] == 0,
       "只有方案名时不会崩溃，存活率为 0")

    print("selftest OK" if ok else "selftest FAILED", file=sys.stderr)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="终极圆桌：火花检测与存活率评估")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("spark")
    ps.add_argument("--state", required=True)
    ps.add_argument("--round", type=int, default=None)
    ps.add_argument("--write", action="store_true")
    ps.add_argument("--no-fail", action="store_true", help="无火花时不返回非零（仅查看用）")
    pv = sub.add_parser("survival")
    pv.add_argument("--state")
    pv.add_argument("--scenario")
    pv.add_argument("--write", action="store_true")
    sub.add_parser("selftest")
    args = ap.parse_args(argv)

    if args.cmd == "spark":
        return cmd_spark(args)
    if args.cmd == "survival":
        return cmd_survival(args)
    return selftest()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    raise SystemExit(main())

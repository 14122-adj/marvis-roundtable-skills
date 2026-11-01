# Report template and field reference

The `ultimate-roundtable` report template, the hand-computed survival-rate example, and the complete JSON fields for stages 3 and 4.

## Contents

1. Frozen report template
2. Pass / fail comparison
3. Hand-computed survival-rate example
4. How to write long-term memory (≤200 characters)
5. `sandbox.json` complete fields (optional sandbox)
6. Stage 4 `meta.json` complete fields
7. Common bad-report checklist

---

## 1. Frozen report template

This is exactly the structure that `ultimate_orchestrator.py report` outputs; **the order and the headings must not be changed**:

```markdown
### ⚔️ Ultimate Roundtable Decision Report V4.1

> Topic: ...  Session: `ur-20261101-012900`  External data: 3 real tool calls / 3 simulated

#### 📌 1. North-star metric and baseline assumptions
- Core metric of this run: xxx
- Hidden assumption we broke: xxx
- Baseline assumption overturned: we assumed xxx from the start, but the sandbox run proved it wrong.
- Cost dimension we ignored: xxx

#### 🔗 2. Evidence chain and external verification
- Data 1 (musk, source: real tool): xxx
  - Call: [Search] keywords: xxx. Based on this data, my view is: xxx
  - Result: xxx

#### 🚦 3. Iron verdict (one of three)
- Aggressive Option A: [one sentence] (votes: musk)
- Conservative Option B: [one sentence] (votes: munger, pg)
- Orthogonal Option C: [one sentence] (votes: feynman, jobs, karpathy)
- 🏆 **Final decision**: adopt option X
- Reason for the decision: xxx

#### 🎯 4. Tactical action items
- Owner: xxx
- Start: xxx
- KPI: xxx
- Kill-switch: xxx
- Need info: xxx

#### 🧠 5. Long-term memory write
- `[MEMORY_UPDATE]`: xxx
- Written to the memory store: M20261101012900 (xx characters)

---

**Process trace (not part of the report body)**

- 6 data demands in stage 1:
  - [musk] needs competitor revenue data for Q3 2024
- Blue/red split: blue team [...] | red team [...]
- Clash sparks: attacks 3 / defenses 2 / targets 2 / hollow statements 0 → **sparked**
- Dynamic summon: legal expert
```

**The data-source tally on the header line cannot be dropped**: it lets the reader judge the evidential quality of the report within 3 seconds.
A report with 0 real calls and 6 simulated data points is not remotely as credible as a report with 6 real calls.

---

## 2. Pass / fail comparison

| Section | Pass | Fail |
|---|---|---|
| North star | "30-day MAU (definition: deduplicated logged-in users, calendar month)" | "Improve user satisfaction" |
| Hidden assumption | "We initially assumed 'success = number of awards'; the sandbox shows effective output dropping 8% by month 3" | "We may have overlooked some important factors" |
| Evidence chain | "Data 1 (musk, source: real tool): Q3 competitor revenue 120M" | "Based on public information, the situation is fairly complex" |
| Option A | "Switch everything to quarterly review, completed within three months (votes: musk)" | "Actively push forward the review reform" |
| Decision | "Adopt Option C; reason: C has 3 votes and an observable criterion, while A's downside risk was never defended" | "After considering everything, we suggest a flexible approach" |
| Owner | "karpathy" | "The product team will drive it" |
| First step | "Ship trigger-based review to 2 teams this week, threshold set at the metric falling below 8%" | "Start pushing forward" |
| KPI | "No more than 5 triggers in 30 days, MAU no lower than 9%" | "Improve process efficiency" |
| Kill | "If there are more than 12 triggers in 30 days, stop immediately and roll back" | "Stop if results are bad" |
| Need Info | "Records of the losses caused by review rejections over the past two years (to validate whether the review is necessary)" | "Need more data" |
| Long-term memory | see section 4 | pasting the meeting minutes in verbatim |

**Judging rule**: any sentence with no subject, no criterion and no number is automatically a fail —
this is the executable version of the spec's ban on "I think it's pretty good" and "everyone worked hard".

> Note: survival rate and the most lethal risk are still useful metrics at the sandbox stage, but they
> no longer appear in the V4 report body — they survive only in the "process trace". V4 cares about
> executability, not about a survival-rate score.

---

## 3. Hand-computed survival-rate example

Given the sandbox data:

```json
{
  "risks": [
    {"name": "Packaging cost runs out of control", "severity": 0.8, "probability": 0.6},
    {"name": "Long-term projects stall", "severity": 0.9, "probability": 0.4},
    {"name": "Review backlash",     "severity": 0.3, "probability": 0.5}
  ],
  "key_assumptions": [
    {"text": "Success criterion = winning an award", "evidence": ""},
    {"text": "Packaging cost is controllable",       "evidence": "order-of-magnitude estimate (example)"},
    {"text": "The team will follow the new criteria",   "evidence": ""}
  ],
  "attacks": [{"text": "Packaging cost", "defended": true},
              {"text": "Long-term projects", "defended": false}],
  "action_plan": {"do": ["pilot"], "dont": ["full switch"], "need_info": ["loss records"]}
}
```

Hand computation:

```
each risk item = 0.8×0.6 = 0.48 ; 0.9×0.4 = 0.36 ; 0.3×0.5 = 0.15
average = (0.48+0.36+0.15)/3 = 0.33
risk_residual     = 100 × (1 - 0.33) = 67.0

evidence_coverage = 1/3 → 33.3
defense_quality   = 1/2 → 50.0
plan_integrity    = 3/3 → 100.0

survival = 0.40×67.0 + 0.25×33.3 + 0.20×50.0 + 0.15×100.0
         = 26.8 + 8.3 + 10.0 + 15.0
         = 60.1  → 60%
```

**Why you must be able to hand-compute it**: every sub-score can be challenged on its own —
"what makes you call that a 0.9 severity?" is a worthwhile discussion.
Whereas "survival rate 60%", if it cannot be computed, is just decoration.

**Band decision**: `60%` falls in `40–69`, which is `medium`:
deliverable, but with conditions attached; if it were `<40` you **must not deliver directly** — you first have to close the Need Info gaps or change the design.

---

## 4. How to write long-term memory (≤200 characters)

**What it is**: a **judgement you can reuse directly next time**, not a record of what happened this time.

**Suggested structure** (not mandatory, but entries containing these elements last longer):
`trigger condition` + `mechanism` + `actionable move`

**Passing example (98 characters)**:
> Once an allocation mechanism is measured by a single packagable metric, it breeds cost that serves the metric;
> defining the success criterion before talking about resource allocation is the only prerequisite move in this kind of topic.

**Failing examples**:
- ❌ "This discussion went well and everyone raised many valuable points." — zero information;
- ❌ Pasting a summary of all six people's remarks — over 200 characters, and not reusable;
- ❌ "Be aware of risk." — no trigger condition, no mechanism, no action.

**How the length is counted**: by character (`len(memory)`); anything over 200 is rejected at write time.
This is not a suggestion, it is a hard gate — an over-long memory gets truncated the next time it is read, which means it was never written.

---

## 5. `sandbox.json` complete fields (optional sandbox; does not override the verdict)

```json
{
  "sandbox": {
    "plan": "Plan A: allocate by capability coverage + keep first-level review",
    "runners": ["karpathy", "musk"],
    "timeline": [
      {"month": 1, "event": "Review form goes live, the team starts packaging materials", "metric": "Packaging spend ratio 12%"},
      {"month": 3, "event": "Packaging cost eats the budget",           "metric": "Effective output down 8%"},
      {"month": 6, "event": "Long-term projects get squeezed out",             "error": "Two multi-year projects stall"}
    ],
    "risks": [{"name": "Packaging cost runs out of control", "severity": 0.8, "probability": 0.6}],
    "key_assumptions": [{"text": "Success criterion = winning an award", "evidence": ""}],
    "attacks": [{"text": "Packaging cost", "defended": true}],
    "action_plan": {
      "do": ["pilot the new criteria on a small scale first"],
      "dont": ["do not switch everything at once"],
      "need_info": ["the real share of packaging cost"]
    },
    "consensus": "The current allocation rule is itself creating extra cost",
    "core_divergence": "Whether the success criterion must equal winning an award (value disagreement, unresolved)"
  },
  "summons": [
    {"role": "legal expert",
     "reason": "Changing the review criteria touches award rules and compliance",
     "statement": "Changing the criteria requires amending the award rules at the same time, otherwise award results can be appealed"}
  ]
}
```

**Validation rules** (enforced by the script):

| Field | Requirement | Consequence of violation |
|---|---|---|
| `plan` | required | rejected (exit code 3) |
| `timeline` | ≥3 nodes, each with `month` + `event` + (`metric` or `error`) | rejected |
| `runners` | must contain `karpathy` and `musk` | rejected |
| `summons[].role/reason/statement` | all three present | rejected |
| `action_plan` all three columns | all must be non-empty when the report is generated | report generation refused |

`severity` and `probability` take decimals between 0–1. When you cannot produce a precise value, give a conservative estimate and state the basis;
**do not leave them empty** — empty means giving up on risk assessment.

---

## 6. Stage 4 `meta.json` complete fields

```json
{
  "meta": {
    "shared_hidden_assumption": "Success must be measured by winning awards",
    "assumption_broken": ["The success criterion equals the number of awards", "Packaging cost can be ignored"],
    "ignored_dimension": "Organisational trust and the opportunity cost of long-term projects",
    "consensus": "The current rule is creating extra cost",
    "core_divergence": "Whether the success criterion must equal winning an award (value disagreement, unresolved)",
    "memory": "Once an allocation mechanism is measured by a single packagable metric, it breeds cost that serves the metric; define the success criterion before talking about resource allocation."
  }
}
```

| Field | Meaning | Validation |
|---|---|---|
| `shared_hidden_assumption` | the premise **everyone** never stepped out of (not one person's oversight) | required |
| `assumption_broken` | premises falsified by the sandbox, ≥1 | required, non-empty |
| `ignored_dimension` | the cost dimension that was ignored | required |
| `consensus` / `core_divergence` | the two sentences for section 1 of the report | required |
| `memory` | long-term memory, ≤200 characters | over-long is rejected |

**Distinguishing two easily confused fields**:
- `shared_hidden_assumption` is **shared by the whole room** (everyone defaults to it);
- `assumption_broken` is **which specific premise** was falsified (it may have been raised by one person, or knocked down by the sandbox).
  Conflating the two turns "breaking hidden assumptions" into an empty phrase.

---

## 7. Common bad-report checklist

1. **Listing remarks round by round** — the report is a decision document, not meeting minutes;
2. **Writing consensus as "everyone agrees"** — no supporters, no strength, no traceability;
3. **Writing disagreement as "needs further discussion"** — it does not say whether this is a factual disagreement (data can settle it) or a value disagreement (irreconcilable);
4. **Action lists saying "strengthen", "optimise", "improve"** — no subject, no criterion, no completion standard;
5. **A survival rate with no breakdown** — the reader cannot tell where it came from, so they cannot rebut it;
6. **Risks written only as "there is a certain level of risk"** — no severity / probability means no assessment was done;
7. **Long-term memory over 200 characters** — it gets truncated the next time it is read, which means it was never written;
8. **Presenting simulated data as real data** — the most serious error; it strips the whole report of credibility;
9. **Summoning roles to pad the count** — forcing in an expert when there is no cross-domain blind spot only dilutes credibility;
10. **"Consensus reached" or "verified" appearing in the report** — the script errors out immediately,
    because when evidence is thin these are exactly the words most easily used to paper over a disagreement.

# Tactical command playbook (V4)

The operating manual for `ultimate-roundtable` V4.1. It answers four questions:
**how to set the north star, how to tune the compartmentalisation lenses, how to judge a deadlock, and when a tactical action list actually counts as "executable".**

## Contents

1. Choosing the north-star metric
2. Tuning the compartmentalisation lenses
3. Deadlock criteria in detail
4. Designing mutually exclusive three-way options
5. Granularity standards for the tactical action list
6. Common bad options and bad lists
7. A complete V4 walkthrough

---

## 1. Choosing the north-star metric

The north star is **the single focus of the whole room**. Every statement must revolve around it, otherwise it is treated as invalid.

### A passing north star

| Criterion | Explanation |
|---|---|
| **Single** | one metric, not a group of metrics (❌ "MAU and profit margin") |
| **Measurable** | it can be given a number and a definition (✅ "30-day MAU", ❌ "user satisfaction") |
| **Directional** | you know whether up is good or bad (❌ "churn rate and retention rate" — pick one, not both) |
| **Time-windowed** | an implicit or explicit time range (✅ "MAU this quarter") |
| **Attributable** | the actions under discussion can move it (❌ "industry growth rate" — the discussion cannot change it) |

### Common mis-selections

- ❌ **Treating a KPI as the north star**: the north star is the decision focus, not a performance-appraisal item;
- ❌ **Picking a metric nobody can influence**: the discussion degenerates into "analysing the situation" instead of "making a decision";
- ❌ **Wanting two at once**: V4 enforces a single metric; multiple metrics make the three-way choice undecidable;
- ❌ **Picking too narrowly**: for example "MAU this quarter", which makes every long-term option count as invalid.

**One-sentence test**: if all three options A/B/C can be ranked by this metric, it is a valid north star.

---

## 2. Tuning the compartmentalisation lenses

The six lenses are defined in `LENSES` in `attention_split.py`; each lens is a set of keywords.
Compartmentalisation decides "whether you can see this piece of history" by literal keyword matching.

### Three iron rules

1. **North-star-related entries are visible to every role** — otherwise roles forget why the meeting was called;
2. **Mandatory entries (`must_respond` / `must_resolve`) are never muted** — otherwise metacognitive injection stops working;
3. **Record ids only, never copy content** — compartmentalisation rewrites no original text; `muted` contains ids only.

### When to tune

| Symptom | Cause | Adjustment |
|---|---|---|
| `visible_ratio = 1.0` | too little history, or keywords too broad | tighten the keywords, or wait for more history |
| `visible = []` | the lens does not match the topic | add words from the topic domain (e.g. "compliance", "supply chain") |
| A role never sees the key challenge | the lens is too narrow | give that role a `must_respond` entry to force visibility |
| The discussion gets noticeably shallower after compartmentalisation | too much is muted | raise the visible ratio (fewer keywords or a whitelist) |

**Do not mute key information just to make compartmentalisation look like it is working** — the point of compartmentalisation is noise reduction, not building an information cocoon.
Muted content stays traceable in the report (the `muted` list), so it can be reviewed by hand when needed.

---

## 3. Deadlock criteria in detail (V4.1 dual path)

### 3.1 Semantic path (primary)

**At the end of every round the chair completes the judgement internally** (without outputting the process), comparing the red and blue sides' statements this round against the previous round, and gives one of three labels for each pair:

| Label | Criterion | Action |
|---|---|---|
| `[REPEAT]` | only rewording, synonym substitution, different examples; the **core argument, supporting data and reasoning logic** are completely unchanged | counted as repetition |
| `[PROGRESS]` | new evidence, a new premise, a revised position, or a targeted rebuttal of the other side's **specific wording** | **pass** (this round made progress) |
| `[PROGRESS]` | a counter-question, a challenge, or a request for data | **pass** (same as above) |
| `[UNCERTAIN]` | cannot be determined | no judgement; leave it to the structural path as fallback |

**Aggregation rule** (`round_semantic_summary`):

```
this round judged == 0            → semantic_repeat = None (not judged, take the structural path)
this round PROGRESS > 0           → semantic_repeat = False (pass, even if similarity is very high)
this round REPEAT > 0 and no PROGRESS → semantic_repeat = True (repetition)
this round all UNCERTAIN          → semantic_repeat = None (take the structural path)
```

**Fuse**: `semantic_repeat = True` → **fuse this round immediately** (no need for two consecutive rounds).

> The original spec wording is "as soon as semantic repetition is detected (**or** two consecutive rounds
> produce no new facts)" —
> these are two **independent** trigger conditions with different thresholds:
> semantic repetition is "as soon as detected" → a single round is enough to fuse;
> only the structural fallback requires "two consecutive rounds".

### 3.2 Structural path (fallback)

When there is no semantic verdict, **two consecutive rounds** must satisfy all four:

| Criterion | Threshold | Explanation |
|---|---|---|
| Repetition | maximum similarity to the previous round ≥ 0.55 | character-bigram Jaccard; catches verbatim repetition only |
| No new facts | `new_arguments = 0` and `new_tool_results = 0` | no new arguments and no new verification |
| Position unmoved | `valid_revisions = 0` | no valid revision at all |
| Targets unchanged | the set of attacked claims is the same as the previous round | still hitting the same targets |

### 3.3 Decision boundaries

- **Semantic outranks structural**: when the semantic path says `PROGRESS`, it passes even at similarity 1.0
  (new evidence can absolutely be expressed in similar wording);
- **The first exchange has no "previous round" to compare with**: the structural path instead asks "did this round contain anything new at all";
- **Changed targets do not count as deadlock**: it means both sides are widening the front, and still making progress;
- **A new tool result does not count as deadlock**: even if the conclusion is unchanged, the information is new;
- **`UNCERTAIN` does not mean pass**: it only means "no judgement"; the structural path makes the final call.

### 3.4 Why the semantic path is needed

Measured: two passages with identical meaning can score as little as **0.0x** character similarity after rewording —
the structural path cannot catch that at all. And if "I think they are repeating" is not recorded as an entry with a reason,
it is nothing but the chair's subjective feeling, unreviewable after the fact.

So every record in `semantic_verdicts` must carry a `reason`:

```json
{"round": 3, "from": "munger", "to": "munger", "label": "REPEAT",
 "reason": "rephrased, but the core argument is still that switching cost is underestimated"}
```

### 3.5 After the fuse

```
[SYSTEM FUSE] Both sides have fallen into substantive repetition. This topic goes straight to the final verdict stage.
```

1. `debate_closed = true`; any later stage2 submission is rejected (exit code 3);
2. The topic moves to stage 3, straight into the three-way vote;
3. The fuse record is written into the report's "process trace", including the **trigger path** (semantic / structural),
   the number of consecutive stalled rounds and the specific reason.

**A fuse is not a failure**: it acknowledges that "these two positions cannot converge through debate" and hands the decision back to the chair.
Arguing on only burns rounds and produces no new information.

---

## 4. Designing mutually exclusive three-way options

The three options must be **mutually exclusive**: not three versions of one plan, but three different roads.

### Design template

| | Option A (aggressive) | Option B (conservative) | Option C (orthogonal) |
|---|---|---|---|
| Risk | high | low | medium (but an entirely new risk type) |
| Upside | high | low | potentially very high |
| Preconditions | requires X to hold | almost no preconditions | requires stepping outside the current constraints |
| Failure mode | collapses all at once | falls behind slowly | aimed in the wrong direction |

### Passing example (review topic)

- **A aggressive**: switch everything to quarterly review, completed within three months
- **B conservative**: keep annual review, only halve the material-preparation workload
- **C orthogonal**: drop fixed review entirely and move to trigger-based review — only convene when a metric breaks the threshold

On the "review frequency" dimension the three options are **increase / unchanged / abolished** — mutually exclusive and all feasible.

### Failing examples

- ❌ A: "switch within three months"; B: "switch within six months"; C: "switch within a year"
  — only the timing differs; in essence it is the same plan;
- ❌ A: "push aggressively"; B: "push steadily"; C: "push cautiously"
  — adjectives with new skins; the script will judge this as description repetition;
- ❌ C written as "a combination of A+B"
  — that is not a third option, it is dodging the choice.

### Exclusivity check

The script detects **identical description text**. Stricter semantic exclusivity needs human judgement,
but this self-check catches most reskins:

> Read the three summaries out loud side by side. If the audience has to ask "what is the difference between these two",
> they are not mutually exclusive enough.

---

## 5. Granularity standards for the tactical action list

Four elements: **owner / start / KPI / kill**, plus Need Info.

### Owner (owner)

- ✅ must be one of the six roles (or an explicitly labelled summoned role);
- ✅ one primary owner per option; do not write "XX and YY jointly responsible";
- ❌ "the team", "everyone", "the relevant colleagues" — no subject means no accountable person.

### First step (start)

- ✅ has an action, an object and a time: "roll out trigger-based review in 2 teams this week";
- ❌ "start pushing", "kick off the project" — no executable first action.

### Key metric (KPI)

- ✅ **must contain a number**: "no more than 5 triggers within 30 days, MAU no lower than 9%";
- ✅ has an observation window (30 days) and thresholds (5 triggers / 9%);
- ❌ "improve user satisfaction", "optimise process efficiency" — no number, so success cannot be judged;
- ❌ "roughly a 10% improvement" — contains "roughly"; rejected outright.

### Kill-switch (kill)

- ✅ **must contain a number**: "if there are more than 12 triggers within 30 days, stop immediately and roll back to annual review";
- ✅ states what happens after stopping (roll back / switch to option B);
- ❌ "stop if results are bad" — "bad" is not a criterion;
- ❌ "adjust as appropriate" — consultant-speak; rejected outright.

### Further research (Need Info)

- ✅ at least one item, and it states clearly "what judgement it would change";
- ❌ an empty list — V4 considers a total absence of unknowns suspicious; it usually means the research was insufficient.

---

## 6. Common bad options and bad lists

| Bad output | Why it is bad | How to fix it |
|---|---|---|
| "Recommend further research before deciding" | consultant-speak; equivalent to not deciding | give A/B/C and pick one |
| "All three aspects must be balanced" | fence-sitting | choose one of three, and say what you give up |
| "The product team will drive this" | no subject | assign it to a specific role |
| "Expected results are good" | no numbers | give a KPI and an observation window |
| "Risk is under control" | no criterion | give a kill threshold |
| "If all goes well..." | hypothetical phrasing | delete it; write only definite actions |
| All three options called "optimisation plan" | not mutually exclusive | redesign them as three different roads |

---

## 7. A complete V4 walkthrough

**Topic**: should annual review be changed to quarterly review
**North star**: MAU

| Stage | What happened | Output |
|---|---|---|
| 0 | Loaded 1 historical memory entry, anchored the north star "MAU" | Opening line + focus rule |
| 1 | Six people each disclosed ≤150 characters, each with `[data demand]` + `[Tool Call]` + a stated position; 6 compartmentalisation manifests generated at the same time | 6 data demands, compartment visible ratio 0.17 |
| 2 | 3v3 clash, 1 interruption + 1 verification; the semantic verdict was `REPEAT` → **fuse triggered immediately** | `[SYSTEM FUSE]` + speaking rights cut |
| 3 | Straight into the three-way choice: A full quarterly switch / B trim materials only / C trigger-based review | C got 3 votes; C was decided |
| 4 | Tactical action list: owned by karpathy, live this week, both KPI and kill carry numbers | executable instructions |
| Report | Five-section V4 report | north star, verdict, tactical action list, memory |

**Key observation**: this discussion was fused back in stage 2, yet the output quality was higher —
because the fuse left the remaining rounds for "making the decision" rather than "continuing to argue".
That is the biggest difference between V4 and V3: **V4 cares about what you can do once you stop.**

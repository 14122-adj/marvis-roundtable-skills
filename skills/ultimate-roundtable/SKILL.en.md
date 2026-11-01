---
name: ultimate-roundtable
description: "Ultimate Roundtable V4.1 — a tactical decision engine for multi-agent deliberation. Six LLM personas stop role-playing and start cross-examining; attention compartmentalisation, semantic deadlock detection, and a forced verdict with a named owner, numeric KPI and numeric kill-switch. Use this skill whenever the user asks to open an ultimate roundtable, run a deep-dive deliberation, stage a red-team vs blue-team debate, run a tactical review, or wants a high-conflict discussion compressed into an executable action plan."
license: MIT
version: 4.1.0
trigger:
  - open an ultimate roundtable
  - deep-dive deliberation
  - red-team vs blue-team debate
  - tactical decision review
permission:
  - read_workspace
  - write_workspace
  - execute_tools
metadata:
  version: 4.1.0
  layer: "Layer 0+ · high-intensity deliberation (ultimate)"
  extends: roundtable-orchestrator
---

# Ultimate Roundtable V4.1 · Tactical Command

V3 solved "has the conclusion ever touched the real world". V4 attacks a harder problem:
**can this discussion stop within a bounded number of rounds, and stop somewhere that can
be executed immediately?**

Three mechanisms are added:

1. **Attention compartmentalisation** — each persona only remembers the slice of history
   inside its own lens, refusing the "brain fog" that comes from context overload.
2. **Semantic deadlock detection** — restating the same argument in different words still
   counts as repetition; **the moment it is detected, the debate is fused**, and speaking
   rights are cut.
3. **Granularity enforcement** — the final output must carry an owner, a KPI, a timeline
   and a kill-switch. "Roughly", "maybe", "we suggest" are rejected outright.

## Version history

| Version | What it solved | Key mechanisms |
|---|---|---|
| V2 | from "taking turns" to "red vs blue" | inner monologue, interruption, 3v3, sandbox, survival rate |
| V3 | from "internal reasoning" to "real-world verification" | memory wake-up, tool closure, cross-verification, sandbox tool validation |
| V4 | from "deep deliberation" to "absolute execution" | attention compartmentalisation, deadlock fuse, three-way verdict, tactical action list |
| **V4.1** | **from "literal repetition" to "semantic repetition"** | **semantic judge (REPEAT/PROGRESS/UNCERTAIN) + dual-path fuse** |

---

## Five stages (every response must follow this structure exactly)

### Stage 0 · Memory wake-up and focus anchoring

```bash
python scripts/ultimate_orchestrator.py stage0 --state S --file mem.json --write
# mem.json: {"store": "...", "north_star": "monthly active users"}
```

- Loads historical `[MEMORY_UPDATE]` entries and prints a fixed opening line:
  `[Session start] loaded historical memory: …`
- **Exactly one north-star metric must be specified** (MAU / profit margin / survival rate…).
  A missing `north_star` is rejected outright (exit code 3).
- Focus rule: `from this round on, every statement must centre on "MAU"; deviation is an
  invalid statement`.

### Stage 1 · Rapid disclosure and tool verification

**Compartmentalisation**: each persona gets at most **150 characters** (punctuation excluded);
one character over is rejected. At the same time, six **attention manifests** are generated —
one per persona — each containing only the history relevant to that persona's lens.

| Persona | Lens | What it watches |
|---|---|---|
| musk | physics & cost | constraints, magnitude, lower bounds, cost structure |
| feynman | testability | definitions, observable criteria, counter-examples |
| munger | risk & incentives | failure paths, incentive misalignment, second-order effects |
| jobs | complexity | subtraction, redundancy, steps, users |
| karpathy | reproducibility | metrics, evidence chains, baselines, experiment design |
| pg | cases | real cases, n=1, patterns, counter-examples |

The V3 three-part requirement is retained: `[data demand]` + `[tool call]` + a stated position.
A statement with no tool support is marked **low-confidence** (`low_confidence`).

### Stage 2 · Red/blue meat grinder and deadlock detection

Retains `(Inner Thought)`, `[interrupt]`, `[interrupt and verify]`, and 3v3 camps.

**Semantic deadlock detection** (V4.1): at **the end of every round the chair must decide,
internally** (without outputting the process), comparing this round's statements against the
previous round's. There is exactly one criterion:

> If the two sides merely **rephrased, substituted synonyms, or gave different examples**,
> while the **core argument, supporting data and reasoning chain** are completely unchanged,
> it counts as "semantic repetition".

| Verdict | Condition | Action |
|---|---|---|
| **Semantic repetition** | rewording / new examples / synonyms, core argument and supporting data unchanged | **fuse**, go to stage 3 |
| **Substantive progress** | new evidence, revised position, or a targeted rebuttal of a **specific phrase** | pass, debate may continue |
| **Substantive progress** | a counter-question, a challenge, or a request for data | pass, debate may continue |

Fuse triggers (meeting **either** one is enough — these are two independent conditions):

1. **Semantic repetition** → **fuse in this round immediately**, no need to wait for a second round;
2. **Two consecutive rounds with no new facts** → fuse (structural fallback: repetition + no new
   argument + no position shift + unchanged targets).

> Note the thresholds differ: semantic repetition is "as soon as detected" and **fires in a
> single round**; only the structural fallback requires "two consecutive rounds". Do not
> mis-write this as "semantic repetition also needs two rounds".

On trigger, print the fixed line and **cut speaking rights**:

```
[SYSTEM FUSE] Both sides have fallen into substantive repetition. This topic goes straight to the final verdict stage.
```

After a fuse, any further stage2 submission is rejected (exit code 3); the only way forward is
stage 3.

**How the two paths cooperate**:

- **Semantic path (primary)**: the chair labels each "previous round vs this round" pair as
  `[REPEAT]` / `[PROGRESS]` / `[UNCERTAIN]` and writes it back to `semantic_verdicts`. A single
  `PROGRESS` in the round is enough to pass; only `REPEAT` counts as repetition. Every record
  carries `from`/`to`/`label`/`reason` and is **auditable**.
- **Structural path (fallback)**: with no semantic verdict, fall back to character similarity
  ≥ 0.55 plus three counters.

> Why the semantic path is needed: a paraphrased repetition often scores only 0.0x on character
> similarity, so the structural path cannot see it. And "I think they are repeating" is just the
> chair's feeling unless it is recorded with a reason.

```bash
# 1) produce the material to judge (the model judges from it, without outputting the process)
python $UR/deadlock_detector.py judge --state S

# 2) write back the semantic verdicts
python $UR/deadlock_detector.py record --state S --file verdicts.json

# 3) decide whether to fuse (--write fuses automatically and cuts speaking rights)
python $UR/deadlock_detector.py check --state S --write
```

Shape of `verdicts.json`:

```json
[{"round": 3, "from": "munger", "to": "munger", "label": "REPEAT",
  "reason": "rephrased, but the core argument is still that switching cost is underestimated"}]
```

`stage2` can also carry a `semantic_verdicts` array directly, completing "sparring + semantic
verdict" in one submission.

### Stage 3 · Iron verdict and the three-way choice

**No fence-sitting**: three mutually exclusive options must be produced, and their descriptions
must not be the same sentence in a different costume.

| Option | Positioning |
|---|---|
| A | Aggressive: high upside, high risk |
| B | Conservative: low upside, low risk |
| C | Wildcard: a physics / dimensional-reduction solution that escapes the current frame |

All six personas cast a final vote with reasons (no further mutual debate). The chair picks one
of A/B/C; if the pick differs from the option with the most votes, `decision_reason` must be
recorded (otherwise a warning is emitted).

### Stage 4 · Tactical action list + memory consolidation

Missing any of the four elements is rejected, and KPI and Kill **must contain concrete numbers**:

```json
{
  "owner": "karpathy",
  "start": "Roll out trigger-based review to 2 teams this week, threshold set at MAU falling below 8%",
  "kpi": "No more than 5 triggers in 30 days, MAU no lower than 9%",
  "kill": "If there are more than 12 triggers in 30 days, stop immediately and roll back to annual review",
  "need_info": ["average person-hours per review over the past two years"]
}
```

Vague wording such as "roughly / maybe / as appropriate / depending on the situation / we
suggest further" is rejected outright.

---

## Quantitative models

### Spark criteria (carried over from V2/V3)

`attack_count ≥ 3`, `defense_count ≥ 2`, `target_spread ≥ 2`, `signal_total ≥ 3`,
`hollow_ratio ≤ 0.34`, `unmet_must_respond` empty. Any failure → exit code 4.

### Deadlock criteria (V4.1 dual path)

| Path | Criterion | Threshold |
|---|---|---|
| **Semantic (primary)** | this round has `REPEAT > 0` and `PROGRESS == 0` | **fuses in a single round** |
| **Structural (fallback)** | similarity ≥ 0.55 + no new argument + no position shift + unchanged targets | **requires 2 consecutive rounds** |

`check` emits a `trigger` field naming the path taken (`semantic` / `structural`), plus
`semantic_coverage` reporting how many statement pairs were judged. The semantic path also emits
`semantic_repeat_immediate: true`, marking this as an "immediate fuse".

**Pass rule**: a single `PROGRESS` in the round (new evidence / revised position / targeted
rebuttal / counter-question / request for data) is enough to pass, even if structural similarity
is very high — because new evidence can absolutely be phrased in similar words.

### Survival rate (optional, demoted to process record)

```
survival = 0.40×risk_residual + 0.25×evidence_coverage
         + 0.20×defense_quality + 0.15×plan_integrity
```

V4 cares about execution, so the survival rate only appears in the process record when the
`sandbox` subcommand has been run.

---

## Command line

```bash
UR=scripts

# Stage 0 (north_star is mandatory)
python $UR/ultimate_orchestrator.py init   --topic "topic" --out DIR
python $UR/ultimate_orchestrator.py stage0 --state S --file mem.json     --write

# Stages 1-4
python $UR/ultimate_orchestrator.py stage1 --state S --file roles.json   --write
python $UR/ultimate_orchestrator.py stage2 --state S --file clash.json   --write
python $UR/ultimate_orchestrator.py stage3 --state S --file vote.json    --write   # three-way choice
python $UR/ultimate_orchestrator.py stage4 --state S --file action.json  --write   # tactical list

# Optional: sandbox simulation (does not overwrite the three-way verdict)
python $UR/ultimate_orchestrator.py sandbox --state S --file sandbox.json --write

# Report and checks
python $UR/ultimate_orchestrator.py check  --state S
python $UR/ultimate_orchestrator.py report --state S --out REPORT.md

# Standalone tools
python $UR/attention_split.py  plan --state S --role pg --write    # compartmentalisation
python $UR/attention_split.py  check --state S                     # manifest + 150-char gate
python $UR/attention_split.py  lenses                              # print the six lenses

# Semantic deadlock detection (three-piece set)
python $UR/deadlock_detector.py judge  --state S                   # produce material to judge
python $UR/deadlock_detector.py record --state S --file v.json     # write back verdicts
python $UR/deadlock_detector.py check  --state S [--write]         # judge + auto fuse
python $UR/deadlock_detector.py fuse   --state S                   # manual fuse

python $UR/clash_analyzer.py spark    --state S --round 2
python $UR/memory_store.py recall --query review
```

**Exit codes**: 0 pass | 2 bad arguments | 3 stage validation failed | **4 no spark in the
red/blue clash — must reopen**.

---

## Input formats

Stage 0 `mem.json`:

```json
{"store": ".ultimate/memories.jsonl", "north_star": "MAU"}
```

Stage 1 `roles.json` (≤150 characters + mentions the north star + three-part closure):

```json
{"confessions": [
  {"role": "musk",
   "text": "The main constraint on MAU growth is acquisition cost. [data demand: need CAC for the past 6 months] "
           "[Tool Call: Search] keywords: SaaS CAC benchmark. Based on this data, my view is: CAC is near its ceiling.",
   "tool_result": {"source": "tool", "tool": "web_search", "query": "…", "result": "…"}}
]}
```

Stage 3 `vote.json`:

```json
{
  "options": {
    "A": {"summary": "Switch everything to quarterly review within three months"},
    "B": {"summary": "Keep annual review, only halve the preparation workload"},
    "C": {"summary": "Drop fixed reviews entirely; trigger review only when the metric breaks the threshold"}
  },
  "votes": {"musk": "A", "feynman": "C", "munger": "B",
            "jobs": "C", "karpathy": "C", "pg": "B"},
  "vote_reasons": {"musk": "the MAU window is only three months", "feynman": "the trigger has an observable criterion", "...": "..."},
  "decision": "C",
  "decision_reason": "C has 3 votes and an observable criterion; A's downside risk was never defended"
}
```

---

## Output format (V4.1 frozen, do not change)

```markdown
### ⚔️ Ultimate Roundtable Decision Report V4.1

#### 📌 1. North-star metric and baseline assumptions
- Core metric of this run: xxx
- Hidden assumption we broke: xxx

#### 🔗 2. Evidence chain and external verification
- External data / tool results adopted: xxx

#### 🚦 3. Iron verdict (one of three)
- **Aggressive Option A**: [summary] (votes: xxx)
- **Conservative Option B**: [summary] (votes: xxx)
- **Orthogonal Option C**: [summary] (votes: xxx)
- 🏆 **Final decision**: adopt option [X]

#### 🎯 4. Tactical action items
- **Owner**: [named persona]
- **Start**: xxx
- **KPI**: xxx
- **Kill-switch**: xxx
- **Need info**: xxx

#### 🧠 5. Long-term memory write
- `[MEMORY_UPDATE]`: xxx
```

`report` errors out (exit code 3) in any of these cases: missing north star, missing decision,
missing owner/start/kpi/kill, KPI or Kill without a number, banned wording (`consensus reached` /
`verified` / `I think it is fine` / `each has merits`) or **consultant-speak** (`on one hand` /
`on the other hand` / `it depends` / `all things considered` / `roughly` / `maybe`).

---

## Anti-patterns

1. ❌ Opening a session with no north-star metric — V4 requires a single focus; it is rejected.
2. ❌ A persona speaking more than 150 characters — compartmentalisation exists to filter padding.
3. ❌ A statement that never mentions the north star — treated as invalid and rejected.
4. ❌ Continuing to argue while the two sides are repeating — semantic repetition fuses on detection.
5. ❌ Sneaking in another stage2 after a fuse — rejected; the only path is the three-way choice.
6. ❌ Judging repetition by character similarity alone — paraphrased repetition often scores 0.0x;
   a semantic verdict is mandatory.
7. ❌ Writing a semantic verdict with no reason — `reason` is the only evidence for that verdict.
8. ❌ Treating `[UNCERTAIN]` as `[PROGRESS]` — undecided is undecided; the structural path handles it.
9. ❌ Three options that are the same sentence in different costumes — the exclusivity check rejects it.
10. ❌ An action list saying "improve communication" or "keep optimising" — no owner, no number, no use.
11. ❌ A kill-switch saying "stop if results are bad" — a decidable threshold is required.
12. ❌ "On one hand… on the other hand…" in the report — consultant-speak errors out.
13. ❌ A decision that differs from the majority vote without a recorded reason — warns, and must be traceable.

---

## Boundaries

- This skill **does not replace** `roundtable-orchestrator`: that one compresses decisions,
  it does not excavate premises.
- The six personas' thinking protocols live in the `role-*` skills; **if they are not installed**,
  first run `host-bootstrap` to detect and deploy them, otherwise the output must declare
  "⚠ degraded mode".
- **The semantic verdict is made by the chair (the model); the scripts only organise material and
  record verdicts.** `deadlock_detector.py` cannot call an LLM: `judge` emits the material,
  `record` collects labels, `check` decides from them. So "semantic-level" accuracy depends on the
  model doing the judging; what the scripts guarantee is that **the process is auditable**
  (every verdict carries from/to/label/reason), not that the verdict is absolutely correct.
- **The structural path is still there**: it is the fallback when no semantic verdict exists. It
  cannot catch paraphrased repetition, but it does catch verbatim repetition — the two paths are
  complementary, not substitutes.
- **Compartmentalisation only affects "what you can see"**; it never rewrites any original text.
  Content in `muted` must not be quoted; when pressed, a persona should admit "that was not in my
  lens".
- The survival rate is demoted to a reference metric in V4, because "a plan that can be executed"
  matters more than "a plan with an 80% survival rate".

## Reference files

Every reference below exists in both Chinese (`X.md`) and English (`X.en.md`). When this English
skill is packaged for the marketplace, the `.en.md` files are shipped as `X.md`.

- `references/adversarial-tactics.en.md`: red/blue tactics, how to write inner monologue,
  interruption triggers, summon criteria, threshold tuning.
- `references/report-template.en.md`: report template, hand-computable survival example, per-stage
  JSON field reference.
- `references/tool-protocol.en.md`: tool-call protocol (Search/Code syntax, real vs simulated
  boundary, closure validation, verification verdicts).
- `references/tactical-playbook.en.md`: **new in V4** — choosing a north star, tuning compartment
  lenses, deadlock criteria in detail, designing mutually exclusive options, granularity standards
  for the tactical list (what a passing owner/KPI/Kill looks like, with counter-examples).
  **Read it when organising stages 3 and 4.**

# Adversarial Tactics Handbook

The operating manual for Stage 2 of `ultimate-roundtable`. It answers three questions: **how the blue team attacks, how the red team defends, and what actually counts as a spark.**

## Contents

1. Blue team (devil's advocate) tactics list
2. Red team (defender) tactics list
3. Inner monologue: how to write it, and what is forbidden
4. Trigger conditions for dynamic interruption
5. Criteria for summoning an ad-hoc role
6. Spark threshold tuning guide
7. Three complete confrontation fragments

---

## 1. Blue Team Tactics List

The blue team's job is not to "raise a different opinion" — it is to **prove this plan will fail**. Nine moves; use at least three different ones per round:

| Tactic | Move | Criterion (missing it means a hollow attack) |
|---|---|---|
| **Failure-path back-cast** | Assume the plan has already failed, then work backwards to how it died | Must give 3+ concrete failure paths; "it might fail" does not count |
| **Premise attack** | Point out an assumption the plan depends on but never verified | Must name a specific claim id or the exact assumption text |
| **Magnitude attack** | Show that some number is off by an order of magnitude | Must show your own estimation path |
| **Second-order effects** | The chain reaction the plan sets off once it works | Must state "who gets hurt by this, and how they will react" |
| **Incentive misalignment** | The executors' incentives do not match the goal | Must name the concrete appraisal/budget/promotion mechanism |
| **Timescale mismatch** | The conclusion only holds inside one time window | Must state what happens outside that window |
| **Worst-case walk** | Follow the worst path all the way down | Must give an observable loss metric |
| **Counter-example search** | Find a real case whose conclusion contradicts the plan's | Must be verifiable; fabricated cases are not allowed |
| **Cost transfer** | The plan shifts cost onto a third party nobody mentioned | Must name that third party |

**Forbidden blue-team moves**:
- Opposing for the sake of opposing (cannot name a concrete failure mechanism);
- Attacking wording instead of substance ("this statement isn't rigorous enough");
- Attacking a point that is already defended (wasted work, and it drags down spark quality).

---

## 2. Red Team Tactics List

The red team's job is not "defending" — it is **repair**. A red team that can only say "this plan is right" is an invalid red team.

| Tactic | Move | Criterion |
|---|---|---|
| **Narrow the conditions** | Concede the attack holds, but narrow the conclusion to the range where it does | Must state clearly "under what conditions it still holds" |
| **Quantified rebuttal** | Use orders of magnitude to show the risk is not fatal | Must give an estimate |
| **Cost comparison** | Cost of this risk vs cost of not doing it | Must give numbers on both sides |
| **Mitigation** | What mechanism blocks this risk | Must be an executable mechanism, not "tighten management" |
| **Evidence reinforcement** | Produce evidence that directly rebuts the attack | Must label the source and whether it is simulated |
| **Accept and revise** | Concede the attack is valid and change the plan | **The highest-quality red-team move** — it triggers a valid position revision |

**Key discipline**: the red team **is allowed to concede**. Conceding and revising the plan raises the final survival rate more than digging in,
because in the survival-rate model `defense_quality` counts "whether the attack was effectively answered",
and "concede and redesign" also counts as an effective answer (`defended: true`), while "no answer" does not.

---

## 3. Inner Monologue: How to Write It, and What Is Forbidden

**Format**: `(Inner Thought: ...)`, placed at the very front of that role's speech.

**What it is**: an **interest or concern** that is not said out loud. Three sources:
1. **Interest**: what this plan does to me (budget, headcount, power, time);
2. **Concern**: what I worry about but am embarrassed to say (afraid of offending someone, afraid of exposing that I do not understand, afraid of being held accountable);
3. **Probing**: I am watching to see who speaks first so I can decide which side to take.

**Acceptable samples**:
- `(Inner Thought: This plan will cut the budget for my line. I can't say that directly, so I have to question its data basis first.)`
- `(Inner Thought: I didn't actually follow his derivation, but I'll act skeptical first and see whether he can hold it together.)`
- `(Inner Thought: I agree, but I don't want to be the first to say so. Let's wait for Musk to speak.)`

**Unacceptable samples (forbidden)**:
- ❌ `(Inner Thought: I feel a lot of pressure.)` — psychological description, no interest and no judgment;
- ❌ `(Inner Thought: I think he's right.)` — this only paraphrases the spoken line, i.e. no inner monologue at all;
- ❌ `(Inner Thought: I despise him.)` — an emotion label, carries no information;
- ❌ The inner monologue has nothing to do with the speech that follows (thinking A, saying B, but no tension between B and A).

**Test**: after reading the inner monologue, the reader should be able to answer "**why is he saying this**".
If you cannot read a motive out of it, the inner monologue is unacceptable.

---

## 4. Trigger Conditions for Dynamic Interruption

`[interrupt]` is allowed only when one of the following holds:

1. **Unverified critical assumption**: the other side's conclusion rests on a premise nobody has verified;
2. **Magnitude clearly wrong**: the number they give differs from your own estimate by more than an order of magnitude;
3. **Concept substitution**: the same word means something different in two consecutive sentences;
4. **Circular argument**: A rests on B and B rests on A;
5. **Non-reproducible evidence**: the data they cite has no source or cannot be checked by a third party.

**Not valid reasons to interrupt** (using them is judged an invalid exchange):
- "I disagree" (without saying why);
- "This isn't comprehensive enough" (a catch-all criticism);
- A question the other side has already answered (repeated pressing);
- Purely a matter of tone/wording.

After an interruption you must give a **concrete challenge**, not just "you're wrong".
Acceptable: `[interrupt] Your M1-1 assumes the organization is willing to change its appraisal, but G1-1 already establishes that the appraisal cycle is one year. These two conflict.`
Unacceptable: `[interrupt] There's a problem with what you're saying.`

---

## 5. Criteria for Summoning an Ad-hoc Role

Summon in Stage 3 only when the following occurs.

### 5.1 Professional Perspective (Cross-domain Blind Spot)

| Trigger | Example summon | Must state clearly |
|---|---|---|
| The plan touches law/compliance/award rules | Legal expert | Which rule gets triggered |
| Touches regulation and policy change | Policy adviser | Which policy window, at what point in time |
| Touches supply chain/capacity | Supply-chain expert | Which link breaks |
| Touches security/privacy | Security expert | Attack surface and compliance obligations |
| Touches finance and cash flow | Finance expert | At what point cash flow breaks |

### 5.2 Layperson Perspective (Elite Blind Spot)

All six roles are elite perspectives. Real decisions go wrong not because the strategy was wrong,
but because **nobody asked the person who has to use it every day**.

| Trigger | Summon | Must state clearly |
|---|---|---|
| All six **vote yes**, nobody objects | Novice user | Where he gets stuck the first time he touches it |
| The plan contains new concepts/processes the user must learn | Novice user | How many steps to learn, whether he gives up |
| "Users should be able to…" or "users will understand" appears in the discussion | Angry customer | Which specific step enrages him |
| The plan shifts cost onto the end user | Frontline executor | Who does extra work, and how much |
| The plan promises a response time/SLA but nobody counted the headcount | Frontline support agent | Who absorbs the peak |

**Unanimous approval is the strongest summon signal**: six people all agreeing usually means they share one blind spot.
`synthesis_generator.check()` marks this signal as `consensus_suspect`.

**Three hard constraints on layperson roles** (otherwise the summon degrades into "speaking on behalf of users"):

1. **Must be concrete**: "users will find it complicated" fails; "I need 4 clicks to submit, and step 3 requires 7 fields" passes;
2. **Must carry numbers**: clicks, field counts, navigation counts, wait time — if you cannot produce numbers, you are not really standing in the user's position;
3. **Zero-cost suggestions such as "add a guide" are not allowed**: any suggestion must also state what cost it adds, and to whom.

**Summoning is not padding the headcount**: if no cross-domain blind spot or elite blind spot appeared, write "no summons this round" in the report;
that is worth more than forcing in a "marketing expert".

A summoned role speaks exactly once, is written into `summons`, and takes no part in later rounds
(it lacks the context of the first two rounds; forcing it in produces pseudo-argumentation).

---

## 6. Spark Threshold Tuning Guide

Default thresholds live in `DEFAULT_THRESHOLDS` in `clash_analyzer.py` and can be overridden in the state file:

```json
{"clash_thresholds": {"min_attack": 4, "min_defense": 3, "min_targets": 3,
                      "min_signal": 5, "max_hollow_ratio": 0.25}}
```

| Scenario | Recommendation |
|---|---|
| Small topic (2–3 person discussion) | Lower to `min_attack: 2, min_defense: 1, min_targets: 1` |
| High-risk decision (irreversible) | Raise to `min_attack: 5, min_defense: 4, max_hollow_ratio: 0.15` |
| Exploration phase (not yet formed) | Keep the defaults; no spark here is a normal signal — it means the plan has not yet matured enough to be attacked |

**Never set the thresholds to 0**: that is equivalent to switching off the "no fence-sitting" rule,
and that rule is exactly what distinguishes this skill from an ordinary roundtable.

---

## 7. Three Complete Confrontation Fragments

### Fragment A · Premise attack + quantified rebuttal (valid exchange)

```
(Inner Thought: His lower-bound derivation never counted packaging cost, but saying that straight out will get me written off as an amateur. I'll come in through the data basis first.)
[interrupt] Your M1-1 assumes cost is driven mainly by propellant, but P2-1 already points out that packaging cost appears in order to match the review criteria,
and these two conflict at least at the review stage. — blue team munger

(Inner Thought: I did miss packaging cost, but the magnitude may not be enough to overturn the conclusion. Give the numbers first.)
Accepted, but by the example magnitude packaging cost is only 3% of total investment, not enough to overturn the lower-bound conclusion.
I'll write it into M2-1 and state the overturn condition: if the measured share exceeds 15%, my conclusion flips. — red team musk
```

**Why it counts as a spark**: the attack has a target (M1-1), a basis (P2-1), and a concrete point of conflict;
the defence does not dig in but concedes + quantifies + states an overturn condition.

### Fragment B · Fake clash (judged hollow)

```
(Inner Thought: Whatever.)
I think munger makes a good point, but musk has a point too. We can take both into consideration. — red team feynman
```

**Why it does not count**: no target, no evidence, pure position-taking; it hits the hollow-phrase list ("good point", "take both into consideration").

### Fragment C · Concession-style repair (highest quality)

```
(Inner Thought: He landed that one. Digging in will only make the plan die harder in the sandbox, so I'd rather change it now.)
That holds. I withdraw "switch everything at once" and change it to "run a three-month controlled pilot on first-level review",
and add to Need Info: I need the records of what review blocked over the past two years. — red team karpathy
```

**Why it is the highest quality**: concede + redesign + add Need Info, all three in one pass;
it raises `defense_quality` (the attack was effectively answered) and hands the sandbox an executable input.

# Tool Calling Protocol

The core discipline of `ultimate-roundtable` V3.0: **data demands must close the loop**.
This document specifies `[Tool Call]`, the real/simulated boundary, closed-loop validation, and how `[interrupt and verify]` works in practice.

## Contents

1. The two kinds of tool call
2. The real vs simulated boundary
3. The three elements of a closed loop
4. Verification (`[interrupt and verify]`)
5. Tool requirements for the sandbox stage
6. Common errors and their verdicts
7. What to do in an environment with no tool capability

---

## 1. The Two Kinds of Tool Call

### Search

```
[Tool Call: Search] keywords: quarterly review context-switching cost case study
```

- Purpose: find **external facts** — public data, cases, standards, policy text;
- Keywords must be written out (not "look up some related material");
- After getting the result you must immediately write `Based on this data, my view is…`.

### Code

```
[Tool Call: Code] purpose: verify what share of packaging cost makes the conclusion flip
```python
base = 100
packaging = 0.12
print("share", packaging, "→", "flipped" if packaging > 0.15 else "unchanged")
```
```

- Purpose: **verify a computable judgment** — magnitude estimates, thresholds, sensitivity;
- Code must be short (under 10 lines), reproducible, and free of external file dependencies;
- The run result must be pasted verbatim; "ran it, looks about right" is not acceptable.

---

## 2. The Real vs Simulated Boundary

| Case | How to label it |
|---|---|
| The host really did run the search/code | `{"source": "tool", "tool": "web_search", "result": "…"}` |
| The host has no tool capability, result constructed by reasoning | `{"source": "text", "simulated": true, "result": "…"}` |

**Three red lines**:

1. `source: "tool"` and `simulated: true` **must never appear together** (self-contradictory);
2. Neither is labelled → judged as "passing simulated data off as real data", **refused entry to the next stage**;
3. The report header prints "Stage 1 real N / simulated M; sandbox real X / simulated Y" —
   this number cannot be changed; it is the reader's only basis for judging the quality of the evidence.

**Discipline for writing simulated data**: prefix the result with `(simulated)` or `simulated: true`,
and be clear in your own head: **simulated data can only demonstrate a mechanism, never support a real decision.**

---

## 3. The Three Elements of a Closed Loop

For a role's speech to count as "closed", all three must be present (the script checks each one; missing any one rejects the whole thing):

| Element | Regex | Meaning |
|---|---|---|
| Data demand | `\[data demand:\s*(.+?)\]` | What data I depend on |
| Tool call | `\[Tool Call:\s*(Search\|Code)\]` | How I obtained it |
| Explicit position | `Based on (this\|that\|the) (data\|result\|verification)` | How my judgment changes once I have it |

**Unacceptable samples**:

```
❌ I need more data before I can judge.                       (demand, no call, no position)
❌ [data demand: need the retention curve] I think retention will drop.   (demand, no call)
❌ [Tool Call: Search] keywords: retention.                   (call, no demand, no position)
❌ Found it, retention did drop.                              (no demand, no call, no standard position sentence)
```

**Acceptable sample**:

```
✅ My conclusion depends on the retention baseline. [data demand: need the monthly retention curve for the past 12 months]
   [Tool Call: Search] keywords: SaaS monthly retention benchmark.
   Based on this data, my view is: an 8% drop in retention is normal fluctuation and is not grounds for a veto.
```

---

## 4. Verification (`[interrupt and verify]`)

A debate action added in V3. How it differs from a plain `[interrupt]`:

| | `[interrupt]` | `[interrupt and verify]` |
|---|---|---|
| What it does | Points out that the other side's assumption is unverified | Points out + **goes and checks on the spot** |
| Requirement | Give a concrete challenge | Challenge + `[Tool Call]` or `verify_result` |
| Consequence of a missing result | Recorded as an invalid exchange | **Stage 2 rejects outright** |

The three `verdict` values of `verify_result`:

| verdict | Meaning | Follow-up requirement |
|---|---|---|
| `supported` | The check supports the other side's claim | The interrupting side must concede, or explain why the evidence is insufficient |
| `refuted` | The check overturns the other side's claim | The challenged side must revise or produce counter-evidence |
| `inconclusive` | No decisive evidence found | The premise must be logged as `Need Info` and must not be treated as resolved |

**Interrupting without verifying is the worst behavior**: it makes the discussion look like it is making substantive progress while in fact nobody gained new information.

---

## 5. Tool Requirements for the Sandbox Stage

Stage 3's `sandbox.tool_calls` must have at least 1 entry, and it must:

- Have `purpose` state which **assumption** is being verified (not "see how things look");
- For type `Code`, include a `code` field, with code that runs standalone;
- Have a non-empty `result` (an empty result equals no verification);
- Follow the same real/simulated labelling.

**Why the sandbox requires tools**: the V2 sandbox was "simulated data forcing a revision";
V3 requires at least one number to be **computed** rather than invented —
this is the dividing line between "internal derivation" and "real-world verification".

---

## 6. Common Errors and Verdicts

| Error | Script verdict | Exit code |
|---|---|---|
| `[data demand]` with no `[Tool Call]` | Stage 1 failure | 3 |
| `[Tool Call]` with no position sentence | Stage 1 failure | 3 |
| `source: tool` + `simulated: true` | Stage 1 failure | 3 |
| Neither labelled | Stage 1 failure (disguised data) | 3 |
| `[interrupt and verify]` with no result | Stage 2 failure | 3 |
| Sandbox has no `tool_calls` | Stage 3 failure | 3 |
| `Code` call missing `code` | Stage 3 failure | 3 |
| Insufficient attacks / all hollow statements | Stage 2 `no_spark` | **4** |

---

## 7. What to Do in an Environment with No Tool Capability

Some hosts (pure text chat) have no search or code execution. In that case:

1. **Still write `[Tool Call]`**, but `tool_result` must be labelled `simulated: true`;
2. The report header statistics will honestly show "real 0 / simulated 6" — **this is not a failure, it is honesty**;
3. Every place in the conclusion that depends on simulated data must go into the `Need Info` column,
   and the text must state "this number is constructed and needs to be replaced by a real measurement".

> Better to hand in a report that says "all data is simulated"
> than one where the reader cannot tell which entry is real.

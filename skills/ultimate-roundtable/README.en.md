# English edition

The skill ships in two languages. Both are complete and structurally identical.

| Language | Files | Bundled as |
|---|---|---|
| Chinese | `SKILL.md`, `references/X.md` | `dist/market/ultimate-roundtable-v1.7.0.zip` |
| English | `SKILL.en.md`, `references/X.en.md` | `dist/market-en/ultimate-roundtable-v1.7.0-en.zip` |

---

## Build

```bash
# Chinese market bundle
python tools/package_bundle.py market --version 1.7.0 --only ultimate-roundtable

# English market bundle
python tools/package_bundle.py market --version 1.7.0 --lang en --only ultimate-roundtable

# Verify either
python tools/package_bundle.py verify-market --dir dist/market
python tools/package_bundle.py verify-market --dir dist/market-en
```

The English bundle is **not** a different skill. `SKILL.en.md` is written into the ZIP as
`SKILL.md`, and `references/X.en.md` becomes `references/X.md` — because an agent only looks for
those exact filenames.

---

## What was translated

| File | Lines | CJK in English version |
|---|---|---|
| `SKILL.md` | 353 | 0 |
| `references/adversarial-tactics.md` | — | 0 |
| `references/tool-protocol.md` | — | 0 |
| `references/report-template.md` | 246 | 0 |
| `references/tactical-playbook.md` | 253 | 0 |

Headings and code-block counts match the Chinese source 1:1, so the two versions stay in sync.

**Not translated** (deliberately): Python scripts, JSON field names, role ids, claim id patterns,
basis/response enums, exit codes, thresholds. Those are protocol, not prose — translating them would
break the contract.

---

## Keeping them in sync

When you change `SKILL.md` or a reference, change the `.en.md` twin in the same commit. There is no
automatic check for drift yet; a stale translation is worse than no translation, because English
buyers will follow instructions that no longer match the code.

A cheap guard before committing:

```bash
# heading counts must match between the two languages
for f in SKILL references/adversarial-tactics references/tool-protocol \
         references/report-template references/tactical-playbook; do
  zh=$(grep -c '^#' "skills/ultimate-roundtable/$f.md")
  en=$(grep -c '^#' "skills/ultimate-roundtable/$f.en.md")
  echo "$f: $zh vs $en"
done
```

---

## A bug this translation surfaced

Translating `report-template.md` revealed that its §1 still documented the **V2/V3 report format**
(consensus / hidden assumptions / action items / sandbox survival / memory), while `SKILL.md` and
`ultimate_orchestrator.py` had already moved to the **V4 five-section format**
(north star / evidence chain / verdict / action items / memory).

Both language versions are now corrected, and the eval `artifact-ultimate-report-sections` was
updated to assert the V4 section names instead of the old ones. If the English edition had been
produced by machine-translating without reading, the inconsistency would have shipped silently in
two languages.

---

## Listing copy

The English marketplace listing copy lives in `docs/agensi-listing.md`. The short description is:

```
Turn 6 LLM personas (Musk, Feynman, Munger, etc.) into a ruthless, multi-agent decision-making engine.
```

# Lane Contract

Each lane directory lives at:

```text
lanes/<lane>/<agent>/
```

`bootstrap-lanes` creates `lane-input.md` for every lane. The agent or human then fills the remaining files.

Required files:

```text
lane-input.md
lane-output.md
lane-output.json
claim-ledger.json
verdict.json
evidence/
```

Additional final-required file for `critic`:

```text
rubric-score.json
```

## Status Model

Lane work should be treated as one of:

- `empty`: lane exists, output not started.
- `draft`: output exists but has placeholder claims or missing proof.
- `needs-human`: user must confirm a fact, consent, quote, or schedule.
- `ready`: lane output can be considered for assembly.
- `verified`: finalizer or critic checked it against evidence.
- `rejected`: output must not be merged.

Current CLI enforces `verdict.status` as:

- `pass`
- `needs-work`
- `blocked`

## Claim Status

- `real`: directly supported by evidence.
- `derived`: derived from real evidence and method is recorded.
- `expected`: clearly-labeled 예상값(가상) — text or notes must contain "예상" or "가상", enforced by `check`.
- `placeholder`: unresolved draft gap, usable in drafts only.
- `forbidden`: must not enter report.

Final candidate accepts `real` and `derived` (both need an evidence path). With `check --final --allow-expected`, labeled `expected` claims are also accepted and listed in `output/expected-claims.md` for later replacement. `placeholder` never passes final.

## Merge Rule

No lane output merges into a final bundle unless:

1. Required files exist.
2. JSON parses.
3. Verdict is `pass`.
4. Every final `real`/`derived` claim has evidence (labeled `expected` claims need `--allow-expected` instead).
5. Every final evidence path is workspace-relative and does not point at `input/raw_private/`.
6. Every production lane has at least one complete agent output.
7. `critic/rubric-score.json` has at least 5 criteria, evidence/risk/fix per criterion, and total score at or above 85%.
8. No final forbidden marker exists.
9. Required assembled bundle files exist.
10. `bundle-manifest.json` has no missing source lanes.

## Critic Rubric Score

`critic` writes a scoring file:

```json
{
  "total_score": 90,
  "max_score": 100,
  "items": [
    {
      "criterion": "학생 변화 근거",
      "score": 18,
      "max_score": 20,
      "evidence": "설문·산출물 근거",
      "risk": "수치 과장 시 감점",
      "fix": "소표본 한계 명시"
    }
  ]
}
```

`total_score` and `max_score` must equal the sum of item scores. Final target is 85% or higher.

## Final Bundle

`assemble` writes:

```text
output/report-draft.md
output/summary-sheet.md
output/toc.md
output/appendix.md
output/finalization-checklist.md
output/bundle-manifest.json
```

This bundle is not a finished `.hwpx`. It is the controlled handoff package for the HWPX finalizer.

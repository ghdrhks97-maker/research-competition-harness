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
- `placeholder`: usable in drafts only.
- `forbidden`: must not enter report.

Final candidate accepts only `real` and `derived`, and both need an evidence path.

## Merge Rule

No lane output merges into a final bundle unless:

1. Required files exist.
2. JSON parses.
3. Verdict is not blocked.
4. Every final claim has evidence.
5. No final forbidden marker exists.
6. Required assembled bundle files exist.
7. `bundle-manifest.json` has no missing source lanes.

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

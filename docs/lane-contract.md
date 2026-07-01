# Lane Contract

Each lane directory lives at:

```text
lanes/<lane>/<agent>/
```

Required files:

```text
lane-input.md
lane-output.md
lane-output.json
claim-ledger.json
verdict.json
evidence/
```

## Claim Status

- `real`: directly supported by evidence.
- `derived`: derived from real evidence and method is recorded.
- `placeholder`: usable in drafts only.
- `forbidden`: must not enter report.

Final candidate accepts only `real` and `derived`.

## Merge Rule

No lane output merges into final report unless:

1. Required files exist.
2. JSON parses.
3. Verdict is not blocked.
4. Every final claim has evidence.
5. No final forbidden marker exists.

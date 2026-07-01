# Architecture

## Conductor + Lanes

This harness separates generation from final assembly.

Parallel agents can produce:

- brainstorm candidates,
- reference-report pattern extractions,
- claim-tagged manuscript drafts,
- table-first layout plans,
- one-page summary plans,
- icon and visual asset manifests,
- adversarial critiques.

Only the finalizer writes HWPX. This prevents package corruption and version-lineage confusion.

## Lane Contract

Every lane emits:

- `lane-output.md`: human-readable result.
- `lane-output.json`: machine-readable summary.
- `claim-ledger.json`: factual claim statuses and evidence paths.
- `verdict.json`: pass/needs-work/blocked.
- `evidence/`: supporting artifacts.

## Gates

1. Rule and rubric gate.
2. Evidence and claim ledger gate.
3. Reference-pattern gate.
4. Draft and table-layout gate.
5. HWPX package gate.
6. Render and Hancom/HOP gate.
7. ULW-style closure gate.

## Agent Roles

- Codex: schemas, HWPX tooling, Python validation, finalizer.
- Antigravity: ideation and visual/report-structure proposals through file-based inbox.
- Claude/Gemini: reference reading and critique.
- Human: only real evidence and owner facts.

# Architecture

## Current Capability

This harness is a report-production operating system, not a fully autonomous AI runner.

It currently:

- creates a competition workspace,
- creates lane-specific Korean prompt/instruction packs,
- gives each agent a fixed file contract,
- checks claim ledgers and final forbidden markers,
- assembles lane outputs into report/summary/toc/appendix/checklist markdown bundle,
- blocks final bundle completion when required bundle files or source lanes are missing.

It does not currently:

- call Codex, Antigravity, Claude, Gemini, or Hancom by itself,
- read raw photos or survey spreadsheets automatically,
- generate a finished `.hwpx` file,
- prove Hancom-rendered page count.

External agents or humans still fill lane outputs. The harness keeps those outputs organized and safer to merge.

## Conductor + Lanes

The conductor is the CLI in `src/rch/cli.py`.

It separates generation from final assembly. Parallel agents work in lane folders. The finalizer owns the final report bundle and later HWPX assembly plan.

Main commands:

```bash
PYTHONPATH=src python3 -m rch.cli init <workspace>
PYTHONPATH=src python3 -m rch.cli bootstrap-lanes <workspace> <agent>
PYTHONPATH=src python3 -m rch.cli assemble <workspace>
PYTHONPATH=src python3 -m rch.cli check <workspace> --final
```

## Lane Set

- `intake`: classify ideas, rules, references, photos, surveys, evidence, privacy risk.
- `brainstorm`: title, research question, instructional model, practical tasks.
- `reference-miner`: extract structure and patterns from reference reports.
- `evidence-curator`: connect claims to real evidence.
- `survey-analyzer`: summarize survey data and limits.
- `photo-curator`: classify photos by scene, privacy, and report use.
- `draft-writer`: write claim-tagged report body.
- `table-layout`: design table-first page flow.
- `summary-sheet`: create one-page summary.
- `toc-builder`: manage headings and page-number assumptions.
- `appendix-builder`: plan lesson plans, rubrics, activity sheets, survey forms, artifacts.
- `icon-visual`: plan icons, diagrams, visual placement.
- `critic`: review scoring fit, privacy, fabrication risk, readability.
- `finalizer`: assemble final candidate checklist and HWPX handoff plan.

## Gates

1. Input/privacy gate.
2. Reference-pattern gate.
3. Evidence and claim-ledger gate.
4. Survey/photo provenance gate.
5. Draft/table/summary consistency gate.
6. Bundle assembly gate.
7. HWPX/Hancom render gate, performed outside this CLI until direct HWPX integration exists.

## Hard Safety Rules

- No fabricated survey numbers, student quotes, class results, dissemination proof, photos, or screenshots.
- No reference-report copying. Structure and pattern extraction only.
- No final body wording such as `(예정)`, `추후`, `보완 예정`, `초안`, `미정`, `TODO`.
- No concurrent HWPX editing.
- Raw student data, unredacted photos, and private survey files stay outside commits.

# Competition Workspace Template

Put only current competition inputs here. Do not commit raw student data.

## Folder Map

- `input/ideas/`: teacher notes, rough report ideas, model names.
- `input/rules/`: official notice, rubric, page limit, template notes.
- `input/references/`: reference reports for structure mining.
- `input/evidence/`: anonymized classroom evidence.
- `input/photos/`: photos after privacy review or redaction.
- `input/surveys/`: anonymized survey tables and summarized metrics.
- `input/raw_private/`: local-only raw files. Never commit.
- `lanes/`: per-agent task inboxes and outputs.
- `output/`: checks, assembled markdown bundle, and final packaging evidence.

## Flow

1. Add rules, references, ideas, evidence, photos, and survey summaries.
2. Run `rch bootstrap-lanes <workspace> <agent>`.
3. Give each `lane-input.md` to the best agent or human owner.
4. Let agents fill lane contracts.
5. Run `rch check`.
6. Run `rch assemble`.
7. Run `rch check --final`.
8. Hand the final bundle to one HWPX finalizer.

## Final Gate

`rch check --final` now requires all production lanes to have complete agent output. Final evidence paths must be workspace-relative and must not point at `input/raw_private/`. The `critic` lane must also write `rubric-score.json` with at least 5 scored criteria and 85% or higher total score.

## Current Boundary

This template does not run external AI tools by itself. It prepares safe work lanes and final bundle structure.

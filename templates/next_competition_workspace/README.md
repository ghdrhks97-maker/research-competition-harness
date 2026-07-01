# Competition Workspace Template

Put only current competition inputs here. Do not commit raw student data.

## Folder Map

- `input/ideas/`: teacher notes, rough report ideas, model names.
- `input/research/`: theory background and prior-research summaries from public routes.
- `input/rules/`: official notice, rubric, page limit, report form/template files.
- `input/references/`: reference reports for structure mining.
- `input/evidence/`: anonymized classroom evidence.
- `input/photos/`: photos after privacy review or redaction.
- `input/surveys/`: anonymized survey tables and summarized metrics.
- `input/raw_private/`: local-only raw files. Never commit.
- `lanes/`: per-agent task inboxes and outputs.
- `output/`: checks, assembled markdown bundle, and final packaging evidence.

## Flow

Fast path:

```bash
rch go <workspace> --competition-name "창의교육 연구대회" --major 과학
```

Detailed path:

1. Run `rch import-rules <workspace> <notice/rubric/form files...>` if contest files exist.
2. Run `rch brainstorm <workspace>`.
3. Run `rch research-background <workspace>`.
4. Add references, evidence, photos, and survey summaries.
5. Run `rch bootstrap-lanes <workspace> <agent>`.
6. Give each `lane-input.md` to the best agent or human owner.
7. Let agents fill lane contracts.
8. Run `rch check`.
9. Run `rch assemble`.
10. Run `rch check --final`.
11. Hand the final bundle to one HWPX finalizer.

## Final Gate

`rch check --final` now requires all production lanes to have complete agent output. Final evidence paths must be workspace-relative and must not point at `input/raw_private/`. The `critic` lane must also write `rubric-score.json` with at least 5 scored criteria and 85% or higher total score.

## Current Boundary

This template does not run external AI tools by itself. It prepares safe work lanes and final bundle structure.

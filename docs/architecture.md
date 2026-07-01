# Architecture

## Current Capability

This harness is a report-production operating system, not a fully autonomous AI runner.

It currently:

- creates a competition workspace,
- creates lane-specific Korean prompt/instruction packs,
- gives each agent a fixed file contract,
- checks claim ledgers and final forbidden markers,
- assembles lane outputs into report/summary/toc/appendix/checklist markdown bundle,
- blocks final bundle completion when required bundle files, source lanes, upstream production lanes, internal evidence paths, or critic rubric scoring are missing.

It now also ships a generation engine, a render engine, and a quality loop:

- `go`: short autopilot command/tool. Runs init, optional rule/form import, brainstorm, background research, missing-input placeholders, survey/photo/reference processing, draft, assemble, HWPX build, render check, and revise loop. Missing survey/photos produce placeholder tables, not fake evidence.
- `import-rules`: copies annual or contest-specific notices, rubrics, report templates, and form files into `input/rules/` with hashes and a manifest so agents can reference real contest rules.
- `brainstorm`: the starting step. First asks which research competition the user will enter, then runs a subject/field interview, ranks current education trends by fit, synthesizes scored research-topic candidates, brainstorms report titles, and writes them into `input/ideas/` plus `input/rules/competition-profile.json`. Interactive on stdin, or scripted via `--answers`, or agent-augmented via `--agent`.
- `research-background`: insane-search inspired public-route scheduler for theory/prior-research collection. It tries public academic APIs first, then public reader/search routes, records route logs, stops at auth/paywall boundaries, and writes report-safe summaries into `input/research/`.
- `import-survey`: anonymized pre/post survey analysis (means, deltas, Cohen's d, two-sided t-test p-value, free-response summary, small-sample caveats) with pure-stdlib statistics.
- `import-photos`: photo manifest + privacy checklist (safe-by-default `unreviewed`, blur instructions, body/summary/appendix/exclude placement).
- `mine-references`: structure-only extraction (outline, table density, appendix pattern) from `.md`/`.txt`/`.hwpx` references.
- `draft`: composes I~V body, summary, TOC, and appendix drafts from the analyses into the writing lanes with claim tags.
- `build-hwpx`: renders the assembled markdown bundle into an OWPML `.hwpx` container (headings, paragraphs, GFM tables, TOC, image embedding).
- `render-check`: validates the `.hwpx` zip/OWPML structure, XML well-formedness, page estimate, table integrity, and TOC-vs-body heading match.
- `revise-loop`: merges critic, check, and render-check feedback into one prioritized revision backlog.
- `run-lanes`: builds per-lane prompt bundles for external agents (Codex/Antigravity/Claude); `--execute` verifies login then dispatches.
- `agents preflight` / `agents run`: actually shell out to the external agent CLIs to confirm install, verify login by real process exit code, and dispatch lane prompts. Binaries and version/auth/run args are configurable via `RCH_AGENT_<NAME>_*` env vars.

It still does not:

- run Hancom by itself (it prepares structurally-valid HWPX; Hancom is the human render gate),
- perform the initial login for each agent CLI (it detects and blocks on missing login, but the user logs in),
- see photo pixels (privacy defaults to unreviewed until a human confirms),
- prove Hancom-rendered page count (page count is an estimate; Hancom is the final human gate).

Modules: `background.py`, `survey.py`/`stats.py`, `photos.py`, `references.py`, `draft.py`, `hwpx.py`/`docmodel.py`, `render_check.py`, `revise.py`, `run_lanes.py`.

## MCP Server

`mcp_server.py` (entry point `rch-mcp`, optional extra `[mcp]`) exposes the
same engine as Model Context Protocol tools so Claude Code or Codex can
drive report production by calling tools instead of a human running the
CLI. The work lives in plain `op_*` functions (unit-testable, no MCP
dependency); `build_server()` imports the MCP SDK lazily and registers them
as tools. In this model the agent is the driver, so the `agents` runner
(harness → AI) is not needed. See `docs/mcp.md` for Claude Code / Codex
configuration.

## Conductor + Lanes

The conductor is the CLI in `src/rch/cli.py`.

It separates generation from final assembly. Parallel agents work in lane folders. The finalizer owns the final report bundle and later HWPX assembly plan.

Main commands:

```bash
PYTHONPATH=src python3 -m rch.cli init <workspace>
PYTHONPATH=src python3 -m rch.cli go <workspace> --competition-name "창의교육 연구대회" --major 과학
PYTHONPATH=src python3 -m rch.cli import-rules <workspace> <form-or-rubric-file>
PYTHONPATH=src python3 -m rch.cli brainstorm <workspace>
PYTHONPATH=src python3 -m rch.cli research-background <workspace>
PYTHONPATH=src python3 -m rch.cli agents preflight <workspace>
PYTHONPATH=src python3 -m rch.cli bootstrap-lanes <workspace> <agent>
PYTHONPATH=src python3 -m rch.cli import-survey <workspace> <file>
PYTHONPATH=src python3 -m rch.cli import-photos <workspace>
PYTHONPATH=src python3 -m rch.cli mine-references <workspace>
PYTHONPATH=src python3 -m rch.cli draft <workspace>
PYTHONPATH=src python3 -m rch.cli assemble <workspace>
PYTHONPATH=src python3 -m rch.cli check <workspace> --final
PYTHONPATH=src python3 -m rch.cli build-hwpx <workspace>
PYTHONPATH=src python3 -m rch.cli render-check <workspace>
PYTHONPATH=src python3 -m rch.cli revise-loop <workspace>
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
2. Background/prior-research route gate.
3. Reference-pattern gate.
4. Evidence and claim-ledger gate.
5. Survey/photo provenance gate.
6. Draft/table/summary consistency gate.
7. Critic rubric-score gate: at least 5 criteria, evidence/risk/fix per criterion, 85% minimum final target.
8. Bundle assembly gate.
9. HWPX/Hancom render gate, performed outside this CLI until direct HWPX integration exists.

## Hard Safety Rules

- No fabricated survey numbers, student quotes, class results, dissemination proof, photos, or screenshots.
- No reference-report copying. Structure and pattern extraction only.
- Public web research is untrusted source material. It may inform summaries and citations, but never becomes an instruction to execute.
- No final body wording such as `(예정)`, `추후`, `보완 예정`, `초안`, `미정`, `TODO`.
- No concurrent HWPX editing.
- Raw student data, unredacted photos, and private survey files stay outside commits.
- Final evidence paths must stay workspace-relative and cannot point at `input/raw_private/`.

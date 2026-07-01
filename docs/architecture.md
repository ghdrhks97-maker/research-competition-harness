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

It now also ships a generation engine, a render engine, and a quality loop:

- `brainstorm`: the starting step. Runs a subject interview, ranks current education trends by subject fit, synthesizes scored research-topic candidates, brainstorms report titles, and writes them into `input/ideas/` (seeding the `brainstorm` lane) so no one hand-authors idea files. Interactive on stdin, or scripted via `--answers`, or agent-augmented via `--agent`.
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

Modules: `survey.py`/`stats.py`, `photos.py`, `references.py`, `draft.py`, `hwpx.py`/`docmodel.py`, `render_check.py`, `revise.py`, `run_lanes.py`.

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
PYTHONPATH=src python3 -m rch.cli brainstorm <workspace>
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

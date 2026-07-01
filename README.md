# Research Competition Harness

Local-first harness for producing Korean research-competition reports with multiple agents while keeping final claims evidence-safe.

## What This Does

- Creates a clean competition workspace.
- Defines lane contracts for Codex, Antigravity, Claude/Gemini, or manual agents.
- Tracks report claims against real evidence.
- Blocks unsupported final-report claims.
- Keeps HWPX assembly as a single-finalizer step.

## Core Idea

Agents work in parallel, but they do not edit the same `.hwpx`.

Each agent writes contract files:

- `lane-output.md`
- `lane-output.json`
- `claim-ledger.json`
- `verdict.json`
- `evidence/`

The conductor compares lane outputs, rejects unsupported claims, then one finalizer assembles the HWPX and runs package/render/Hancom checks.

## Quick Start

```bash
python3 -m rch init my-competition
python3 -m rch lane my-competition brainstorm codex
python3 -m rch check my-competition
```

## Recommended Lanes

| Lane | Best owner | Output |
| --- | --- | --- |
| `brainstorm` | Antigravity / Codex | title, frame, research questions, scoring fit |
| `reference-miner` | Claude/Gemini/Codex | reference report structure patterns |
| `draft-writer` | Codex/Claude | claim-tagged manuscript |
| `table-layout` | Codex | table-first report map |
| `summary-sheet` | Codex/Antigravity | one-page summary plan |
| `icon-visual` | Codex/Antigravity | icon/chart/evidence asset manifest |
| `critic` | Claude/Gemini/Codex | rubric, format, fabrication, anonymity review |
| `finalizer` | Codex | HWPX assembly and validation |

## Non-Negotiables

- No fabricated student quotes, survey numbers, class results, dissemination proof, photos, or screenshots.
- No final body wording like `(예정)`, `추후`, `보완 예정`, `초안`, `미정`, `TODO`.
- No reference-report copying. Extract structure and patterns only.
- No concurrent HWPX editing. One finalizer owns the package.
- RHWP/visual metrics are diagnostics. Hancom/HOP proof decides final readiness.

## Repository Scope

This repository contains only harness code, schemas, templates, docs, and synthetic examples. It intentionally excludes real `.hwpx` reports, student data, photos, local outputs, and competition evidence.

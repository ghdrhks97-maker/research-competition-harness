# Competition Workspace Template

Put only current competition inputs here.

## Folder Map

- `input/rules/`: official notice, rubric, template notes.
- `input/references/`: reference reports for structure mining.
- `input/evidence/`: real classroom evidence. Do not commit real student data.
- `lanes/`: per-agent task inboxes and outputs.
- `output/`: generated checks, reports, and final packaging evidence.

## Flow

1. Add rules and references.
2. Create lanes with `rch lane`.
3. Let agents fill lane contracts.
4. Run `rch check`.
5. Finalizer assembles HWPX only after claims pass.

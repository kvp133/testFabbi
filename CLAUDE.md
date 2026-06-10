# AI Tooling Disclosure

This file satisfies the README requirement to commit "all resources and
configurations related to the coding agents you used (such as
`Claude.md`, `.agents`, `.claude`, `.cursor`, etc.) and any custom
instructions or documentation you defined for the AI."

## Tools used

| Tool        | Version / model                   | Purpose                                                                                                       |
| ----------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Claude Code | Anthropic CLI, model Opus 4.7 (1M context) | End-to-end pair-programming during the assessment: codebase exploration, bug audit, draft of fixes/tests/PR descriptions |

No other AI assistants (Cursor, Copilot, ChatGPT, Cline, etc.) were used.

## How it was used

1. **Audit phase**
   Claude Code was prompted to read every Python file under `backend/app/`,
   every TypeScript file under `frontend/src/`, the Alembic migrations,
   the Docker Compose stack, and the test suite. It produced the
   severity-ranked bug catalogue you can see in
   [`pr-descriptions/00-overview.md`](./pr-descriptions/00-overview.md).
   Each finding was cross-checked manually against the source file
   before being accepted.

2. **Fix phase**
   For each of the seven shipped fixes the workflow was:
   - Branch off `main`.
   - Ask Claude Code to propose an edit and the matching test(s).
   - Read the proposed diff line by line, request adjustments where
     needed (e.g., naming, defence-in-depth choices, migration
     fail-loud semantics).
   - Run the test suite inside the backend container or `tsc -b` for
     the frontend.
   - Commit with a hand-edited message that explains the *why*.

3. **Documentation phase**
   The bug-report overview and the seven per-PR descriptions in
   `pr-descriptions/` were drafted by Claude Code following the
   `Location / Reason / Fix proposal` template from the assessment
   brief, then human-reviewed for accuracy.

## Custom instructions / project config

No project-scoped Claude config (`.claude/`, `CLAUDE.md` with custom
rules, MCP servers, hooks, etc.) was created for this assessment — the
default Claude Code behaviour was used throughout. This file is
therefore the only AI-related artefact committed to the repository.

User-level Claude Code memory and conversation transcripts live outside
the repo under `~/.claude/` and are intentionally not committed; the
README also forbids committing private credentials and editor-specific
history files.

## Limits of AI assistance

Generated code was only accepted after manual review and a green test
run. Generated prose (commit messages, PR descriptions, this file) was
edited for accuracy and tone before commit. Where Claude Code suggested
adding error handling, abstractions, or fallbacks beyond the scope of
the bug being fixed, those suggestions were declined to keep each diff
focused — per the assessment guidance to "keep changes focused" and
"prioritise correctness over cosmetic cleanup".

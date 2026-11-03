# Changelog

## v0.5 — 2026-11-03

From the Flow Timer run (research-notes §11): the workflow decided the planted edge cases as silently as a single agent, and its cost was coordination and test volume, not correctness.

| Problem | Change |
| --- | --- |
| Edge cases decided silently by every build | Gate 1 edge-case sweep: PRD "Edge cases" table over seven categories (`edge_categories`), no forced Cartesian product, "No dispute" line per undisputed category; the CEO fills every Decision; `gw gate 1` refuses until done and `gw brief` refuses before it |
| Edge decisions lost between PRD and tests | Brief "Edge cases" table, decision copied verbatim (`gw brief` compares); every row named by a test (`gw planned`); rows found later are `Main provisional` and `gw gate 3 M` waits for the CEO |
| Test cap was prose; 192 tests against 171 | `gw planned` counts test cases (`test_case_pattern`) against one visible and two held-out per criterion or edge row (`test_caps`) |
| 25 tests asserted on source text | `gw planned` refuses tests that read files under `source_dirs` or the brief's file list |
| Junction for `node_modules` emptied by `git worktree remove --force` | `gw close` unlinks links and junctions before deleting the worktree; architecture template recommends per-worktree installs from a shared cache |
| A half-failed close needed hand edits to state.json | `gw close` skips what is already done and can be rerun |
| `gw planned` could not be rerun | allowed while the task is `planned` |
| "500 > 500" | word counts shown with one decimal |
| Four calls per task end; Codex Guardian reviewed each | `gw finish N`: review pass → holdout → merge → close |
| Gate 2 turned into a question to the CEO | `gw next` says only Gates 1 and 3, parked tasks and irreversible actions wait; SKILL says so too |
| Main's context 79k → 410k, one-task-per-session not followed | prototype `gw drive N` (`scripts/drive.py`, `references/drive.md`): every step a fresh `claude -p --output-format json` session, usage per session in log.md; Main tells the CEO to clear context after each Gate 3 |
| Tester waited for the previous merge | the Tester may run one task ahead; rerun only if a merge changes a contract its tests rely on |
| A wrong attribution in Main's report | claims about who did what cite the log or a diff |
| Single agents shipped six common UX faults | Punk "Always check" table and report line; at most 12 screenshots, one theme, one script per round (`gw docs`) |
| Seal guessed "worktree open" from a folder's existence | uses the task's slot |
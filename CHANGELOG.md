# Changelog

## v0.7 — 2026-11-10

The two lines are one again: v0.6 (documents and prompts) and v0.5.1 (merge fixes) were merged, with the `gw drive` patches from its first real milestone (repo agent files first, `env`, prompt fixes). That milestone ran seven tasks in 67 sessions. It stopped nine times, never for a decision, and the session that launched the drives was woken 23 times and grew to 519 thousand tokens of context (research-notes §12).

| Problem | Change |
| --- | --- |
| A commit hook rejected test files inside `gw merge`, five times; the fix then had to be copied to the worktree, the test folder and the vault | `gw planned` and `gw check` stage the files in a throwaway clone of the main branch, run the repo's pre-commit hook there and refuse what it rejects, so the Tester or the Coder fixes it at the source. Nothing is committed; the clone has its own object store and is deleted. `commit_rehearsal`: `auto` (repos with `.pre-commit-config.yaml`), `true`, `false` |
| A note on a Files line made `gw check` call the Coder's file out of scope | `gw brief` refuses a path with spaces or full-width brackets, and a `May change` path that matches no file; a path that names an existing file is taken as it stands; `、` `;` `；` also separate paths; `none` is skipped |
| Main said pass, `gw check` then failed on Main's own edit, and the drive counted two Coder loops and parked the task | Main gets the check output once to settle it; if it does not, the drive stops without using a loop. A `gw check` failure after the Coder goes back to the Coder once before any review; a Coder blocked on that retry gets its answer and runs again |
| Two tasks were parked after three failed reviews, and the CEO overruled both: the reviews had asked for more than the brief | A review fails only by naming an acceptance criterion or an edge row of the brief, `check` or `cheat` (`gw review N fail "<ids>"`); anything else is a `deferred` row and a pass. The review no longer runs the tests |
| Parked tasks were resumed by editing `state.json` | `gw unpark N "<the CEO's words>" [state]`: back to where it stopped, or to `review` to accept the work, which is then checked again; only states the task's files allow; the words are logged |
| The launching session was woken after every task and after every stop, each time re-reading its whole context | `gw drive N [N ...]` runs a queue; a stop leaves one page (`.gw/stop-N.md`: why, who, what resumes it) for a fresh session; `gw next` names it. Sessions have one purpose each: plan, build or gate |
| "One task per session" was prose and was not followed for three milestones | `gw hook [k]`, a Claude Code PreToolUse hook: no `gw brief` or `gw drive` from a session over k thousand tokens of context (default 200) |
| Review and spec check were two thirds of the drive's cost; on UI tasks the held-out tests found nothing and eyes found the defects | A task whose one risk layer is UI takes no held-out tests; the spec session runs only when `gw planned` finds a held-out file or a test plan that does not plainly say nothing is open |
| The Tester's first output was refused seven times out of ten, and three of seven briefs were written twice | `gw try brief N` and `gw try planned N`: the same refusals with nothing changed, run by the author before handing over |
| A session with nobody to ask cannot get an approval | Approvals sweep before Gate 1: the PRD's Approvals table, by category (`approval_categories`), decided by the CEO; `gw gate 1` checks it; a step that needs something the table does not hold stops |
| Seven of 67 log rows under-reported tokens and time: a session that starts a background task is woken again, and the JSON's `usage` covers only the last stretch | Drive sessions run with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`; tokens come from `modelUsage`, seconds from the script's own clock; the row names the model. A repo's `drive.env` adds to the default |
| Two `gw` processes could overwrite each other's task state, and the rehearsal widened that window | Every per-task command writes only its own task into the latest state |
| No regression test survived earlier versions | `tests/test_gw.py`: a toy repository, a fake `claude`, a hook that stands in for a linter |

Migration for a project set up before this version: move `debt.md` rows into `decisions.md`; bring STATE and the architecture index under the v0.6 budgets; add the Approvals table to the PRD before the next Gate 1; copy the skill's agent files over the project's own, keeping the project's additions; register the context hook.

## v0.6 — 2026-11-04 (local branch, from the GenEC Image run)

| Problem | Change |
| --- | --- |
| Main told the Tester things in chat that the Coder never saw in the brief, so the two did not test and build the same spec | Prompts to subagents are paths only; Coder and Tester refuse extra instructions and point at the brief (agents, SKILL hand-off rules) |
| Punk was told it had no way to see the UI, so it reviewed from screenshots Main took | Punk gets the browser pane tools (`mcp__Claude_Browser__*`), opens the product itself, clicks and screenshots; the CEO enters any credential |
| Too many documents and too many words per document | `debt.md` and `test-report.md` removed (deferred rows live in `decisions.md`); budgets cut to brief 350, Punk 350, gate 400, test plan 300, STATE 300, handoff 150 words, three rows per handoff table; Main's messages to the CEO at most 150 words outside gate packets |
| Organisation-specific wording | none in the skill; it stays product-neutral |

## v0.5.1 — 2026-11-04

From a real project run: one task's code was lost after `gw finish` reported it merged.

| Problem | Change |
| --- | --- |
| A pre-commit hook rejected the worktree commit; `gw merge` ignored the failure (`check=False`), merged a branch with nothing new, reported MERGED, and `gw close` then deleted the worktree with the uncommitted code | `gw merge` stops when the worktree commit fails, unstages and removes the copied held-out tests, and says why; it also refuses to merge a task branch with no commits ahead of the main branch |
| Two `gw` commands at once (two `gw finish` on parallel tasks) overwrote each other's task state, because each loaded `state.json` at the start and saved all of it at the end | `gw holdout` and `gw merge` re-read the state before saving and write only their own task (`save_task`) |
| The Coder never ran the repo's commit hooks, so lint failures surfaced only inside `gw merge` | `gw-coder` runs the repo's commit hooks on its changed files before handing off |

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
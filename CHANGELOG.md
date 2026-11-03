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

## v0.4 — 2026-11-02

From the CEO's review of v0.3 (research-notes §10). Mechanical rules move from prose into `scripts/gw.py`.

| Problem | Change |
| --- | --- |
| Prompt rules lose to model habits (heavy-RL models now, possibly others later) | New `scripts/gw.py` (Python stdlib): per-task step order with refusals and `gw next`; brief, file-list, visible-test, registry, shell-import and handoff checks; vault for held-out sets; test lock and slot environment; merge with refresh; `gw docs`; `gw archive`; gate log lines. New `docs/workflow/gw.json` and git-ignored `docs/workflow/.gw/` |
| Main overloaded | Mechanics in `gw`; one task per Main session; hot/cold documents. Auditor role recorded under Scaling → Up for large projects, not added |
| Coder could peek at held-out tests | Held-out sets are single use (`gw burn`: spent set becomes visible, Tester writes a fresh one); sets live in `~/.gw-vault/` and enter the worktree only during a run |
| Test-first fails in UI/native/glue | "Orchestration as a headless state machine": pure `step(state, event) -> (state, effects)`, time as an event, shell may not import state (`gw check`), events/effects tables as the brief's Interface; Tester drives event sequences; shell verified by Punk and the CEO |
| Documents | Two kinds: record files tables only; thinking files at most three sentences per heading, bullets ≤ 40 words; architecture as an index plus `architecture/<component>.md`; `gw archive M<n>` folds each milestone |
| Parallel worktrees | Serial test runs; `GW_SLOT`/`GW_PORT_BASE`/`GW_TMP`; refresh from main before merge with `conflict`/`drift` states; registry files Main-only plus a skeleton commit; `conflicts_with` covers shared behavior |
| Templates | STATE, tasks, decisions, debt, log, handoff, test report rewritten as tables; brief gains events/effects tables; architecture rewritten as an index; all templates pass `gw docs` |

## v0.3 — 2026-11-01

Driven by the first real run (v0.2 on Codex, desktop pet M1; details in research-notes §9). Each change answers one finding.

| Finding in run 1 | Change in v0.3 |
| --- | --- |
| 66 workflow files, ~24k words; the CEO stopped after one | New "Writing and documents" section: closed file layout (no feasibility/demo/follow-up/release files), page budgets per file, raw logs never in the repo, each limitation said once in STATE "Not verified", CEO-facing files in the CEO's language |
| Briefs of 8–9 KB dictated ~85% of interface decisions | Brief ≤ 1 page; Interface = what a test calls and observes, no internals; template rewritten |
| Zero tests on the orchestration/native layers where most guards lived; every Gate 2 passed first loop, no held-out ever failed | Brief names a risk layer; at least one test or a written manual check must reach it (spec check, Tester, test plan, test report); Gate 3 checklist asks why no held-out failed |
| ~200 lines of small defenses (flags, counters, triple resets) passed review | Coder lists every defense in the handoff's "Defenses added"; audit names the small kinds; unlisted or unnamed guards are deleted; two mechanisms for one failure keep one |
| A cast worked around a file the brief froze | Workarounds around frozen files fail review; the brief is fixed instead |
| Reminders moved behind Advanced without the CEO seeing it | Gate packet (new `templates/gate.md`, one page) lists every feature removed, hidden or moved |
| No Git: invented snapshots, 5.2 GB work copy | "Without Git" section: source-only work copy, shared dependencies/build output, diff base of allowed files only, delete at close-out |
| Usage "not reported" on every log line | Log records usage per node (tokens or wall time) and a milestone total at each gate; gate packet shows cost |
| Punk report ~8 KB of evidence caveats | Punk ≤ 1 page, limits in a "Not checked" list |
| Feasibility notes as a separate file | PRD gains a "Planning notes" section |

## v0.2 — 2026-10-31

### Testing

- **Tester writes tests before the code.** Visible tests go to the Coder; held-out tests are kept back; a one-page test plan carries an ambiguity list. `agents/gw-tester.md` rewritten; `templates/test-plan.md` new.
- **Spec check.** Main reads the test plan and fixes the brief before any code exists (Phase B step 4).
- **Acceptance after the code** is Main's review followed by a full test run with the held-out tests copied in. No second Tester call. Main writes `test-report-N.md`, on pass only.
- **No leaks of held-out tests.** Loop feedback describes failing behavior, never test code; copied held-out files are deleted before the Coder reruns; raw run output stays outside the repo; the log carries counts only.

### Workspace

- **One git worktree per task** (`<repo>.gw/N/`, branch `gw/N`), parallel or not. Held-out tests live in `<repo>.tests/N/`, outside every checkout.
- **Coder** works only inside its worktree, may not edit tests, reports disputed tests, and fails review if it special-cases test inputs.
- **STATE.md** tracks open worktrees; each session starts by reconciling them with `git worktree list`.
- **Install location.** The skill must live in the personal skills folder, not inside the product repo, because SKILL.md says where held-out tests are kept. Setup copies only the seven long-lived templates into `docs/workflow/`.

### Punk

- **Punk gets eyes.** It starts the product from the new Demo section of `architecture.md`, takes screenshots, reads them, and cites them per objection. If it cannot see the product it stops and Main supplies screenshots. Gains the Write tool for its report and throwaway screenshot scripts.
- Round 0 reads the architecture only to learn what will be built.

### Models

- **Tiers instead of product names.** Agent files no longer pin a model or reasoning effort. SKILL.md has a Models section with three tiers (strongest; fast coder; judgment + vision) that each installation maps to its own model family.

### Merged from the first review

- **Unattended mode.** `Mode: unattended` in STATE.md: a task that fails its third loop is parked with a diagnosis and the run continues with independent tasks. Gates 1 and 3 and irreversible actions still wait for the CEO.
- **Non-negotiables.** New section in `architecture.md` for trust boundaries (auth, untrusted input, secrets). The over-defense audit may simplify them, never delete them, and a brief that touches one states it as an acceptance criterion.
- **Trigger scope.** The description now applies the short commands ("continue", "GO", "state" …) only inside a repo with `docs/workflow/`.
- **MAST claims corrected.** failure-checklist and research-notes now give the actual Table 5 numbers, the 32-task sample, the AG2 counter-result and the authors' "not sufficient" conclusion. The advice is "find the failing node in the log, change the smallest thing", not "structure beats wording".
- **Run log.** `docs/workflow/log.md`, one line per node run, with its own delete trigger.
- **No hard-coded handle.** The operative files say "the CEO"; research-notes keeps the dated record of who decided what.
- **Serves line** in every brief quotes the PRD criterion it moves; the spec check asks whether the criteria, as the Tester read them, actually move it.

### Housekeeping

- ICT-related lines removed from research-notes.md and SKILL.md Setup.

## v0.1 — 2026-10-31

First draft: four roles, three gates, repo state, over-defense rules. Not tested on a real project.

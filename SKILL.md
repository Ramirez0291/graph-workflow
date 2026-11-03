---
name: graph-workflow
license: MIT
description: Run a product build as a small graph of four roles — Main (this session: PM + Architect + orchestrator + code reviewer), Coder, Tester and Punk (product/UX objector) — with the user as CEO at the plan gate and at every milestone gate, and a Python script (gw.py) that enforces step order and mechanical gates. State lives in docs/workflow/ inside the repo. Use it when the current repo already has docs/workflow/, or when the user asks to set the workflow up, to plan or build a product "with the team" or "graph workflow", or names Main, Coder, Tester or Punk. Inside such a repo, short commands like "开搞", "GO!", "Go ahead", "milestone", "punk", "state", "run the next task", "what's blocked" mean this workflow; outside one they do not. Do not use for one-off scripts, quick fixes outside a workflow project, or non-software tasks.
---

# graph-workflow (v0.5)

You are **Main**: product manager, architect, orchestrator and code reviewer. The user is the CEO and the only human. Everything else is you, three subagents, and `scripts/gw.py`. The design rests on five observations:

- One strong model running the role chain in one conversation loses nothing between PM and architect. So Main stays one brain; fan out only for fresh eyes, for parallel work, or to keep Main's context small on large projects.
- A model decides ambiguous cases silently. In the Flow Timer run, all three builds (this workflow included) settled four planted edge cases without asking, and two of them chose differently. Only Gate 1's edge-case sweep puts those choices in front of the CEO.
- Coders and testers pile up defensive scaffolding, and some models do it whatever the prompt says. The prompt lowers it; your review removes it. The same urge moves into paperwork and test volume.
- A builder does not see its own product. Both single-agent Flow Timer builds shipped all six of Punk's common UX faults; one had taken screenshots itself. Punk is the cheapest role and the one a single agent lacks most.
- Rules in prose lose to a model's habits; rules in code do not. Whatever can be checked mechanically is checked by `gw.py`, not by your diligence.

Research and run history: [research-notes.md](research-notes.md). Changes: [CHANGELOG.md](CHANGELOG.md).

This skill applies only in a repo that has `docs/workflow/`, or when the CEO asks to set one up. A bare "continue" anywhere else is not a reason to start it.

## The team

| Role | Who | Model tier | Sees | Produces |
|---|---|---|---|---|
| Main | this session | strongest | everything | PRD with edge cases, architecture, tasks, briefs, reviews, gate packets |
| Coder | subagent `gw-coder` | fast coder | its worktree: the brief, the files it names, the visible tests | code + handoff |
| Tester | subagent `gw-tester` | fast coder | the brief + test conventions, before the code exists | visible tests, held-out tests, test plan |
| Punk | subagent `gw-punk` | judgment + vision | PRD + the running product's screens; never the code | ranked objections, with screenshots |
| gw.py | script | — | the repo, the worktrees, the vault | refusals, gate results, log lines |

Copy the agent files once into your harness's agent folder (Claude Code: the project's `.claude/agents/`) and invoke them with a prompt that is mostly paths. If a subagent needs something that is not in its file, fix the file.

**Models.** Tiers, not product names: *strongest* for Main; *fast coder* (strong coding model at its highest reasoning setting) for Coder and Tester; *judgment + vision* (must read images) for Punk. A second model family is best spent on the Tester or Punk. Set models per installation; left unset, subagents usually run on Main's model.

**Why Coder and Tester are separate sessions.** Their context never enters Main's, which is what keeps Main alive on a large project, and their worktrees let tasks run in parallel. On a small project that split costs more than it saves; the Flow Timer numbers are in research-notes §11.

## gw.py — the deterministic layer

Run from the main checkout: `python <skill>/scripts/gw.py <command>`. Python 3.8+, standard library only. Every step below names its command. Never create worktrees, move held-out tests or merge by hand: those happen only through `gw`, and `gw` refuses a step taken out of order and says what comes next (`gw next`).

What it enforces:
- **Gates:** no brief before `gw gate 1` passes, and it passes only when every PRD edge case has the CEO's decision. `gw gate 3 M<n>` waits for closed tasks, no provisional edge rows, the gate packet, Punk's report and clean docs; `gw archive` waits for it.
- **Step order** per task: brief → planned → sealed → open → check → review → holdout → merge → close, with loops and parking after three failures. `gw finish N` runs review pass through close as one call.
- **Briefs:** required sections, a named risk layer, a file list, the page budget, edge rows copied verbatim from the PRD.
- **Tests (`gw planned`, rerunnable):** at most one visible and two held-out tests per criterion or edge row (`test_caps`); each edge row named by a test; no test that reads product source as text.
- **Coder output (`gw check`):** files within the brief's list (taken from the brief on main); visible tests and registry files untouched; shell files free of state imports; a handoff with "Defenses added"; no stray changes in the main checkout. Build outputs must be git-ignored.
- **Held-out tests:** sealed in a vault outside the repo (`~/.gw-vault/`), in the worktree only during a run. Not a sandbox; single use (Phase B step 8) is what makes a peek worthless.
- **Runs and merges:** one test run at a time (a lock) with `GW_SLOT`, `GW_PORT_BASE`, `GW_TMP`; merge = commit, refresh from main, full suite, merge, suite on main.
- **Close:** unlinks links and junctions before deleting a worktree, so a linked dependency folder is never emptied; rerunnable after a partial failure.
- **Documents (`gw docs`):** kind rules, budgets, the layout, at most `screens_max` screenshots and one script per Punk round.

Configuration is `docs/workflow/gw.json` (`gw init` writes it): `test_command`, `test_dir`, `setup_command`, `registry_files`, `shell_paths`, `shell_forbid`, `parallel_max`, `port_base`, `edge_categories`, `test_caps`, `test_case_pattern`, `source_dirs`, `screens_max`, `drive`. The test command runs in the system shell (cmd.exe on Windows).

If your harness has command hooks (Claude Code has), add one that blocks `git worktree` and `git merge` outside `gw`. Without hooks, `gw check` and `gw merge` still verify after the fact.

## gw drive (prototype)

`gw drive N` inverts the control for one task: the script schedules and Main only judges. Each step (brief, tests, spec check, code, review, loop notes) runs as a fresh `claude -p --output-format json` session with only that step's inputs; `gw` runs the gates between them and logs each session's usage. It stops for a person at gates, parked tasks, conflicts, drift and refusals. Details and configuration: [references/drive.md](references/drive.md). Claude Code only for now.

## Writing and documents

Documents are part of the product's cost. Two kinds, checked by `gw docs`:

| Kind | Files | Rule |
|---|---|---|
| Record | STATE, tasks, decisions, debt, log, handoffs, test reports | Tables only. Headings and at most two `>` note lines; no prose. |
| Thinking | PRD, architecture, briefs, gate packets, Punk reports, test plans | At most three sentences of prose per heading; bullets of at most 40 words; tables allowed. |

- **Budgets** (≈500 words a page; Chinese counts two characters a word): brief, test plan, Punk report, gate packet, STATE ≤ 1 page; handoff, test report ≤ ½ page; architecture index ≤ 2 pages.
- **Only the files in the layout exist.** Planning notes go in the PRD, milestone results in the gate packet.
- **Raw output never enters the repo**; it stays in the vault.
- **Each limitation is said once,** in STATE's "Not verified" table.
- **CEO-facing files** (STATE, PRD, gate packets) are in the CEO's language.
- **Claims about who did what** (a stray server, a broken file) cite `log.md` or a diff, or are not made.
- **Hot and cold.** `architecture.md` is an index; each component's detail lives in `architecture/<component>.md`, read only when a brief needs it. After Gate 3, `gw archive M<n>` moves the milestone's briefs, handoffs, tests, gates, Punk files, log and decisions to `archive/M<n>/`. Main reads only the hot files.

## Project layout

```
<parent>/
├── <repo>/                           # main checkout. Main works here.
│   └── docs/workflow/
│       ├── STATE.md  PRD.md  tasks.md  decisions.md  debt.md  log.md
│       ├── architecture.md           # index; details in architecture/<component>.md
│       ├── gw.json                   # gw configuration
│       ├── .gw/                      # gw task and gate state (git-ignored)
│       ├── briefs/  handoffs/  tests/  gates/  punk/
│       └── archive/M<n>/             # cold: finished milestones
├── <repo>.gw/N/                      # one worktree per open task; the Coder works only here
└── <repo>.tests/N/                   # Tester output: visible/ stays, holdout/ and the plan move to the vault
```

Keep these off cloud-synced drives. Install this skill in your personal skills folder, never inside the product repo.

## Orchestration as a headless state machine

When a task's risk layer is orchestration (window and app lifecycle, pause/resume, sync, anything with flags and races), split it in two:

- **Core:** a pure function `step(state, event) -> (state, effects)`. Events are plain data (`FullscreenEntered`, `UserRecalled`, `Tick(now)`); effects are plain data (`HidePet`, `ShowBubble(text)`). Time arrives as an event, never from a clock. A plain enum and a function: no state-machine library, no framework.
- **Shell:** turns OS, DOM or Tauri facts into events, and executes effects one to one. It may translate (thresholds, coordinates, debouncing). It may not see the state: shell files never import the state type, and `gw check` enforces this through `shell_paths` and `shell_forbid`.

For such a task the brief's Interface is two tables, events in and effects out, and the Tester drives the core with event sequences: reordered, duplicated, interleaved with ticks. The shell has no automated tests by design. Punk's screenshots and the CEO's three-minute try are its test. Do not apply this to simple glue: a state machine around two flags is over-defense.

## Setup (once per repo)

1. Confirm Git (`gw` needs it; see "Without Git"). If `docs/workflow/` exists, go to the session protocol.
2. Copy the agent files and set their models.
3. `gw init`, then fill `gw.json`. Create STATE, PRD, architecture, tasks, decisions, debt and log from the templates.
4. Commit: `chore(workflow): set up graph-workflow`.

## Session protocol

- **Start:** read STATE, run `gw next`. Say in one line where the project is and what you will do. Do not re-derive the plan from the code.
- **One task per session.** After `gw close N`, end the session or clear your context; the next starts from STATE and `gw next`. A model cannot clear its own context, so in a single-session harness tell the CEO at each Gate 3 to clear it (Claude Code: `/clear`) before the next milestone, or use `gw drive`.
- **Do not ask the CEO between gates.** Gate 2 (review and held-out run) belongs to you and `gw`; after a merge, go on to the next task.
- **Log** each subagent run in `log.md` with its usage (tokens if reported, else wall time); `gw` logs the gates. At each gate, add the milestone total.
- **End:** update STATE.

## Phase A — Plan, then Gate 1

1. **PRD.** Interview the CEO. Push on non-goals and success criteria. Existing-code notes go in Planning notes.
2. **Edge-case sweep (Main).** Go through every requirement against each category in `edge_categories` (the PRD template says what each asks). Each case that reads two ways becomes a row of the PRD's Edge cases table, with options and your recommendation. Do not fill the Cartesian product: a category with nothing in dispute gets one "No dispute" line instead.
3. **CEO completion.** Stop and hand the table to the CEO. The CEO fills the Decision column in the file, or answers in chat and you transcribe each answer verbatim; "as recommended" counts only when written. The CEO may add rows. Source stays `CEO`.
4. **Architecture.** The index: components, contracts, layers and how each is tested, Non-negotiables, registry files, shared resources, test command, worktree setup, Demo. Component detail goes in `architecture/`.
5. **Punk round 0** on PRD + architecture; triage into `decisions.md`.
6. **Tasks.** Demoable milestones of about ten day-sized tasks, the first one the thinnest end-to-end path. `conflicts_with` covers shared **behavior**, not only shared files: two tasks that change what the same function returns conflict.
7. **Verify against the objective:** every PRD success criterion maps to a task.
8. **Gate 1 (CEO):** `gates/gate-0.md`, then `gw gate 1`; it refuses while a Decision is empty, a row's source is not the CEO, or a category has neither a row nor a "No dispute" line. Three rounds at most.

## Phase B — Build loop, per task

1. **Pick the task** (`gw next`). Parallel tasks are allowed up to `parallel_max`. Before opening parallel tasks, commit one **skeleton** on main that adds every registry entry they need (module declarations, routes, exports, dependencies). Registry files are Main-only; a Coder that needs another entry says so in its handoff.

2. **Brief** (template, ≤ 1 page), then `gw brief N`. Interface = what a test calls and what it observes, nothing internal; for orchestration, the events and effects tables. Name the risk layer. Write Non-negotiables as acceptance criteria. Copy every edge row the task touches into the brief's Edge cases table, decision verbatim; the Tester never reads the PRD.

3. **Tester** (subagent `gw-tester`, prompt: brief path + `<repo>.tests/N/`), then `gw planned N`. The Tester may run one task ahead: a task whose brief is ready does not wait for the previous merge. If a merge later changes a contract the tests rely on, rerun the Tester for that task; otherwise do not.

4. **Spec check.** Read the test plan. Fix ambiguities in the brief and rerun the Tester for those criteria. A product question in the ambiguity list becomes a new PRD edge row with source `Main provisional`, copied into the brief; work goes on, and `gw gate 3` waits until the CEO confirms it. Delete held-out cases the brief does not support. At least one test, or a written manual check, reaches the risk layer. Commit the brief (`docs(N): brief`), then `gw seal N`.

5. **Open** — `gw open N`: worktree, setup command, visible tests.

6. **Coder** (subagent `gw-coder`, prompt: worktree + brief inside it), then `gw check N`. If the handoff says blocked, fix the brief in the worktree and rerun the Coder.

7. **Review** — your judgment on top of `gw check`:
   - Does the diff do what the brief asks, the way the architecture says, and nothing else?
   - **Over-defense audit.** Compare the diff with "Defenses added"; anything defensive that is not listed is a finding. Look hardest at the small kinds: state flags, version counters, re-entrancy guards, the same reset twice, re-validation, double fetches, catch-alls, unrequested clamps. A guard that names no failure from the brief, a test or an observation: delete. Two mechanisms for one failure: keep one. Non-negotiables: simplify, never delete.
   - Casts or copies around a frozen file, and code that recognises visible-test inputs, fail.
   - Record deletions in `decisions.md`. Pass: `gw finish N`. Fail: write Loop notes first, as behavior, then `gw review N fail`.

8. **Held-out run** (inside `gw finish`, or `gw holdout N`).
   - **Pass** → merge (commit, refresh from main, full suite, merge, suite on main) and close. `conflict`: two tasks shared a file you did not plan for; resolve it yourself or re-cut, then `gw merge N` and `gw close N`. `drift`: it passes alone and fails with main, so two tasks shared behavior; decide which is right. Then update tasks and STATE, commit `docs(N): close`.
   - **Fail** → write Loop notes (behavior only), then `gw burn N`. **Each held-out set is used once.** The failed set becomes visible tests for the Coder. The Tester writes a fresh set that differs from every earlier one (`gw planned N`, `gw seal N`), and the Coder reruns. A Coder that peeked at a set saw only a spent one.
   - Three loops in total, then `gw` parks the task: bring the CEO the diagnosis.

## Phase C — Milestone, then Gate 3

1. All milestone tasks merged; full suite green; only parked tasks open.
2. **Punk round M** (PRD, Demo section, `punk/objections-M.md`, `punk/screens-M/`). If Punk cannot see the product, take the screenshots yourself and rerun it.
3. **Triage** into `decisions.md`; real disagreement goes to the CEO.
4. **Gate 3 (CEO):** `gates/gate-M.md`, one page in the CEO's language: what to try in three minutes, what changed, **every feature removed, hidden or moved**, provisional edge rows to confirm, top "Not verified" items, the milestone's usage, the decision asked. Then `gw gate 3 M<n>`.
5. After approval: `gw archive M<n>`, update tasks and STATE, commit `release(M): <name>`, and tell the CEO to clear the session's context.

## When the CEO is away

STATE's Mode: `attended` or `unattended`, set by the CEO. Unattended, a task `gw` parks gets its diagnosis under "Open questions for the CEO" and work continues with tasks that do not depend on it. Gates 1 and 3, and anything irreversible (deleting data, rewriting history, acting outside the repo and its sibling folders), always wait.

## Without Git

`gw` needs Git; fix Git first. If that is impossible, run the same steps by hand with plain folders: a source-only work copy per task (never copy dependencies or build output; share them by link or the tool's shared setting), a diff base of only the files the brief allows, integration by copying back the handoff's Changed files, deletion at close-out. Held-out single use and the review rules still apply.

## Scaling

- **Down:** fewer than three files and no design decision: do it yourself in the main checkout, commit, one log line. The edge-case sweep and Punk still apply to anything a user sees.
- **Up (large projects):** `gw drive` for the build loop, so Main's context holds one judgment step at a time. Next after that: a fresh-context **Auditor** subagent for the over-defense audit. It reads the brief, the diff and "Defenses added" and returns a findings table; Main decides. Not part of the default team yet.

## Hand-off rules

- PRD edge rows → brief, verbatim; brief → Tester: goal, PRD criterion, criteria, edge rows, interface, risk layer, test command, before any code.
- Tester → Main: test plan, visible, held-out, outside the repo; `gw seal` moves held-out and the plan to the vault.
- Brief + visible tests → Coder, in its worktree. It knows more tests exist, not what they are.
- Coder → Main: handoff tables: changed, defenses added, registry entries needed, uncertain, disputed tests, suggested hardening; done or blocked.
- PRD + product → Punk: objections about what the product does, never how.

## Failure checklist

Before closing any phase: [references/failure-checklist.md](references/failure-checklist.md).

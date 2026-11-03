# Why Prompt Rules Lose to Model Habits: Building a Deterministic Graph Workflow for AI Coding Agents (v0.1 to v0.5)

*Rami0291 · 2026-11-03*

*Two real builds, 24,000 words of agent-written paperwork, 11 smuggled state flags and a 40.7-million-token context bill pushed us from prompt-based multi-agent ceremony to a standard-library Python state machine (`gw.py`), and then to a prototype that inverts who schedules whom (`gw drive`).*

---

## Two traps

If you have built anything multi-week with frontier coding agents (Claude Code, Codex, Cursor), you have probably met both:

1. **The single-agent trap.** One agent is fast and often correct. But it settles every ambiguous product question by itself without saying so, tends to write tests shaped by its own implementation, adds defensive scaffolding (catch-alls, redundant state flags, repeated resets), and does not see the UI it shipped.
2. **The ceremony trap.** The usual fix is a simulated company: analyst, PM, architect, scrum master, developer, QA, each a chatting persona. In practice information is lost at every hand-off, the context windows grow, and the agents write long Markdown to each other instead of code.

Over four days and five versions (v0.1 on 2026-10-31 to v0.5 on 11-03) we built, broke, measured and rebuilt **`graph-workflow` (`gw`)**, now open source under the MIT License. This is what happened, including the parts that did not go our way.

---

## Iteration 1 (v0.1 → v0.2): topology, tests first, and eyes for the objector

v0.1 started from the literature on multi-agent failure: MAST's taxonomy of 14 failure modes (arXiv 2503.13657), AgentCoder (2312.13010) on separating test writing from code writing, and SpecBench (2605.21384), where a model that could see the tests produced a 2,900-line "compiler" that was mostly a lookup table of the test inputs.

### Principle 1: PM, architect and reviewer in one brain (`Main`)

The costliest hand-off in software is between product and architecture, and splitting them into two LLM sessions invites drift. So **PM, architect, orchestrator and code reviewer are one role, `Main`**, on the strongest model. Subagents exist only where a separate perspective or a separate workspace pays for itself:

- **`gw-tester`** sees only the task brief and writes tests before any code exists.
- **`gw-coder`** works in its own Git worktree (`<repo>.gw/N`) with the brief, the files it may change, and the visible tests.
- **`gw-punk`**, the designated objector, sees only the PRD and screenshots of the running product, never the source.
- **The human CEO** steps in at **Gate 1** (the plan) and **Gate 3** (a three-minute try of each milestone). The per-task loop (**Gate 2**) runs without them.

### Principle 2: edges are documents, not chat

Subagents never talk to each other. Every hand-off is a file in `docs/workflow/`: `brief-N.md`, `test-plan-N.md`, `handoff-N.md`, `objections-M.md`, `gate-M.md`.

v0.2 split the Tester's output into **visible tests** for the Coder and **held-out tests** kept outside the repo for acceptance, and gave Punk a way to take and read screenshots. Then it got its first real job: Milestone 1 of a native desktop pet app (Tauri, Rust, TypeScript), run on Codex.

---

## Iteration 2 (v0.2 → v0.3): the desktop pet post-mortem

Milestone 1 passed every automated test on the first loop. Then the CEO opened the repository:

1. **Paperwork.** Five tasks produced **66 workflow files, about 24,000 words**. The CEO stopped reading after the first one. A gate whose material cannot be read in three minutes becomes a rubber stamp.
2. **Micromanaging briefs.** Briefs of 8–9 KB dictated about 85% of the internal interface decisions, leaving the Coder little to decide.
3. **No tests where the bugs were.** Not one test reached the native window and orchestration layer, which is where the defensive code had piled up. No held-out test ever failed.
4. **Smuggled defenses, about 200 lines.** Despite the prompt, the code carried **11 state flags, two version counters and triple resets**. They broke no test, so Main's review passed them.
5. **Quiet changes.** A reminder feature moved behind an "Advanced" submenu without anyone telling the CEO. And with no Git configured, the agent invented its own snapshot scheme and produced a **5.2 GB** working copy, dependencies and build output included.

### What v0.3 changed

- **Page budgets and a closed file layout.** Brief, test plan, Punk report and gate packet: one page (about 500 words) each. No other files.
- **A one-page gate packet** with a mandatory list of **every feature removed, hidden or moved**.
- **A named risk layer.** Every brief names the layer most likely to break, and at least one test (or a written manual check) must reach it.
- **`## Defenses added`.** The Coder lists every guard, flag, retry or fallback it added, with the failure it prevents. Anything defensive in the diff that is not listed fails review.

---

## Iteration 3 (v0.3 → v0.4): prompt rules lose to model habits, so enter `gw.py`

Reviewing v0.3 made one thing plain: **a prompt is a request; a heavily RL-trained habit is a reflex.** "Do not edit files outside the brief", "keep sections short", "do not look for the held-out tests" mostly hold, and give way when a task gets hard.

There was a second cost. Making Main create worktrees, copy held-out tests and run merges by hand filled its context with mechanics. A separate model with a clean context found the 11 flags that Main's review had passed.

v0.4 moved every mechanical rule out of prose and into **`scripts/gw.py`**, a single Python file using only the standard library:

```text
[briefed] -> gw planned -> [planned] -> gw seal   -> [sealed]   -> gw open    -> [coding]
[coding]  -> gw check   -> [review]  -> gw review -> [reviewed] -> gw holdout -> [passed]
[passed]  -> gw merge   -> [merged]  -> gw close  -> [done]
```

Out-of-order steps are refused, with the command to run next.

### Three mechanisms in v0.4

1. **Held-out sets are single use (`gw seal`, `gw burn`).** Held-out tests are sealed in `~/.gw-vault/`, outside the repository, and copied into the worktree only for the run. If a set fails, Main's feedback to the Coder leaks part of it. So `gw burn N` turns the spent set into visible tests and the Tester writes a fresh one. The vault is not a sandbox; single use is what makes a peek worthless.
2. **Orchestration as a headless state machine.** For UI, window lifecycles and timers, split the code in two:
   - **Pure core:** `step(state, event) -> (state, effects)`, plain data in and out, with time arriving as an event (`Tick(now)`). The Tester drives it with reordered, duplicated and interleaved event sequences, and the tests run in milliseconds.
   - **Thin shell:** turns OS or DOM facts into events and executes effects one to one. `gw check` scans shell files and fails the task if one imports the state type. The shell has no unit tests by design; Punk and the CEO test it by using it.
3. **A document linter (`gw docs`).** Every file in `docs/workflow/` is either a **record** (tables only, no prose) or a **thinking** file (at most three sentences per heading, bullets of at most 40 words). `gw docs` counts and refuses.

---

## Iteration 4 (v0.4 → v0.5): the *Flow Timer* benchmark

With v0.4's gates in place we ran a four-way comparison. The task was *Flow Timer*, a focus timer with idle detection, written with **four deliberately planted ambiguities**: idle starting with under two minutes left, idle interleaved with a manual pause, rapid clicks, and a return inside the grace window (including the countdown crossing zero inside it).

1. `graph-workflow` v0.4 on **Claude Code**
2. `graph-workflow` v0.4 on **Codex**
3. a **single agent** on Claude Code, no workflow
4. a **single agent** on Codex, no workflow

### The numbers

| | v0.4, Claude Code | v0.4, Codex | Single, Claude Code | Single, Codex |
| :--- | :--- | :--- | :--- | :--- |
| Finished | yes | under half | yes | yes |
| Active build time | ≈ 101 min | — | ≈ 10 min | 15 min |
| Orchestrator tokens | 410k peak, 40.7M cache reads | 48.1M total, 12.9M of it in 145 approval reviews | 161k peak, 4.5M cache reads | 1.1M cache reads |
| Planted cases put to the human | 0 / 4 | 0 / 4 | 0 / 4 | 0 / 4 |
| Planted cases pinned by tests | 4 / 4 | — | 2 / 4 | 2 / 4 |
| Six common UX faults shipped | 0 of the 4 checked (2 not checked) | — | 6 / 6 | 6 / 6 |
| Tests : product code (lines) | ≈ 5 : 1 (192 unit + 17 e2e) | — | 0.8 : 1 | 0.9 : 1 |

Start with the uncomfortable part. **The workflow did not produce a more correct timer.** All three finished builds behave identically on the four planted cases. What the extra ten times the time bought was evidence and safety: every planted case pinned by a test, a confirmation before skipping a session, a warning before leaving, state in the tab title, and browser tests.

Four findings shaped v0.5.

#### 1. With or without a workflow, ambiguous cases are decided silently

None of the four builds asked about any planted case. The workflow did ask the CEO four questions up front; none of them was one of the four. The single agents agreed with it on the planted cases, but each made another undisclosed call. Single Codex counts a return inside the grace window as an interruption. Single Claude starts the two-minute away timer from the last input rather than from the tab switch. Both are defensible, and nobody was told.

**v0.5: a Gate 1 edge-case sweep.** The PRD gets an eight-column `## Edge cases` table. Main goes through every requirement against seven categories (`threshold`, `interleave`, `repeat`, `time-cross`, `counting`, `environment`, `failure`) and writes a row, with options and a recommendation, for each case that reads two ways. Categories with nothing in dispute get one `- No dispute:` line instead, so the table does not become requirement × category. The CEO fills the `Decision` column. **`gw gate 1` refuses until every category is covered and every row carries the CEO's decision, and `gw brief` refuses before Gate 1.** Each brief copies its rows verbatim, and every row must be named by a test.

#### 2. A builder does not see its own product

Both single-agent builds shipped all six of a set of common UX faults: skip with no confirmation, no state in the tab title, text contrast below WCAG AA, focus not moved to a banner that appears, touch targets under 44 px, and nothing against losing a session on reload. The single Codex agent had taken four screenshots and fixed a phone layout itself, and still missed contrast and focus. What was missing was a reviewer whose only job is to object, not a pair of eyes.

**v0.5:** those six are now Punk's `Always check` table, and the report must say which it checked.

#### 3. Verification volume

On Claude Code, verification took **47% of the 139-minute wall time** (Tester 36 min, Punk 29 min), while the Coder took **6%** (8 min); another 27% was waiting for the CEO at gates. The Tester wrote 192 unit tests against a cap of 171 that existed only in prose, about five lines of test code per line of product code. And 25 of the tests (13%) opened files under `src/` to look for strings in the source instead of checking behavior.

**v0.5:** `gw planned N` counts test cases with a regex, allows at most **one visible and two held-out tests** per acceptance criterion or edge row, and refuses any test that reads product source files as text.

#### 4. The coordination tax

Why did Main read 40.7M cached tokens? A long-running orchestrator session pays for its whole context on every turn, and Main's grew from 79k to 410k tokens; 26% of its requests were turn ceremony. On Codex the cost showed up differently: an approval reviewer ran 145 reviews worth 12.9M tokens, and the agent stopped to ask the CEO after every task.

**v0.5, as a prototype: `gw drive`.** Instead of Main scheduling the script, **the script schedules Main**. Each step of a task (brief → tests → spec check → code → review → loop notes) runs as a **fresh `claude -p --output-format json` session with no earlier conversation**, given only that step's file paths, with `gw`'s gates between steps. Main becomes a judge that ends with `VERDICT: done | pass | fail | rerun-tester | stop`. `gw finish N` runs review pass → held-out run → merge → close as one call that stops at the first failure. So far `gw drive` has run end to end only against a fake CLI; whether it actually lowers the tax is the next experiment.

Smaller fixes came from the same run. `git worktree remove --force` followed a Windows junction for `node_modules` and emptied the main checkout's copy, so `gw close` now removes links before deleting a worktree and can be rerun after a partial failure.

---

## What we would tell you to take

- **For a small project, do not take the whole thing.** On Flow Timer a single agent was about ten times cheaper and just as correct. Take the Gate 1 edge-case sweep and a Punk pass; together they cover the two gaps the single agents actually had.
- **For a multi-milestone build,** the parts that keep paying are the held-out sets, the over-defense audit, the headless state machine for glue code, and putting every rule a script can check into the script.
- **v0.5 is experimental.** Its answers to the benchmark have not yet run on a real project; the next test is a large one.

`graph-workflow` v0.5 is MIT-licensed, needs only the Python 3.8+ standard library, and installs into your personal skills folder (`~/.claude/skills/graph-workflow`). Benchmarks, failure reports and PRs are welcome, especially the ones that show where it does not help.

👉 **GitHub:** https://github.com/Ramirez0291/graph-workflow

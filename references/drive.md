# gw drive — script-led orchestration (prototype)

`gw drive N [N ...]` inverts the control: the script schedules, Main only judges. It takes each task from its current state to done, in the order given, starting every step as a fresh `claude -p --output-format json` session with only that step's inputs:

| Step | Session | Inputs |
|---|---|---|
| brief | Main | PRD with edge cases, architecture index, the task row |
| tests | Tester | brief, output folder |
| spec check | Main, only when `gw planned` found something to judge | brief, test plan, test folders |
| code | Coder, cwd = its worktree | brief, visible tests |
| check, holdout, merge, close | gw itself, no model | — |
| review | Main | brief, handoff, diff, `gw check` output |
| loop notes | Main | the failed run's output |

- Main sessions end with `VERDICT: <word>`; the script reads only that line. A blocked Coder gets one Main session to fix the brief, at most twice, and then runs again.
- **A refusal goes back to its author, once.** `gw brief` refuses: Main rewrites the brief. `gw planned` refuses: the Tester fixes its files. `gw check` fails: the Coder fixes its output before any review is spent on it. None of these uses a loop. The brief's author and the Tester are told to run `gw try` before they finish, so most refusals should not happen at all.
- **Only judgment uses a loop.** A failed held-out run uses one of the task's three loops. So does a review that ends `VERDICT: fail: <ids>`, when the ids are acceptance criteria or edge rows of the brief, `check` (while `gw check` fails) or `cheat`. A fail that names none of these is asked again once; so is a pass while `gw check` fails. If the second session does not settle it, the drive stops and no loop is used.
- **No spec session when there is nothing to judge.** `gw planned` records whether the test set has a held-out file to audit or the test plan an open item (an ambiguity, a criterion it could not test, a risk layer it could not reach). Whatever it cannot read as "none" counts as open. If nothing is open, the script commits the brief and seals.
- **A stop ends the queue and leaves one page,** `docs/workflow/.gw/stop-N.md`: when, the task's state and loop, why, who has to act (the CEO, Main in a fresh session, or nobody's judgment), the next command, the command that resumes the queue, the last `gw` output and the task's log rows. `gw next` names the page; it is deleted when the task is driven again or closes. Whoever picks the work up reads STATE and that page, not the drive's output.
- It stops at: Gate 1 not passed, a parked task, a refresh conflict or drift, a step refused twice, a review that does not settle, `VERDICT: stop`, any session error, or a crash of the script itself (the page then carries the error). A step that needs an approval the PRD's Approvals table does not hold ends `VERDICT: stop: needs approval: <what>`. Gates stay interactive. The CEO's answer on a parked task goes in with `gw unpark N "<words>" [state]`.
- Each session's tokens, cost, wall-clock seconds, turns, session id and model go into `log.md`. Tokens come from the JSON's `modelUsage`, which adds up the whole session; its `usage`, `duration_ms` and `num_turns` cover only the last stretch of a session that was woken again. A session that timed out or returned no JSON is logged with its seconds.
- **No background tasks.** Sessions run with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`. A session that starts one ends its turn and is woken when the task finishes; the result the script reads is then only the last stretch, and a `VERDICT` written earlier is lost.
- `drive` in gw.json: `command` (default `claude`), `permission_mode` (default `dontAsk`; tools come from each agent file's `tools:` line), `models` per role, `max_budget_usd` per session, `step_timeout_min`, `extra_args`, `env` (added to the default above, not replacing it). Set `models`: unset, every session runs on the account's default model.
- Agent files: the repo's own `.claude/agents/gw-<role>.md` wins over the skill's copy. Keep it in step with the skill's when the skill changes.
- Claude Code only. Other harnesses wait until the skill is open-sourced.

Use it for a milestone's build. Start it from a small, fresh session, or from a terminal, and let that session do nothing else until the drive ends: each time a long session is woken, its whole context is read again. Keep planning and gates in sessions of their own.

## Configuration example

```json
"drive": {
  "command": "claude",
  "permission_mode": "dontAsk",
  "models": {"main": "<strongest>", "coder": "<fast coder>", "tester": "<fast coder>"},
  "max_budget_usd": 5,
  "step_timeout_min": 60,
  "extra_args": [],
  "env": {}
}
```

`dontAsk` denies every tool call the agent file's `tools:` line does not allow, with nobody to ask. Each session's permission denials are counted in `log.md`; a step that needed a denied tool shows up there. The Coder session gets no `--add-dir`, so its file tools reach only its worktree. Tester sessions get the test folder (and the worktree on a later loop); Main's review gets the worktree.

## What the prototype does not do yet

| Gap | Today |
|---|---|
| Parallel tasks | a queue runs one task at a time; for two at once, run two queues in two terminals |
| A stop in the middle of a queue | the queue ends there, also for the tasks that do not depend on the stopped one |
| Tester one task ahead | not scheduled |
| Refresh conflict, drift | stops; Main resolves interactively |
| Punk, gates | not driven; they stay in sessions of their own, with the CEO |
| Other harnesses | Claude Code only |

## How it was tested

End to end on a toy repository with a fake `claude` that writes files per step. The flag combination (`-p`, stdin prompt, `--output-format json`, `--permission-mode dontAsk`, `--allowedTools`, `--add-dir`) was checked against Claude Code 2.1.316; the system prompt goes in through `--append-system-prompt-file`, which that version lists, because cmd.exe mangles multi-line arguments when `claude` is an npm `.cmd` shim.

It then ran one milestone of a real project: seven tasks, 67 sessions. It stopped nine times, never for a decision: five on a commit hook that rejected test files inside `gw merge`, two on Files lines that carried notes, two on its own defects. Two tasks were parked after three failed reviews that the CEO then overruled. Seven of the 67 log rows under-reported tokens and time, because those sessions had started background tasks. The session that launched the drives was woken 23 times by them and grew from 122 to 519 thousand tokens of context.

v0.7 answers each of these. `tests/test_gw.py` replays them on a toy repository with a fake `claude` (`python3 -m unittest discover -s tests`). The background-task behavior, the JSON's `modelUsage` and the PreToolUse hook (its input and exit code 2) were checked against Claude Code 2.1.318. The queue and the stop page have not yet run a real milestone.

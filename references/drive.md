# gw drive — script-led orchestration (prototype)

`gw drive N` inverts the control: the script schedules, Main only judges. It takes task N from its current state to done, starting every step as a fresh `claude -p --output-format json` session with only that step's inputs:

| Step | Session | Inputs |
|---|---|---|
| brief | Main | PRD with edge cases, architecture index, the task row |
| tests | Tester | brief, output folder |
| spec check | Main | brief, test plan, test folders |
| code | Coder, cwd = its worktree | brief, visible tests |
| check, holdout, merge, close | gw itself, no model | — |
| review | Main | brief, handoff, diff, `gw check` output |
| loop notes | Main | the failed run's output |

- Main sessions end with `VERDICT: <word>`; the script reads only that line. A Coder block gets one Main session to fix the brief, at most twice.
- It stops for a person at Gate 1, Gate 3, a parked task, a refresh conflict or drift, a step refused twice, `VERDICT: stop`, or any session error. Gates stay interactive.
- Each session's tokens, cost, turns, duration and session id go into `log.md`.
- `drive` in gw.json: `command` (default `claude`), `permission_mode` (default `dontAsk`; tools come from each agent file's `tools:` line), `models` per role, `max_budget_usd` per session, `step_timeout_min`, `extra_args`. Set `models`: unset, every session runs on the account's default model.
- Claude Code only. Other harnesses wait until the skill is open-sourced.

Use it for build loops on a large project, where Main's growing context is the cost; keep planning and gates in your own session.

## Configuration example

```json
"drive": {
  "command": "claude",
  "permission_mode": "dontAsk",
  "models": {"main": "<strongest>", "coder": "<fast coder>", "tester": "<fast coder>"},
  "max_budget_usd": 5,
  "step_timeout_min": 60,
  "extra_args": []
}
```

`dontAsk` denies every tool call the agent file's `tools:` line does not allow, with nobody to ask. Each session's permission denials are counted in `log.md`; a step that needed a denied tool shows up there. The Coder session gets no `--add-dir`, so its file tools reach only its worktree. Tester sessions get the test folder (and the worktree on a later loop); Main's review gets the worktree.

## What the prototype does not do yet

| Gap | Today |
|---|---|
| Parallel tasks | one task per `gw drive` call; run two calls in two terminals for parallel tasks |
| Tester one task ahead | not scheduled; start `gw drive N+1` while N is coding |
| Refresh conflict, drift | stops; Main resolves interactively |
| Punk, gates | not driven; they stay in Main's own session with the CEO |
| Other harnesses | Claude Code only |

## How it was tested

End to end on a toy repository with a fake `claude` that writes files per step: brief, tests, spec check, code with a bug, a failing held-out set, Loop notes, a burned set, a fresh set, a fixed Coder, review, merge and close, ten sessions in all. The flag combination (`-p`, stdin prompt, `--output-format json`, `--permission-mode dontAsk`, `--allowedTools`, `--add-dir`) was checked against Claude Code 2.1.316; the system prompt goes in through `--append-system-prompt-file`, which that version lists, because cmd.exe mangles multi-line arguments when `claude` is an npm `.cmd` shim. It has not yet run a real project.

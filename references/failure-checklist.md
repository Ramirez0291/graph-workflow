# Failure checklist

Derived from MAST, *Why Do Multi-Agent LLM Systems Fail?* (arXiv 2503.13657, 1,642 traces, 14 failure modes). Percentages are how often each mode appeared. Run the relevant block before closing a phase or a task. Mechanical checks belong to `gw.py`; these rows are the judgment it cannot make.

## Before sending a brief (Main)

| Mode | % | Check |
|---|---|---|
| Disobey task specification | 11.8 | Does the brief restate the goal and the acceptance criteria in its own words? Are the edge rows it touches copied verbatim? Could a stranger build this? Does the Interface section name everything the tests will call, and nothing a test does not call? Is it within its word budget? Does it name the risk layer? Does the Serves line quote the PRD criterion? If the task touches a Non-negotiable, is it an acceptance criterion? For an orchestration task, is the Interface an events table and an effects table, with time as an event? Did `gw brief N` pass? |
| Unaware of termination | 12.4 | Does the brief say what done looks like and what the test command is? |
| Fail to ask for clarification | 6.8 | Did you tell the Coder that `blocked` is acceptable and guessing is not? |

## At the spec check, before opening the worktree (Main)

| Mode | % | Check |
|---|---|---|
| Fail to ask for clarification | 6.8 | Is every item in the Tester's ambiguity list resolved in the brief, not in your head? Is every product question among them a PRD edge row marked `Main provisional`, copied into the brief? |
| Incorrect verification | 9.1 | Does every held-out case cite a criterion? Any that does not is a new requirement: delete it or put it in the brief. Does at least one test, or a written manual check, reach the risk layer? |
| Information withholding | 0.85 | Is the vault path absent from every file in the repo? On a later loop, does the fresh held-out set differ from every spent set? |

## Before Gate 2 (Main)

| Mode | % | Check |
|---|---|---|
| Step repetition | 15.7 | Is this the third loop on the same task? Stop and bring the CEO the diagnosis (unattended: park it). Did each failed review name an acceptance criterion or an edge row? A finding the brief did not ask for is a `deferred` row, not a loop. |
| Reasoning–action mismatch | 13.2 | Does the handoff's "Changed" list match the diff? Does the test plan's Cases table match the test files? |
| No or incomplete verification | 8.2 | Did every step go through `gw` (no hand-made worktrees, copies or merges)? Did `gw check` pass before you reviewed? |
| Incorrect verification | 9.1 | Does any code branch on the exact inputs the visible tests use? For orchestration, does any decision live in the shell instead of the core? |
| Task derailment | 7.4 | Did the diff touch files outside the brief's list, directly or through a cast or duplicate? Is every defensive piece in the diff (flag, counter, guard, repeated reset, re-validation, double fetch, catch-all, clamp) on the handoff's "Defenses added" with a named failure? Is the main checkout free of changes you did not make? Did the audit delete anything on the Non-negotiables list? |
| Premature termination | 6.2 | Is every acceptance criterion in the test plan's Cases table, or did a "pass" skip one? |
| Information withholding | 0.85 | After a failed run, are the Loop notes behavior rather than test code? Was the spent set burned (`gw burn`) and a fresh one written? |

## Before Gate 1 and Gate 3 (Main, with the CEO)

| Mode | % | Check |
|---|---|---|
| Disobey task specification | 11.8 | Does every PRD success criterion map to a task? Does the milestone demo show a PRD user task? |
| Fail to ask for clarification | 6.8 | Gate 1: did every requirement go through every edge category, and did the CEO, not you, write each Decision? Did the Approvals sweep go through every category, so that no build session has to ask? Gate 3: is every `Main provisional` row in the gate packet for the CEO to confirm? |
| Ignored other agent's input | 1.9 | Is every Punk objection in `decisions.md` with accept / reject / defer and a reason? Did Punk's report say which "Always check" faults it checked? |
| Loss of conversation history | 2.8 | Is `STATE.md` current, including mode and parked tasks? Would a fresh session know what to do next? Is `log.md` up to date? |
| Information withholding | 0.85 | Is anything the CEO needs to decide sitting only in your head or in chat? Does the gate packet list every feature removed, hidden or moved? |
| No or incomplete verification | 8.2 | Did any held-out test fail during this milestone? If none did, do the tests reach the layers where the code actually changed, or only the easy ones? |
| Unaware of termination | 12.4 | Is the gate packet within its 400-word budget, in the CEO's language? Is `gw docs` clean? After approval, did `gw archive` move the milestone to cold storage? |

## Every session start (Main)

| Mode | % | Check |
|---|---|---|
| Conversation reset | 2.2 | Did you start from `STATE.md` and `gw next`, in a fresh context for this purpose (plan, build or gate)? If `gw next` named a stop page, did you read it before anything else? |
| Disobey role specification | 1.5 | Are you about to write code that should go through a brief? Are you about to skip the Tester because you are confident? |

## What MAST's own fixes showed, and what they did not

The MAST authors tried two kinds of fix on two systems (Table 5 of the latest version):

| System, benchmark | Baseline | Better prompts | New topology |
|---|---|---|---|
| ChatDev, ProgramDev-v0 (32 tasks) | 25.0 | 34.4 | 40.6 |
| ChatDev, HumanEval | 89.6 | 90.3 | 91.5 |
| AG2 MathChat, GSM-Plus, GPT-4 | 84.75 | 89.75 | 85.50 |
| AG2 MathChat, GSM-Plus, GPT-4o | 84.25 | 89.00 | 88.83 |

- ChatDev's "better prompts" were role specifications: only a superior role such as the CEO may end a conversation, and the verifier's role was strengthened. Its "new topology" made the graph cyclic, ending only when the CTO confirms the reviews are satisfied, with an iteration cap. In this workflow those correspond to the CEO deciding at Gates 1 and 3, and Gate 2's bounded review loop.
- On ProgramDev the gains are 3 and 5 extra tasks out of 32. On HumanEval they are under two points. On AG2 the prompt fix beat the topology change.
- The authors' own conclusion: these fixes help but are not sufficient, and more fundamental changes are needed.

So neither structure nor wording reliably wins, and the systems measured ran GPT-4-era models with chat hand-offs, not this workflow. If something keeps failing, read `log.md` to find the node that fails, then change the smallest thing that fixes it, whether that is a sentence in a brief, the brief's shape, a gate or the task cut.

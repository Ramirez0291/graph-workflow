# graph-workflow — research notes (2026-10-31 → 11-03)

Goal: a Claude Code skill that runs a big product build as a **graph of roles**
(PM, PjM, Architect, UI/UX, Test, DBA, Security …), where every role is
"Claude + USER", and USER is the human CEO with final say.

## 1. Sources worth reading

### arXiv

| Paper | Why it matters |
| --- | --- |
| MAST — *Why Do Multi-Agent LLM Systems Fail?* (2503.13657, NeurIPS 2025) | 14 failure modes in 3 categories from 1,642 traces. Use as a design checklist. |
| *Designing LLM-based MAS for SE Tasks* (2511.08475) | 16 design patterns from 94 papers. Role-Based Cooperation (47%), Self-Reflection (36%), Cross-Reflection (13%) dominate. Security is a design goal in only 3% of papers. |
| *Rethinking the Value of Multi-Agent Workflow: A Strong Single Agent Baseline* (2601.12307) | One LLM running the whole role chain as one conversation matched multi-agent on 7 benchmarks at lower cost. Fan out only when you need isolated context, parallelism, or different models. |
| *From Static Templates to Dynamic Runtime Graphs* (2603.22386) | Survey of workflow-as-graph optimisation (AFlow, GPTSwarm, MaAS, Flow, G-Designer, DyFlow). Key advice: start with a constrained static scaffold; inspect traces before tuning prompts; add graph-level changes only when traces show structural failure; minimum plasticity. |
| Flow: Modularized Agentic Workflow Automation (2501.07834) | Workflow = Activity-on-Vertex DAG, edited at runtime. |
| GPTSwarm (2402.16823) | Agents as optimisable graphs: nodes = prompts, edges = information flow. |
| ChatDev 2.0 / DevAll (2609.00714) | "Declarative executable graph" with a cycle-aware engine and human-in-the-loop steps, no-code UI. |
| MetaGPT (2308.00352) | "Code = SOP(Team)": PM → PRD, Architect → design/API/data, PjM → task list, Engineer → code, QA → tests. Roles pass **structured documents**, not chat. |
| A Survey on Agent Workflow (2508.01186); Multi-Agent Collaboration Mechanisms survey (2501.06322) | Background. |

### GitHub

| Repo | Shape | Take-away |
| --- | --- | --- |
| bmad-code-org/BMAD-METHOD (MIT, ~55k stars) | Agile role agents: Analyst, PM, Architect, Scrum Master, Dev, QA (~21 agents, 50+ workflows). Claude Code plugin in v7. | Story files carry context to the Dev agent (story + architecture + conventions). Scales down: small fix skips planning. Users complain about context cost and PM/Architect drift; they add manual handoff checklists. |
| automazeio/ccpm (MIT, ~8k stars) | PRD → epic → tasks → GitHub issues → parallel agents in worktrees. | Tasks carry `depends_on / parallel / conflicts_with`. State lives in markdown files in the repo; main conversation = coordinator only. |
| zhsama/claude-sub-agent | 8 spec-* subagents in 3 phases with 3 quality gates (95 / 80 / 85) that loop back on failure. Mermaid graph in README. | Cleanest "gates with loop-back" example for Claude Code. |
| FoundationAgents/MetaGPT (MIT, ~71k stars) | Reference implementation of SOP roles + publish/subscribe message pool. | Too heavy to adopt; steal the artifact chain. |
| OpenBMB/ChatDev | Virtual software company (CEO/CTO/programmer/reviewer/tester). | MAST case study on it (ProgramDev-v0, 32 tasks): role-spec prompts incl. CEO final say 25.0 → 34.4; cyclic topology ending on CTO-confirmed review 25.0 → 40.6. Small sample; HumanEval moved under 2 points. |
| VoltAgent/awesome-claude-code-subagents, rahulvrane/awesome-claude-agents | Role prompt libraries (160+). | Mine for role prompts; do not install wholesale. |
| ibm/awesome-agentic-workflow-optimization | Curated paper list for graph optimisation. | Reading list. |
| GitHub Spec Kit | Spec artifacts (spec → plan → tasks). | "Spec Kit organises artifacts, BMAD organises people." We want both. |

## 2. Patterns to steal (ranked)

1. **Edges are documents, not chat.** Every node consumes typed artifacts and emits one (PRD, architecture.md, threat-model.md, schema.md, tasks.md, story-N.md, test-report.md). Context for a node = only the artifacts it needs. (MetaGPT, BMAD, ccpm)
2. **Verification against the objective is cheap and catches the costliest error.** In MAST's ChatDev case study the review-loop topology gave the largest gain (+15.6 points, i.e. 5 of 32 tasks), but on AG2 a prompt fix beat the topology change, so treat it as a strong default, not a law. Put a verifier after every phase, and give the CEO final say at gates.
3. **Gates with bounded loop-back.** Three gates (plan / build / release), each with explicit pass criteria and a max retry count. (zhsama; MAST FM-1.3 step repetition 15.7%, FM-1.5 unaware of termination 12.4%)
4. **Role is not the same as agent.** Run the role chain as one conversation (single-agent baseline) by default. Spawn a separate agent only when: (a) fresh eyes are needed (tester, reviewer, security must not share the developer's context), (b) tasks are independent and parallel, (c) context would overflow. (2601.12307, Cross-Reflection pattern)
5. **Scale the graph to the task.** Classify first: tiny fix → Dev only; feature → PM+Arch+Dev+Test; new product → full graph. (BMAD, survey "minimum plasticity")
6. **Parallelism by file scope + dependency metadata.** Tasks declare `depends_on`, `parallel`, `conflicts_with`; each agent owns a file set; integrate via worktrees or the Workflow tool. (ccpm)
7. **Human-in-the-loop as a first-class node type.** USER approves at gates, resolves PM/Architect conflicts, and owns product judgement. (ChatDev 2.0, Human-Reflection pattern)
8. **State lives in the repo, not in the conversation.** A `docs/` (or `.workflow/`) folder is the graph's memory; the coordinator conversation stays thin. (ccpm, BMAD)
9. **Design against the failure taxonomy.** Checklist per node: task spec restated? role boundaries? termination condition? reasoning→action consistent? verification present and correct? (MAST)
10. **Trace before you tune.** Log every node run (inputs, outputs, gate result). Change prompts only after traces show which node failed; change topology only after structural failures recur. (2603.22386)
11. **Security as an explicit node.** Almost nobody does it (3.2%); a threat-model node on PRD+architecture and a re-check before release is cheap differentiation.

## 3. Draft graph (to discuss with Rami)

```mermaid
Rami: idea --> PM: PRD --> [ UX: flows+wireframes || Architect: design/API/data || Security: threat model ]
                                   |
                           DBA: schema review --> Planner: tasks.md (depends_on / parallel)
                                   |
                           <-- GATE 1 (R approves plan; verifier checks PRD coverage) -- loop <=3
                                   |
     per task (parallel where allowed): Dev --> Test (fresh ctx) --> Review (fresh ctx) --> GATE 2 -- loop <=3
                                   |
                           Integrate --> Security re-check --> Release verifier --> GATE 3 (R) --> done
```

Node types: `human`, `role` (prompt + artifact in/out), `verifier`, `gate`, `parallel`, `loop(max)`.
Representation: one YAML/Markdown graph file per project + role prompt files; runnable via Claude Code subagents / Workflow tool.

## 4. Implementation options

| Option | Pros | Cons |
| --- | --- | --- |
| A. Adopt BMAD or ccpm | Mature, documented | Heavy (21 agents), opinionated, less learning |
| B. Build own thin skill (recommended) | Fits Claude Code natively (skill + `.claude/agents` + Workflow tool); we understand every edge; grows with us | We own the maintenance |
| C. Hybrid | Steal BMAD artifact templates + ccpm task metadata, own graph runner | Best of both; slightly more upfront design |

## 5. Decision 2026-10-31 — Rami's team: 4 agents, not 8

Rami's reasoning: Claude is strong enough now; every extra hand-off loses information. Keep the team small.

| # | Agent | Model | Role bundle | Context it sees |
| --- | --- | --- | --- | --- |
| 1 | **Main** | strongest available | PM + Architect + orchestrator + code reviewer. Talks to R. Owns PRD, architecture, tasks.md. | Everything (repo files are its memory so it survives compaction) |
| 2 | **Coder** | fast coder, highest reasoning setting | Implements one task brief at a time. | brief-N.md + the files named in it + relevant architecture excerpt. Returns code + handoff-N.md |
| 3 | **Tester** | fast coder, highest reasoning setting | Writes/runs tests from acceptance criteria. Fresh context, never sees Coder's reasoning. | brief-N.md + acceptance criteria + code |
| 4 | **Punk** | strong judgment + vision | UI/UX designer + objector / devil's advocate. Reviews the whole product and raises ranked objections and UX proposals. | PRD + architecture + running product / screens; not the chat history |

Graph:

```mermaid
R <--> Main: PRD, architecture.md, tasks.md
Main --> Punk (round 1, before code): objections on PRD + architecture --> Main triages --> USER decides
per task:
  Main --> Coder: brief-N.md --> code + handoff-N.md
  Main --> Tester (fresh): brief-N.md + code --> test-report-N.md      (Tester and Main review run in parallel)
  Main reviews diff + test report --> pass, or back to Coder with failures (loop <= 3)
per milestone / demo:
  Main --> Punk: whole product --> objections.md (top 5, each with cost/benefit)
  Main triages: accept -> new tasks; reject/defer -> written reason; USER arbitrates disagreements
release: Tester full regression + Punk final pass + USER gate
```

### Rules added by USER (2026-10-31)

**Punk scope.** Punk reviews the *product* and *UI/UX* only: does it solve the user's problem, is it usable, what is missing, what is ugly. Punk does not review code. Code quality is Main's job.

**Over-defense is a failure mode.** Observed: Coder and Tester pile up hashes, probes, snapshots, gates, smoke tests, acceptance matrices until the program has scaffolding and no function. Main, as Architect, must make the trade-off: which hardening is justified, which is over-defense, which creates tech debt that costs more than it saves.

Mechanisms:

1. **Function first.** Order of work for every task: make it work end-to-end → make it right → harden. Hardening is a separate task that Main schedules deliberately; Coder never improvises it.
2. **No unrequested infrastructure.** Coder may add defensive scaffolding only if the brief names it. Anything else goes into handoff-N.md under "suggested hardening" for Main to decide.
3. **Tests are bounded by acceptance criteria.** Tester writes one or a few tests per acceptance criterion, uses the test command in the brief, and adds no new test infrastructure. Tester's success metric is "criteria verified with the smallest test set", not "most tests".
4. **Main's review has an over-defense audit.** For each non-functional piece in the diff: what failure does it prevent, how likely is that failure, what does it cost to maintain. Keep, simplify, or delete. Write the decision down.
5. **Tech-debt ledger.** `debt.md` records hardening that Main consciously deferred, with the trigger that would make it worth doing. Deferred is a decision, not an accident.
6. **Punk is the function detector.** Because Punk uses the product like a user, a build that is all scaffolding and no feature fails Punk's review loudly.

Hand-off rules to stop information loss: the brief carries goal, acceptance criteria, file list, constraints, test command; the handoff report carries what changed, what is uncertain, how to run. Nothing important lives only in chat.

## 6. USER answers (2026-10-31)

- Size: months-level in vibe coding (half a year if human-coded). So: milestones, repo-state, session protocol are mandatory, not optional.
- Git: yes.
- Gates: USER approves Gate 1 (plan) and Gate 3 only. Gate 2 (per task) is automatic: Main review + Tester pass.
  Main's amendment: Gate 3 runs **per milestone**, not once at project end, otherwise USER sees nothing for months. USER to confirm.
- Models: strongest model for Main, a fast coding model at its highest reasoning setting for Coder and Tester, a strong-judgment model for Punk (from USERami's team design; written as tiers in v0.2 so the skill is not tied to one model family).

## 7. Draft v0.1 written (2026-10-31)

SKILL.md, agents/gw-coder.md, gw-tester.md, gw-punk.md, references/failure-checklist.md, templates/ (STATE, PRD, architecture, tasks, brief, handoff, test-report, objections, decisions, debt). Not yet tested on a real project.

## 8. v0.2 decisions (2026-10-31)

**Tester moves before the code.** It writes visible tests (given to the Coder), held-out tests (kept back), and a test plan whose ambiguity list Main resolves in the brief before any code is written.

- AgentCoder (arXiv 2312.13010): a test-designer agent that never sees the code. In its GPT-3.5 ablation, tests written by the same agent that wrote the code had 61.0% accuracy on HumanEval; a separate test designer reached 87.8%. Old models and function-level tasks, and the paper does not separate the two causes it names (divided attention, tests inheriting the code's errors). Direction, not proof.
- SpecBench (arXiv 2605.21384): visible tests exercise features in isolation, held-out tests combine them. Every frontier agent saturates the visible suite; the held-out gap grows about 28 points per tenfold increase in code size; one agent produced a 2,900-line hash-table "compiler" that memorised test inputs. A months-long project lands exactly where the gap is largest.
- Rule taken from SpecBench: held-out tests check what the brief already says (other inputs, combinations, realistic use). A case the brief does not justify is a new requirement, not a test.

**Considered and rejected: drop the Tester, let Main accept.** Main has no fatigue, but its context is its budget and Main is the one role that must stay sharp for months. And the author of a brief is its worst reader for ambiguity, because the author already knows what was meant. The simplification it wanted is kept: after the code, acceptance is a test run plus Main's review, with no second LLM call.

**Held-out tests live outside the repo** (`<repo>.tests/N/`). Loop feedback to the Coder describes failing behavior only; a pasted held-out test stops being held-out. After the task merges, all its tests join the regression suite.

**One git worktree per task** (`<repo>.gw/N/`, branch `gw/N`), parallel or not. Fixes v0.1's shared working tree: parallel test runs interfering, diffs mixing tasks, the Tester's files landing in a review. It also keeps held-out tests out of the Coder's tree. Separation, not a sandbox: the Coder has Bash.

**Punk gets eyes.** The Demo section of architecture.md says how to start the product and take screenshots (Playwright CLI or a throwaway script). Punk reads the images and cites them per objection. When that fails, Main or USER supplies screenshots; Punk never falls back to reading code.

**Models as tiers.** Agent files no longer pin a model or reasoning effort. SKILL.md describes three tiers (strongest; fast coder; judgment + vision) and each installation maps them to whatever family its harness runs. Punk's tier must read images.

**Also merged into v0.2 from the first review:** unattended mode (park instead of stop), Non-negotiables at trust boundaries (audit may simplify, never delete), trigger words scoped to repos with docs/workflow/, MAST claims corrected in the failure checklist, a run log, the CEO instead of a hard-coded handle, and a Serves line in every brief.

## 9. First run (2026-10-31 → 11-01): v0.2 on Codex, Physics Clawd Pet M1

**Setup.** The baseline desktop pet (Tauri 2 + TypeScript + Rust, built earlier by single-agent chat) was copied to `rebuild/` and M1 ran as five tasks: independent identity with agent hooks disabled, three feel presets with replayable scenes, control panel and recall, fullscreen quiet behavior, packaging. Main and the fallback Punk ran on Codex; the Claude CLI Punk failed on an expired login. Git did not work in that environment, so the CEO banned it. The CEO did not stop the run before M1 finished.

**What the numbers say** (code comparison done statically by a separate agent; spot-checked):

- Product code +1,268 / −844 lines; about 670 of the removals were deliberate (agent bridge, token, 13 agent commands, hook auto-install). Proportionate to five tasks.
- About 200 added lines (16%) were defensive. They clustered where the briefs left room: the overlay quiet/recall orchestration has 11 state flags, the same reset in three places and two layers of version counters, with no tests. The CEO's view: this is a habit of the Coder model that prompts do not fix.
- Briefs ran 8–9 KB each. About 85% of interface decisions were dictated by them, while 30–35% of added lines transcribe a brief.
- Tests: 29 cases, 1,015 lines. Held-out tests genuinely varied inputs (30/60/144 Hz, shifted bounds, a resume race). Zero automated coverage of the orchestration, watcher and native layers, where most guards live. Every task passed Gate 2 on the first loop; no held-out test ever failed.
- Paperwork: 66 files and about 24,000 words in docs/workflow, including feasibility, demo, follow-up and release files outside the layout, 15 raw logs, a 24 KB relay pack. The CEO stopped reading after one document.
- Without Git, Main invented per-task snapshots and a work copy; the work copy's src-tauri alone reached 5.2 GB of build output. Usage was never recorded per node ("not reported" on every line).
- Possible regressions surfaced by code review, not by tests or Punk: reminders moved from the tray into Advanced → 小助手; the renderer's idle early-return can no longer trigger, so idle frames redraw fully (unmeasured).

**What worked.** Punk round 0 found five real plan gaps; Punk M1 found the hidden trial buttons and the wide-canvas layout; all were fixed. Tester ambiguity lists pinned two vague placements and a timing question before any code. The over-defense audit removed the big items (bridge, generic plugins/retries/telemetry, new dependencies). The main desktop interaction could not be automated and was left, correctly, for the CEO at Gate 3.

**v0.3 response, one change per finding:** document layout closed and budgeted, raw logs out of the repo, each limitation stated once (STATE "Not verified"); brief ≤ 1 page with the interface limited to what tests call; a named risk layer that a test or a written manual check must reach; the Coder lists every defense it adds and the audit names the small kinds; casts around frozen files fail review; a one-page gate packet in the CEO's language that lists removed or moved features; a minimal no-Git procedure that never copies dependencies or build output; usage recorded per node and per milestone; a checklist question when no held-out test ever fails.

## 10. v0.4 decisions (2026-11-02): the CEO's review of v0.3

The CEO found five problems in v0.3 and proposed an external script. Main's responses and the CEO's decisions:

| v0.3 problem (CEO) | Response in v0.4 |
| --- | --- |
| Main overloaded: interviews, architecture, briefs, spec checks, diff audits, held-out runs, merges, gates | Mechanics move to `gw.py`; one task per Main session, restarted from STATE and `gw next`; hot/cold documents. A fresh-context Auditor is the next step for large projects (CEO: record it, do not split yet). Evidence: in run 1 a separate Sonnet with a clean context found the 11 flags that Main's review passed. |
| Separation is not a sandbox; at loops 2–3 a Coder might `ls ..` for held-out tests | Held-out sets are single use: a failed set becomes visible, the Tester writes a fresh one. Sets live in a vault outside the repo and its siblings and exist in the worktree only during a run. Same logic as not tuning on a test set. |
| Test-first fails in UI, native and glue layers | Headless state machine + thin shell (the CEO's proposal), matching Functional Core / Imperative Shell, Elm's `update : Msg -> Model -> (Model, Cmd Msg)` and sans-I/O libraries. Amendments: the shell may translate but may not see state (checked by import rule, since "no if/else" is gameable); time is an event; apply only to orchestration, plain enum + function. |
| One-page budget too tight for long-lived documents | Budgets never applied to PRD or architecture, but long-lived files had no rule at all. Now: record files are tables only, thinking files have at most three sentences per heading (CEO's decision), architecture is an index with component files, `gw archive` folds each milestone into cold storage. |
| Parallel worktrees: port/DB/cache contention, baseline drift, registry conflicts | Code in parallel, test serially (lock); `GW_SLOT`/`GW_PORT_BASE`/`GW_TMP`; refresh from main and rerun before merge, with `conflict` and `drift` states; registry files Main-only plus a skeleton commit before parallel tasks; `conflicts_with` covers shared behavior. Correction: a shared `CARGO_TARGET_DIR` mostly serialises on cargo's lock rather than failing. |

**Script.** Python 3.8+, standard library, single file (CEO's choice for portability across Windows, WSL and Codex). Target was about 200 lines; it came to about 440 lines of code, mostly refusal messages that say what to do next. Tested end to end on a toy repository: out-of-order refusal, registry and shell-rule failures, a held-out failure burned and replaced by a fresh set, parallel slots and the parallel cap, a refresh conflict resolved and merged, close-out, archive with a parked task, and `gw docs` against every template and against deliberately bad documents. Found and fixed during testing: build outputs counted as changes (now documented: they must be git-ignored), a misleading loop message, parked briefs swept into the archive.

## 11. Flow Timer run (2026-11-02 → 11-03) and the v0.5 decisions

**Setup.** One prompt (a Pomodoro-style focus timer with idle detection), four planted edge cases the CEO did not spell out: (a) idle starts with under two minutes left; (b) idle 90 s, manual pause, resume, idle 30 s more; (c) rapid clicks; (d) return within the 10 s grace window, including crossing zero inside it. Four builds: v0.4 on Claude Code, v0.4 on Codex, and a single agent without the skill on each.

| | v0.4 Claude | v0.4 Codex | Single Claude | Single Codex |
| --- | --- | --- | --- | --- |
| Finished | yes | under half | yes | yes |
| Active time | ≈ 101 min (139 wall) | — | ≈ 10 min | 15 min |
| Coordinator context peak / cache reads | 410k / 40.7M | Root 30.4M of 48.1M total | 161k / 4.5M | — / 1.1M |
| Probes put to the CEO | 0 / 4 | 0 / 4 | 0 / 4 | 0 / 4 |
| Probes pinned by tests | 4 / 4 | — | 2 / 4 | 2 / 4 |
| Tests (unit + e2e) | 192 (cap 171) + 17 | — | 49 + 0 | 36 + 12 |
| Test : product lines | ≈ 5 : 1 | — | 0.8 : 1 | 0.9 : 1 |
| Punk's six UX faults shipped | 0 of 4 (2 not checked) | — | 6 / 6 | 6 / 6 |

**Findings.**

- *Correctness was the same.* All three finished builds time the four probes identically. The workflow asked the CEO four questions up front, none of them a probe; it decided (a), (b) and (d) silently, like the single agents.
- *Silent decisions diverge.* Single Codex counts a grace-window flashback as an interruption; single Claude starts the two-minute away timer from the last input, not from the tab switch. Both choices are defensible and neither was told to anyone.
- *No Punk is the biggest gap.* Both single builds shipped all six: skip without confirmation, no state in the tab title, contrast below AA, no focus move to the banner, touch targets under 44 px, nothing against losing a round on reload. Single Codex took four screenshots and fixed a phone layout itself, and still missed contrast and focus.
- *What the workflow bought:* every probe pinned by a test, a skip confirmation, a leave warning, state in the title, 17 browser tests and a pure reducer with randomised sequences. At ≈ 10× the time and ≈ 5× the test volume.
- *Coordination tax.* In Claude Code Main's context grew from 79k to 410k and 26 % of its requests were turn ceremony. In Codex the Guardian approval reviewer ran 145 reviews (12.9M tokens) and the agent stopped for a confirmation after every task.
- *Mechanical failures:* the template's recommended junction for `node_modules` was followed by `git worktree remove --force` and emptied the main checkout's folder; a close that failed halfway could only be repaired by editing state.json; `gw planned` could not be rerun; the test cap was prose only; 25 tests asserted on source text.

**v0.5 decisions (CEO, 2026-11-03).**

| Question | Decision |
| --- | --- |
| Split into a small and a large skill? | No. A small task is the testbed for watching execution and judgment; simplifying the skill for it would hide what is being measured |
| What must Gate 1 do? | Sweep every requirement against fixed edge categories; the CEO completes the Decision column; `gw gate 1` refuses until done |
| Force requirement × category? | No: 6 × 7 = 42 rows, most of them not applicable or common sense, breaks the three-minute gate. Undisputed categories get one "No dispute" line |
| Script-led orchestration? | Prototype `gw drive` with `claude -p --output-format json`. Codex dropped; other harnesses after open-sourcing |
| Group D (single agent + sweep + Punk)? | Not run. Coder and Tester are separate to keep Main's context small and to allow parallel work on large projects; the CEO tests v0.5 on a large project instead |

**Tested.** `gw.py` on a toy repository: Gate 1 refusals per category, empty decision, missing packet; brief refusal before Gate 1 and on a decision that differs from the PRD; `gw planned` refusing an over-cap set, an edge row without a test and a test reading `src/calc.py`; rerun of `planned`; links inside a worktree removed before deletion with their target intact; a held-out failure burned and replaced; a replan sealing into the open worktree; `close` rerun after the worktree was already gone; Gate 3 refusals for a provisional row, a missing packet and 13 screenshots; `archive` before Gate 3. `gw drive` end to end with a fake CLI (ten sessions, one held-out loop), and its flag combination against Claude Code 2.1.316.

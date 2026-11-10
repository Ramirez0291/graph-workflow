"""gw drive N [N ...] — prototype. Runs each task's loop by starting every step as a fresh `claude -p` session.

gw stays the scheduler: it picks the step from the task's state, starts one session with only that step's
inputs, then runs its own gate. Models judge or build; they never choose the next step and never talk to
the CEO. Each session's usage goes into log.md. Tasks run one after another, in the order given.

A gate's refusal goes back once to the session that can fix it (brief, tests, code) before anyone else is
asked, and only a failed review or a failed held-out run uses up one of the task's loops. A review fails
only by naming what the brief asks (gw.fail_reasons).

It stops at: parked, conflict, drift, a refused step after one retry, a 'VERDICT: stop', or any session
error. A stop ends the queue and leaves one page, docs/workflow/.gw/stop-N.md: why, who has to act, what
resumes it. Whoever picks it up reads STATE and that page, not this script's output. Gates 1 and 3 stay
interactive.

Configuration: the "drive" object in docs/workflow/gw.json (see DRIVE).
"""
import contextlib, io, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

import gw

SKILL = Path(__file__).resolve().parent.parent
GW = '"%s" "%s"' % (sys.executable, SKILL / "scripts" / "gw.py")
DRIVE = {"command": "claude", "permission_mode": "dontAsk", "models": {"main": "", "coder": "", "tester": ""},
         "extra_args": [], "step_timeout_min": 60, "max_budget_usd": 0,
         # A session that starts a background task ends its turn and is woken again when the task finishes. The
         # JSON then reports only the last stretch (usage, turns, duration), and the VERDICT may sit in an earlier one.
         "env": {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"}}
MAIN = ("You are Main in graph-workflow: product manager, architect and code reviewer. A script, gw, runs the "
        "steps; you do one judgment step and stop. Never run gw commands, except the `gw try` self-check a step "
        "names. Never ask the CEO, never touch files the step does not name. If the step needs something the PRD's "
        "Approvals table does not cover (a new dependency, an outside service, sending or publishing anything, "
        "deleting data, touching production), do not do it: end with 'VERDICT: stop: needs approval: <what>'. "
        "Claims about who did what must cite the log or a diff. Your last line is always 'VERDICT: <word>'; if you "
        "cannot decide, 'VERDICT: stop: <why>'.")
MAIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
PROMPTS = {
    "brief": "Write docs/workflow/briefs/brief-{n}.md for task {n} in docs/workflow/tasks.md from the template "
             "{skill}/templates/brief.md. Read only docs/workflow/PRD.md (with its Edge cases), "
             "docs/workflow/architecture.md (and architecture/<component>.md if the task names one) and the task's row. "
             "Copy every edge row the task touches into the brief's Edge cases table with the Decision cell identical to "
             "the PRD's. At most {words} words (a CJK character counts half). The Files lines list bare paths separated "
             "by ', ', with no notes or brackets; 'May change' paths exist on the main branch. {extra}"
             "Before you end, run `{gw} try brief {n}` and fix what it reports until it prints ok. "
             "End with 'VERDICT: done'.",
    "spec": "Spec check for task {n}. Read docs/workflow/briefs/brief-{n}.md and {tests}/test-plan.md; the test files "
            "are in {tests}/visible and {tests}/holdout. Fix every ambiguity in the brief itself, never by copying test "
            "code into it. Delete held-out cases the brief does not support. At least one test or a written manual "
            "check must reach the risk layer. A product question the PRD's Edge cases do not answer becomes a new PRD "
            "row with Source 'Main provisional', copied into the brief. The brief stays within {words} words (a "
            "CJK character counts half): tighten wording instead of growing it, and keep each Edge-cases Decision cell "
            "identical to the PRD's Decision cell (put explanations in the Case cell). Do not run the tests. Then commit: "
            "`git add docs/workflow && git commit -m \"docs({n}): brief\"`. "
            "End with 'VERDICT: pass', or 'VERDICT: rerun-tester: <criteria>' if tests must change.",
    "unblock": "The Coder of task {n} is blocked. Its question is in {wt}/docs/workflow/handoffs/handoff-{n}.md. "
               "Answer it by editing the worktree brief {wt}/docs/workflow/briefs/brief-{n}.md (Change notes say what "
               "changed). A product question the PRD does not answer: add a PRD edge row with Source 'Main provisional'. "
               "Delete the handoff file. End with 'VERDICT: done'.",
    "review": "Review task {n}. Worktree: {wt}. Read its brief and handoff (docs/workflow/briefs/brief-{n}.md and "
              "docs/workflow/handoffs/handoff-{n}.md inside it) and the diff (`git -C {wt} status --porcelain -uall`, "
              "`git -C {wt} diff`, and the untracked files). gw check said:\n{check}\n"
              "Does the diff do what the brief asks and nothing else? Over-defense audit: anything defensive not on "
              "'Defenses added', or naming no failure from the brief or a test, you delete yourself in the worktree "
              "and record as a row in {root}/docs/workflow/decisions.md (the main checkout; never edit the worktree's "
              "copy, gw check rejects it); two mechanisms for one failure keep one; Non-negotiables are simplified, "
              "never deleted. "
              "You may fail the task for three reasons only. One: the diff does not meet an acceptance criterion or an "
              "edge row of the brief; name the ids. Two: gw check fails on something the Coder must fix; say `check`. "
              "Three: the code recognises visible-test inputs, or casts or copies around a frozen file; say `cheat`. "
              "Whatever else you would change is not a fail, however sure you are: the brief did not ask for it. Add a "
              "`deferred` row to {root}/docs/workflow/decisions.md and pass. How a screen looks is judged by Punk and "
              "the CEO, not here. Do not run the tests: gw runs the full suite right after your verdict. "
              "On fail, write Loop notes in the worktree brief as behavior. "
              "End with 'VERDICT: pass' or 'VERDICT: fail: <ids, check or cheat>'.",
    "notes": "The held-out run of task {n} failed. The run output is {log}. Write Loop notes in {wt}/docs/workflow/"
             "briefs/brief-{n}.md that describe the failing behavior; never copy test code, test names or inputs. "
             "End with 'VERDICT: done'.",
    "tester": "Brief: {brief}. Output folder: {tests}. Every test that covers an edge row carries its id (E3 ...) in "
              "its name. Self-check before you end: run `{gw} try planned {n}` in {root} and fix what it reports "
              "until it prints ok. {extra}",
    "coder": "Worktree: {wt}. Brief: docs/workflow/briefs/brief-{n}.md inside it. {extra}",
}
AGAIN = ("You passed this review, but gw check fails now (below). If an edit of yours caused it, undo or fix it in "
         "the worktree and pass again. If the Coder must fix it, write Loop notes and fail with `check`.\n")
UNNAMED = ("Your fail named no acceptance criterion or edge row of the brief, and neither `check` nor `cheat`, so gw "
           "does not take it. Either name the ids the diff does not meet, or add a `deferred` row to decisions.md for "
           "what you would change and pass.\n")
WHO = {"ceo": "the CEO decides", "main": "Main judges, in a fresh session",
       "any": "no judgment needed: a mechanical fix, then run it again"}
TOTAL = {"cost": 0.0, "secs": 0, "steps": 0}
LAST = {"out": ""}


class Stop(Exception):
    def __init__(self, why, who="any"):
        Exception.__init__(self, why)
        self.who = who


def conf():
    d = dict(DRIVE)
    d.update(gw.conf().get("drive", {}))
    d["env"] = dict(DRIVE["env"], **(d.get("env") or {}))  # a repo's env adds to the default, it does not replace it
    return d


def agent(role):
    """The repo's own agent file (.claude/agents/gw-<role>.md, customized per installation) wins over the skill's."""
    own = gw.ROOT / ".claude" / "agents" / ("gw-%s.md" % role)
    text = (own if own.exists() else SKILL / "agents" / ("gw-%s.md" % role)).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    tools = re.search(r"^tools:\s*(.*)$", m.group(1), re.M).group(1)
    return m.group(2).strip(), [x.strip() for x in tools.split(",") if x.strip()]


def claude(role, prompt, cwd, dirs, n, node, loop):
    d = conf()
    system, tools = (MAIN, MAIN_TOOLS) if role == "main" else agent(role)
    sp = gw.VAULT / "drive" / ("%s.md" % role)  # a file, because cmd.exe mangles multi-line arguments
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(system, encoding="utf-8")
    cmd = [shutil.which(d["command"]) or d["command"], "-p", "--output-format", "json",
           "--append-system-prompt-file", str(sp), "--permission-mode", d["permission_mode"],
           "--allowedTools", ",".join(tools)]
    for x in dirs:
        cmd += ["--add-dir", str(x)]
    if d["models"].get(role):
        cmd += ["--model", d["models"][role]]
    if d["max_budget_usd"]:
        cmd += ["--max-budget-usd", str(d["max_budget_usd"])]
    cmd += d["extra_args"]
    print("· %s %s (%s) in %s" % (node, n, role, cwd))
    began = time.time()
    try:
        r = subprocess.run(cmd, input=prompt, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=d["step_timeout_min"] * 60, env=dict(os.environ, **d["env"]))
    except subprocess.TimeoutExpired:
        lost(n, node, "timeout", loop, began)
        raise Stop("%s step timed out after %d min" % (node, d["step_timeout_min"]))
    try:
        out = json.loads(r.stdout)
        if isinstance(out, list):  # an output format that prints every event: the result is the last of them
            out = [x for x in out if isinstance(x, dict) and "result" in x][-1]
        out.get("result")
    except (ValueError, IndexError, AttributeError):
        lost(n, node, "no JSON (exit %d)" % r.returncode, loop, began)
        raise Stop("%s step returned no JSON (exit %d): %s" % (node, r.returncode, (r.stdout + r.stderr)[-600:]))
    # modelUsage and the cost add up the whole session; `usage` and duration_ms cover only its last stretch.
    # So tokens come from modelUsage and the seconds from this script's own clock.
    num = lambda x: x if isinstance(x, (int, float)) else 0
    per, u = out.get("modelUsage"), out.get("usage")
    per, u = per if isinstance(per, dict) else {}, u if isinstance(u, dict) else {}
    cost, secs = num(out.get("total_cost_usd")), int(time.time() - began)
    tok = [sum(num(m.get(k)) for m in per.values() if isinstance(m, dict)) if per else num(u.get(old)) for k, old in (
        ("inputTokens", "input_tokens"), ("cacheCreationInputTokens", "cache_creation_input_tokens"),
        ("cacheReadInputTokens", "cache_read_input_tokens"), ("outputTokens", "output_tokens"))]
    TOTAL["cost"], TOTAL["secs"], TOTAL["steps"] = TOTAL["cost"] + cost, TOTAL["secs"] + secs, TOTAL["steps"] + 1
    usage = "in %d · cache %d · out %d · $%.2f · %ds · %d turns · %s · %s" % (
        tok[0] + tok[1], tok[2], tok[3], cost, secs, num(out.get("num_turns")), str(out.get("session_id") or "")[:8],
        "+".join(sorted(per)) or d["models"].get(role) or "default model")
    denied = out.get("permission_denials") or []
    gw.log(n, node, "error" if out.get("is_error") else
           "ok" + (", %d denied" % len(denied) if denied else ""), loop, usage)
    if out.get("is_error"):
        raise Stop("%s step failed: %s" % (node, str(out.get("result"))[-600:]))
    if denied:
        print("WARN  %d tool calls denied; widen drive.permission_mode or the agent's tools if the step needed them"
              % len(denied))
    return out.get("result") or ""


def lost(n, node, what, loop, began):
    """A session that gave no result still took time, and it is still a session in the total."""
    secs = int(time.time() - began)
    TOTAL["secs"], TOTAL["steps"] = TOTAL["secs"] + secs, TOTAL["steps"] + 1
    gw.log(n, node, what, loop, "%ds" % secs)


def verdict(text):
    found = re.findall(r"VERDICT:\s*([\w-]+)(.*)", text)
    return (found[-1][0].lower(), found[-1][1].strip(" :")) if found else ("none", "")


def step(fn, *args):
    """Run a gw command, echo its output, return (exit code, output)."""
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            fn(*args)
        except SystemExit as e:
            code = e.code or 0
    print(buf.getvalue(), end="")
    LAST["out"] = buf.getvalue()
    return code, buf.getvalue()


def fill(key, n, **kw):
    return PROMPTS[key].format(n=n, skill=SKILL, gw=GW, root=gw.ROOT, tests=gw.TESTS / n, wt=gw.TREES / n,
                               words=gw.BUDGET["briefs/brief-*.md"], **dict({"extra": ""}, **kw))


def run_main(key, n, loop, dirs=(), **kw):
    v, why = verdict(claude("main", fill(key, n, **kw), gw.ROOT, list(dirs), n, "main:" + key, loop))
    if v == "stop" or v == "none":
        raise Stop("Main stopped at %s: %s" % (key, why or "no VERDICT line"),
                   "ceo" if why.lower().startswith("needs approval") else "main")
    return v, why


def tester(n, t, extra=""):
    wt_brief = gw.TREES / n / "docs" / "workflow" / "briefs" / ("brief-%s.md" % n)
    brief = wt_brief if wt_brief.exists() else gw.WF / "briefs" / ("brief-%s.md" % n)
    dirs = [gw.TESTS / n] + ([gw.TREES / n] if (gw.TREES / n).exists() else [])
    (gw.TESTS / n).mkdir(parents=True, exist_ok=True)
    claude("tester", fill("tester", n, brief=brief, extra=extra), gw.ROOT, dirs, n, "tester", t["loop"])
    code, out = step(gw.cmd_planned, n)
    if code:
        claude("tester", fill("tester", n, brief=brief, extra="gw refused your output; fix exactly this:\n" + out),
               gw.ROOT, dirs, n, "tester retry", t["loop"])
        if step(gw.cmd_planned, n)[0]:
            raise Stop("gw planned refused the Tester's output twice")


def commit_brief(n, t):
    """No spec session ran, so nobody committed the brief, and `gw seal` wants it on the main branch."""
    rel = "docs/workflow/briefs/brief-%s.md" % n
    if t.get("slot") or not gw.git("status", "--porcelain", "--", rel, check=False).stdout.strip():
        return
    gw.git("add", "--", rel, check=False)
    r = gw.git("commit", "-q", "-m", "docs(%s): brief" % n, "--", rel, check=False)
    if r.returncode:
        raise Stop("the brief could not be committed: " + (r.stdout + r.stderr)[-600:])


def review(n, loop, check):
    """Main's review, at most two sessions. gw check has the last word on a pass; a fail counts only when it names
    what the brief asks. Neither a pass against a failing check nor an unnamed fail uses one of the Coder's loops."""
    ask = check[-3000:]
    for _ in (1, 2):
        v, why = run_main("review", n, loop, dirs=[gw.TREES / n], check=ask)
        if v == "pass":
            code, out = step(gw.cmd_check, n)  # Main's own edits get checked too
            if not code:
                return step(gw.cmd_finish, n)
            ask = AGAIN + out[-3000:]
        elif v == "fail":
            if gw.fail_reasons(n, why):
                return step(gw.cmd_review, n, "fail", why)
            ask = UNNAMED + check[-3000:]
        else:
            raise Stop("review verdict '%s'" % v, "main")
    raise Stop("the review did not settle in two sessions (a pass while gw check fails, or a fail that names no "
               "criterion); no loop was used", "main")


def run_task(n):
    """Take task n from its current state to done. Returns when it is done; raises Stop when somebody has to act."""
    spec, unblock, last_check = 0, 0, ""
    while True:
        s = gw.state()
        t = s["tasks"].get(n)
        st = t["state"] if t else "new"
        loop = t["loop"] if t else 0
        if st == "done":
            return
        if st == "new":
            if not s["gates"].get("1"):
                raise Stop("Gate 1 has not passed; run it with the CEO first", "ceo")
            run_main("brief", n, 0)
            code, out = step(gw.cmd_brief, n)
            if code:
                run_main("brief", n, 0, extra="gw refused the last version; fix exactly this:\n%s\n" % out)
                if step(gw.cmd_brief, n)[0]:
                    raise Stop("gw brief refused twice")
        elif st in ("briefed", "replan"):
            tester(n, t, "Earlier held-out sets are spent: write a fresh set." if st == "replan" else "")
        elif st == "planned" and t.get("spec") is False:
            commit_brief(n, t)  # nothing for Main to judge: no held-out case to audit, no open item in the test plan
            if step(gw.cmd_seal, n)[0]:
                raise Stop("gw seal refused")
            spec = 0
        elif st == "planned":
            spec += 1
            if spec > 2:
                raise Stop("two spec checks without a pass", "main")
            v, why = run_main("spec", n, loop, dirs=[gw.TESTS / n])
            if v == "rerun-tester":
                tester(n, t, "Main's spec check asks you to revise: %s" % why)
            elif v == "pass":
                if step(gw.cmd_seal, n)[0]:
                    raise Stop("gw seal refused")
                spec = 0  # the next held-out set, after a burn, gets its own two spec checks
            else:
                raise Stop("spec check verdict '%s'" % v, "main")
        elif st == "sealed":
            if step(gw.cmd_open, n)[0]:
                raise Stop("gw open refused")
        elif st == "coding":
            claude("coder", fill("coder", n), gw.TREES / n, [], n, "coder", loop)
            code, last_check = step(gw.cmd_check, n)
            if code == 1:  # what gw can name, the Coder can fix: once, before a review is spent on it
                claude("coder", fill("coder", n, extra="gw check refused your output; fix exactly this:\n" + last_check),
                       gw.TREES / n, [], n, "coder retry", loop)
                code, last_check = step(gw.cmd_check, n)
            if code == 2:  # gw itself could not check (git failed): do not start the Coder again on it
                raise Stop("gw check refused")
            if code == 3:
                unblock += 1
                if unblock > 2:
                    raise Stop("the Coder blocked twice after Main's answers", "main")
                run_main("unblock", n, loop, dirs=[gw.TREES / n])
        elif st == "review":
            if not last_check:
                last_check = step(gw.cmd_check, n)[1]
            review(n, loop, last_check)
            last_check = ""
        elif st == "holdout-failed":
            run_main("notes", n, loop, dirs=[gw.TREES / n, gw.VAULT / n], log=gw.VAULT / n / "last.log")
            step(gw.cmd_burn, n)
        elif st in ("reviewed", "passed", "merged"):
            fn = {"reviewed": gw.cmd_holdout, "passed": gw.cmd_merge, "merged": gw.cmd_close}[st]
            if step(fn, n)[0] and gw.state()["tasks"][n]["state"] == st:
                raise Stop("gw %s refused" % fn.__name__[4:])
        else:
            raise Stop(*{"parked": ("task %s is parked" % n, "ceo"),
                         "conflict": ("refresh from the main branch conflicts", "main"),
                         "drift": ("it passes alone and fails with the main branch", "main")}[st])


def packet(n, e, rest):
    """One page for whoever picks this up. A fresh session reads STATE and this, not the drive's output."""
    t = gw.state()["tasks"].get(n)
    one = lambda x: re.sub(r"[|\s]+", " ", str(x)).strip()
    log = gw.WF / "log.md"
    mine = [l for l in (log.read_text(encoding="utf-8").splitlines() if log.exists() else [])
            if re.match(r"\|[^|]*\|\s*%s\s*\|" % re.escape(n), l)][-12:]
    page = ["# Drive stopped at task %s" % n, "", "| Field | Value |", "|---|---|",
            "| When | %s |" % time.strftime("%Y-%m-%d %H:%M"),
            "| Task | %s |" % ("%s: %s, loop %d of %d" % (n, t["state"], t["loop"], gw.MAX_LOOPS) if t else n + ": not started"),
            "| Why | %s |" % one(e)[:600],
            "| Who | %s |" % WHO[e.who],
            "| Next | %s |" % one(gw.hint(n, t) if t else "what Why says"),
            "| Then | `gw drive %s` |" % " ".join(rest),
            "| So far | %d sessions, $%.2f, %d s in sessions |" % (TOTAL["steps"], TOTAL["cost"], TOTAL["secs"]),
            "", "## Last gw output", "```", LAST["out"].strip()[-1500:] or "(none)", "```",
            "", "## Log, this task", "| When | Task | Node | Result | Loop | Usage |", "|---|---|---|---|---|---|"] + mine
    p = gw.WF / ".gw" / ("stop-%s.md" % n)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(page) + "\n", encoding="utf-8")
    gw.log(n, "drive stop", one(e)[:200], t["loop"] if t else "")
    return p


def main(ns):
    start = time.time()
    for i, n in enumerate(ns):
        old = gw.WF / ".gw" / ("stop-%s.md" % n)
        if old.exists():
            old.unlink()  # somebody acted on it and started the task again
        try:
            run_task(n)
            print("task %s is done" % n)
            continue
        except Stop as stop:
            e = stop
        except (Exception, SystemExit) as crash:  # not a decision anybody made: still a stop, still a page
            e = Stop("%s: %s" % (type(crash).__name__, crash))
        p = packet(n, e, ns[i:])
        print("drive stopped at task %s: %s\n%s. The page for whoever picks this up: %s"
              % (n, e, WHO[e.who], p.relative_to(gw.ROOT)))
        break
    else:
        print("the queue is done: %s" % " ".join(ns))
    print("drive: %d sessions, $%.2f, %ds in sessions, %ds wall. Usage per step is in log.md."
          % (TOTAL["steps"], TOTAL["cost"], TOTAL["secs"], time.time() - start))

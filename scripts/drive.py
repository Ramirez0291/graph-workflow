"""gw drive N — prototype. Runs one task's loop by starting every step as a fresh `claude -p` session.

gw stays the scheduler: it picks the step from the task's state, starts one session with only that step's
inputs, then runs its own gate. Models judge or build; they never choose the next step and never talk to
the CEO. Each session's usage goes into log.md. Stops at: done, parked, conflict, drift, a refused step
after one retry, a 'VERDICT: stop', or any session error. Gates 1 and 3 stay interactive.

Configuration: the "drive" object in docs/workflow/gw.json (see DRIVE).
"""
import contextlib, io, json, re, shutil, subprocess, sys, time
from pathlib import Path

import gw

SKILL = Path(__file__).resolve().parent.parent
DRIVE = {"command": "claude", "permission_mode": "dontAsk", "models": {"main": "", "coder": "", "tester": ""},
         "extra_args": [], "step_timeout_min": 60, "max_budget_usd": 0}
MAIN = ("You are Main in graph-workflow: product manager, architect and code reviewer. A script, gw, runs the "
        "steps; you do one judgment step and stop. Never run gw commands, never ask the CEO, never touch files "
        "the step does not name. Claims about who did what must cite the log or a diff. Your last line is always "
        "'VERDICT: <word>'; if you cannot decide, 'VERDICT: stop: <why>'.")
MAIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
PROMPTS = {
    "brief": "Write docs/workflow/briefs/brief-{n}.md for task {n} in docs/workflow/tasks.md from the template "
             "{skill}/templates/brief.md. Read only docs/workflow/PRD.md (with its Edge cases), "
             "docs/workflow/architecture.md (and architecture/<component>.md if the task names one) and the task's row. "
             "Copy every edge row the task touches verbatim into the brief's Edge cases table. One page. {extra}"
             "End with 'VERDICT: done'.",
    "spec": "Spec check for task {n}. Read docs/workflow/briefs/brief-{n}.md and {tests}/test-plan.md; the test files "
            "are in {tests}/visible and {tests}/holdout. Fix every ambiguity in the brief itself, never by copying test "
            "code into it. Delete held-out cases the brief does not support. At least one test or a written manual "
            "check must reach the risk layer. A product question the PRD's Edge cases do not answer becomes a new PRD "
            "row with Source 'Main provisional', copied into the brief. Then commit: "
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
              "and record as a row in docs/workflow/decisions.md; two mechanisms for one failure keep one; "
              "Non-negotiables are simplified, never deleted. Casts or copies around a frozen file, and code that "
              "recognises visible-test inputs, fail. On fail, write Loop notes in the worktree brief as behavior. "
              "End with 'VERDICT: pass' or 'VERDICT: fail'.",
    "notes": "The held-out run of task {n} failed. The run output is {log}. Write Loop notes in {wt}/docs/workflow/"
             "briefs/brief-{n}.md that describe the failing behavior; never copy test code, test names or inputs. "
             "End with 'VERDICT: done'.",
    "tester": "Brief: {brief}. Output folder: {tests}. Every test that covers an edge row carries its id (E3 ...) in "
              "its name. {extra}",
    "coder": "Worktree: {wt}. Brief: docs/workflow/briefs/brief-{n}.md inside it. {extra}",
}
TOTAL = {"cost": 0.0, "secs": 0, "steps": 0}


class Stop(Exception):
    pass


def conf():
    d = dict(DRIVE)
    d.update(gw.conf().get("drive", {}))
    return d


def agent(role):
    text = (SKILL / "agents" / ("gw-%s.md" % role)).read_text(encoding="utf-8")
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
    try:
        r = subprocess.run(cmd, input=prompt, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=d["step_timeout_min"] * 60)
    except subprocess.TimeoutExpired:
        gw.log(n, node, "timeout", loop)
        raise Stop("%s step timed out after %d min" % (node, d["step_timeout_min"]))
    try:
        out = json.loads(r.stdout)
    except ValueError:
        gw.log(n, node, "no JSON (exit %d)" % r.returncode, loop)
        raise Stop("%s step returned no JSON (exit %d): %s" % (node, r.returncode, (r.stdout + r.stderr)[-600:]))
    u, cost, secs = out.get("usage", {}), out.get("total_cost_usd") or 0, (out.get("duration_ms") or 0) // 1000
    TOTAL["cost"], TOTAL["secs"], TOTAL["steps"] = TOTAL["cost"] + cost, TOTAL["secs"] + secs, TOTAL["steps"] + 1
    usage = "in %d · cache %d · out %d · $%.2f · %ds · %d turns · %s" % (
        u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0),
        u.get("output_tokens", 0), cost, secs, out.get("num_turns") or 0, (out.get("session_id") or "")[:8])
    denied = out.get("permission_denials") or []
    gw.log(n, node, "error" if out.get("is_error") else
           "ok" + (", %d denied" % len(denied) if denied else ""), loop, usage)
    if out.get("is_error"):
        raise Stop("%s step failed: %s" % (node, str(out.get("result"))[-600:]))
    if denied:
        print("WARN  %d tool calls denied; widen drive.permission_mode or the agent's tools if the step needed them"
              % len(denied))
    return out.get("result") or ""


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
    return code, buf.getvalue()


def fill(key, n, **kw):
    return PROMPTS[key].format(n=n, skill=SKILL, tests=gw.TESTS / n, wt=gw.TREES / n, **dict({"extra": ""}, **kw))


def run_main(key, n, loop, dirs=(), **kw):
    v, why = verdict(claude("main", fill(key, n, **kw), gw.ROOT, list(dirs), n, "main:" + key, loop))
    if v == "stop" or v == "none":
        raise Stop("Main stopped at %s: %s" % (key, why or "no VERDICT line"))
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


def main(n):
    start, spec, unblock, last_check = time.time(), 0, 0, ""
    try:
        while True:
            s = gw.state()
            t = s["tasks"].get(n)
            st = t["state"] if t else "new"
            loop = t["loop"] if t else 0
            if st == "new":
                if not s["gates"].get("1"):
                    raise Stop("Gate 1 has not passed; run it with the CEO first")
                run_main("brief", n, 0)
                code, out = step(gw.cmd_brief, n)
                if code:
                    run_main("brief", n, 0, extra="gw refused the last version; fix exactly this:\n%s\n" % out)
                    if step(gw.cmd_brief, n)[0]:
                        raise Stop("gw brief refused twice")
            elif st in ("briefed", "replan"):
                tester(n, t, "Earlier held-out sets are spent: write a fresh set." if st == "replan" else "")
            elif st == "planned":
                spec += 1
                if spec > 2:
                    raise Stop("two spec checks without a pass")
                v, why = run_main("spec", n, loop, dirs=[gw.TESTS / n])
                if v == "rerun-tester":
                    tester(n, t, "Main's spec check asks you to revise: %s" % why)
                elif v == "pass":
                    if step(gw.cmd_seal, n)[0]:
                        raise Stop("gw seal refused")
                else:
                    raise Stop("spec check verdict '%s'" % v)
            elif st == "sealed":
                if step(gw.cmd_open, n)[0]:
                    raise Stop("gw open refused")
            elif st == "coding":
                claude("coder", fill("coder", n), gw.TREES / n, [], n, "coder", loop)
                code, last_check = step(gw.cmd_check, n)
                if code == 3:
                    unblock += 1
                    if unblock > 2:
                        raise Stop("the Coder blocked twice after Main's answers")
                    run_main("unblock", n, loop, dirs=[gw.TREES / n])
            elif st == "review":
                if not last_check:
                    last_check = step(gw.cmd_check, n)[1]
                v, _ = run_main("review", n, loop, dirs=[gw.TREES / n], check=last_check[-3000:])
                last_check = ""
                if v == "pass" and step(gw.cmd_check, n)[0] == 0:  # Main's own deletions get checked too
                    step(gw.cmd_finish, n)
                else:
                    step(gw.cmd_review, n, "fail")
            elif st == "holdout-failed":
                run_main("notes", n, loop, dirs=[gw.TREES / n, gw.VAULT / n], log=gw.VAULT / n / "last.log")
                step(gw.cmd_burn, n)
            elif st in ("reviewed", "passed", "merged"):
                fn = {"reviewed": gw.cmd_holdout, "passed": gw.cmd_merge, "merged": gw.cmd_close}[st]
                if step(fn, n)[0] and gw.state()["tasks"][n]["state"] == st:
                    raise Stop("gw %s refused" % fn.__name__[4:])
            else:
                raise Stop({"done": "task %s is done" % n, "parked": "task %s is parked: the CEO decides" % n,
                            "conflict": "refresh conflict: Main resolves it interactively",
                            "drift": "drift: Main decides which behavior is right"}[st])
    except Stop as e:
        print("drive stopped: %s" % e)
    print("drive: %d sessions, $%.2f, %ds in sessions, %ds wall. Usage per step is in log.md."
          % (TOTAL["steps"], TOTAL["cost"], TOTAL["secs"], time.time() - start))

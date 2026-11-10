"""End-to-end checks for gw.py and drive.py on a toy repository, with a fake `claude`.

    python3 -m unittest discover -s tests -v        (from the skill folder; standard library only)

Each test builds its own repository under a temporary HOME, so the vault and the worktrees never touch a real one.
The repository has a pre-commit hook that rejects any staged file containing the word LINTBAD: it stands in for
a linter, and lets the tests see where a commit-hook failure surfaces.
"""
import json, os, shutil, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
GW = SKILL / "scripts" / "gw.py"

EDGES = """
## Edge cases
| # | Req | Category | Case | Options | Recommended | Decision | Source |
|---|---|---|---|---|---|---|---|
| E1 | R1 | threshold | add of zero | a / b | a | returns the other number | CEO |

- No dispute: interleave, repeat, time-cross, counting, environment, failure
"""
APPROVALS = """
## Approvals
| # | Category | What | Decision | Source |
|---|---|---|---|---|
| P1 | dependency | nothing beyond the standard library | approved | CEO |

- Nothing needed: service, send, delete, production
"""
PRD = "# PRD\n" + EDGES + APPROVALS
BRIEF = """# Brief N — add function

## Goal
Add `add`.

## Acceptance criteria
| # | Criterion |
|---|---|
| A1 | add(2, 3) returns 5 |

## Edge cases
| # | Case | Decision |
|---|---|---|
| E1 | add of zero | returns the other number |

## Interface
`MOD.add(a, b)`.

## Risk layer
RISK

## Files
- May change: CHANGE
- May create: CREATE
- Must not touch: tests/test_base.py
"""
VISIBLE = """import unittest
from MOD import add


class Visible(unittest.TestCase):
    def test_a1_add(self):
        self.assertEqual(add(2, 3), 5)MARK

    def test_e1_zero(self):
        self.assertEqual(add(0, 0), 0)
"""
HOLDOUT = """import unittest
from MOD import add


class Held(unittest.TestCase):
    def test_e1_add_zero(self):
        self.assertEqual(add(0, 7), 7)
"""
PLAN = "# Test plan N — add function\n\n## Ambiguities\n- none\n"
HANDOFF = """# Handoff N — add function

| Field | Value |
|---|---|
| status | STATUS |

## Defenses added
| Where | Failure it prevents |
|---|---|
| none | none |
"""
HOOK = """#!/bin/sh
bad=$(git diff --cached --name-only --diff-filter=ACM | xargs -r grep -l LINTBAD 2>/dev/null)
if [ -n "$bad" ]; then echo "lint: LINTBAD in $bad"; exit 1; fi
"""


def module(n):
    return "src.calc" if n == "1" else "src.mod" + n


def target(n):
    return module(n).replace(".", "/") + ".py"


def brief_text(n, change=None, create=None, risk="domain"):
    change = change or ("src/calc.py" if n == "1" else "none")
    create = create or ("none" if n == "1" else target(n))
    return (BRIEF.replace("CHANGE", change).replace("CREATE", create).replace("RISK", risk)
            .replace("MOD", module(n)).replace("Brief N", "Brief " + n))


# The fake `claude`: decides from the prompt which step it is, does that step's file work, prints the CLI's JSON.
# FAKE_MODE: happy = every author gets it wrong once (brief, tests, code, review) and right on the retry;
# clean = right the first time; stubborn = the review keeps an out-of-scope edit; vague = the review fails without
# naming a criterion, then passes; vague-stubborn = it never names one; named = it fails A1 once; ui = a UI-layer
# brief and no held-out tests; blocked = the Coder's retry ends blocked; odd = right the first time, odd JSON.
FAKE = r'''#!/usr/bin/env python3
import importlib.util, json, os, re, subprocess, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("fixture", os.environ["FAKE_FIXTURE"])
fx = importlib.util.module_from_spec(spec); spec.loader.exec_module(fx)
prompt, home, mode = sys.stdin.read(), Path(os.environ["FAKE_DIR"]), os.environ.get("FAKE_MODE", "happy")
seen = home / "calls.json"
calls = json.loads(seen.read_text()) if seen.exists() else []
root, retry = Path.cwd(), "gw refused" in prompt or "gw check refused" in prompt
n = [x for x in re.search(r"brief-(\d+)\.md|[Tt]ask (\d+)", prompt).groups() if x][0]
before = lambda step: len([c for c in calls if c["step"] == step and c["n"] == n])
messy = mode in ("happy", "stubborn", "blocked")
say = "done"
if prompt.startswith("Write docs/workflow/briefs"):
    step = "brief"
    (root / "docs/workflow/briefs").mkdir(exist_ok=True)
    bad = messy and not retry
    (root / ("docs/workflow/briefs/brief-%s.md" % n)).write_text(fx.brief_text(
        n, change="src/calc.py（the add function）" if bad else None, risk="UI" if mode == "ui" else "domain"))
elif prompt.startswith("Brief: "):
    step = "tester"
    out = Path(re.search(r"Output folder: (\S+?)\. ", prompt).group(1))
    (out / "visible").mkdir(parents=True, exist_ok=True)
    (out / ("visible/test_add_%s.py" % n)).write_text(
        fx.VISIBLE.replace("MOD", fx.module(n)).replace("MARK", "  # LINTBAD" if messy and not retry else ""))
    if mode != "ui":
        (out / "holdout").mkdir(exist_ok=True)
        (out / ("holdout/test_more_%s.py" % n)).write_text(fx.HOLDOUT.replace("MOD", fx.module(n)))
    (out / "test-plan.md").write_text(fx.PLAN)
elif prompt.startswith("Spec check"):
    step, say = "spec", "pass"
    subprocess.run('git add docs/workflow && git commit -q -m "docs(%s): brief"' % n, shell=True, check=True)
elif prompt.startswith("The Coder of task"):
    step = "unblock"
    Path(re.search(r"is in (\S+handoff-\d+\.md)", prompt).group(1)).unlink()
elif prompt.startswith("Worktree: "):
    step, k = "coder", before("coder")
    w = Path(re.search(r"Worktree: (\S+?)\. ", prompt).group(1))
    (w / fx.target(n)).write_text("def add(a, b):\n    return a + b%s\n" % ("  # LINTBAD" if messy and k == 0 else ""))
    (w / "docs/workflow/handoffs").mkdir(parents=True, exist_ok=True)
    (w / ("docs/workflow/handoffs/handoff-%s.md" % n)).write_text(
        fx.HANDOFF.replace("STATUS", "blocked" if mode == "blocked" and k == 1 else "done").replace("Handoff N", "Handoff " + n))
elif prompt.startswith("Review task"):
    step, say = "review", "pass"
    stray = Path(re.search(r"Worktree: (\S+?)\. ", prompt).group(1)) / "stray.txt"
    if mode in ("happy", "stubborn"):
        if "You passed this review" not in prompt or mode == "stubborn":
            stray.write_text("an edit of Main's outside the brief's file list\n")
        elif stray.exists():
            stray.unlink()
    elif mode == "vague-stubborn" or (mode == "vague" and "Your fail named no" not in prompt):
        say = "fail"
    elif mode == "named" and before("review") == 0:
        say = "fail: A1 is not met"
else:
    step = "other"
calls.append({"step": step, "retry": retry, "n": n, "bg": os.environ.get("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS"),
              "foo": os.environ.get("FOO")})
seen.write_text(json.dumps(calls))
if mode == "odd":   # shapes the CLI should never print; the drive must still log the session and go on
    print(json.dumps([{"type": "system"}, {"result": "ok\nVERDICT: " + say, "usage": None, "modelUsage": "n/a",
                                            "total_cost_usd": "free", "num_turns": None, "session_id": 7}]))
    sys.exit(0)
print(json.dumps({"result": "ok\nVERDICT: " + say, "is_error": False, "num_turns": 1, "duration_ms": 5, "total_cost_usd": 0.5,
                  "session_id": "feedbeef-0000", "permission_denials": [],
                  "usage": {"input_tokens": 1, "cache_creation_input_tokens": 1, "cache_read_input_tokens": 1, "output_tokens": 7},
                  "modelUsage": {"toy-model": {"inputTokens": 10, "cacheCreationInputTokens": 20, "cacheReadInputTokens": 3000, "outputTokens": 400}}}))
'''


def sh(cmd, cwd, env=None, check=True, stdin=None):
    r = subprocess.run(cmd, cwd=str(cwd), env=env, shell=isinstance(cmd, str), capture_output=True, text=True, input=stdin)
    if check and r.returncode:
        raise AssertionError("%s failed:\n%s%s" % (cmd, r.stdout, r.stderr))
    return r


class Toy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gw-test-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.repo, self.home = self.tmp / "toy", self.tmp / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), FAKE_DIR=str(self.home), FAKE_FIXTURE=str(Path(__file__).resolve()))
        for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "FAKE_MODE"):
            self.env.pop(k, None)
        files = {"src/__init__.py": "", "src/calc.py": "", "tests/__init__.py": "",
                 "tests/test_base.py": "import unittest\n\n\nclass Base(unittest.TestCase):\n    def test_base(self):\n        self.assertTrue(True)\n",
                 "docs/workflow/PRD.md": PRD, "docs/workflow/gates/gate-0.md": "# Gate 1\n\nPlan ready.\n",
                 "docs/workflow/log.md": "# Run log\n\n| When | Task | Node | Result | Loop | Usage |\n|---|---|---|---|---|---|\n"}
        for rel, text in files.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(text, encoding="utf-8")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "toy")
        self.git("config", "user.email", "toy@example.invalid")
        self.commit("toy")
        self.gw("init")
        fake = self.home / "claude"
        fake.write_text(FAKE, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.conf(test_command="%s -m unittest discover -s tests -t . -q" % sys.executable, commit_rehearsal=True,
                  drive={"command": str(fake), "models": {"main": "big", "coder": "small", "tester": "small"}, "env": {"FOO": "bar"}})
        self.commit("chore(workflow): set up graph-workflow")
        self.hook = self.repo / ".git/hooks/pre-commit"
        self.hook.write_text(HOOK)
        self.hook.chmod(0o755)
        self.gw("gate", "1")

    def git(self, *args, cwd=None):
        return sh(["git"] + list(args), cwd or self.repo, self.env).stdout

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def conf(self, **kw):
        p = self.repo / "docs/workflow/gw.json"
        p.write_text(json.dumps(dict(json.loads(p.read_text()), **kw)))

    def gw(self, *args, ok=True, cwd=None, stdin=None):
        r = sh([sys.executable, str(GW)] + list(args), cwd or self.repo, self.env, check=False, stdin=stdin)
        if ok and r.returncode:
            raise AssertionError("gw %s -> %d\n%s%s" % (" ".join(args), r.returncode, r.stdout, r.stderr))
        return r

    def task(self, n="1"):
        return json.loads((self.repo / "docs/workflow/.gw/state.json").read_text())["tasks"].get(n)

    def log(self):
        return (self.repo / "docs/workflow/log.md").read_text(encoding="utf-8")

    def brief(self, ok=True, **kw):
        (self.repo / "docs/workflow/briefs").mkdir(exist_ok=True)
        (self.repo / "docs/workflow/briefs/brief-1.md").write_text(brief_text("1", **kw), encoding="utf-8")
        return self.gw("brief", "1", ok=ok)

    def write_tests(self, mark="", holdout=True, plan=PLAN):
        out = self.tmp / "toy.tests" / "1"
        shutil.rmtree(str(out), True)
        (out / "visible").mkdir(parents=True)
        (out / "visible/test_add_1.py").write_text(VISIBLE.replace("MOD", "src.calc").replace("MARK", mark))
        if holdout:
            (out / "holdout").mkdir()
            (out / "holdout/test_more_1.py").write_text(HOLDOUT.replace("MOD", "src.calc"))
        (out / "test-plan.md").write_text(plan)

    def to_coding(self, **kw):
        self.brief(**kw)
        self.write_tests()
        self.gw("planned", "1")
        self.git("add", "docs/workflow")
        self.git("commit", "-q", "-m", "docs(1): brief")
        self.gw("seal", "1")
        self.gw("open", "1")
        return self.tmp / "toy.gw" / "1"

    def code(self, w, mark=""):
        (w / "src/calc.py").write_text("def add(a, b):\n    return a + b%s\n" % mark)
        (w / "docs/workflow/handoffs").mkdir(parents=True, exist_ok=True)
        (w / "docs/workflow/handoffs/handoff-1.md").write_text(HANDOFF.replace("STATUS", "done").replace("Handoff N", "Handoff 1"))

    def nothing_left_in_the_repo(self):
        self.assertEqual(len(self.git("worktree", "list").strip().splitlines()), 1, "a rehearsal worktree was left behind")
        for l in self.git("fsck", "--unreachable", "--no-reflogs").splitlines():   # git's own leftovers are fine
            if " tree " not in l:
                self.assertNotIn("class Held", self.git("cat-file", "-p", l.split()[-1]), "a held-out test is in the repo's objects")
        self.assertFalse((self.home / ".gw-vault").exists() and list((self.home / ".gw-vault").glob("*/rehearse/*")))


class FilesLine(Toy):
    def test_a_note_on_a_path_is_refused_at_the_brief(self):
        r = self.brief(change="src/calc.py（the add function）", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not a bare path", r.stdout)

    def test_may_change_must_name_a_file(self):
        r = self.brief(change="src/clac.py", ok=False)
        self.assertIn("matches no file", r.stdout)

    def test_none_globs_and_other_separators_pass(self):
        self.brief(change="src/calc.py； src/*.py、tests/test_base.py", create="none")
        self.assertEqual(self.task()["state"], "briefed")

    def test_brackets_in_a_folder_name_do_not_break_a_glob(self):
        (self.repo / "app/[id]").mkdir(parents=True)
        (self.repo / "app/[id]/page.tsx").write_text("x\n")
        self.commit("a route folder")
        w = self.to_coding(change="src/calc.py, app/[id]/*")
        self.code(w)
        (w / "app/[id]/page.tsx").write_text("y\n")
        self.assertNotIn("outside the brief's file list", self.gw("check", "1").stdout)

    def test_may_create_needs_no_existing_file(self):
        self.brief(change="src/calc.py", create="src/new_module.py, app/(shop)/new.tsx")

    def test_a_tracked_path_is_taken_as_it_stands(self):
        for rel in ("docs/損益コンパス.md", "app/(shop)/page.tsx", "app/[id]/page.tsx", "docs/My Notes.md"):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text("x\n", encoding="utf-8")
        self.commit("odd names")
        w = self.to_coding(change="src/calc.py, docs/損益コンパス.md, app/(shop)/page.tsx, app/[id]/page.tsx, docs/My Notes.md")
        self.code(w)
        (w / "app/[id]/page.tsx").write_text("y\n")
        r = self.gw("check", "1")
        self.assertNotIn("outside the brief's file list", r.stdout)


class CommitHook(Toy):
    def test_planned_refuses_tests_the_hook_would_reject(self):
        self.brief()
        self.write_tests(mark="  # LINTBAD")
        r = self.gw("planned", "1", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("commit hook rejects these tests", r.stdout)
        self.assertIn("lint: LINTBAD in tests/test_add_1.py", r.stdout)
        self.assertEqual(self.task()["state"], "briefed")
        self.nothing_left_in_the_repo()
        self.assertEqual(self.git("status", "--porcelain", "--", "tests", "src").strip(), "", "the main checkout was touched")
        self.write_tests()
        self.gw("planned", "1")
        self.assertEqual(self.task()["state"], "planned")
        self.nothing_left_in_the_repo()   # the held-out tests are in no object the Coder could dig out

    def test_when_the_hook_is_rehearsed(self):
        self.brief()
        self.write_tests(mark="  # LINTBAD")
        self.conf(commit_rehearsal=False)
        self.gw("planned", "1")
        self.conf(commit_rehearsal="auto")                    # auto: only a repo with .pre-commit-config.yaml
        self.gw("planned", "1")
        (self.repo / ".pre-commit-config.yaml").write_text("repos: []\n")
        self.assertEqual(self.gw("planned", "1", ok=False).returncode, 1)
        self.conf(commit_rehearsal=True)
        self.hook.unlink()                                    # no hook, nothing to rehearse
        self.gw("planned", "1")

    def test_a_hook_that_cannot_run_in_a_clone_is_skipped_not_believed(self):
        self.hook.write_text("#!/bin/sh\ntest -d .venv || { echo 'no .venv here'; exit 1; }\n")   # needs an ignored folder
        self.brief()
        self.write_tests()
        r = self.gw("planned", "1")
        self.assertIn("WARN  commit rehearsal skipped", r.stdout)
        self.assertEqual(self.task()["state"], "planned")

    def test_check_fails_code_the_hook_would_reject_then_merges_when_clean(self):
        w = self.to_coding()
        self.code(w, mark="  # LINTBAD")
        r = self.gw("check", "1", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("commit hook rejects this change", r.stdout)
        self.assertFalse(self.task()["check_ok"])
        self.code(w)
        self.gw("check", "1")
        self.gw("finish", "1")
        self.assertEqual(self.task()["state"], "done")
        self.assertIn("merge(1)", self.git("log", "--oneline", "main"))
        self.nothing_left_in_the_repo()

    @unittest.skipIf(os.name == "nt", "needs symlinks")
    def test_the_rehearsal_never_writes_through_a_link(self):
        outside = self.tmp / "outside.txt"
        outside.write_text("keep\n")
        os.symlink(str(outside), str(self.repo / "link.txt"))
        (self.repo / "src/thing").write_text("a file that becomes a folder\n")
        self.commit("a link and a file")
        w = self.to_coding(change="src/calc.py, link.txt, src/thing", create="src/thing/a.py")
        self.code(w)
        os.unlink(str(w / "link.txt"))
        (w / "link.txt").write_text("the Coder made it a plain file\n")
        os.unlink(str(w / "src/thing"))
        (w / "src/thing").mkdir()
        (w / "src/thing/a.py").write_text("x = 1\n")
        r = self.gw("check", "1", ok=False)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(outside.read_text(), "keep\n")


class Review(Toy):
    def test_a_fail_names_what_the_brief_asks(self):
        w = self.to_coding()
        self.code(w)
        self.gw("check", "1")
        for why in ("", "the naming is not to my taste", "A9", "check",    # A9 is not in the brief; the check passed
                    "test_a1_add is fine", "nothing wrong with A1", "check_ok is true, cheat-proof"):   # mentions, not reasons
            r = self.gw("review", "1", "fail", why, ok=False)
            self.assertEqual(r.returncode, 1, why)
            self.assertIn("fails only on what the brief asks", r.stdout)
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("review", 0))
        self.gw("review", "1", "fail", "a1, E1: the sum is wrong")
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("coding", 1))
        self.assertIn("| loop | review fail: A1, E1 | 1 |", self.log())

    def test_check_is_a_reason_while_the_check_fails(self):
        w = self.to_coding()
        self.code(w, mark="  # LINTBAD")
        self.gw("check", "1", ok=False)
        self.gw("review", "1", "fail", "check")
        self.assertEqual(self.task()["loop"], 1)


class Unpark(Toy):
    def park_after_three_fails(self):
        w = self.to_coding()
        self.code(w)
        for _ in range(3):
            self.gw("check", "1")
            self.gw("review", "1", "fail", "A1")
        self.assertEqual(self.task()["state"], "parked")

    def test_the_ceo_accepts_parked_work_and_it_is_checked_again(self):
        self.park_after_three_fails()
        self.assertEqual(self.gw("unpark", "1", " ", ok=False).returncode, 2)             # no reason
        for to in ("done", "merged", "replan", "sealed"):                                 # where its files do not allow
            self.assertEqual(self.gw("unpark", "1", "why", to, ok=False).returncode, 2, to)
        self.gw("unpark", "1", "CEO: accept it | merge", "review")
        t = self.task()
        self.assertEqual((t["state"], t["loop"], t["check_ok"]), ("review", 2, False))
        self.assertIn("| unpark | CEO: accept it merge -> review |", self.log())
        self.assertNotEqual(self.gw("finish", "1", ok=False).returncode, 0)                # not without a fresh check
        self.gw("check", "1")
        self.gw("finish", "1")
        self.assertEqual(self.task()["state"], "done")

    def test_by_default_it_goes_back_to_where_it_stopped(self):
        self.park_after_three_fails()
        self.gw("unpark", "1", "CEO: one more try")
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("coding", 2))

    def test_unpark_goes_back_to_where_main_parked_it(self):
        self.brief()
        self.gw("park", "1")
        self.gw("unpark", "1", "CEO: go on")
        self.assertEqual(self.task()["state"], "briefed")
        self.assertEqual(self.gw("unpark", "1", "again", ok=False).returncode, 2)          # not parked

    def test_a_task_parked_by_an_older_gw_needs_a_destination(self):
        self.park_after_three_fails()
        p = self.repo / "docs/workflow/.gw/state.json"
        s = json.loads(p.read_text())
        del s["tasks"]["1"]["resume"]
        p.write_text(json.dumps(s))
        r = self.gw("unpark", "1", "CEO: go on", ok=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("review (accept the work as it is", r.stdout)
        self.assertIn("coding (the Coder tries again)", r.stdout)
        self.gw("unpark", "1", "CEO: go on", "coding")


class LightPath(Toy):
    def test_a_ui_task_takes_no_held_out_tests_and_needs_no_spec_check(self):
        self.brief(risk="UI")
        self.write_tests()
        r = self.gw("planned", "1", ok=False)
        self.assertIn("risk layer is UI", r.stdout)
        self.write_tests(holdout=False)
        r = self.gw("planned", "1")
        self.assertIs(self.task()["spec"], False)
        self.assertIn("nothing to judge", r.stdout)
        self.assertIn("nothing for a spec check", self.log())

    def test_an_open_item_or_a_held_out_test_keeps_the_spec_check(self):
        self.brief(risk="UI")
        head = "# Test plan 1 — add function\n\n"
        for plan, spec in (
                (PLAN.replace("- none", "- A1: can mean sum or concatenation. Tests assume sum."), True),
                (PLAN + "\n## Not testable through the brief's interface\n| # | Why |\n|---|---|\n| A1 | no interface |\n", True),
                (head + "## Ambiguities\nA1 can mean sum or concatenation; the tests assume sum.\n", True),     # prose
                (head + "### Ambiguities\n1) A1 reads two ways\n", True),                                       # another heading level, another bullet
                (head + "**Ambiguities**\n\n- A1 reads two ways\n", True),                                     # not a heading at all
                (head + "Nothing to add.\n", True),                                                             # no heading: unknown
                ("Risk layer: UI — reached by: not reachable through the interface\n\n" + PLAN, True),
                (head + "## Ambiguities\n\n| # | Reading |\n|---|---|\n| 1 | none |\n", False),
                (head + "### Ambiguities\n- None.\n\n## Not testable through the brief's interface\n- none\n", False)):
            self.write_tests(holdout=False, plan=plan)
            self.gw("planned", "1")
            self.assertIs(self.task()["spec"], spec, plan)
        (self.repo / "docs/workflow/briefs/brief-1.md").write_text(brief_text("1"))   # a domain task whose held-out file
        self.write_tests(holdout=False)                                                # holds no test case gw can count
        (self.tmp / "toy.tests/1/holdout").mkdir()
        (self.tmp / "toy.tests/1/holdout/more.ts").write_text('Deno.test("e1 again", () => {});\n')
        r = self.gw("planned", "1")
        self.assertIs(self.task()["spec"], True)
        self.assertIn("WARN  test files with no test case counted", r.stdout)
        (self.repo / "docs/workflow/briefs/brief-1.md").write_text(brief_text("1"))   # now a domain task, with held-out tests
        self.write_tests()
        self.gw("planned", "1")
        self.assertIs(self.task()["spec"], True)


class Try(Toy):
    def test_try_reports_what_would_be_refused_and_changes_nothing(self):
        (self.repo / "docs/workflow/briefs").mkdir()
        (self.repo / "docs/workflow/briefs/brief-1.md").write_text(brief_text("1", change="src/calc.py (note)"))
        log = self.log()
        r = self.gw("try", "brief", "1", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not a bare path", r.stdout)
        self.assertIsNone(self.task())
        self.brief()
        self.write_tests(mark="  # LINTBAD")
        r = self.gw("try", "planned", "1", ok=False)
        self.assertIn("commit hook rejects these tests", r.stdout)
        self.write_tests()
        self.assertIn("ok:", self.gw("try", "planned", "1").stdout)
        self.assertEqual(self.task()["state"], "briefed")
        self.assertEqual(self.log().count("\n"), log.count("\n") + 1)   # only `gw brief` wrote a line


class Gate1(Toy):
    def prd(self, approvals):
        (self.repo / "docs/workflow/PRD.md").write_text("# PRD\n" + EDGES + approvals, encoding="utf-8")
        return self.gw("gate", "1", ok=False)

    def test_approvals_are_decided_before_the_build(self):
        self.assertIn("no '## Approvals' section", self.prd("").stdout)
        r = self.prd(APPROVALS.replace("- Nothing needed: service, send, delete, production", "- Nothing needed: service"))
        self.assertIn("approval category 'send' has no row and no 'Nothing needed' line", r.stdout)
        r = self.prd(APPROVALS.replace("| approved | CEO |", "| | CEO |"))
        self.assertIn("P1: Decision is empty", r.stdout)
        r = self.prd(APPROVALS.replace("| approved | CEO |", "| fine | Main |"))
        self.assertIn("P1: Source is 'Main'", r.stdout)
        self.assertEqual(self.prd(APPROVALS).returncode, 0)
        loose = APPROVALS.replace("| dependency |", "| Dependency |").replace("delete, production", "Delete, production.")
        self.assertEqual(self.prd(loose).returncode, 0)        # case and a full stop are not a missing category


class Hook(Toy):
    def ask(self, command, *args, lines=None):
        t = self.tmp / "transcript.jsonl"
        use = lambda cr, side=False: json.dumps({"type": "assistant", "isSidechain": side, "message": {
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": 990, "cache_read_input_tokens": cr}}})
        t.write_text("\n".join(lines or [json.dumps({"type": "user"}), use(250000), use(900000, side=True), "not json"]) + "\n")
        stdin = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "transcript_path": str(t),
                            "tool_input": {"command": command}})
        return self.gw("hook", *args, ok=False, cwd=self.tmp, stdin=stdin)   # run where there is no gw.json

    def test_new_work_is_refused_from_a_session_over_the_budget(self):
        r = self.ask("cd /repo && python3 /skills/graph-workflow/scripts/gw.py drive 3 4")
        self.assertEqual(r.returncode, 2)
        self.assertIn("carries 251k tokens of context", r.stderr)
        self.assertEqual(self.ask('python3 "/skills/gw/scripts/gw.py" brief 3').returncode, 2)
        for command, args in (("python3 /s/gw.py check 3", ()), ("python3 /s/gw.py finish 3", ()), ("ls", ()),
                              ("python3 /s/gw.py drive 3", ("300",)), ("python3 /s/gw.py drive 3", ("0",))):
            self.assertEqual(self.ask(command, *args).returncode, 0, command)
        self.assertEqual(self.ask(".venv/bin/python -u /s/gw.py drive 3; echo done").returncode, 2)
        for command in ("cat scripts/gw.py drive.py", "diff gw.py brief.md", "git commit -m 'gw.py drive notes'",
                        "python3 tools/x.py && cat gw.py drive"):   # they name the file, they do not run it
            self.assertEqual(self.ask(command).returncode, 0, command)
        big = json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 300000}}})
        empty = json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 0, "output_tokens": 0}}})
        self.assertEqual(self.ask("python3 /s/gw.py drive 3", lines=[big, empty]).returncode, 2)    # an empty line is not a request
        odd = [json.dumps({"type": "assistant", "message": {"usage": [1, 2]}}), json.dumps({"type": "assistant", "message": "usage"})]
        self.assertEqual(self.ask("python3 /s/gw.py drive 3", lines=odd).returncode, 0)
        self.assertEqual(self.gw("hook", ok=False, cwd=self.tmp, stdin="not json").returncode, 0)
        self.assertEqual(self.ask("python3 /s/gw.py drive 3", lines=["nothing readable"]).returncode, 0)   # unknown: let it run


class Drive(Toy):
    def calls(self, key="step"):
        p = self.home / "calls.json"
        return [c[key] if isinstance(key, str) else tuple(c[k] for k in key) for c in json.loads(p.read_text())] if p.exists() else []

    def drive(self, *ns, mode="happy"):
        self.env["FAKE_MODE"] = mode
        return self.gw("drive", *(ns or ("1",)))

    def test_refusals_go_back_to_their_author_and_use_no_loop(self):
        r = self.drive()
        self.assertEqual(self.calls(("step", "retry")),
                         [("brief", False), ("brief", True), ("tester", False), ("tester", True), ("spec", False),
                          ("coder", False), ("coder", True), ("review", False), ("review", False)], r.stdout)
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("done", 0), r.stdout)
        self.assertIn("| coder retry | ok |", self.log())
        self.assertNotIn("review fail", self.log())
        self.assertIn("merge(1)", self.git("log", "--oneline", "main"))
        self.nothing_left_in_the_repo()
        self.assertIn("task 1 is done", self.drive().stdout)          # driving a done task starts no session
        self.assertEqual(len(self.calls()), 9)

    def test_usage_is_the_whole_session_and_names_the_model(self):
        self.drive(mode="clean")
        row = [l for l in self.log().splitlines() if "| main:brief |" in l][0]
        self.assertIn("in 30 · cache 3000 · out 400 · $0.50 ·", row)   # modelUsage, not the last stretch's `usage`
        self.assertTrue(row.rstrip(" |").endswith("feedbeef · toy-model"), row)

    def test_the_default_env_reaches_every_session_beside_the_repos_own(self):
        self.drive(mode="clean")
        self.assertEqual(set(self.calls(("bg", "foo"))), {("1", "bar")})

    def test_a_review_that_does_not_settle_stops_with_a_page_and_no_loop(self):
        r = self.drive("1", "2", mode="stubborn")
        self.assertIn("the review did not settle in two sessions", r.stdout)
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("review", 0))
        self.assertIsNone(self.task("2"))                               # a stop ends the queue
        page = (self.repo / "docs/workflow/.gw/stop-1.md").read_text()
        self.assertIn("| Who | Main judges, in a fresh session |", page)
        self.assertIn("| Then | `gw drive 1 2` |", page)
        self.assertIn("outside the brief's file list: stray.txt", page)
        self.assertIn("| drive stop | the review did not settle", self.log())
        self.assertIn("drive stopped: read docs/workflow/.gw/stop-1.md", self.gw("next").stdout)

    def test_an_unnamed_fail_is_asked_again_and_uses_no_loop(self):
        r = self.drive(mode="vague")
        self.assertEqual(self.calls().count("review"), 2)
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("done", 0), r.stdout)
        self.assertIn("did not settle", self.drive("2", mode="vague-stubborn").stdout)
        self.assertEqual(self.task("2")["loop"], 0)

    def test_a_named_fail_uses_a_loop(self):
        r = self.drive(mode="named")
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("done", 1), r.stdout)
        self.assertIn("| loop | review fail: A1 | 1 |", self.log())

    def test_a_ui_task_runs_without_a_spec_session(self):
        r = self.drive(mode="ui")
        self.assertEqual(self.calls(), ["brief", "tester", "coder", "review"], r.stdout)
        self.assertEqual(self.task()["state"], "done", r.stdout)
        self.assertIn("docs(1): brief", self.git("log", "--oneline", "main"))

    def test_a_queue_runs_its_tasks_in_order(self):
        r = self.drive("1", "2", mode="clean")
        self.assertIn("the queue is done: 1 2", r.stdout)
        self.assertEqual([self.task(n)["state"] for n in "12"], ["done", "done"], r.stdout)
        self.assertEqual(self.calls(("step", "n")), [(s, n) for n in "12" for s in ("brief", "tester", "spec", "coder", "review")])
        self.assertEqual(list((self.repo / "docs/workflow/.gw").glob("stop-*.md")), [])

    def test_a_crash_is_a_stop_with_a_page_too(self):
        self.conf(drive={"command": str(self.tmp / "no-such-claude")})
        r = self.drive("1", "2", mode="clean")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("drive stopped at task 1: FileNotFoundError", r.stdout)
        page = (self.repo / "docs/workflow/.gw/stop-1.md").read_text()
        self.assertIn("| Task | 1: not started |", page)
        self.assertIn("| Then | `gw drive 1 2` |", page)

    def test_odd_result_shapes_are_logged_not_fatal(self):
        r = self.drive(mode="odd")
        self.assertEqual(self.task()["state"], "done", r.stdout + r.stderr)
        self.assertIn("in 0 · cache 0 · out 0 · $0.00 ·", self.log())

    def test_a_coder_blocked_on_its_retry_gets_the_answer_and_runs_again(self):
        r = self.drive(mode="blocked")
        self.assertEqual(self.calls()[5:], ["coder", "coder", "unblock", "coder", "review"], r.stdout)
        self.assertEqual((self.task()["state"], self.task()["loop"]), ("done", 0), r.stdout)


if __name__ == "__main__":
    unittest.main()

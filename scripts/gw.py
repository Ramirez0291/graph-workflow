#!/usr/bin/env python3
"""gw: deterministic gates and step scheduler for graph-workflow v0.5.

Run from the main checkout:  python <skill>/scripts/gw.py <command> [args]
Python 3.8+, standard library only. It refuses steps taken out of order and
checks what can be checked mechanically. Judgment stays with Main.

  init                 set up gw.json, .gitignore entry, sibling folders
  next | status        what each task needs next | one line per task
  gate 1               PRD edge cases fully decided by the CEO, gate-0.md ready
  gate 3 M             milestone closed, no provisional edge rows, Punk ran, docs clean
  brief N              check brief-N.md (needs gate 1), register task N
  planned N            Tester done: sets present, test caps, edge coverage, no source-text tests
  seal N               spec check done: lock the held-out set away
  open N               create the worktree, run setup, copy visible tests
  check N              Coder done: file list, tests, registry, shell rule, handoff
  review N pass|fail   record Main's review
  finish N             review pass, holdout, merge, close in one step
  holdout N            run the full suite with the held-out set (test lock)
  burn N               held-out failed: the set becomes visible, Tester writes a new one
  merge N              commit, refresh from main, full suite, merge (test lock)
  close N              archive the test plan, unlink, remove worktree and held-out files (rerunnable)
  park N               stop a task for the CEO
  show N plan|log      print the sealed test plan or the last run log
  docs                 check every workflow document against its kind and budget
  archive M            after gate 3: move milestone files to archive/M
  drive N              prototype: run task N's loop with `claude -p` (scripts/drive.py)
"""
import fnmatch, hashlib, json, os, re, shutil, stat, subprocess, sys, time
from pathlib import Path

ROOT = Path.cwd()
WF = ROOT / "docs" / "workflow"
CONF, STATE = WF / "gw.json", WF / ".gw" / "state.json"
TESTS, TREES = ROOT.parent / (ROOT.name + ".tests"), ROOT.parent / (ROOT.name + ".gw")
VAULT = Path.home() / ".gw-vault" / (ROOT.name + "-" + hashlib.sha1(str(ROOT.resolve()).encode()).hexdigest()[:8])
MAX_LOOPS = 3
DEFAULTS = {"main_branch": "main", "test_command": "", "test_dir": "tests", "setup_command": "",
            "parallel_max": 2, "port_base": 20000, "lock_timeout_min": 60,
            "registry_files": [], "shell_paths": [], "shell_forbid": [],
            "edge_categories": ["threshold", "interleave", "repeat", "time-cross", "counting",
                                "environment", "failure"],
            "test_caps": {"visible": 1, "holdout": 2},
            "test_case_pattern": r"^\s*(?:it|test)(?:\.\w+)*\s*\(|^\s*(?:async\s+)?def\s+test_|^\s*#\[[\w:]*test\]|^\s*func\s+Test",
            "source_dirs": ["src"], "screens_max": 12}
RECORD = ["STATE.md", "tasks.md", "decisions.md", "debt.md", "log.md",
          "handoffs/handoff-*.md", "tests/test-report-*.md"]
THINK = ["PRD.md", "architecture.md", "architecture/*.md", "briefs/brief-*.md",
         "gates/gate-*.md", "punk/objections-*.md", "tests/test-plan-*.md"]
BUDGET = {"briefs/brief-*.md": 500, "gates/gate-*.md": 500, "punk/objections-*.md": 500,
          "tests/test-plan-*.md": 500, "handoffs/handoff-*.md": 250, "tests/test-report-*.md": 250,
          "STATE.md": 500, "architecture.md": 1000}
OTHER = ["gw.json", ".gw/*", "punk/screens-*", "archive/*"]
IMAGES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
NEXT = {
    "briefed": "run gw-tester with the brief and {tests}; then `gw planned {n}`",
    "planned": "spec check {tests}/test-plan.md, amend the brief (product questions -> PRD edge row, "
               "source 'Main provisional'), commit it on main; then `gw seal {n}`",
    "sealed": "`gw open {n}`",
    "coding": "run gw-coder in {wt}; then `gw check {n}`",
    "review": "review the diff and the handoff's Defenses added; then `gw finish {n}` or `gw review {n} fail`",
    "reviewed": "`gw holdout {n}`",
    "holdout-failed": "write Loop notes in the worktree brief (behavior only); then `gw burn {n}`",
    "replan": "run gw-tester for a fresh held-out set and test plan in {tests}; then `gw planned {n}`",
    "passed": "`gw merge {n}`",
    "conflict": "refresh from main conflicts: resolve in {wt} or re-cut the task; then `gw merge {n}`",
    "drift": "passes alone, fails with main: decide which behavior is right, fix; then `gw merge {n}`",
    "merged": "`gw close {n}`; then update tasks.md and STATE.md and commit `docs({n}): close`",
    "parked": "waiting for the CEO (diagnosis in STATE)",
    "done": "done",
}
CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿가-힯]")


def die(msg, code=2):
    print("REFUSED: " + msg)
    sys.exit(code)


def run(cmd, cwd=ROOT, env=None, check=True):
    r = subprocess.run(cmd, cwd=str(cwd), env=env, shell=isinstance(cmd, str), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        die("%s failed:\n%s%s" % (cmd, r.stdout, r.stderr))
    return r


def git(*args, cwd=ROOT, check=True):
    return run(["git"] + list(args), cwd=cwd, check=check)


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def conf():
    c = dict(DEFAULTS)
    c.update(load(CONF, {}))
    return c


def state():
    s = load(STATE, {"tasks": {}})
    s.setdefault("gates", {})
    return s


def task(s, n, want):
    t = s["tasks"].get(n)
    if t is None:
        die("task %s is unknown; start with `gw brief %s`" % (n, n))
    if t["state"] not in want:
        die("task %s is '%s'; this step needs %s. Next: %s" % (n, t["state"], "/".join(want), hint(n, t)))
    return t


def hint(n, t):
    return NEXT[t["state"]].format(n=n, tests=TESTS / n, wt=TREES / n)


def log(n, node, result, loop="", usage=""):
    with open(WF / "log.md", "a", encoding="utf-8") as f:
        f.write("| %s | %s | %s | %s | %s | %s |\n" % (time.strftime("%Y-%m-%d %H:%M"), n, node, result, loop, usage))


def units(s):
    return len(re.findall(r"[A-Za-z0-9][\w'.-]*", CJK.sub(" ", s))) + len(CJK.findall(s)) / 2


def sentences(s):
    return len([x for x in re.split(r"(?<=[。！？!?])|(?<=\.)\s+", s) if x.strip()])


def section(text, name):
    m = re.search(r"^##\s+%s.*?$(.*?)(?=^##\s|\Z)" % re.escape(name), text, re.M | re.S)
    return m.group(1) if m else ""


def rows(text, prefix):
    """Table rows whose first cell matches prefix (e.g. 'E' -> E1, E2 ...), as lists of cells."""
    out = []
    for l in text.splitlines():
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if l.strip().startswith("|") and re.fullmatch(prefix + r"\d+", cells[0]):
            out.append(cells)
    return out


def blank(cell):
    return not cell or cell.startswith("<") or cell.startswith(("（", "("))


def check_doc(p, rel):
    text = p.read_text(encoding="utf-8")
    kind = "record" if any(fnmatch.fnmatch(rel, g) for g in RECORD) else \
           "think" if any(fnmatch.fnmatch(rel, g) for g in THINK) else None
    if kind is None:
        return [] if any(fnmatch.fnmatch(rel, g) for g in OTHER) else ["not in the layout"]
    probs = ["%.1f words > budget %d" % (units(text), b) for g, b in BUDGET.items()
             if fnmatch.fnmatch(rel, g) and units(text) > b]
    lines = re.sub(r"^```.*?^```", "", text, flags=re.M | re.S).splitlines()
    if kind == "record":
        bad = [l.strip() for l in lines if l.strip() and not l.strip().startswith(("#", "|", ">"))]
        if bad:
            probs.append("record file must be tables only; first offending line: " + bad[0][:50])
        if sum(l.strip().startswith(">") for l in lines) > 2:
            probs.append("more than two '>' note lines")
        return probs
    head, body = "(top)", []
    for l in lines + ["## (end)"]:
        if l.startswith("#"):
            prose = " ".join(x.strip() for x in body if x.strip()
                             and not re.match(r"[|#>*-]|\d+\.", x.strip()))
            if sentences(prose) > 3:
                probs.append("section '%s': %d sentences > 3" % (head, sentences(prose)))
            if any(re.match(r"[*-]|\d+\.", x.strip()) and units(x) > 40 for x in body):
                probs.append("section '%s': a bullet over 40 words" % head)
            head, body = l.lstrip("# ").strip(), []
        else:
            body.append(l)
    return probs


def edges():
    """PRD edge-case table: {E#: cells}. Columns: # | Req | Category | Case | Options | Recommended | Decision | Source."""
    p = WF / "PRD.md"
    text = section(p.read_text(encoding="utf-8"), "Edge cases") if p.exists() else ""
    return {r[0]: (r + [""] * 8)[:8] for r in rows(text, "E")}, text


def provisional(table):
    return [k for k, r in table.items() if r[7].upper() != "CEO"]


def brief_file(n):
    w = TREES / n / "docs" / "workflow" / "briefs" / ("brief-%s.md" % n)
    return w if w.exists() else WF / "briefs" / ("brief-%s.md" % n)


def allowed(text, n):
    pats = []
    for m in re.finditer(r"^\s*-\s*May (?:change|create):\s*(.*)$", text, re.M | re.I):
        pats += [x.strip(" `") for x in re.split(r"[,，]", m.group(1)) if x.strip(" `<>") and "<" not in x]
    return pats


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def check_brief(p, n):
    if not p.exists():
        return ["%s is missing" % p]
    text = p.read_text(encoding="utf-8")
    probs = check_doc(p, "briefs/brief-%s.md" % n)
    probs += ["no '## %s' section" % h for h in ("Acceptance criteria", "Edge cases", "Interface", "Risk layer", "Files")
              if not re.search(r"^##\s+%s" % h, text, re.M)]
    if not re.search(r"domain|orchestration|native|\bui\b", section(text, "Risk layer"), re.I):
        probs.append("Risk layer must name domain / orchestration / native / UI")
    if not allowed(text, n):
        probs.append("no '- May change:' or '- May create:' paths")
    table, _ = edges()
    for r in rows(section(text, "Edge cases"), "E"):
        if r[0] not in table:
            probs.append("%s is not in the PRD's Edge cases" % r[0])
        elif norm(r[-1]) != norm(table[r[0]][6]):
            probs.append("%s decision differs from the PRD; copy it verbatim" % r[0])
    return probs


def changed(path):
    files = []
    for l in git("status", "--porcelain", "-uall", cwd=path).stdout.splitlines():
        f = l[3:].split(" -> ")[-1].strip('"')
        files.append(f)
    return files


def copy_in(src, dst):
    out = []
    for f in sorted(src.rglob("*")) if src.exists() else []:
        if f.is_file():
            rel = f.relative_to(src)
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(f), str(dst / rel))
            out.append(rel)
    return out


def env_for(t, c):
    slot = t.get("slot") or 0
    e = dict(os.environ, GW_SLOT=str(slot), GW_PORT_BASE=str(c["port_base"] + 100 * slot),
             GW_TMP=str(VAULT / "tmp" / str(slot)))
    Path(e["GW_TMP"]).mkdir(parents=True, exist_ok=True)
    return e


def run_tests(cwd, t, c, logfile):
    if not c["test_command"]:
        die("set test_command in docs/workflow/gw.json")
    r = run(c["test_command"], cwd=cwd, env=env_for(t, c), check=False)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logfile.write_text(r.stdout + r.stderr, encoding="utf-8")
    return r.returncode == 0


class TestLock:
    """One test run at a time across all worktrees: no port, file or cache races."""
    def __init__(self, c):
        self.p, self.limit = VAULT / "test.lock", c["lock_timeout_min"] * 60

    def __enter__(self):
        VAULT.mkdir(parents=True, exist_ok=True)
        start = time.time()
        while True:
            try:
                os.close(os.open(str(self.p), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.p.stat().st_mtime > 3 * 3600:
                        self.p.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.time() - start > self.limit:
                    die("test lock busy for %d min" % (self.limit // 60))
                time.sleep(2)

    def __exit__(self, *exc):
        if self.p.exists():
            self.p.unlink()


def loop_back(s, t, n, why, then="coding"):
    t["loop"] += 1
    t["state"] = "parked" if t["loop"] >= MAX_LOOPS else then
    log(n, "loop", why, t["loop"])
    save(STATE, s)
    print("loop %d/%d: %s -> %s" % (t["loop"], MAX_LOOPS, why, t["state"]))


def is_link(p):
    """Symlink or Windows junction. A junction is a reparse point that os.path.islink misses before 3.12."""
    if os.path.islink(p) or getattr(os.path, "isjunction", lambda _: False)(p):
        return True
    try:
        return bool(getattr(os.lstat(p), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def unlink_links(top, depth=4):
    """Remove links inside a worktree without following them, so deleting the worktree cannot reach their targets."""
    gone = []
    try:
        entries = list(os.scandir(str(top)))
    except OSError:
        return gone
    for e in entries:
        if e.name == ".git":
            continue
        if is_link(e.path):
            try:
                os.unlink(e.path)
            except OSError:
                try:
                    os.rmdir(e.path)  # Windows: junctions and directory symlinks
                except OSError:  # another kind of reparse point (a cloud placeholder): not a link
                    continue
            gone.append(e.path)
        elif depth > 1 and e.is_dir(follow_symlinks=False):
            gone += unlink_links(e.path, depth - 1)
    return gone


def count_tests(folder, pattern):
    n = 0
    for f in folder.rglob("*") if folder.exists() else []:
        if f.is_file():
            n += len(re.findall(pattern, f.read_text(encoding="utf-8", errors="ignore"), re.M))
    return n


def source_reads(folder, c, extra):
    """Test files that read product source files as text (a test of the source, not the behavior)."""
    reads = re.compile(r"readFile|read_text|read_to_string|include_str!|open\(|fs\.read|Deno\.readTextFile")
    dirs = [d.strip("/") + "/" for d in c["source_dirs"]]
    lit = re.compile(r"""["'`]([^"'`\n]*\.(?:ts|tsx|js|jsx|mjs|vue|svelte|py|rs|go|java|kt|cs|css|scss|html))["'`]""")
    hits = []
    for f in folder.rglob("*") if folder.exists() else []:
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        if not reads.search(text):
            continue
        for l in text.splitlines():
            if re.match(r"\s*(import|export|from|use)\b", l) or "require(" in l:
                continue
            for m in lit.finditer(l):
                path = m.group(1).replace("\\", "/")
                if any(d in path or path.startswith(d) for d in dirs) or \
                        any(fnmatch.fnmatch(path.lstrip("./"), p) for p in extra):
                    hits.append("%s: %s" % (f.name, path))
    return hits


def cmd_init():
    if not (ROOT / ".git").exists():
        die("run from the main checkout of a git repository")
    if not CONF.exists():
        c = dict(DEFAULTS, main_branch=git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip())
        save(CONF, c)
    gi = ROOT / ".gitignore"
    lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    if "docs/workflow/.gw/" not in lines:
        gi.write_text("\n".join(lines + ["docs/workflow/.gw/"]) + "\n", encoding="utf-8")
    TESTS.mkdir(exist_ok=True)
    TREES.mkdir(exist_ok=True)
    save(STATE, state())
    print("ready. Fill docs/workflow/gw.json: test_command, test_dir, setup_command, registry_files, shell rules.")


def cmd_next():
    s = state()
    if not s["gates"].get("1"):
        print("Gate 1 not passed: sweep the PRD's Edge cases, let the CEO fill every Decision, then `gw gate 1`")
    for n, t in sorted(s["tasks"].items()):
        print("[%s] %s: %s" % (n, t["state"], hint(n, t)))
    if not s["tasks"]:
        print("no tasks: write briefs/brief-N.md, then `gw brief N`")
    print("Only Gate 1, Gate 3, parked tasks and irreversible actions wait for the CEO. "
          "Everything else, Gate 2 included: continue without asking.")


def cmd_status():
    for n, t in sorted(state()["tasks"].items()):
        print("%5s  %-15s loop %d  set %d  slot %s" % (n, t["state"], t["loop"], t["set"], t.get("slot") or "-"))


def cmd_gate(which, m=""):
    s, c, probs = state(), conf(), []
    table, text = edges()
    if which == "1":
        if not table:
            probs.append("PRD has no '## Edge cases' table with E# rows")
        named = set()
        for l in text.splitlines():
            mm = re.match(r"\s*[-*]\s*(?:No dispute|无争议|無争議|争議なし)\s*[:：]\s*(.+)$", l, re.I)
            if mm:
                named |= {x.strip() for x in re.split(r"[,，、]", mm.group(1)) if x.strip()}
        used = {r[2] for r in table.values()}
        probs += ["category '%s' has no row and no 'No dispute' line" % k for k in c["edge_categories"]
                  if k not in used and k not in named]
        probs += ["%s: category '%s' is not in gw.json edge_categories" % (k, r[2]) for k, r in table.items()
                  if r[2] not in c["edge_categories"]]
        probs += ["%s: Decision is empty" % k for k, r in table.items() if blank(r[6])]
        probs += ["%s: Source is '%s'; at Gate 1 every decision is the CEO's" % (k, r[7]) for k, r in table.items()
                  if r[7].upper() != "CEO"]
        packet = WF / "gates" / "gate-0.md"
        probs += ["gates/gate-0.md is missing"] if not packet.exists() else \
                 ["gate-0.md: " + p for p in check_doc(packet, "gates/gate-0.md")]
    elif which == "3":
        if not m:
            die("gate 3 takes the milestone: `gw gate 3 M1`")
        probs += ["task %s is '%s'" % (n, t["state"]) for n, t in s["tasks"].items() if t["state"] not in ("done", "parked")]
        probs += ["%s is 'Main provisional': the CEO confirms it first" % k for k in provisional(table)]
        for rel in ("gates/gate-%s.md" % m, "punk/objections-%s.md" % m):
            if not (WF / rel).exists():
                probs.append(rel + " is missing")
        probs += doc_problems()
    else:
        die("gate takes 1 or 3")
    if probs:
        die("gate %s:\n  " % which + "\n  ".join(probs), 1)
    key = "1" if which == "1" else "3:" + m
    s["gates"][key] = time.strftime("%Y-%m-%d %H:%M")
    save(STATE, s)
    log("—", "gate " + (which if which == "1" else "3 " + m), "ready for the CEO")
    print("gate %s ready: present the packet to the CEO." % which +
          (" After approval, `gw archive %s`; then tell the CEO to clear the session's context." % m if which == "3" else ""))


def cmd_brief(n):
    s = state()
    if not s["gates"].get("1"):
        die("Gate 1 has not passed (`gw gate 1`): no brief before every edge case has the CEO's decision")
    if n in s["tasks"] and s["tasks"][n]["state"] != "briefed":
        die("task %s is already '%s'" % (n, s["tasks"][n]["state"]))
    probs = check_brief(WF / "briefs" / ("brief-%s.md" % n), n)
    if probs:
        die("brief: " + "; ".join(probs), 1)
    s["tasks"][n] = {"state": "briefed", "loop": 0, "set": 1, "slot": None}
    save(STATE, s)
    log(n, "brief", "ok")
    print("next: " + hint(n, s["tasks"][n]))


def cmd_planned(n):
    s, c = state(), conf()
    t = task(s, n, ["briefed", "replan", "planned"])
    for need in ("visible", "holdout", "test-plan.md"):
        if not (TESTS / n / need).exists():
            die("missing %s" % (TESTS / n / need))
    probs = ["test plan: " + p for p in check_doc(TESTS / n / "test-plan.md", "tests/test-plan-%s.md" % n)]
    text = (WF / "briefs" / ("brief-%s.md" % n)).read_text(encoding="utf-8")
    crit = len(rows(section(text, "Acceptance criteria"), "A"))
    eids = [r[0] for r in rows(section(text, "Edge cases"), "E")]
    vis, held = TESTS / n / "visible", TESTS / n / "holdout"
    nv, nh = count_tests(vis, c["test_case_pattern"]), count_tests(held, c["test_case_pattern"])
    cap_v, cap_h = (crit + len(eids)) * c["test_caps"]["visible"], (crit + len(eids)) * c["test_caps"]["holdout"]
    if t["set"] == 1 and nv > cap_v:
        probs.append("%d visible tests > cap %d (%d criteria + %d edge rows); merge or cut" % (nv, cap_v, crit, len(eids)))
    if nh > cap_h:
        probs.append("%d held-out tests > cap %d; merge or cut" % (nh, cap_h))
    both = "".join(f.read_text(encoding="utf-8", errors="ignore") for d in (vis, held)
                   for f in (d.rglob("*") if d.exists() else []) if f.is_file())
    probs += ["%s has no test naming it" % e for e in eids
              if not re.search(r"(?<![A-Za-z0-9])%s(?!\d)" % e, both, re.I)]
    probs += ["test reads product source as text: " + h for d in (vis, held) for h in source_reads(d, c, allowed(text, n))]
    if probs:
        die("planned:\n  " + "\n  ".join(probs), 1)
    if (nv + nh) == 0 and any(vis.rglob("*")):
        print("WARN  no test cases counted; set test_case_pattern in gw.json")
    t["state"] = "planned"
    save(STATE, s)
    log(n, "tester", "plan ok: %d visible, %d held-out" % (nv, nh), t["loop"])
    print("next: " + hint(n, t))


def cmd_seal(n):
    s = state()
    t = task(s, n, ["planned"])
    rel = "docs/workflow/briefs/brief-%s.md" % n
    probs = check_brief(brief_file(n), n)
    if probs:
        die("brief: " + "; ".join(probs), 1)
    if not t.get("slot") and (git("status", "--porcelain", "--", rel).stdout.strip()
                                     or git("ls-files", "--error-unmatch", rel, check=False).returncode):
        die("commit the brief on main first: `docs(%s): brief`" % n)
    dest = VAULT / n / ("set-%d" % t["set"])
    if dest.exists():
        die("set %d is already sealed" % t["set"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(TESTS / n / "holdout"), str(dest))
    if (VAULT / n / "test-plan.md").exists():
        (VAULT / n / "test-plan.md").unlink()
    shutil.move(str(TESTS / n / "test-plan.md"), str(VAULT / n / "test-plan.md"))
    t["state"] = "coding" if t.get("slot") else "sealed"  # a replan seals into the open worktree
    save(STATE, s)
    log(n, "seal", "held-out set %d sealed" % t["set"], t["loop"])
    print("next: " + hint(n, t))


def cmd_open(n):
    s, c = state(), conf()
    t = task(s, n, ["sealed"])
    used = {x.get("slot") for x in s["tasks"].values()}
    free = [i for i in range(1, c["parallel_max"] + 1) if i not in used]
    if not free:
        die("parallel_max=%d worktrees are already open" % c["parallel_max"])
    t["slot"] = free[0]
    git("worktree", "add", str(TREES / n), "-b", "gw/" + n, c["main_branch"])
    if c["setup_command"]:
        run(c["setup_command"], cwd=TREES / n, env=env_for(t, c))
    copy_in(TESTS / n / "visible", TREES / n / c["test_dir"])
    t["state"] = "coding"
    save(STATE, s)
    log(n, "open", "slot %d" % t["slot"])
    print("next: " + hint(n, t))


def cmd_check(n):
    s, c = state(), conf()
    t = task(s, n, ["coding", "review"])
    w, probs, warns = TREES / n, [], []
    files = changed(w)
    h = w / "docs" / "workflow" / "handoffs" / ("handoff-%s.md" % n)
    if h.exists() and re.search(r"\|\s*status\s*\|\s*blocked\s*\||status:\s*blocked", h.read_text(encoding="utf-8"), re.I):
        die("the Coder is blocked: answer by fixing the brief in the worktree, then rerun it", 3)
    main_brief = (WF / "briefs" / ("brief-%s.md" % n)).read_text(encoding="utf-8")
    if section(main_brief, "Files") != section(brief_file(n).read_text(encoding="utf-8"), "Files"):
        warns.append("the worktree brief's Files section differs from main; only main's list counts")
    pats = allowed(main_brief, n) + [
        "docs/workflow/handoffs/handoff-%s.md" % n, "docs/workflow/briefs/brief-%s.md" % n]
    visible = {(Path(c["test_dir"]) / r).as_posix(): TESTS / n / "visible" / r
               for r in [f.relative_to(TESTS / n / "visible") for f in (TESTS / n / "visible").rglob("*") if f.is_file()]}
    for f in files:
        if f in visible:
            if (w / f).read_bytes() != visible[f].read_bytes():
                probs.append("visible test edited: " + f)
        elif f in c["registry_files"]:
            probs.append("registry file is Main-only: " + f)
        elif not any(fnmatch.fnmatch(f, p) for p in pats):
            (warns if f.startswith(c["test_dir"] + "/") else probs).append("outside the brief's file list: " + f)
        if any(f.startswith(sp) for sp in c["shell_paths"]) and (w / f).is_file():
            text = (w / f).read_text(encoding="utf-8", errors="ignore")
            probs += ["shell file reaches into state (%s): %s" % (rx, f) for rx in c["shell_forbid"] if re.search(rx, text)]
    if not h.exists():
        probs.append("handoff-%s.md is missing" % n)
    else:
        probs += ["handoff: " + p for p in check_doc(h, "handoffs/handoff-%s.md" % n)]
        text = h.read_text(encoding="utf-8")
        if not re.search(r"^##\s+Defenses added", text, re.M):
            probs.append("handoff has no 'Defenses added' section")
        warns += ["defense listed in an unchanged file: " + r for r in
                  re.findall(r"([\w./-]+\.\w+):\d+", section(text, "Defenses added")) if r not in files]
    stray = [f for f in changed(ROOT) if not f.startswith("docs/workflow/") and f != ".gitignore"]
    if stray:
        warns.append("main checkout changed outside docs/workflow (Coder left its worktree?): " + ", ".join(stray[:5]))
    t["state"], t["check_ok"] = "review", not probs
    save(STATE, s)
    log(n, "check", "pass" if not probs else "fail: %d problems" % len(probs), t["loop"])
    for p in probs:
        print("FAIL  " + p)
    for p in warns:
        print("WARN  " + p)
    print("%d changed files, %d problems, %d warnings. next: %s" % (len(files), len(probs), len(warns), hint(n, t)))
    sys.exit(1 if probs else 0)


def cmd_review(n, verdict):
    s = state()
    t = task(s, n, ["review"])
    if verdict == "pass":
        if not t.get("check_ok"):
            die("`gw check %s` did not pass; fail the review or fix and rerun the check" % n)
        t["state"] = "reviewed"
        save(STATE, s)
        log(n, "review", "pass", t["loop"])
        print("next: " + hint(n, t))
    elif verdict == "fail":
        loop_back(s, t, n, "review fail")
    else:
        die("review takes pass or fail")


def cmd_holdout(n):
    s, c = state(), conf()
    t = task(s, n, ["reviewed"])
    w = TREES / n
    with TestLock(c):
        copied = copy_in(VAULT / n / ("set-%d" % t["set"]), w / c["test_dir"])
        ok = run_tests(w, t, c, VAULT / n / "last.log")
        for rel in copied:
            (w / c["test_dir"] / rel).unlink()
    t["state"] = "passed" if ok else "holdout-failed"
    save(STATE, s)
    log(n, "holdout", "pass" if ok else "fail (set %d)" % t["set"], t["loop"])
    print(("PASS" if ok else "FAIL (read it with `gw show %s log`)" % n) + ". next: " + hint(n, t))


def cmd_burn(n):
    s, c = state(), conf()
    t = task(s, n, ["holdout-failed"])
    src = VAULT / n / ("set-%d" % t["set"])
    copy_in(src, TESTS / n / "visible")
    copy_in(src, TREES / n / c["test_dir"])
    t["set"] += 1
    loop_back(s, t, n, "held-out set %d failed; it is now visible" % (t["set"] - 1), then="replan")
    print("next: " + hint(n, t))


def cmd_merge(n):
    s, c = state(), conf()
    t = task(s, n, ["passed", "conflict", "drift"])
    w = TREES / n
    m = re.search(r"^#\s*Brief\s+\S+\s*[—-]\s*(.+)$", brief_file(n).read_text(encoding="utf-8"), re.M)
    title = m.group(1).strip() if m else "task " + n
    with TestLock(c):
        copy_in(VAULT / n / ("set-%d" % t["set"]), w / c["test_dir"])
        git("add", "-A", cwd=w)
        git("commit", "-m", "feat(%s): %s" % (n, title), cwd=w, check=False)
        if git("merge", "--no-edit", c["main_branch"], cwd=w, check=False).returncode:
            git("merge", "--abort", cwd=w, check=False)
            t["state"] = "conflict"
        elif not run_tests(w, t, c, VAULT / n / "last.log"):
            t["state"] = "drift"
        else:
            r = git("merge", "--no-ff", "-m", "merge(%s): %s" % (n, title), "gw/" + n, check=False)
            if r.returncode:
                die("merge into main refused (commit or stash your docs first):\n" + r.stdout + r.stderr)
            t["state"] = "merged" if run_tests(ROOT, t, c, VAULT / n / "last.log") else "drift"
    save(STATE, s)
    log(n, "merge", t["state"], t["loop"])
    print(t["state"].upper() + ". next: " + hint(n, t))
    sys.exit(0 if t["state"] == "merged" else 1)


def cmd_close(n):
    """Each step skips what is already done, so a close that failed halfway can simply be rerun."""
    s = state()
    t = task(s, n, ["merged"])
    w = TREES / n
    if (VAULT / n / "test-plan.md").exists():
        (WF / "tests").mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(VAULT / n / "test-plan.md"), str(WF / "tests" / ("test-plan-%s.md" % n)))
    if w.exists():
        for p in unlink_links(w):
            print("unlinked " + p)
        if git("worktree", "remove", "--force", str(w), check=False).returncode and w.exists():
            shutil.rmtree(str(w))
    git("worktree", "prune", check=False)
    if git("rev-parse", "--verify", "--quiet", "gw/" + n, check=False).returncode == 0:
        git("branch", "-d", "gw/" + n)
    shutil.rmtree(str(TESTS / n), ignore_errors=True)
    shutil.rmtree(str(VAULT / n), ignore_errors=True)
    t["state"], t["slot"] = "done", None
    save(STATE, s)
    log(n, "close", "done", t["loop"])
    print("closed. next: " + hint(n, t))


def cmd_finish(n):
    """Review pass -> holdout -> merge -> close: one call instead of four, stopping at the first failure."""
    cmd_review(n, "pass")
    cmd_holdout(n)
    if state()["tasks"][n]["state"] != "passed":
        sys.exit(1)
    try:
        cmd_merge(n)
    except SystemExit as e:
        if e.code:
            raise
    cmd_close(n)


def cmd_park(n):
    s = state()
    t = task(s, n, [k for k in NEXT if k not in ("done", "parked")])
    t["state"] = "parked"
    save(STATE, s)
    log(n, "park", "parked by Main", t["loop"])
    print("parked. Write the diagnosis under 'Open questions for the CEO' in STATE.md.")


def cmd_show(n, what):
    p = VAULT / n / ("test-plan.md" if what == "plan" else "last.log")
    print(p.read_text(encoding="utf-8") if p.exists() else "nothing at %s" % p)


def doc_problems():
    probs, c = [], conf()
    for p in sorted(WF.rglob("*")):
        rel = p.relative_to(WF).as_posix()
        if p.is_file() and not rel.startswith((".gw/", "archive/", "punk/screens-")):
            probs += ["%s: %s" % (rel, x) for x in check_doc(p, rel)]
    for d in sorted((WF / "punk").glob("screens-*")) if (WF / "punk").exists() else []:
        files = [f for f in d.rglob("*") if f.is_file()]
        imgs = [f for f in files if f.suffix.lower() in IMAGES]
        if len(imgs) > c["screens_max"]:
            probs.append("punk/%s: %d screenshots > %d" % (d.name, len(imgs), c["screens_max"]))
        if len(files) - len(imgs) > 1:
            probs.append("punk/%s: %d non-image files; keep one script" % (d.name, len(files) - len(imgs)))
    return probs


def cmd_docs():
    probs = doc_problems()
    print("\n".join(probs) if probs else "docs ok")
    sys.exit(1 if probs else 0)


def cmd_archive(m):
    s = state()
    if not s["gates"].get("3:" + m):
        die("`gw gate 3 %s` has not passed" % m)
    if any(t["state"] not in ("done", "parked") for t in s["tasks"].values()):
        die("close or park every task first")
    dst = WF / "archive" / m
    dst.mkdir(parents=True, exist_ok=True)
    for name in ("briefs", "handoffs", "tests", "gates", "punk"):
        if (WF / name).exists():
            shutil.move(str(WF / name), str(dst / name))
            (WF / name).mkdir()
    for name in ("log.md", "decisions.md"):
        p = WF / name
        if p.exists():
            lines = p.read_text(encoding="utf-8").splitlines()
            cut = next((i for i, l in enumerate(lines) if re.match(r"^\|\s*-", l)), len(lines) - 1)
            shutil.move(str(p), str(dst / name))
            p.write_text("\n".join(lines[:cut + 1]) + "\n", encoding="utf-8")
    s["tasks"] = {k: v for k, v in s["tasks"].items() if v["state"] == "parked"}
    for k in s["tasks"]:  # parked tasks keep their brief in the hot area
        b = dst / "briefs" / ("brief-%s.md" % k)
        if b.exists():
            shutil.move(str(b), str(WF / "briefs" / b.name))
    save(STATE, s)
    print("archived to %s. Main reads hot files only from now on." % dst.relative_to(ROOT))


def cmd_drive(n):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import drive
    drive.main(n)


CMDS = {"init": cmd_init, "next": cmd_next, "status": cmd_status, "gate": cmd_gate, "brief": cmd_brief,
        "planned": cmd_planned, "seal": cmd_seal, "open": cmd_open, "check": cmd_check, "review": cmd_review,
        "finish": cmd_finish, "holdout": cmd_holdout, "burn": cmd_burn, "merge": cmd_merge, "close": cmd_close,
        "park": cmd_park, "show": cmd_show, "docs": cmd_docs, "archive": cmd_archive, "drive": cmd_drive}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] != "init" and not CONF.exists():
        die("run `gw init` first")
    fn, args = CMDS[sys.argv[1]], sys.argv[2:]
    most = fn.__code__.co_argcount
    if not most - len(fn.__defaults__ or ()) <= len(args) <= most:
        die("wrong arguments for `%s`; run gw.py with no arguments for usage" % sys.argv[1])
    fn(*args)

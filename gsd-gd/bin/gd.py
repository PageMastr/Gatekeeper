#!/usr/bin/env python3
"""gd - the GSD-GameDev toolchain CLI.

One command surface over Godot and Blender so that every agent drives the
toolchain the same way, and every result comes back as machine-readable JSON.

Design rules (see gsd-gd/references/laws.md):
  * Every invocation is headless or windowed-offscreen - never interactive.
  * Every invocation prints a single `GD<VERB> {json}` line for the caller.
  * Nothing is hardcoded twice: toolchain paths live in gsd-gd/config.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]      # D:/ClaudeGameDev
SYS_DIR = ROOT / "gsd-gd"
CONFIG = SYS_DIR / "config.json"
PLANNING = ROOT / ".planning"


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def die(msg: str, code: int = 2):
    print("gd: error: " + msg, file=sys.stderr)
    raise SystemExit(code)


def cfg() -> dict:
    if not CONFIG.exists():
        die("missing config at " + str(CONFIG))
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def emit(verb: str, payload: dict) -> None:
    """Single-line machine-readable result. Agents parse this, not the log noise."""
    print("GD" + verb.upper() + " " + json.dumps(payload, default=str))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd, cwd=None, timeout=900):
    try:
        return subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        die("timed out after " + str(timeout) + "s: " + str(cmd[0]), 124)


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", s or "")


def locate_project(start=None):
    """Walk up looking for project.godot, then fall back to ./game/*. None if absent."""
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / "project.godot").exists():
            return cand
    for cand in sorted(ROOT.glob("game/*/project.godot")):
        return cand.parent
    return None


def find_project(start=None) -> Path:
    proj = locate_project(start)
    if proj is None:
        die("no Godot project found (looked for project.godot upward from cwd "
            "and under ./game/). Run `gd init <name>`.")
    return proj


def godot_bin() -> str:
    c = cfg()["toolchain"]["godot"]
    exe = c["console"] if Path(c["console"]).exists() else c["editor"]
    if not Path(exe).exists():
        die("Godot binary not found: " + exe)
    return exe


def blender_bin() -> str:
    exe = cfg()["toolchain"]["blender"]["exe"]
    if not Path(exe).exists():
        die("Blender binary not found: " + exe)
    return exe


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
def cmd_doctor(a) -> int:
    c = cfg()
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})

    g = c["toolchain"]["godot"]
    gexe = g["console"] if Path(g["console"]).exists() else g["editor"]
    if Path(gexe).exists():
        r = run([gexe, "--headless", "--version"], timeout=120)
        ver = (r.stdout or r.stderr or "").strip().splitlines()
        check("godot", r.returncode == 0, ver[-1] if ver else "")
        check("godot.console_binary", Path(g["console"]).exists(),
              "stdout capture works only via the .console.exe on Windows")
    else:
        check("godot", False, "not found: " + gexe)

    bexe = c["toolchain"]["blender"]["exe"]
    if Path(bexe).exists():
        r = run([bexe, "--version"], timeout=120)
        first = (r.stdout or "").splitlines()
        check("blender", r.returncode == 0, first[0] if first else "")
        lib = str(SYS_DIR / "lib").replace("\\", "/")
        expr = ("import sys;sys.path.insert(0,'" + lib + "');"
                "import gdblend;print('GDBLEND',gdblend.__version__)")
        r = run([bexe, "-b", "--factory-startup", "--python-expr", expr], timeout=180)
        m = re.search(r"GDBLEND (\S+)", r.stdout or "")
        check("blender.gdblend", bool(m),
              m.group(1) if m else ((r.stdout or "") + (r.stderr or ""))[-300:])
    else:
        check("blender", False, "not found: " + bexe)

    check("git", shutil.which("git") is not None, shutil.which("git") or "")
    check("python", sys.version_info >= (3, 10), sys.version.split()[0])
    checks.append({"check": "planning_dir", "ok": PLANNING.exists(), "detail": str(PLANNING)})
    proj = locate_project()
    checks.append({"check": "godot_project", "ok": proj is not None,
                   "detail": str(proj) if proj else "none yet - run `gd init <name>`"})

    soft = ("planning_dir", "godot_project")
    ok = all(x["ok"] for x in checks if x["check"] not in soft)
    emit("doctor", {"ok": ok, "checks": checks})
    for x in checks:
        mark = "  [ok]   " if x["ok"] else "  [FAIL] "
        print(mark + x["check"] + ("  " + str(x["detail"]) if x["detail"] else ""))
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# init / state / phase
# --------------------------------------------------------------------------- #
def tpl(name: str) -> str:
    p = SYS_DIR / "templates" / name
    if not p.exists():
        die("missing template " + name)
    return p.read_text(encoding="utf-8")


def cmd_init(a) -> int:
    name = a.name
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-")
    proj = ROOT / "game" / slug
    if proj.exists() and not a.force:
        die(str(proj) + " already exists (use --force)")
    for d in ("scenes", "scripts", "assets/models", "assets/textures", "assets/audio",
              "generators", "lab", "addons/gd_harness"):
        (proj / d).mkdir(parents=True, exist_ok=True)

    (proj / "project.godot").write_text(
        tpl("project.godot.tpl").replace("{{NAME}}", name).replace("{{SLUG}}", slug),
        encoding="utf-8")
    (proj / ".gitignore").write_text(".godot/\n.gd_out/\nexport/\n*.tmp\n", encoding="utf-8")

    PLANNING.mkdir(exist_ok=True)
    (PLANNING / "phases").mkdir(exist_ok=True)
    subs = {"{{NAME}}": name, "{{SLUG}}": slug, "{{DATE}}": now(),
            "{{PROJECT_PATH}}": str(proj).replace("\\", "/")}
    for t, dest in (("STATE.md", PLANNING / "STATE.md"),
                    ("CONTEXT.md", PLANNING / "CONTEXT.md"),
                    ("COLOR_BIBLE.md", PLANNING / "COLOR_BIBLE.md"),
                    ("CORE_LOOP.md", PLANNING / "CORE_LOOP.md"),
                    ("BUDGET.md", PLANNING / "BUDGET.md"),
                    ("CREDITS.md", PLANNING / "CREDITS.md")):
        if dest.exists() and not a.force:
            continue
        body = tpl(t)
        for k, v in subs.items():
            body = body.replace(k, v)
        dest.write_text(body, encoding="utf-8")

    # Starting scene: a playable greybox, not an empty project. The Core Loop
    # gets proven in grey before any asset exists.
    for t, dest in (("main.tscn.tpl", proj / "scenes" / "main.tscn"),
                    ("greybox_player.gd.tpl", proj / "scripts" / "greybox_player.gd"),
                    ("minute_one.json.tpl", proj / "lab" / "minute_one.json"),
                    ("example_generator.py.tpl", proj / "generators" / "crate.py")):
        if dest.exists() and not a.force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(tpl(t).replace("{{NAME}}", name).replace("{{SLUG}}", slug),
                        encoding="utf-8")

    installed = install_harness(proj)
    cmd_palette(argparse.Namespace(project=str(proj)))
    emit("init", {"ok": True, "name": name, "slug": slug, "project": str(proj),
                  "planning": str(PLANNING), "harness": installed,
                  "next": "/gd:frame - lock the Color Bible and Core Loop before any code"})
    return 0


def install_harness(proj: Path):
    src = SYS_DIR / "harness" / "godot"
    dst = proj / "addons" / "gd_harness"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in sorted(src.glob("*")):
        if f.is_file():
            shutil.copy2(f, dst / f.name)
            copied.append(f.name)
    return copied


def cmd_harness(a) -> int:
    proj = Path(a.project).resolve() if a.project else find_project()
    files = install_harness(proj)
    emit("harness", {"ok": True, "project": str(proj), "installed": files})
    return 0


def state_path() -> Path:
    p = PLANNING / "STATE.md"
    if not p.exists():
        die("no .planning/STATE.md - run `gd init <name>`")
    return p


def parse_state(text: str) -> dict:
    out = {}
    for m in re.finditer(r"^-\s+([a-z_]+):\s*(.*)$", text, re.M):
        out[m.group(1)] = m.group(2).strip()
    return out


def cmd_state(a) -> int:
    p = state_path()
    text = p.read_text(encoding="utf-8")
    if a.key is None:
        emit("state", {"ok": True, "fields": parse_state(text), "path": str(p)})
        print(text)
        return 0
    if a.value is None:
        emit("state", {"ok": True, "key": a.key, "value": parse_state(text).get(a.key)})
        return 0
    pat = r"^(-\s+" + re.escape(a.key) + r":).*$"
    new, n = re.subn(pat, r"\1 " + a.value, text, count=1, flags=re.M)
    if n == 0:
        new = text.replace("## Now\n", "## Now\n- " + a.key + ": " + a.value + "\n", 1)
    new = re.sub(r"^(-\s+updated:).*$", r"\1 " + now(), new, count=1, flags=re.M)
    p.write_text(new, encoding="utf-8")
    emit("state", {"ok": True, "key": a.key, "value": a.value, "written": True})
    return 0


def cmd_phase(a) -> int:
    phases = PLANNING / "phases"
    phases.mkdir(parents=True, exist_ok=True)
    existing = sorted(d for d in phases.iterdir() if d.is_dir())
    if a.action == "list":
        emit("phase", {"ok": True, "phases": [d.name for d in existing]})
        for d in existing:
            print(" ", d.name)
        return 0
    if a.action == "new":
        if not a.name:
            die("`gd phase new <name>` requires a name")
        n = len(existing) + 1
        slug = re.sub(r"[^a-z0-9_-]+", "-", a.name.lower()).strip("-")
        d = phases / ("%02d-%s" % (n, slug))
        (d / "jobs").mkdir(parents=True, exist_ok=True)
        (d / "verdicts").mkdir(parents=True, exist_ok=True)
        (d / "PLAN.md").write_text(
            tpl("PLAN.md").replace("{{PHASE}}", d.name).replace("{{DATE}}", now()),
            encoding="utf-8")
        emit("phase", {"ok": True, "created": d.name, "dir": str(d),
                       "plan": str(d / "PLAN.md")})
        return 0
    if a.action == "current":
        cur = parse_state(state_path().read_text(encoding="utf-8")).get("phase")
        emit("phase", {"ok": True, "current": cur})
        return 0
    die("unknown phase action " + str(a.action))


# --------------------------------------------------------------------------- #
# blender
# --------------------------------------------------------------------------- #
def cmd_blender(a) -> int:
    script = Path(a.script).resolve()
    if not script.exists():
        die("no such script: " + str(script))
    boot = SYS_DIR / "harness" / "blender" / "bootstrap.py"
    if not boot.exists():
        die("missing blender bootstrap at " + str(boot))
    env = dict(os.environ,
               GD_LIB=str(SYS_DIR / "lib"),
               GD_ROOT=str(ROOT),
               GD_PLANNING=str(PLANNING),
               GD_SCRIPT=str(script))
    cmd = [blender_bin(), "-b", "--factory-startup", "--python", str(boot), "--", str(script)]
    cmd += list(a.args or [])
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        emit("blender", {"ok": False, "script": str(script), "reason": "timeout",
                         "seconds": a.timeout})
        return 124
    out = p.stdout or ""
    metrics = None
    for line in out.splitlines():
        if line.startswith("GDMETRICS "):
            try:
                metrics = json.loads(line[len("GDMETRICS "):])
            except json.JSONDecodeError:
                pass
    tb = "Traceback" in out or "Traceback" in (p.stderr or "")
    # A generator that ran to completion but failed its own contract checks has
    # NOT succeeded. Exit code alone would say otherwise, and a green gate on a
    # broken asset is worse than no gate at all.
    checks_ok = True if metrics is None else bool(metrics.get("ok", False))
    failed_checks = [] if metrics is None else [
        c["name"] for c in metrics.get("checks", []) if not c.get("ok")]
    ok = p.returncode == 0 and not tb and checks_ok
    payload = {"ok": ok, "script": str(script), "exit": p.returncode,
               "seconds": round(time.time() - t0, 2), "metrics": metrics}
    if failed_checks:
        payload["failed_checks"] = failed_checks
    if metrics is None:
        payload["reason"] = "generator printed no GDMETRICS line"
    if not ok:
        payload["stdout_tail"] = out[-2500:]
        payload["stderr_tail"] = (p.stderr or "")[-1500:]
    emit("blender", payload)
    if a.verbose or not ok:
        sys.stdout.write(out[-6000:])
        sys.stderr.write((p.stderr or "")[-4000:])
    return 0 if ok else 1


def cmd_asset(a) -> int:
    """Build a Blender generator, land the GLB in the project, reimport, report metrics."""
    proj = Path(a.project).resolve() if a.project else find_project()
    gen = Path(a.generator)
    if not gen.exists():
        alt = proj / "generators" / a.generator
        if alt.exists():
            gen = alt
        else:
            die("no such generator: " + str(a.generator))
    gen = gen.resolve()
    outdir = Path(a.out).resolve() if a.out else (proj / "assets" / "models")
    outdir.mkdir(parents=True, exist_ok=True)

    ns = argparse.Namespace(script=str(gen),
                            args=["--out", str(outdir)] + list(a.args or []),
                            timeout=a.timeout, verbose=a.verbose)
    if cmd_blender(ns) != 0:
        return 1
    if a.no_import:
        emit("asset", {"ok": True, "generator": str(gen), "outdir": str(outdir),
                       "imported": False})
        return 0
    g = run([godot_bin(), "--headless", "--path", str(proj), "--import"], timeout=1200)
    imported = g.returncode == 0
    payload = {"ok": imported, "generator": str(gen), "outdir": str(outdir),
               "imported": imported, "godot_exit": g.returncode}
    if not imported:
        payload["log_tail"] = strip_ansi(g.stdout)[-1200:]
    emit("asset", payload)
    return 0 if imported else 1


# --------------------------------------------------------------------------- #
# godot
# --------------------------------------------------------------------------- #
def cmd_godot(a) -> int:
    proj = Path(a.project).resolve() if a.project else find_project()
    if a.action == "import":
        r = run([godot_bin(), "--headless", "--path", str(proj), "--import"], timeout=1200)
        emit("godot", {"ok": r.returncode == 0, "action": "import", "project": str(proj),
                       "exit": r.returncode, "log_tail": strip_ansi(r.stdout)[-1500:]})
        return 0 if r.returncode == 0 else 1
    if a.action == "script":
        if not a.target:
            die("`gd godot script <res://file.gd>` requires a target")
        r = run([godot_bin(), "--headless", "--path", str(proj), "--script", a.target],
                timeout=a.timeout)
        out = strip_ansi(r.stdout)
        err = strip_ansi(r.stderr)
        bad = (r.returncode != 0 or "SCRIPT ERROR" in out + err
               or "Parse Error" in out + err)
        emit("godot", {"ok": not bad, "action": "script", "target": a.target,
                       "exit": r.returncode, "stdout": out[-6000:], "stderr_tail": err[-1500:]})
        print(out[-6000:])
        if err.strip():
            print(err[-2000:], file=sys.stderr)
        return 0 if not bad else 1
    die("unknown godot action " + str(a.action))


# --------------------------------------------------------------------------- #
# check  (GDScript correctness gate: engine truth + Godot-3-ism scan)
# --------------------------------------------------------------------------- #
def cmd_check(a) -> int:
    """Two passes, because neither alone is enough.

    1. The engine's own analyser (`--check-only`). Ground truth for types,
       unknown identifiers and signatures - it even suggests the Godot 4 name
       for a Godot 3 class. But its exit code is 0 even on a parse error, and it
       silently accepts some 3.x idioms on untyped receivers.
    2. `gddoc scan`. Catches the 3.x idioms pass 1 lets through, and gives the
       replacement rather than just a complaint.
    """
    proj = Path(a.project).resolve() if a.project else find_project()
    targets = []
    for t in (a.files or []):
        p = Path(t)
        targets.append(p.resolve() if p.exists() else (proj / t).resolve())
    if not targets:
        targets = sorted(p for p in proj.rglob("*.gd") if ".godot" not in p.parts)
    targets = [p for p in targets if p.exists()]
    if not targets:
        die("no .gd files to check")

    results = []
    for p in targets:
        try:
            res = "res://" + str(p.relative_to(proj)).replace("\\", "/")
        except ValueError:
            die(str(p) + " is not inside the Godot project at " + str(proj))
        r = run([godot_bin(), "--headless", "--path", str(proj),
                 "--check-only", "--script", res], timeout=a.timeout)
        out = strip_ansi((r.stdout or "") + (r.stderr or ""))
        engine_errors = [ln.strip() for ln in out.splitlines()
                         if "SCRIPT ERROR" in ln or "Parse Error" in ln]

        g = run([sys.executable, str(SYS_DIR / "bin" / "gddoc.py"), "scan", str(p)],
                timeout=300)
        scan = {"ok": True, "findings": []}
        for ln in (g.stdout or "").splitlines():
            if ln.startswith("GDDOCSCAN "):
                try:
                    scan = json.loads(ln[len("GDDOCSCAN "):])
                except json.JSONDecodeError:
                    pass
        results.append({"file": res, "ok": not engine_errors and scan.get("ok", True),
                        "engine_errors": engine_errors[:12],
                        "godot3_findings": scan.get("findings", [])})

    ok = all(x["ok"] for x in results)
    emit("check", {"ok": ok, "files": len(results),
                   "failed": [x["file"] for x in results if not x["ok"]],
                   "results": results})
    for x in results:
        print(("  [ok]   " if x["ok"] else "  [FAIL] ") + x["file"])
        for e in x["engine_errors"]:
            print("         engine: " + e[:190])
        for f in x["godot3_findings"]:
            print("         line %s [%s] %s -> %s"
                  % (f.get("line"), f.get("kind"), f.get("symbol"), f.get("detail")))
    if not ok:
        print("\n  Look the API up before rewriting:")
        print("    python gsd-gd/bin/gddoc.py member <Class>.<member>")
        print("    python gsd-gd/bin/gddoc.py class <Class>")
        print("    python gsd-gd/bin/gddoc.py search <keyword>")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# playtest  (the "measure" + "look" gate)
# --------------------------------------------------------------------------- #
def cmd_playtest(a) -> int:
    proj = Path(a.project).resolve() if a.project else find_project()
    plan_p = Path(a.plan)
    if not plan_p.exists():
        # Accept `minute_one`, `lab/minute_one.json`, or an absolute path, from
        # anywhere - agents should not have to think about cwd.
        name = a.plan if a.plan.endswith(".json") else a.plan + ".json"
        for alt in (proj / name, proj / "lab" / name, proj / "lab" / Path(name).name):
            if alt.exists():
                plan_p = alt
                break
        else:
            die("no such playtest plan: " + str(a.plan)
                + " (looked in " + str(proj / "lab") + ")")
    plan_p = plan_p.resolve()
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    install_harness(proj)

    stem = plan_p.stem
    outdir = Path(a.out).resolve() if a.out else (proj / ".gd_out" / stem)
    shutil.rmtree(outdir, ignore_errors=True)
    (outdir / "shots").mkdir(parents=True, exist_ok=True)

    inbox = proj / ".gd_out" / "_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

    d = cfg()["defaults"]
    want_shots = bool(plan.get("shots")) and not a.headless
    res = a.resolution or (d["shot_resolution"] if want_shots else d["playtest_resolution"])

    # Hard engine-level backstop. If the harness script itself fails to parse,
    # nothing in GDScript runs and the window would sit open forever - so the
    # engine is told to quit regardless. Generous margin over the plan's own
    # timeout_frames so it never pre-empts a legitimate slow run.
    quit_after = int(plan.get("timeout_frames", 3600)) + 1200

    cmd = [godot_bin(), "--path", str(proj)]
    if a.headless:
        cmd.append("--headless")          # measure only; the dummy renderer cannot screenshot
    cmd += ["--resolution", res,
            "--position", "9000,9000",    # renders for real, stays off the visible desktop
            "--quit-after", str(quit_after),
            "res://addons/gd_harness/gd_playtest.tscn",
            "--",
            "--plan=res://.gd_out/_inbox/plan.json",
            "--out=res://.gd_out/" + stem]

    t0 = time.time()
    r = run(cmd, timeout=a.timeout)
    out = strip_ansi(r.stdout) + "\n" + strip_ansi(r.stderr)

    verdict = None
    for line in out.splitlines():
        if line.startswith("GDVERDICT "):
            try:
                verdict = json.loads(line[len("GDVERDICT "):])
            except json.JSONDecodeError:
                pass
    vfile = outdir / "verdict.json"
    if verdict is None and vfile.exists():
        verdict = json.loads(vfile.read_text(encoding="utf-8"))
    if verdict is None:
        emit("playtest", {"ok": False, "reason": "harness produced no verdict",
                          "exit": r.returncode, "seconds": round(time.time() - t0, 2),
                          "log_tail": out[-4000:]})
        print(out[-4000:])
        return 1

    verdict["plan"] = plan_p.name
    verdict["seconds"] = round(time.time() - t0, 2)
    verdict["shot_files"] = sorted(p.name for p in (outdir / "shots").glob("*.png"))
    verdict["shots_dir"] = str(outdir / "shots")

    b = cfg()["budget"]
    perf = verdict.get("perf") or {}
    fails = []
    if perf.get("fps_avg") is not None and perf["fps_avg"] < b["min_fps"]:
        fails.append("fps_avg %.1f < %s" % (perf["fps_avg"], b["min_fps"]))
    if perf.get("draw_calls_max") is not None and perf["draw_calls_max"] > b["max_draw_calls"]:
        fails.append("draw_calls_max %s > %s" % (perf["draw_calls_max"], b["max_draw_calls"]))
    if perf.get("shadow_lights") is not None and perf["shadow_lights"] > b["max_shadow_casting_lights"]:
        fails.append("shadow_lights %s > %s (see references/godot-patterns.md#shadow-discipline)"
                     % (perf["shadow_lights"], b["max_shadow_casting_lights"]))
    # A run that "passed" while spraying script errors has not passed. The
    # harness cannot see these; the process output can.
    runtime_errors = [ln.strip() for ln in out.splitlines()
                      if "SCRIPT ERROR" in ln or "Parse Error" in ln
                      or "USER ERROR" in ln][:20]
    verdict["runtime_errors"] = runtime_errors
    verdict["budget_fails"] = fails
    verdict["ok"] = bool(verdict.get("passed")) and not fails and not runtime_errors
    vfile.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    emit("playtest", verdict)
    print("")
    print("  plan      " + plan_p.name)
    print("  verdict   " + ("PASS" if verdict["ok"] else "FAIL"))
    for chk in verdict.get("checks", []):
        mark = "ok" if chk.get("ok") else "FAIL"
        print("    [%s] %s  %s" % (mark, chk.get("name"), chk.get("detail", "")))
    for f in fails:
        print("    [FAIL] budget: " + f)
    for e in runtime_errors:
        print("    [FAIL] runtime: " + e[:160])
    if perf:
        print("  perf      " + json.dumps(perf))
    if verdict["shot_files"]:
        print("  shots     %d in %s" % (len(verdict["shot_files"]), verdict["shots_dir"]))
        print("            -> hand these to gd-critic; a builder never grades its own frames")
    return 0 if verdict["ok"] else 1


# --------------------------------------------------------------------------- #
# palette sync  (the Color Bible, enforced on the engine side too)
# --------------------------------------------------------------------------- #
def parse_color_bible(path: Path) -> dict:
    if not path.exists():
        die("no COLOR_BIBLE.md at " + str(path) + " - run /gd:frame first")
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", cells[1])
        if not m or cells[0].lower() == "key":
            continue

        def num(i, d):
            try:
                return float(cells[i])
            except (IndexError, ValueError):
                return d

        entries[cells[0]] = {"hex": m.group(1).lower(), "roughness": num(2, 0.7),
                             "metallic": num(3, 0.0), "emission": num(4, 0.0),
                             "role": cells[5] if len(cells) > 5 else ""}
    if not entries:
        die("COLOR_BIBLE.md has no parsable palette rows")
    return entries


def cmd_palette(a) -> int:
    """Generate res://scripts/palette.gd so GDScript is bound by the same contract
    the Blender generators are. Any colour typed by hand in a .gd file is a bug."""
    proj = Path(a.project).resolve() if a.project else find_project()
    entries = parse_color_bible(PLANNING / "COLOR_BIBLE.md")
    dest = proj / "scripts" / "palette.gd"
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "class_name Palette",
        "## GENERATED by `gd palette` from .planning/COLOR_BIBLE.md. Do not edit.",
        "##",
        "## Use Palette.get_color(\"key\") / Palette.material(\"key\") instead of typing a",
        "## hex anywhere in game code. If a colour you need is not here, the answer is",
        "## a new row in the Color Bible with a reason - not a literal in a script.",
        "",
        "const COLORS := {",
    ]
    for k, e in entries.items():
        lines.append('\t"%s": Color("%s"),' % (k, e["hex"]))
    lines.append("}")
    lines.append("")
    lines.append("const SURFACE := {")
    for k, e in entries.items():
        lines.append('\t"%s": {"roughness": %s, "metallic": %s, "emission": %s},'
                     % (k, e["roughness"], e["metallic"], e["emission"]))
    lines.append("}")
    lines += [
        "",
        "static func get_color(key: String) -> Color:",
        "\tassert(COLORS.has(key), \"'%s' is not in the Color Bible\" % key)",
        "\treturn COLORS.get(key, Color.MAGENTA)  # magenta = you shipped an unpalettable colour",
        "",
        "",
        "static func material(key: String) -> StandardMaterial3D:",
        "\tvar m := StandardMaterial3D.new()",
        "\tm.albedo_color = get_color(key)",
        "\tvar s: Dictionary = SURFACE.get(key, {})",
        "\tm.roughness = s.get(\"roughness\", 0.7)",
        "\tm.metallic = s.get(\"metallic\", 0.0)",
        "\tif float(s.get(\"emission\", 0.0)) > 0.0:",
        "\t\tm.emission_enabled = true",
        "\t\tm.emission = get_color(key)",
        "\t\tm.emission_energy_multiplier = s[\"emission\"]",
        "\treturn m",
        "",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")
    emit("palette", {"ok": True, "keys": list(entries), "count": len(entries),
                     "written": str(dest)})
    return 0


# --------------------------------------------------------------------------- #
# credits ledger
# --------------------------------------------------------------------------- #
def cmd_credits(a) -> int:
    p = PLANNING / "CREDITS.md"
    if not p.exists():
        die("no .planning/CREDITS.md - run `gd init` first")
    row = "| %s | %s | %s | %s | %s |" % (
        a.asset, a.source, a.license, a.url or "-", a.attribution or "-")
    text = p.read_text(encoding="utf-8").rstrip("\n")
    p.write_text(text + "\n" + row + "\n", encoding="utf-8")
    emit("credits", {"ok": True, "added": a.asset, "license": a.license, "file": str(p)})
    return 0


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gd", description="GSD-GameDev toolchain CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="verify the toolchain end to end").set_defaults(fn=cmd_doctor)

    p = sub.add_parser("init", help="scaffold a game project + .planning artifacts")
    p.add_argument("name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("harness", help="(re)install the Godot playtest harness into a project")
    p.add_argument("--project")
    p.set_defaults(fn=cmd_harness)

    p = sub.add_parser("state", help="read/write .planning/STATE.md")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.set_defaults(fn=cmd_state)

    p = sub.add_parser("phase", help="phase directories under .planning/phases/")
    p.add_argument("action", choices=["new", "list", "current"])
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=cmd_phase)

    p = sub.add_parser("blender", help="run a Blender python script headless with gdblend on path")
    p.add_argument("script")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_blender)

    p = sub.add_parser("asset", help="build a generator -> GLB -> project -> reimport")
    p.add_argument("generator")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.add_argument("--project")
    p.add_argument("--out")
    p.add_argument("--no-import", action="store_true")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_asset)

    p = sub.add_parser("godot", help="headless Godot operations")
    p.add_argument("action", choices=["import", "script"])
    p.add_argument("target", nargs="?")
    p.add_argument("--project")
    p.add_argument("--timeout", type=int, default=900)
    p.set_defaults(fn=cmd_godot)

    p = sub.add_parser("check", help="GDScript gate: engine type-check + Godot-3-ism scan")
    p.add_argument("files", nargs="*", help="paths or res:// -relative; default = every .gd")
    p.add_argument("--project")
    p.add_argument("--timeout", type=int, default=300)
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("playtest", help="run a scripted playtest: measure + look + perf")
    p.add_argument("plan")
    p.add_argument("--project")
    p.add_argument("--out")
    p.add_argument("--resolution")
    p.add_argument("--headless", action="store_true", help="measure only; no screenshots")
    p.add_argument("--timeout", type=int, default=600)
    p.set_defaults(fn=cmd_playtest)

    p = sub.add_parser("palette", help="generate res://scripts/palette.gd from the Color Bible")
    p.add_argument("--project")
    p.set_defaults(fn=cmd_palette)

    p = sub.add_parser("credits", help="append to the license ledger")
    p.add_argument("asset")
    p.add_argument("source")
    p.add_argument("license")
    p.add_argument("--url")
    p.add_argument("--attribution")
    p.set_defaults(fn=cmd_credits)

    a = ap.parse_args(argv)
    extra = getattr(a, "args", None)
    if extra and extra[0] == "--":
        a.args = extra[1:]
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())

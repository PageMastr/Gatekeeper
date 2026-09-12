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
import uuid
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# Two different roots, and conflating them is the bug that makes a global
# install share one game's contracts across every project on the machine.
#
#   SYS_DIR - where gsd-gd is installed. Read-only at runtime except for cache/:
#             config, templates, lib, harness. Found from this file's location,
#             so the system works wherever it is installed.
#   WORK    - the user's game workspace. Owns .planning/ and game/. Found from
#             the cwd, so one install can drive many separate games.
SYS_DIR = Path(__file__).resolve().parents[1]   # .../gsd-gd
CONFIG = SYS_DIR / "config.json"


def _true_case(p: Path) -> Path:
    """The path as the filesystem actually spells it.

    Windows is case-insensitive, so `cd d:\\testgame` yields a cwd of
    `D:\\testgame` even though the directory is `TestGame` - and that miscased
    string then gets written into STATE.md and echoed everywhere. Resolve each
    component against its real parent listing.
    """
    try:
        p = p.resolve()
        if os.name != "nt":
            return p
        parts = list(p.parts)
        out = Path(parts[0])
        for seg in parts[1:]:
            match = next((c.name for c in out.iterdir()
                          if c.name.lower() == seg.lower()), None)
            out = out / (match or seg)
        return out
    except OSError:
        return p


def _find_work_root() -> Path:
    """Resolve the workspace: explicit override, then an existing project, then
    a repo root, then the cwd."""
    env = os.environ.get("GD_PROJECT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return _true_case(p)
    here = Path.cwd().resolve()
    for cand in [here, *here.parents]:
        if (cand / ".planning").is_dir():
            return _true_case(cand)
    for cand in [here, *here.parents]:
        if (cand / ".git").exists():
            return _true_case(cand)
    return _true_case(here)


WORK = _find_work_root()
PLANNING = WORK / ".planning"


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #
def die(msg: str, code: int = 2):
    print("gd: error: " + msg, file=sys.stderr)
    raise SystemExit(code)


PROJECT_CONFIG_NAME = "config.json"


def _deep_merge(base: dict, over: dict) -> dict:
    """Recursive override. Scalars and lists replace; dicts merge key by key."""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def project_config_path() -> Path:
    return PLANNING / PROJECT_CONFIG_NAME


def cfg() -> dict:
    """Effective config: machine defaults, overridden per project.

    `gsd-gd/config.json` lives in the install root and is shared by every game
    on this machine, so everything in it can only ever be a *default*. A project
    overrides any of it in `.planning/config.json`, which is deep-merged on top
    and lives under the project's own version control.

    This exists because the alternative leaked: shared machine-global state with
    no per-project override meant one game's numbers were every game's numbers,
    and one game's lighting presets ended up in three others.

    `toolchain` is the deliberate exception in spirit - it describes the machine,
    not the game - but it is still overridable, because a project pinned to a
    different engine build is a real case.
    """
    if not CONFIG.exists():
        die("missing config at " + str(CONFIG))
    base = json.loads(CONFIG.read_text(encoding="utf-8"))
    p = project_config_path()
    if p.exists():
        try:
            return _deep_merge(base, json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            die("%s is not valid JSON: %s" % (p, e))
    return base


def config_provenance() -> dict:
    """Which keys the project overrode, for `gd config` and verdict stamps."""
    p = project_config_path()
    if not p.exists():
        return {}
    try:
        over = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    def flat(d, prefix=""):
        out = {}
        for k, v in d.items():
            if k.startswith("_"):
                continue
            key = prefix + k
            if isinstance(v, dict):
                out.update(flat(v, key + "."))
            else:
                out[key] = v
        return out
    return flat(over)


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
    for cand in sorted(WORK.glob("game/*/project.godot")):
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
    if proj:
        dr = harness_drift(proj)
        if dr["status"] == "current":
            check("harness", True, "canonical=%s" % dr["canonical"])
        elif dr["status"] == "stale":
            check("harness", True,
                  "stale (on an older canonical; `gd harness` to update)")
        else:
            check("harness", False,
                  "local edits to the grader: %s - run `gd harness --check`"
                  % ", ".join(dr["modified"] + dr["missing"]))

    soft = ("planning_dir", "godot_project")
    ok = all(x["ok"] for x in checks if x["check"] not in soft)
    emit("doctor", {"ok": ok, "checks": checks,
                    "system_dir": str(SYS_DIR), "work_root": str(WORK),
                    "work_root_from": ("GD_PROJECT" if os.environ.get("GD_PROJECT")
                                       else ".planning found" if PLANNING.is_dir()
                                       else "git root / cwd")})
    print("  system  " + str(SYS_DIR))
    print("  work    " + str(WORK))
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
    proj = WORK / "game" / slug
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
                    ("ROADMAP.md", PLANNING / "ROADMAP.md"),
                    ("SYSTEM_FINDINGS.md", PLANNING / "SYSTEM_FINDINGS.md"),
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

    # Every project gets its own overridable config from the start, so the
    # per-project path is the obvious one rather than something to discover
    # after a machine-global value has already leaked into another game.
    if not project_config_path().exists() or a.force:
        cmd_config(argparse.Namespace(init=True, force=True))

    cmd_version(argparse.Namespace(record=True))
    installed = install_harness(proj)["copied"]
    cmd_palette(argparse.Namespace(project=str(proj)))
    emit("init", {"ok": True, "name": name, "slug": slug, "project": str(proj),
                  "planning": str(PLANNING), "harness": installed,
                  "next": "/gd:frame - lock the Color Bible and Core Loop before any code"})
    return 0


_TSCN_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\",
                 "'": "'", "0": "\0", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def unescape_tscn_string(raw: str) -> str:
    """Decode a Godot .tscn quoted string, in ONE left-to-right pass.

    A `.tscn` stores an embedded script on a single line, so:
        \\n   -> a real newline in the source
        \\\\n  -> the two characters \\ and n, i.e. an escape inside a GDScript
                 string literal, which must survive intact
        \\"   -> a quote

    Chained `str.replace()` cannot do this: it either misses `\\n` entirely
    (leaving the whole script on one line, so GDScript hits a stray backslash
    and reports `Expected new line after "\\"`) or it rewrites the output of a
    previous pass. A single scan is the only correct way - each backslash
    consumes exactly one following character and is never re-examined.
    """
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt == "u" and i + 5 < n:
                try:
                    out.append(chr(int(raw[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            # An unknown escape is left exactly as written rather than guessed at.
            out.append(_TSCN_ESCAPES.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def embedded_scripts(path: Path):
    """GDScript embedded in a .tscn/.tres as `[sub_resource type="GDScript"]`.

    A scene whose driver is a built-in script had no way to be analysed at all:
    `gd check` only ever globbed `*.gd`, so a 50-line embedded script was
    invisible to the gate and its type errors surfaced 150 seconds later as a
    runtime failure. One project worked around it by writing the source to a
    temp file, checking that, and pasting it back.

    Yields (sub_resource_id, source_text).
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for m in re.finditer(
            r'\[sub_resource type="GDScript"[^\]]*id="([^"]+)"\]\s*'
            r'script/source\s*=\s*"(.*?)"\s*(?=\n\[|\Z)',
            text, re.S):
        sid, raw = m.group(1), m.group(2)
        if raw.strip():
            yield sid, unescape_tscn_string(raw)


def ensure_class_cache(proj: Path) -> dict:
    """Reimport when Godot's global class cache is missing or stale.

    The cache is what makes one file's `class_name` visible to another. Two ways
    it lies, and both produce failures on correct code:

      missing - a never-imported project: every cross-file `class_name` reads as
                "Identifier not declared".
      stale   - a `class_name` in a file newer than the cache is absent from it,
                so "Could not find type X" on a type that exists.

    The stale case is not rare: `install_harness()` rewrites the harness scripts
    on every `gd playtest`, which by itself makes the cache stale and would make
    `GDLightingRig` unresolvable for the rest of the run. Observed exactly that.
    """
    cache = proj / ".godot" / "global_script_class_cache.cfg"
    stale = False
    if cache.exists():
        mtime = cache.stat().st_mtime
        stale = any(p.stat().st_mtime > mtime
                    for p in proj.rglob("*.gd") if ".godot" not in p.parts)
    if not cache.exists() or stale:
        run([godot_bin(), "--headless", "--path", str(proj), "--import"], timeout=1200)
        return {"reimported": True, "was_stale": stale, "was_missing": not cache.exists()}
    return {"reimported": False, "was_stale": False, "was_missing": False}


SYSTEM_PARTS = {
    "cli": ["bin/gd.py", "bin/gddoc.py"],
    "harness": ["harness/godot", "harness/blender"],
    "lib": ["lib/gdblend"],
    "templates": ["templates"],
    "references": ["references"],
    "config": ["config.json"],
}


def system_fingerprint() -> dict:
    """Content hash of the installed system, by component.

    `harness_hash` covers the grader and `.installed_hash` covers staleness, but
    nothing fingerprinted `gd.py`, the templates or the references - so a phase
    had no way to notice the toolchain changing underneath it. That is not
    hypothetical: three builds were mid-flight when this install was hot-patched,
    and the only trace was an incidental recopy inside an unrelated commit.

    A verdict is a claim about a moment. It should be able to name the toolchain
    that produced it.
    """
    import hashlib

    def digest(paths):
        h = hashlib.sha256()
        files = []
        for rel in paths:
            p = SYS_DIR / rel
            if p.is_dir():
                files += [f for f in sorted(p.rglob("*"))
                          if f.is_file() and f.suffix in (".py", ".gd", ".tscn",
                                                          ".md", ".json", ".tpl")
                          and "__pycache__" not in f.parts]
            elif p.is_file():
                files.append(p)
        for f in files:
            h.update(str(f.relative_to(SYS_DIR)).replace("\\", "/").encode())
            h.update(f.read_bytes())
        return h.hexdigest()[:12], len(files)

    parts, total = {}, hashlib.sha256()
    for name, paths in SYSTEM_PARTS.items():
        d, n = digest(paths)
        parts[name] = {"hash": d, "files": n}
        total.update((name + d).encode())
    declared = "unknown"
    try:
        declared = json.loads(CONFIG.read_text(encoding="utf-8")).get("version", "unknown")
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": declared, "hash": total.hexdigest()[:12],
            "parts": parts, "root": str(SYS_DIR)}


def cmd_version(a) -> int:
    fp = system_fingerprint()
    recorded = None
    stamp = PLANNING / ".system"
    if stamp.exists():
        try:
            recorded = json.loads(stamp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    changed = []
    if recorded:
        for name, cur in fp["parts"].items():
            was = (recorded.get("parts") or {}).get(name, {}).get("hash")
            if was and was != cur["hash"]:
                changed.append(name)
    if a.record:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(json.dumps(fp, indent=2), encoding="utf-8")
        emit("version", {"ok": True, "action": "record", **fp})
        print("  recorded %s (%s) to %s" % (fp["hash"], fp["version"], stamp))
        return 0
    emit("version", {"ok": not changed, **fp,
                     "recorded": (recorded or {}).get("hash"),
                     "changed_since_recorded": changed})
    print("  system    %s   (declared %s)" % (fp["hash"], fp["version"]))
    for name in sorted(fp["parts"]):
        p = fp["parts"][name]
        mark = " !" if name in changed else "  "
        print("  %s%-11s %s  %d file(s)" % (mark, name, p["hash"], p["files"]))
    if recorded:
        if changed:
            print("")
            print("  CHANGED since this project recorded %s: %s"
                  % (recorded.get("hash"), ", ".join(changed)))
            print("  Verdicts taken before the change were produced by a different")
            print("  toolchain. `gd version --record` once you have accounted for it.")
        else:
            print("  matches what this project recorded")
    else:
        print("  (this project has recorded no system version - `gd version --record`)")
    # Informative by default. A drifted baseline is normal - every project on a
    # machine goes stale the moment the system is improved - and a check that is
    # red on every healthy board is a check people learn to ignore. Gate on it
    # only when asked: `gd version --check`.
    return 1 if (changed and a.check) else 0


def harness_hash(d: Path) -> str:
    """Fingerprint of a harness directory - which grader is in play."""
    import hashlib
    h = hashlib.sha256()
    for f in sorted((d).glob("*")):
        if f.is_file() and f.suffix in (".gd", ".tscn"):
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


def harness_drift(proj: Path) -> dict:
    """Compare a project's harness against the installed canonical one.

    This exists because of an observed incident: one game's agent edited the
    *shared* harness under the install root, and because `install_harness()`
    recopies on every playtest, its game-specific lighting presets propagated
    into three other games - two of them referencing a palette swatch those
    games do not define. Nothing recorded it, because the install root is not
    under version control.

    A harness is the instrument that grades the work. Drift in it must be
    visible, not silent.
    """
    src = SYS_DIR / "harness" / "godot"
    dst = proj / "addons" / "gd_harness"
    out = {"canonical": harness_hash(src), "project": None, "installed": None,
           "status": "absent", "modified": [], "missing": [], "extra": []}
    if not dst.is_dir():
        return out
    out["project"] = harness_hash(dst)
    stamp = dst / ".installed_hash"
    out["installed"] = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else None
    if out["project"] == out["canonical"]:
        out["status"] = "current"
    elif out["installed"] and out["project"] == out["installed"]:
        # Untouched since install; canonical has simply moved ahead.
        out["status"] = "stale"
    elif out["installed"] is None:
        out["status"] = "unknown"        # installed before hashes were stamped
    else:
        out["status"] = "edited"         # the Law 6b case
    for f in sorted(src.glob("*")):
        if not f.is_file():
            continue
        p = dst / f.name
        if not p.exists():
            out["missing"].append(f.name)
        elif p.read_bytes() != f.read_bytes():
            out["modified"].append(f.name)
    names = {f.name for f in src.glob("*") if f.is_file()}
    out["extra"] = sorted(p.name for p in dst.glob("*")
                          if p.is_file() and p.name not in names
                          and not p.name.endswith(".uid")
                          and p.name != ".installed_hash")
    return out


def install_harness(proj: Path, force: bool = False):
    """Copy the canonical harness into a project.

    Never silently overwrites a locally modified harness file - a local edit is
    either a fix worth upstreaming or a builder tampering with its own grader,
    and both deserve to be seen. Modified files are backed up alongside and
    named in the return value.
    """
    src = SYS_DIR / "harness" / "godot"
    dst = proj / "addons" / "gd_harness"
    dst.mkdir(parents=True, exist_ok=True)
    copied, preserved = [], []
    for f in sorted(src.glob("*")):
        if not f.is_file():
            continue
        target = dst / f.name
        if target.exists() and target.read_bytes() != f.read_bytes():
            if not force:
                backup = dst / (f.name + ".local")
                shutil.copy2(target, backup)
                preserved.append(f.name)
        shutil.copy2(f, target)
        copied.append(f.name)
    h = harness_hash(src)
    # Stamp what was installed. Without it, "the project edited the grader" and
    # "the canonical moved on and this project has not caught up" look
    # identical - and only one of them is a Law 6b concern.
    (dst / ".installed_hash").write_text(h, encoding="utf-8")
    return {"copied": copied, "overwrote_local_edits": preserved, "hash": h}


def cmd_harness(a) -> int:
    proj = Path(a.project).resolve() if a.project else find_project()
    drift = harness_drift(proj)
    if a.check:
        # Only a genuine local edit is a failure. A project sitting on an older
        # canonical is stale, not tampered - and saying "a local edit to the
        # instrument that grades this project" about it is both wrong and
        # alarming.
        ok = drift["status"] in ("current", "stale") and not drift["missing"]
        emit("harness", {"ok": ok, "action": "check", "project": str(proj), **drift})
        print("  canonical %s" % drift["canonical"])
        print("  project   %s" % (drift["project"] or "(not installed)"))
        print("  status    " + drift["status"])
        if drift["status"] == "stale":
            print("  This project is on an older canonical harness. Nothing was "
                  "edited here;")
            print("  run `gd harness` to bring it up to date.")
            for f in drift["modified"]:
                print("    behind: " + f)
        elif drift["status"] in ("edited", "unknown"):
            for f in drift["modified"]:
                print("  [DRIFT] %s differs from canonical - a local edit to the "
                      "instrument that grades this project" % f)
        for f in drift["missing"]:
            print("  [MISSING] " + f)
        if ok and drift["project"]:
            print("  harness matches canonical")
        if drift["status"] in ("edited", "unknown") and drift["modified"]:
            print("")
            print("  If the edit is a real improvement, upstream it to")
            print("  %s and reinstall - do not leave it local." % (SYS_DIR / "harness" / "godot"))
        return 0 if ok else 1
    res = install_harness(proj, force=a.force)
    emit("harness", {"ok": True, "project": str(proj), **res})
    for f in res["overwrote_local_edits"]:
        print("  [warn] %s had local edits; backed up as %s.local" % (f, f))
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


def write_state(key: str, value: str, touch_only: bool = False) -> bool:
    """Set one STATE.md field and refresh `updated`.

    Shared so that every verb which changes the project's real state can stamp
    it. Observed fault: contract edits left `updated` fifteen minutes stale, and
    STATE is the first thing a resumed session trusts.
    """
    p = PLANNING / "STATE.md"
    if not p.exists():
        return False
    text = p.read_text(encoding="utf-8")
    if not touch_only:
        pat = r"^(-\s+" + re.escape(key) + r":).*$"
        text, n = re.subn(pat, r"\1 " + value, text, count=1, flags=re.M)
        if n == 0:
            text = text.replace("## Now\n", "## Now\n- " + key + ": " + value + "\n", 1)
    text = re.sub(r"^(-\s+updated:).*$", r"\1 " + now(), text, count=1, flags=re.M)
    p.write_text(text, encoding="utf-8")
    return True


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
    write_state(a.key, a.value)
    emit("state", {"ok": True, "key": a.key, "value": a.value, "written": True})
    return 0


def cmd_now(a) -> int:
    """The clock, for anything an agent would otherwise type from memory.

    Observed fault: a Color Bible change log stamped sixteen rows
    `18:40:00Z` in a file whose real mtime was `18:09:49`. An agent will invent
    a plausible timestamp every time; this makes reading the real one cheaper
    than guessing.
    """
    emit("now", {"ok": True, "utc": now(),
                 "local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                 "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")})
    print(now())
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
        # Creating a phase and not making it current was a separate call the
        # agent had to remember, and STATE ended up claiming `phase: none` while
        # the directory sat there. There is no case where you create a phase and
        # do not want it current.
        made_current = write_state("phase", d.name)
        emit("phase", {"ok": True, "created": d.name, "dir": str(d),
                       "plan": str(d / "PLAN.md"), "set_current": made_current})
        return 0
    if a.action == "current":
        cur = parse_state(state_path().read_text(encoding="utf-8")).get("phase")
        emit("phase", {"ok": True, "current": cur})
        return 0
    die("unknown phase action " + str(a.action))


# --------------------------------------------------------------------------- #
# run  (the phase driver's bookkeeping brain)
# --------------------------------------------------------------------------- #
# Model routing lives in config.json (`models`), not here - it is a tuning
# decision, and burying it in code means it gets changed in two places.
# These are only the fallbacks if the config block is missing entirely.
_FALLBACK_LADDER = ["haiku", "sonnet", "opus", "fable"]
_FALLBACK_ATTEMPTS = 3


def models_cfg() -> dict:
    return cfg().get("models") or {}


def model_ladder() -> list:
    return models_cfg().get("ladder") or _FALLBACK_LADDER


def attempts_per_tier() -> int:
    return int(models_cfg().get("attempts_per_tier") or _FALLBACK_ATTEMPTS)


def agent_model(agent: str) -> str:
    """Starting model for an agent. Accepts either {"model": x, "why": ...} or a
    bare string in config, so the file stays easy to hand-edit."""
    entry = (models_cfg().get("agents") or {}).get(agent)
    if isinstance(entry, dict):
        m = entry.get("model")
    elif isinstance(entry, str):
        m = entry
    else:
        m = None
    if not m:
        # Unknown agent: start one tier below the top rather than guessing high.
        ladder = model_ladder()
        m = ladder[max(len(ladder) - 2, 0)]
    return m


# --------------------------------------------------------------------------- #
# roadmap  (the whole game, as stages that stack)
# --------------------------------------------------------------------------- #
PLACEHOLDER_RE = re.compile(r"[<>]|^-$|^$|^TBD$|^\.\.\.$", re.I)


def _unfilled(cell: str) -> bool:
    """True if a table cell is still template boilerplate."""
    c = (cell or "").strip()
    return bool(re.search(r"[<>]", c)) or c in ("", "-", "TBD", "...", "…")


def parse_roadmap(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    stages = []
    for row in _rows(text, "#"):
        sid = (row.get("#") or "").strip()
        if not re.fullmatch(r"\d+", sid):
            continue
        stages.append({
            "id": "%02d" % int(sid),
            "stage": row.get("stage", ""),
            "playable": row.get("playable at the end", ""),
            "depends": [d.strip() for d in re.split(r"[,\s]+", row.get("depends on", ""))
                        if d.strip() and d.strip() != "-"],
            "gate": row.get("gate", ""),
            "status": (row.get("status") or "planned").strip().lower(),
        })
    coverage = [{"element": r.get("element", ""), "stage": (r.get("delivered by stage") or "").strip()}
                for r in _rows(text, "element")]
    placeholders = [{"placeholder": r.get("placeholder", ""),
                     "stands_for": r.get("stands in for", ""),
                     "stage": (r.get("replaced by stage") or "").strip()}
                    for r in _rows(text, "placeholder")]
    doors = [{"door": r.get("door", ""), "stage": (r.get("taken in stage") or "").strip(),
              "decided": r.get("decided", "")} for r in _rows(text, "door")]
    m = re.search(r"^-\s+end state:\s*(.+)$", text, re.M)
    cur = re.search(r"^-\s+current stage:\s*(.+)$", text, re.M)
    return {"stages": stages, "coverage": coverage, "placeholders": placeholders,
            "doors": doors, "end_state": (m.group(1).strip() if m else ""),
            "current": (cur.group(1).strip() if cur else "")}


def core_loop_beats() -> list:
    """Filled beat rows from CORE_LOOP.md's loop table."""
    p = PLANNING / "CORE_LOOP.md"
    if not p.exists():
        return []
    out = []
    for row in _rows(p.read_text(encoding="utf-8"), "beat"):
        b = (row.get("beat") or "").strip()
        action = (row.get("player action") or "").strip()
        if re.fullmatch(r"\d+", b) and action and not _unfilled(action):
            out.append(b)
    return out


def cmd_roadmap(a) -> int:
    path = PLANNING / "ROADMAP.md"
    if not path.exists():
        die("no .planning/ROADMAP.md - run /gd:new")
    rm = parse_roadmap(path)
    ids = [s["id"] for s in rm["stages"]]

    if a.action == "done":
        if not a.stage:
            die("`gd roadmap done <stage id>`")
        sid = "%02d" % int(a.stage) if str(a.stage).isdigit() else str(a.stage)
        if sid not in ids:
            die("no stage " + sid + " in ROADMAP.md")
        text = path.read_text(encoding="utf-8")
        # Rewrite that stage's status cell, and advance `current stage`.
        def fix(mo):
            cells = mo.group(0).strip().strip("|").split("|")
            if cells[0].strip().lstrip("0") == sid.lstrip("0"):
                cells[-1] = " done "
                return "|" + "|".join(cells) + "|"
            return mo.group(0)
        text = re.sub(r"^\|.*\|$", fix, text, flags=re.M)
        nxt = next((i for i in ids if i > sid), sid)
        text = re.sub(r"^(-\s+current stage:).*$", r"\1 " + nxt, text, count=1, flags=re.M)
        path.write_text(text, encoding="utf-8")
        emit("roadmap", {"ok": True, "action": "done", "stage": sid, "current": nxt})
        return 0

    # ---- validate -------------------------------------------------------- #
    errors, warnings = [], []
    if not rm["stages"]:
        errors.append("no stage rows - the Stages table is still empty")
    if _unfilled(rm["end_state"]):
        errors.append("`end state` is not filled in - the roadmap has no destination")

    seen = set()
    for i, s in enumerate(rm["stages"]):
        tag = "stage " + s["id"]
        if s["id"] in seen:
            errors.append(tag + ": duplicate id")
        seen.add(s["id"])
        # One error per stage, not one per field - a stage that is wholly
        # unfilled would otherwise produce three lines and bury everything else.
        unfilled = [("playable at the end" if f == "playable" else f)
                    for f in ("stage", "playable", "gate") if _unfilled(s[f])]
        if unfilled:
            errors.append("%s: still a placeholder (%s)" % (tag, ", ".join(unfilled)))
        if s["status"] not in ("planned", "active", "done"):
            warnings.append(tag + ": unknown status '" + s["status"] + "'")
        for d in s["depends"]:
            dd = "%02d" % int(d) if d.isdigit() else d
            if dd not in ids:
                errors.append(tag + ": depends on '" + d + "', which is not a stage")
            elif dd >= s["id"]:
                errors.append(tag + ": depends on '" + dd + "', which is not an earlier stage "
                              "- stages must stack forward")

    # Coverage: every Core Loop beat, and no dangling stage references.
    beats = core_loop_beats()
    cov_text = " ".join(c["element"].lower() for c in rm["coverage"])
    for b in beats:
        if not re.search(r"beat\s*" + re.escape(b) + r"\b", cov_text):
            errors.append("coverage: Core Loop beat %s has no row - that beat of the "
                          "loop is not assigned to any stage" % b)
    for c in rm["coverage"]:
        if _unfilled(c["element"]):
            continue
        if _unfilled(c["stage"]):
            errors.append("coverage: '%s' names no stage - a hole in the plan"
                          % c["element"][:60])
        else:
            sid = "%02d" % int(c["stage"]) if c["stage"].isdigit() else c["stage"]
            if sid not in ids:
                errors.append("coverage: '%s' points at stage '%s', which does not exist"
                              % (c["element"][:40], c["stage"]))
    if not beats:
        warnings.append("CORE_LOOP.md has no filled beat rows yet, so coverage of the "
                        "loop cannot be checked")

    # Placeholder ledger: everything fake must have a stage that makes it real.
    for ph in rm["placeholders"]:
        if _unfilled(ph["placeholder"]):
            continue
        if _unfilled(ph["stage"]):
            errors.append("placeholder '%s' names no replacing stage - it will ship"
                          % ph["placeholder"][:40])
        else:
            sid = "%02d" % int(ph["stage"]) if ph["stage"].isdigit() else ph["stage"]
            if sid not in ids:
                errors.append("placeholder '%s' points at stage '%s', which does not exist"
                              % (ph["placeholder"][:40], ph["stage"]))

    for d in rm["doors"]:
        if _unfilled(d["door"]):
            continue
        if _unfilled(d["stage"]):
            warnings.append("one-way door '%s' is not assigned to a stage" % d["door"][:50])

    done = [s for s in rm["stages"] if s["status"] == "done"]
    ok = not errors
    emit("roadmap", {"ok": ok, "action": "validate", "stages": len(rm["stages"]),
                     "done": len(done), "current": rm["current"],
                     "coverage_rows": len([c for c in rm["coverage"] if not _unfilled(c["element"])]),
                     "core_loop_beats": beats,
                     "placeholders_open": len([p for p in rm["placeholders"]
                                               if not _unfilled(p["placeholder"])]),
                     "errors": errors, "warnings": warnings})

    print("  end state   " + (rm["end_state"][:100] or "(not set)"))
    print("  progress    %d / %d stages done, current %s"
          % (len(done), len(rm["stages"]), rm["current"] or "?"))
    for s in rm["stages"]:
        mark = {"done": "x", "active": ">", "planned": " "}.get(s["status"], "?")
        print("  [%s] %s %-24s %s" % (mark, s["id"], s["stage"][:24], s["playable"][:60]))
    if a.action == "status":
        return 0
    for w in warnings[:6]:
        print("  [warn] " + w)
    for e in errors[:14]:
        print("  [FAIL] " + e)
    if len(errors) > 14:
        print("  ... and %d more (the full list is in the GDROADMAP json line)"
              % (len(errors) - 14))
    if ok:
        print("\n  roadmap valid: every stage stacks forward, the loop is fully covered, "
              "and every placeholder has a stage that replaces it.")
    else:
        print("\n  Fix ROADMAP.md (see gsd-gd/references/decomposition.md), then re-run.")
    return 0 if ok else 1


def cmd_config(a) -> int:
    """The effective config, and which keys this project overrode."""
    eff = cfg()
    prov = config_provenance()
    p = project_config_path()
    if a.init:
        if p.exists() and not a.force:
            die(str(p) + " already exists (use --force)")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "_doc": ("Per-project overrides, deep-merged over gsd-gd/config.json. "
                     "Set ONLY what differs from the machine default - anything "
                     "absent here inherits. This file is the reason one game's "
                     "numbers are not every game's numbers."),
            "budget": {},
            "defaults": {},
            "models": {"agents": {}},
        }, indent=2), encoding="utf-8")
        emit("config", {"ok": True, "action": "init", "path": str(p)})
        print("  wrote " + str(p))
        return 0
    emit("config", {"ok": True, "machine": str(CONFIG),
                    "project": str(p) if p.exists() else None,
                    "overrides": prov, "effective": eff})
    print("  machine  " + str(CONFIG))
    print("  project  " + (str(p) if p.exists() else "(none - `gd config --init` to add one)"))
    if prov:
        print("")
        print("  overridden by this project:")
        for k, v in sorted(prov.items()):
            print("    %-44s %s" % (k, v))
    else:
        print("")
        print("  this project overrides nothing; every value is the machine default")
    b = project_budget()
    print("")
    print("  budget in force (%s):" % b["source"])
    for k in sorted(b["budget"]):
        mark = " *" if k in b["overrides"] else "  "
        v = b["budget"][k]
        print("   %s %-30s %s" % (mark, k, v if not isinstance(v, dict) else json.dumps(v)))
    return 0


def cmd_models(a) -> int:
    """Show the routing table, and flag drift.

    Two places name a model: `models.agents` in config.json (what `gd run`
    dispatches and escalates with) and the `model:` frontmatter of each
    .claude/agents/*.md (what Claude Code uses when an agent is spawned by name
    with no override). They must agree, and nothing would otherwise tell you
    when they stop agreeing.
    """
    # Frontmatter in .claude/agents/*.md is machine-global, so it can only be
    # compared against the MACHINE config. A project override is not drift - it
    # is the feature - so the two are reported separately.
    machine = json.loads(CONFIG.read_text(encoding="utf-8")).get("models") or {}
    mc = models_cfg()
    agents_cfg = machine.get("agents") or {}
    proj_over = {k.split(".", 2)[2]: v for k, v in config_provenance().items()
                 if k.startswith("models.agents.")}
    rows, drift = [], []
    # Agent files may be project-scoped or installed at user scope; check both.
    agent_dirs = [WORK / ".claude" / "agents",
                  Path.home() / ".claude" / "agents"]
    agent_dir = next((d for d in agent_dirs if d.is_dir()), agent_dirs[0])
    for name in sorted(set(agents_cfg) | {p.stem for p in agent_dir.glob("gd-*.md")}):
        entry_m = agents_cfg.get(name)
        want = (entry_m.get("model") if isinstance(entry_m, dict)
                else entry_m if isinstance(entry_m, str) else None)
        entry = agents_cfg.get(name)
        why = entry.get("why", "") if isinstance(entry, dict) else ""
        fm = None
        f = agent_dir / (name + ".md")
        if f.exists():
            m = re.search(r"^model:\s*(\S+)\s*$", f.read_text(encoding="utf-8"), re.M)
            fm = m.group(1) if m else None
        eff = agent_model(name) if name in (mc.get("agents") or {}) else want
        rows.append({"agent": name, "machine": want, "effective": eff,
                     "frontmatter": fm, "why": why, "defined": f.exists(),
                     "overridden": eff != want})
        if want and fm and want != fm:
            drift.append("%s: config=%s frontmatter=%s" % (name, want, fm))
        if want and not f.exists():
            drift.append("%s: in config but no .claude/agents/%s.md" % (name, name))
        if fm and not want:
            drift.append("%s: agent file exists but no config entry" % name)

    emit("models", {"ok": not drift, "ladder": model_ladder(),
                    "attempts_per_tier": attempts_per_tier(),
                    "agents": rows, "drift": drift,
                    "project_overrides": proj_over})
    print("  ladder   " + " -> ".join(model_ladder())
          + "   (%d attempts per tier before escalating)" % attempts_per_tier())
    print("")
    for r in rows:
        mark = " " if (not r["machine"] or r["machine"] == r["frontmatter"]) else "!"
        model = r["effective"] or "-"
        if r["overridden"]:
            model += "*"
        print("%s %-18s %-8s %s" % (mark, r["agent"], model, r["why"][:94]))
    if proj_over:
        print("")
        print("  * = overridden by this project (.planning/config.json)")
    if drift:
        print("\n  DRIFT - config and agent frontmatter disagree:")
        for d in drift:
            print("    " + d)
        print("  Fix the frontmatter to match config.json; config is the source of truth.")
    return 0 if not drift else 1


def phase_dir(name=None) -> Path:
    phases = PLANNING / "phases"
    if name:
        d = phases / name
        if not d.is_dir():
            matches = sorted(p for p in phases.glob(name + "*") if p.is_dir()) if phases.is_dir() else []
            if not matches:
                die("no such phase: " + name)
            d = matches[0]
        return d
    cur = parse_state(state_path().read_text(encoding="utf-8")).get("phase")
    if cur and cur not in ("none", ""):
        d = phases / cur
        if d.is_dir():
            return d
    dirs = sorted(p for p in phases.iterdir() if p.is_dir()) if phases.is_dir() else []
    if not dirs:
        die("no phases yet - run /gd:plan")
    return dirs[-1]


def _rows(text: str, header_key: str):
    """Rows of the markdown table whose header's first cell is header_key, as
    dicts keyed by column name.

    Keyed by name, not index, because these tables are written by hand (or by an
    agent) and columns get reordered or left out. An index-based parser silently
    reads the wave number as the model name, which is a very confusing bug to
    chase from the other end.
    """
    out, cols = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            cols = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cols is None:
            if cells and cells[0].lower() == header_key:
                cols = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= {"-", ":", " "}:
            continue
        out.append({cols[i]: cells[i].strip() for i in range(min(len(cols), len(cells)))})
    return out


def parse_plan(plan: Path) -> dict:
    text = plan.read_text(encoding="utf-8")
    jobs = {}
    for row in _rows(text, "#"):
        jid = row.get("#", "")
        if not re.fullmatch(r"\d+", jid):
            continue
        agent = row.get("agent") or "gd-mechanics"
        model = row.get("model") or agent_model(agent)
        wave = row.get("wave", "")
        jobs["%02d" % int(jid)] = {
            "title": row.get("job", ""), "agent": agent,
            "wave": int(wave) if wave.isdigit() else 1,
            "touches": row.get("touches", ""), "gate": row.get("gate", ""),
            "status": "pending", "model": model, "start_model": model,
            "attempts_at_tier": 0, "total_attempts": 0, "history": [],
        }
    checkpoints = []
    for row in _rows(text, "after job"):
        aj = row.get("after job", "")
        if aj:
            checkpoints.append({"after_job": "%02d" % int(aj) if aj.isdigit() else aj,
                                "decision": row.get("decision", ""),
                                "resolved": False})
    gates = [m.group(1).strip() for m in re.finditer(r"^-\s+gate:\s*(.+)$", text, re.M)]
    return {"jobs": jobs, "checkpoints": checkpoints, "phase_gate": gates}


def archive_verdict(d: Path, jid: str, attempt: int, src=None):
    """Copy the verdict that graded an attempt into <phase>/verdicts/.

    `gd phase new` has always created that directory and nothing ever wrote to
    it. Meanwhile `.gd_out/<plan>/verdict.json` is overwritten by the next run,
    so a per-attempt history existed nowhere - exactly what the ship retro
    wants. Given an explicit --verdict path, use it; otherwise take the most
    recently modified verdict.json under the project."""
    dest_dir = d / "verdicts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    cand = None
    if src:
        p = Path(src)
        cand = p if p.exists() else None
    if cand is None:
        proj = locate_project()
        if proj:
            found = sorted(proj.glob(".gd_out/*/verdict.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            cand = found[0] if found else None
    if cand is None:
        return None
    dest = dest_dir / ("%s-attempt%02d.json" % (jid, attempt))
    try:
        shutil.copy2(cand, dest)
    except OSError:
        return None
    return str(dest)


def run_file(d: Path) -> Path:
    return d / "RUN.json"


def load_run(d: Path) -> dict:
    f = run_file(d)
    if not f.exists():
        die("no RUN.json in " + d.name + " - run `gd run init` first")
    return json.loads(f.read_text(encoding="utf-8"))


def save_run(d: Path, r: dict) -> None:
    r["updated"] = now()
    run_file(d).write_text(json.dumps(r, indent=2), encoding="utf-8")


def cmd_run(a) -> int:
    d = phase_dir(a.phase)
    act = a.action

    if act == "init":
        plan = d / "PLAN.md"
        if not plan.exists():
            die("no PLAN.md in " + str(d))
        parsed = parse_plan(plan)
        if not parsed["jobs"]:
            die("PLAN.md has no job rows - the Jobs table is still the template")
        # Refuse a plan that is still partly boilerplate. Left alone, a
        # placeholder gate fails much later with a baffling shell error, and an
        # untitled job gets dispatched to an agent with no objective.
        problems = []
        for jid, j in sorted(parsed["jobs"].items()):
            if not j["title"]:
                problems.append("job %s has no title" % jid)
            if not j["gate"]:
                problems.append("job %s has no gate - a job without a gate is a wish" % jid)
            elif re.search(r"[<>]", j["gate"]):
                problems.append("job %s gate is still a placeholder: %s" % (jid, j["gate"]))
        if not parsed["phase_gate"]:
            problems.append("PLAN.md has no `- gate:` lines - the phase has no "
                            "machine-readable definition of done")
        for g in parsed["phase_gate"]:
            if re.search(r"[<>]", g):
                problems.append("phase gate is still a placeholder: " + g)
        if problems and not a.force:
            emit("run", {"ok": False, "action": "init", "phase": d.name,
                         "reason": "PLAN.md is incomplete", "problems": problems})
            for pb in problems:
                print("  [FAIL] " + pb)
            print("\n  Finish PLAN.md (see /gd:plan), then run this again.")
            return 1
        if run_file(d).exists() and not a.force:
            die("RUN.json already exists (use --force to restart the phase)")
        _sf = system_fingerprint()
        r = {"phase": d.name, "created": now(), "updated": now(),
             "status": "running", "stop_reason": None,
             "system": {"version": _sf["version"], "hash": _sf["hash"]},
             "model_ladder": model_ladder(), "attempts_per_tier": attempts_per_tier(),
             "waves_completed": [], "gate_runs": [], **parsed}
        save_run(d, r)
        emit("run", {"ok": True, "action": "init", "phase": d.name,
                     "jobs": len(r["jobs"]), "waves": sorted({j["wave"] for j in r["jobs"].values()}),
                     "checkpoints": len(r["checkpoints"]), "phase_gate": r["phase_gate"]})
        return 0

    r = load_run(d)

    if act == "next":
        payload = run_next(r)
        emit("run", {"ok": True, "action": "next", "phase": d.name, **payload})
        print("  " + payload["action"] + ": " + payload.get("why", ""))
        for j in payload.get("jobs", []):
            print("    job %s  %s  model=%s  gate=%s" % (j["id"], j["agent"], j["model"], j["gate"]))
        return 0

    if act == "start":
        # Without this, a job being worked right now is indistinguishable from
        # one nobody has touched - both read `pending / 0 attempts`. That breaks
        # observability and, worse, makes a crashed half-done job resume
        # identically to a fresh one.
        if not a.job:
            die("`gd run start <job>`")
        jid = "%02d" % int(a.job) if str(a.job).isdigit() else str(a.job)
        if jid not in r["jobs"]:
            die("no job " + jid + " in " + d.name)
        j = r["jobs"][jid]
        j["status"] = "running"
        j["started_at"] = now()
        save_run(d, r)
        emit("run", {"ok": True, "action": "start", "job": jid,
                     "model": j["model"], "attempt": j["total_attempts"] + 1,
                     "started_at": j["started_at"]})
        return 0

    if act == "record":
        if not a.job or a.result not in ("pass", "fail"):
            die("`gd run record <job> pass|fail [--note ...]`")
        jid = "%02d" % int(a.job) if str(a.job).isdigit() else str(a.job)
        if jid not in r["jobs"]:
            die("no job " + jid + " in " + d.name)
        j = r["jobs"][jid]
        # Archive the verdict that graded this attempt. `.gd_out/<plan>/` only
        # ever holds the last run, so without this the per-attempt history the
        # /gd:ship retro asks for does not exist anywhere.
        archived = archive_verdict(d, jid, j["total_attempts"] + 1, a.verdict)
        j["total_attempts"] += 1
        j["attempts_at_tier"] += 1
        j["history"].append({"at": now(), "model": j["model"],
                             "result": a.result, "note": (a.note or "")[:500]})
        escalated = None
        if a.result == "pass":
            j["status"] = "passed"
        else:
            # Escalation ladder from config: N attempts at the current tier,
            # then climb. At the top tier, a full tier of failures stops the run -
            # the problem is the job or the gate, not the model.
            ladder = model_ladder()
            per_tier = attempts_per_tier()
            if j["attempts_at_tier"] >= per_tier:
                cur = j["model"] if j["model"] in ladder else ladder[-2]
                i = ladder.index(cur)
                if i < len(ladder) - 1:
                    j["model"] = ladder[i + 1]
                    j["attempts_at_tier"] = 0
                    j["status"] = "pending"
                    escalated = j["model"]
                else:
                    j["status"] = "blocked"
                    r["status"] = "blocked"
                    r["stop_reason"] = ("job %s failed %d times at the top of the model "
                                        "ladder (%s) - the job or its gate is wrong, not the model"
                                        % (jid, j["total_attempts"], cur))
            else:
                j["status"] = "pending"
        save_run(d, r)
        write_state("last_verdict", "%s job %s %s (%s)"
                    % (d.name, jid, a.result, j["model"]))
        emit("run", {"ok": True, "action": "record", "job": jid, "result": a.result,
                     "status": j["status"], "model": j["model"], "escalated_to": escalated,
                     "verdict_archived": archived,
                     "attempts_at_tier": j["attempts_at_tier"],
                     "total_attempts": j["total_attempts"],
                     "run_status": r["status"], "stop_reason": r["stop_reason"]})
        if escalated:
            print("  job %s: %d failures at that tier -> escalated to %s"
                  % (jid, attempts_per_tier(), escalated))
        elif j["status"] == "blocked":
            print("  job %s: BLOCKED. %s" % (jid, r["stop_reason"]))
        return 0

    if act == "gate":
        gates = r.get("phase_gate") or []
        if not gates:
            die("PLAN.md defines no `- gate:` lines - the phase has no definition of done")
        results = []
        for cmd_s in gates:
            p = subprocess.run(cmd_s, shell=True, cwd=str(WORK), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=a.timeout)
            tail = strip_ansi((p.stdout or "") + (p.stderr or ""))[-600:]
            results.append({"cmd": cmd_s, "ok": p.returncode == 0,
                            "exit": p.returncode, "tail": tail})
        ok = all(x["ok"] for x in results)
        r["gate_runs"].append({"at": now(), "ok": ok,
                               "failed": [x["cmd"] for x in results if not x["ok"]]})
        if ok:
            r["status"] = "gate_green"
        save_run(d, r)
        # STATE is what a fresh session trusts, and it was being left behind:
        # one phase passed all five of its gates and STATE still read
        # `last_verdict: none` an hour later. Nothing wrote that field - only
        # two command docs mentioned it, and the driver is not either of them.
        summary = "%s %d/%d gates green" % (d.name, sum(1 for x in results if x["ok"]),
                                            len(results))
        if not ok:
            summary += " - failed: " + ", ".join(
                Path(x["cmd"].split()[-1]).name for x in results if not x["ok"])
        write_state("last_verdict", summary)
        write_state("phase_gate", "green" if ok else "red")
        emit("run", {"ok": ok, "action": "gate", "phase": d.name, "results": results})
        for x in results:
            print(("  [ok]   " if x["ok"] else "  [FAIL] ") + x["cmd"])
            if not x["ok"]:
                print("         " + x["tail"].replace("\n", "\n         ")[:900])
        return 0 if ok else 1

    if act == "resolve":
        if not a.job:
            die("`gd run resolve <after_job>` - the job the checkpoint follows")
        jid = "%02d" % int(a.job) if str(a.job).isdigit() else str(a.job)
        hit = [c for c in r["checkpoints"] if c["after_job"] == jid]
        if not hit:
            die("no checkpoint after job " + jid)
        for c in hit:
            c["resolved"] = True
            c["resolved_at"] = now()
            c["resolution"] = a.note or ""
        if r["status"] == "blocked" and "checkpoint" in (r.get("stop_reason") or ""):
            r["status"] = "running"
            r["stop_reason"] = None
        save_run(d, r)
        emit("run", {"ok": True, "action": "resolve", "after_job": jid,
                     "resolution": a.note or "", "run_status": r["status"]})
        return 0

    if act == "block":
        r["status"] = "blocked"
        r["stop_reason"] = a.note or "blocked by operator"
        save_run(d, r)
        emit("run", {"ok": True, "action": "block", "stop_reason": r["stop_reason"]})
        return 0

    if act == "complete":
        r["status"] = "complete"
        save_run(d, r)
        emit("run", {"ok": True, "action": "complete", "phase": d.name})
        return 0

    cur_sys = system_fingerprint()["hash"]
    armed_sys = (r.get("system") or {}).get("hash")
    sys_changed = bool(armed_sys) and armed_sys != cur_sys

    if act == "status":
        by_status = {}
        for jid, j in sorted(r["jobs"].items()):
            by_status.setdefault(j["status"], []).append(jid)
        emit("run", {"ok": True, "action": "status", "phase": d.name,
                     "run_status": r["status"], "stop_reason": r.get("stop_reason"),
                     "system_armed": armed_sys, "system_now": cur_sys,
                     "system_changed_mid_phase": sys_changed,
                     "by_status": by_status,
                     "phase_gate": r.get("phase_gate"),
                     "last_gate": (r.get("gate_runs") or [None])[-1]})
        print("  phase   %s   [%s]" % (d.name, r["status"]))
        if sys_changed:
            print("  SYSTEM  changed mid-phase: armed on %s, now %s" % (armed_sys, cur_sys))
            print("          Jobs graded before the change used a different toolchain."
                  " `gd version` for what moved.")
        if r.get("stop_reason"):
            print("  stop    " + r["stop_reason"])
        for jid, j in sorted(r["jobs"].items()):
            print("  job %s  %-9s wave %s  %-14s %s  (%d attempts)"
                  % (jid, j["status"], j["wave"], j["agent"], j["model"], j["total_attempts"]))
        for c in r["checkpoints"]:
            print("  ckpt    after %s  %s  %s"
                  % (c["after_job"], "resolved" if c["resolved"] else "OPEN", c["decision"]))
        return 0

    die("unknown run action " + str(act))


def run_next(r: dict) -> dict:
    """The state machine. Returns the one thing the driver should do next."""
    if r["status"] == "complete":
        return {"action": "stop", "why": "phase already complete"}
    if r["status"] == "blocked":
        return {"action": "stop", "why": r.get("stop_reason") or "blocked"}

    jobs = r["jobs"]
    waves = sorted({j["wave"] for j in jobs.values()})

    for w in waves:
        in_wave = {k: v for k, v in jobs.items() if v["wave"] == w}
        unfinished = {k: v for k, v in in_wave.items() if v["status"] != "passed"}
        if any(v["status"] == "blocked" for v in in_wave.values()):
            return {"action": "stop",
                    "why": "job(s) blocked in wave %d: %s"
                           % (w, ", ".join(k for k, v in in_wave.items() if v["status"] == "blocked"))}
        inflight = {k: v for k, v in in_wave.items() if v["status"] == "running"}
        if inflight and len(inflight) == len(unfinished):
            return {"action": "in_flight", "wave": w,
                    "why": "wave %d job(s) already dispatched and not yet recorded: %s"
                           % (w, ", ".join(sorted(inflight))),
                    "jobs": [{"id": k, "agent": v["agent"], "model": v["model"],
                              "started_at": v.get("started_at")}
                             for k, v in sorted(inflight.items())]}
        if unfinished:
            return {
                "action": "dispatch",
                "wave": w,
                "why": "wave %d has %d job(s) to run" % (w, len(unfinished)),
                "jobs": [{"id": k, "agent": v["agent"], "model": v["model"],
                          "gate": v["gate"], "title": v["title"], "touches": v["touches"],
                          "attempt": v["total_attempts"] + 1,
                          "attempts_at_tier": v["attempts_at_tier"]}
                         for k, v in sorted(unfinished.items())
                         if v["status"] != "running"],
                "in_flight": sorted(inflight),
            }
        # Wave complete - an unresolved checkpoint inside it halts before the next.
        open_ck = [c for c in r["checkpoints"]
                   if not c["resolved"] and c["after_job"] in in_wave]
        if open_ck:
            return {"action": "checkpoint", "wave": w, "checkpoints": open_ck,
                    "why": "one-way door after job %s: %s"
                           % (open_ck[0]["after_job"], open_ck[0]["decision"])}

    return {"action": "phase_gate", "why": "all jobs passed - run the phase gate",
            "phase_gate": r.get("phase_gate", [])}


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
               GD_ROOT=str(WORK),
               GD_PLANNING=str(PLANNING),
               GD_SCRIPT=str(script),
               # The effective config, so a generator's snap grid and triangle
               # budgets come from THIS project rather than from whatever the
               # machine default happens to be.
               GD_CONFIG_JSON=json.dumps(cfg()))
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

    write_project_gd(proj)
    cache_state = ensure_class_cache(proj)
    imported_first = cache_state["reimported"]
    stale = cache_state["was_stale"]
    autoloads = project_autoloads(proj)

    # Scene-embedded scripts: extract to a temp .gd inside the project so res://
    # resolves, check it, then remove. Reported under `<scene>::<sub_resource id>`.
    embedded = []
    if not a.files:
        for scene in sorted(list(proj.rglob("*.tscn")) + list(proj.rglob("*.tres"))):
            if ".godot" in scene.parts:
                continue
            for sid, src in embedded_scripts(scene):
                embedded.append((scene, sid, src))
    tmp_dir = proj / "scripts" / "_gd_embedded_check"
    tmp_written = []
    if embedded:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        for scene, sid, src in embedded:
            f = tmp_dir / (re.sub(r"[^A-Za-z0-9_]", "_", scene.stem + "_" + sid) + ".gd")
            f.write_text(src, encoding="utf-8")
            tmp_written.append((f, scene, sid))
        targets = list(targets) + [f for f, _, _ in tmp_written]
        ensure_class_cache(proj)

    label_for = {f: "%s::%s" % ("res://" + str(sc.relative_to(proj)).replace("\\", "/"), sid)
                 for f, sc, sid in tmp_written}

    results = []
    for p in targets:
        try:
            res = "res://" + str(p.relative_to(proj)).replace("\\", "/")
        except ValueError:
            die(str(p) + " is not inside the Godot project at " + str(proj))
        r = run([godot_bin(), "--headless", "--path", str(proj),
                 "--check-only", "--script", res], timeout=a.timeout)
        out = strip_ansi((r.stdout or "") + (r.stderr or ""))
        raw_errors = [ln.strip() for ln in out.splitlines()
                      if "SCRIPT ERROR" in ln or "Parse Error" in ln]
        # `--check-only --script` returns from Main::start() BEFORE autoload
        # globals are registered, so a reference to an autoload singleton fails
        # as "Identifier not found" on code that is perfectly correct at
        # runtime. That is a false failure, and one project had already bent its
        # architecture into a static-accessor workaround to satisfy it.
        # The global *class* cache IS loaded in this mode, so real unknown types
        # are still caught - only declared autoload names are forgiven.
        engine_errors, autoload_notes = [], []
        for ln in raw_errors:
            m = re.search(r'Identifier (?:"([^"]+)" not declared|not found: ([A-Za-z_][A-Za-z0-9_]*))', ln)
            name = (m.group(1) or m.group(2)) if m else None
            if name and name in autoloads:
                autoload_notes.append(name)
            else:
                engine_errors.append(ln)

        g = run([sys.executable, str(SYS_DIR / "bin" / "gddoc.py"), "scan", str(p)],
                timeout=300)
        scan = {"ok": True, "findings": []}
        for ln in (g.stdout or "").splitlines():
            if ln.startswith("GDDOCSCAN "):
                try:
                    scan = json.loads(ln[len("GDDOCSCAN "):])
                except json.JSONDecodeError:
                    pass
        results.append({"file": label_for.get(p, res),
                        "embedded": p in label_for,
                        "ok": not engine_errors and scan.get("ok", True),
                        "engine_errors": engine_errors[:12],
                        "autoloads_forgiven": sorted(set(autoload_notes)),
                        "godot3_findings": scan.get("findings", [])})

    # Remove the whole temp tree: Godot writes a .uid beside each script it
    # imports, so unlinking only the .gd files leaves the directory behind.
    if tmp_written and tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    ok = all(x["ok"] for x in results)
    emit("check", {"ok": ok, "files": len(results),
                   "embedded_scripts": len(tmp_written),
                   "imported_first": imported_first, "cache_was_stale": stale,
                   "autoloads": autoloads,
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
def project_budget() -> dict:
    """Budget for THIS game.

    One source of truth: `.planning/config.json` overrides the machine defaults
    in `gsd-gd/config.json`, deep-merged by cfg(). `BUDGET.md` justifies the
    numbers in prose and holds the cost model; it does not carry them, because
    two places holding the same value means the wrong one eventually wins - and
    it did, silently, on the first try.
    """
    b = dict(cfg().get("budget") or {})          # already project-merged
    over = {k.split(".", 1)[1]: v for k, v in config_provenance().items()
            if k.startswith("budget.")}
    return {"budget": b, "overrides": over,
            "source": str(project_config_path()) if over else str(CONFIG)}


PLAN_CHECK_KINDS = {"moved", "still", "node_exists", "prop_between", "prop_gt",
                    "prop_lt", "prop_eq", "expr"}


def project_autoloads(proj: Path) -> list:
    """Autoload singleton names declared in project.godot."""
    f = proj / "project.godot"
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8", errors="replace")
    if "[autoload]" not in text:
        return []
    body = text.split("[autoload]", 1)[1]
    body = re.split(r"^\[", body, maxsplit=1, flags=re.M)[0]
    return sorted(set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", body, re.M)))


def project_actions(proj: Path) -> list:
    """Input actions declared in project.godot."""
    f = proj / "project.godot"
    if not f.exists():
        return []
    text = f.read_text(encoding="utf-8", errors="replace")
    body = text.split("[input]", 1)[1] if "[input]" in text else ""
    body = re.split(r"^\[", body, maxsplit=1, flags=re.M)[0]
    return sorted(set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=\{", body, re.M)))


def lint_plan(plan: dict, proj: Path) -> dict:
    """Validate a playtest plan without running it.

    The gap this closes: a plan's only feedback used to be a full run, so a
    typo'd action name or a check with no `kind` cost a whole Godot launch to
    discover - and one game's planner resorted to an improvised python
    one-liner as a gate because no verb existed for this."""
    errors, warnings = [], []
    scene = str(plan.get("scene", ""))
    if not scene:
        errors.append("no `scene`")
    elif not scene.startswith("res://"):
        errors.append("`scene` must be a res:// path, got " + scene)
    else:
        rel = scene[len("res://"):]
        if not (proj / rel).exists():
            errors.append("scene does not exist: " + scene)

    have = project_actions(proj)
    for i, step in enumerate(plan.get("steps", []), 1):
        if not isinstance(step, dict):
            errors.append("step %d is not an object" % i)
            continue
        for act in step.get("actions", []):
            if act not in have:
                errors.append("step %d presses '%s', which is not in the InputMap. "
                              "Available: %s" % (i, act, ", ".join(have) or "(none)"))
        if not any(k in step for k in ("actions", "wait", "frames", "seconds",
                                       "shot", "shot_after")):
            warnings.append("step %d does nothing" % i)

    probes = plan.get("probes", {})
    for c in plan.get("checks", []):
        if not isinstance(c, dict):
            errors.append("a check is not an object")
            continue
        kind = c.get("kind", "expr")
        name = c.get("name", kind)
        if kind not in PLAN_CHECK_KINDS:
            errors.append("check '%s' has unknown kind '%s'. Valid: %s"
                          % (name, kind, ", ".join(sorted(PLAN_CHECK_KINDS))))
        if kind in ("moved", "still") and c.get("probe") not in probes:
            errors.append("check '%s' references probe '%s', which is not declared"
                          % (name, c.get("probe")))
        if kind == "moved" and not c.get("via") and not c.get("distance_only"):
            # An error, not a warning. As a warning this was observed being
            # emitted and ignored, which is how a check named
            # "walked_the_spine" passed at 41 m in a scene with no spine.
            # Distance-only is still allowed - it just has to be stated.
            errors.append("check '%s' asserts distance only - any open floor "
                          "satisfies it. Add `via` with the nodes that must be "
                          "traversed, or set \"distance_only\": true to say you "
                          "mean it." % name)
        if kind in ("prop_between", "prop_gt", "prop_lt", "prop_eq") and not c.get("path"):
            errors.append("check '%s' has no `path`" % name)
        if kind == "expr" and not str(c.get("expr", "")).strip():
            errors.append("check '%s' has an empty `expr`" % name)
    if not plan.get("checks"):
        warnings.append("plan has no checks - it can only prove the harness boots")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "actions_available": have}


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

    if a.lint:
        res = lint_plan(plan, proj)
        emit("playtest", {"ok": res["ok"], "action": "lint", "plan": plan_p.name, **res})
        for w in res["warnings"]:
            print("  [warn] " + w)
        for e in res["errors"]:
            print("  [FAIL] " + e)
        if res["ok"] and not res["warnings"]:
            print("  plan ok: " + plan_p.name)
        return 0 if res["ok"] else 1

    drift_before = harness_drift(proj)
    harness_info = install_harness(proj)
    # install_harness() just rewrote the harness scripts, which makes Godot's
    # global class cache stale - leave it and the run sprays
    # `Could not find type "GDLightingRig"` and fails on runtime_errors.
    cache_state = ensure_class_cache(proj)

    stem = plan_p.stem
    outdir = Path(a.out).resolve() if a.out else (proj / ".gd_out" / stem)
    shutil.rmtree(outdir, ignore_errors=True)
    (outdir / "shots").mkdir(parents=True, exist_ok=True)

    # A UNIQUE inbox per run. The single shared `_inbox/plan.json` made
    # concurrent playtests silently swap plans: two overlapping runs in one
    # parallel wave produced a green PASS reported under the *other* plan's
    # name. A false green is the worst failure this system can produce, and
    # `/gd:run` dispatches parallel waves by design.
    run_id = "%d-%s" % (os.getpid(), uuid.uuid4().hex[:8])
    inbox = proj / ".gd_out" / "_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    plan_rel = "_inbox/%s-%s.json" % (stem, run_id)
    (proj / ".gd_out" / plan_rel).write_text(json.dumps(plan), encoding="utf-8")
    # Clear stale inbox files from previous runs, but never one in flight.
    for old in inbox.glob("*.json"):
        try:
            if old.name != Path(plan_rel).name and time.time() - old.stat().st_mtime > 3600:
                old.unlink()
        except OSError:
            pass

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
            "--plan=res://.gd_out/" + plan_rel,
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

    # Cross-validate identity. Previously `verdict["plan"]` was simply stamped
    # from our own argument, so a swapped plan was undetectable - it is how a
    # green PASS ended up filed under the wrong plan name.
    mismatch = []
    want_name = str(plan.get("name", stem))
    got_name = str(verdict.get("name", ""))
    if got_name and got_name != want_name:
        mismatch.append("verdict name %r != plan name %r" % (got_name, want_name))
    want_checks = {str(c.get("name", c.get("kind", "")))
                   for c in plan.get("checks", []) if isinstance(c, dict)}
    got_checks = {str(c.get("name", "")) for c in verdict.get("checks", [])}
    # Harness-generated checks (input_action:*, shot:*, timeout, harness) are not
    # in the plan, so only unexplained *plan-shaped* names are a mismatch.
    unexplained = {c for c in got_checks - want_checks
                   if c and not re.match(r"^(input_action:|shot:|timeout$|harness$)", c)}
    if want_checks and unexplained:
        mismatch.append("verdict contains checks not in this plan: %s"
                        % ", ".join(sorted(unexplained)[:6]))
    if mismatch:
        emit("playtest", {"ok": False, "reason": "verdict does not match the plan that was run",
                          "plan": plan_p.name, "mismatch": mismatch,
                          "hint": "another playtest was probably in flight; re-run this one alone"})
        for m in mismatch:
            print("  [FAIL] " + m)
        print("  Refusing to report this verdict. Re-run serially.")
        return 1

    verdict["plan"] = plan_p.name
    verdict["plan_name"] = want_name
    verdict["run_id"] = run_id
    verdict["seconds"] = round(time.time() - t0, 2)
    # Which grader graded this. A verdict is only as trustworthy as the harness
    # that produced it, and that harness turned out to be mutable.
    verdict["harness_hash"] = harness_info["hash"]
    _fp = system_fingerprint()
    verdict["system"] = {"version": _fp["version"], "hash": _fp["hash"]}
    if cache_state["reimported"]:
        verdict["class_cache_reimported"] = cache_state
    if drift_before["modified"]:
        verdict["harness_was_modified"] = drift_before["modified"]
    verdict["shot_files"] = sorted(p.name for p in (outdir / "shots").glob("*.png"))
    verdict["shots_dir"] = str(outdir / "shots")

    bres = project_budget()
    b = bres["budget"]
    verdict["budget_source"] = bres["source"]
    if bres["overrides"]:
        verdict["budget_overrides"] = bres["overrides"]
    perf = verdict.get("perf") or {}
    fails = []
    if perf.get("fps_avg") is not None and perf["fps_avg"] < b["min_fps"]:
        fails.append("fps_avg %.1f < %s" % (perf["fps_avg"], b["min_fps"]))
    if perf.get("draw_calls_max") is not None and perf["draw_calls_max"] > b["max_draw_calls"]:
        fails.append("draw_calls_max %s > %s" % (perf["draw_calls_max"], b["max_draw_calls"]))
    if perf.get("shadow_lights") is not None and perf["shadow_lights"] > b["max_shadow_casting_lights"]:
        fails.append("shadow_lights %s > %s (see references/godot-patterns.md#shadow-discipline)"
                     % (perf["shadow_lights"], b["max_shadow_casting_lights"]))
    if a.smoke:
        # Kickoff needs to prove the harness runs, not that the game exists yet.
        # Grading content checks as failures there leaves a verdict.json that is
        # indistinguishable from a real regression and poisons `last_verdict`.
        pending = [c for c in verdict.get("checks", []) if not c.get("ok")]
        for c in pending:
            c["ok"] = None
            c["pending"] = True
        verdict["smoke"] = True
        verdict["pending_checks"] = len(pending)
        booted = bool(verdict.get("frames_run")) and not verdict.get("errors")
        shots = sorted(p.name for p in (outdir / "shots").glob("*.png"))
        verdict["passed"] = booted and (bool(shots) or a.headless)
        verdict["smoke_reason"] = ("harness booted, scene loaded, %d shot(s); "
                                   "%d content check(s) recorded as pending"
                                   % (len(shots), len(pending)))

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


def write_project_gd(proj: Path) -> Path:
    """Generate res://scripts/gd_project.gd from the effective config.

    The engine side needs the project's numbers, not the machine's. Without
    this, `GDLightingRig.shadow_budget` defaulted to the shared 4 while
    `gd playtest` failed the verdict at the project's 1 - the runtime enforcing
    one number and the gate enforcing another.

    Same pattern as the generated `Palette`: the project's contract, compiled
    into something GDScript can read.
    """
    b = project_budget()["budget"]
    dest = proj / "scripts" / "gd_project.gd"
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "class_name GDProject",
        "## GENERATED by `gd palette` / `gd playtest` from the effective config",
        "## (gsd-gd/config.json overridden by .planning/config.json). Do not edit.",
        "##",
        "## These are THIS project's numbers. Read them instead of hardcoding a",
        "## budget in game code - a literal here is a number that disagrees with",
        "## the gate.",
        "",
        "const BUDGET := {",
    ]
    for k in sorted(b):
        v = b[k]
        if isinstance(v, dict):
            inner = ", ".join('"%s": %s' % (ik, b[k][ik]) for ik in sorted(v))
            lines.append('	"%s": {%s},' % (k, inner))
        else:
            lines.append('	"%s": %s,' % (k, v))
    lines += ["}", "",
              "static func budget(key: String, fallback: Variant = 0) -> Variant:",
              "	return BUDGET.get(key, fallback)", ""]
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


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
    proj_gd = write_project_gd(proj)
    write_state("palette_synced", now())
    emit("palette", {"ok": True, "keys": list(entries), "count": len(entries),
                     "written": str(dest), "project_gd": str(proj_gd)})
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

    p = sub.add_parser("harness", help="(re)install the harness, or --check it for drift")
    p.add_argument("--project")
    p.add_argument("--check", action="store_true",
                   help="report drift between the project harness and canonical; do not write")
    p.add_argument("--force", action="store_true",
                   help="overwrite local harness edits without backing them up")
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

    p = sub.add_parser("roadmap", help="validate / show the stage roadmap")
    p.add_argument("action", nargs="?", default="validate",
                   choices=["validate", "status", "done"])
    p.add_argument("stage", nargs="?", help="stage id, for `done`")
    p.set_defaults(fn=cmd_roadmap)

    p = sub.add_parser("version", help="fingerprint of the installed system; --record to pin it")
    p.add_argument("--record", action="store_true",
                   help="record the current fingerprint as this project's baseline")
    p.add_argument("--check", action="store_true",
                   help="exit non-zero if the install has moved since this project recorded it")
    p.set_defaults(fn=cmd_version)

    p = sub.add_parser("config", help="effective config, and this project's overrides")
    p.add_argument("--init", action="store_true", help="create .planning/config.json")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_config)

    sub.add_parser("now", help="current UTC timestamp - never type one from memory"
                   ).set_defaults(fn=cmd_now)

    sub.add_parser("models", help="show model routing, and flag config/frontmatter drift"
                   ).set_defaults(fn=cmd_models)

    p = sub.add_parser("run", help="phase driver state machine (used by /gd:run)")
    p.add_argument("action", choices=["init", "next", "start", "record", "gate",
                                      "resolve", "block", "complete", "status"])
    p.add_argument("job", nargs="?", help="job id, for record/resolve")
    p.add_argument("result", nargs="?", choices=["pass", "fail"], help="for record")
    p.add_argument("--phase", help="phase dir name; default = STATE.md's current")
    p.add_argument("--note")
    p.add_argument("--verdict", help="verdict.json that graded this attempt; archived into <phase>/verdicts/")
    p.add_argument("--force", action="store_true")
    p.add_argument("--timeout", type=int, default=1800)
    p.set_defaults(fn=cmd_run)

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
    p.add_argument("--lint", action="store_true",
                   help="validate the plan without running it: schema, input actions, check kinds")
    p.add_argument("--smoke", action="store_true",
                   help="kickoff mode: gate on the harness booting; record content checks as pending")
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

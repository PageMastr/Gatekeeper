#!/usr/bin/env python3
"""gd - the Gatekeeper toolchain CLI.

One command surface over Godot and Blender so that every agent drives the
toolchain the same way, and every result comes back as machine-readable JSON.

Design rules (see gatekeeper/references/laws.md):
  * Every invocation is headless or windowed-offscreen - never interactive.
  * Every invocation prints a single `GD<VERB> {json}` line for the caller.
  * Nothing is hardcoded twice: toolchain paths live in gatekeeper/config.json.
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
#   SYS_DIR - where gatekeeper is installed. Read-only at runtime except for cache/:
#             config, templates, lib, harness. Found from this file's location,
#             so the system works wherever it is installed.
#   WORK    - the user's game workspace. Owns .planning/ and game/. Found from
#             the cwd, so one install can drive many separate games.
SYS_DIR = Path(__file__).resolve().parents[1]   # .../gatekeeper
CONFIG = SYS_DIR / "config.json"


def claude_home() -> Path:
    """Where Claude Code keeps user-scope configuration."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


# The machine's toolchain, written once by `gd setup` and never shipped.
#
# This deliberately lives OUTSIDE the installed payload. `install.py` copies
# `gatekeeper/` wholesale on every upgrade, so anything the wizard wrote into
# `gatekeeper/config.json` would be destroyed by the next install - and the first
# symptom would be `gd doctor` reporting a Godot binary that used to be there.
# Keeping it beside the install instead of inside it makes upgrades safe and
# makes the shipped config.json pure, version-controllable defaults.
MACHINE_CONFIG = Path(os.environ.get("GD_MACHINE_CONFIG")
                      or (claude_home() / "gatekeeper.machine.json"))

# Derived caches (the Godot API index) must not be written into the install
# root: it is shared by every project on the machine and, when installed with
# --link, is a working git checkout. Keyed by engine build so two engines on one
# machine cannot serve each other's API.
CACHE_ROOT = Path(os.environ.get("GD_CACHE_DIR") or (claude_home() / "gatekeeper-cache"))


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


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def _find_work_root() -> Path:
    """Resolve the workspace: explicit override, then an existing project, then
    a repo root, then the cwd."""
    env = os.environ.get("GD_PROJECT")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return _true_case(p)
    here = Path.cwd().resolve()
    # An existing workspace always wins, from anywhere inside it - this is what
    # lets `gd` be run from `game/<slug>/` and still find the contracts.
    for cand in [here, *here.parents]:
        if (cand / ".planning").is_dir():
            return _true_case(cand)
    # Then the enclosing repository, so a fresh checkout of a game repo works
    # before `.planning/` exists. Stop at the install root: a game must never
    # take the shared system's directory as its workspace.
    for cand in [here, *here.parents]:
        if _is_inside(cand, SYS_DIR):
            break
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

    `gatekeeper/config.json` lives in the install root and is shared by every game
    on this machine, so everything in it can only ever be a *default*. A project
    overrides any of it in `.planning/config.json`, which is deep-merged on top
    and lives under the project's own version control.

    This exists because the alternative leaked: shared machine-global state with
    no per-project override meant one game's numbers were every game's numbers,
    and one game's lighting presets ended up in three others.

    Three layers, lowest first:

      1. `gatekeeper/config.json`  - shipped defaults. Version-controlled, identical
         on every machine, and **overwritten by every upgrade**. It carries no
         absolute paths, because a path that works on the author's machine is
         the one thing guaranteed not to work on anybody else's.
      2. `~/.claude/gatekeeper.machine.json` - this machine's toolchain, written by
         `gd setup`. Outside the install payload so upgrades cannot destroy it.
      3. `.planning/config.json` - this game's overrides, under the game's own
         version control.

    Then `GD_GODOT` / `GD_BLENDER` / `GD_GODOT_SOURCE` on top, as a per-shell
    escape hatch.
    """
    if not CONFIG.exists():
        die("missing config at " + str(CONFIG))
    base = json.loads(CONFIG.read_text(encoding="utf-8"))
    base = _deep_merge(base, machine_config())
    p = project_config_path()
    if p.exists():
        try:
            base = _deep_merge(base, json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            die("%s is not valid JSON: %s" % (p, e))
    return _deep_merge(base, _env_toolchain())


def machine_config() -> dict:
    """This machine's toolchain, from `gd setup`. Empty before the wizard runs."""
    if not MACHINE_CONFIG.exists():
        return {}
    try:
        return json.loads(MACHINE_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die("%s is not valid JSON: %s\n"
            "       Delete it and re-run `gd setup`." % (MACHINE_CONFIG, e))


def _env_toolchain() -> dict:
    """Per-shell escape hatch, applied last.

    Exists so a single invocation can be pointed at a different engine without
    editing any file - useful when testing against two Godot builds. It is
    deliberately the *last* layer: an env var set for one experiment should not
    be silently outranked by a project file.
    """
    out: dict = {}
    g, b, src = (os.environ.get("GD_GODOT"), os.environ.get("GD_BLENDER"),
                 os.environ.get("GD_GODOT_SOURCE"))
    if g:
        out.setdefault("toolchain", {})["godot"] = {"console": g, "editor": g}
    if src:
        out.setdefault("toolchain", {}).setdefault("godot", {})["source_root"] = src
    if b:
        out.setdefault("toolchain", {})["blender"] = {"exe": b}
    return out


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


def write_text_atomic(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, then replace.

    One install drives many projects, and `/gd:run` dispatches parallel waves -
    so two writers can reach the same file. A half-written `RUN.json` or
    `STATE.md` is worse than a stale one: the next session parses it, fails,
    and reports the *project* as broken. `os.replace` is atomic on both POSIX
    and Windows, so a reader sees either the old file or the new one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%d-%s" % (os.getpid(), uuid.uuid4().hex[:6]))
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_json_atomic(path: Path, data) -> None:
    write_text_atomic(path, json.dumps(data, indent=2, default=str))


class FileLock:
    """Cooperative lock around a read-modify-write of a shared state file.

    `gd run record` reads RUN.json, mutates it and writes it back. Two jobs of
    the same wave recording within the same instant would otherwise lose one of
    the two results - and a lost `fail` reads as a job that was never attempted,
    which quietly grants an extra turn of the escalation ladder.

    Deliberately simple: an O_EXCL sentinel, a bounded wait, and a staleness
    break. It does not try to be a distributed lock; it only has to make two
    processes on one machine take turns.
    """

    def __init__(self, target: Path, timeout: float = 30.0):
        self.path = target.with_name(target.name + ".lock")
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, ("%d %s" % (os.getpid(), now())).encode())
                return self
            except FileExistsError:
                # A process that died mid-write must not wedge the project
                # forever; after the timeout the lock is assumed abandoned.
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    age = 0
                if age > self.timeout or time.time() > deadline:
                    try:
                        self.path.unlink()
                    except OSError:
                        pass
                    continue
                time.sleep(0.05)

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
        try:
            self.path.unlink()
        except OSError:
            pass
        return False


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


NO_TOOLCHAIN = (
    "\n       The toolchain has not been configured on this machine yet."
    "\n       Run `gd setup` - it autodetects Godot and Blender, and asks only"
    "\n       for what it cannot find. It writes %s,"
    "\n       which no upgrade of the system touches.")


def _tool_path(kind: str, keys) -> str:
    """First configured key that exists on disk, with an actionable error."""
    c = (cfg().get("toolchain") or {}).get(kind) or {}
    tried = []
    for k in keys:
        v = (c.get(k) or "").strip()
        if not v:
            continue
        tried.append(v)
        if Path(v).exists():
            return v
    if not tried:
        die("no %s path is configured." % kind + NO_TOOLCHAIN % MACHINE_CONFIG)
    die("%s is configured but not on disk: %s\n"
        "       Re-run `gd setup` to point it somewhere real."
        % (kind, ", ".join(tried)))


def godot_bin() -> str:
    # `console` first: on Windows the plain .exe detaches from the terminal and
    # every line of engine output is lost, which reads as a silent hang.
    return _tool_path("godot", ("console", "editor"))


def blender_bin() -> str:
    return _tool_path("blender", ("exe",))


# --------------------------------------------------------------------------- #
# setup  (make the system work on THIS machine, without editing anything)
# --------------------------------------------------------------------------- #
# Nothing below may assume a drive letter, a home directory layout, or an OS.
# This system is meant to be downloaded and used by people whose disks look
# nothing like the author's - so every path here is either discovered at
# runtime or supplied by the user, and the answer is written to a file the
# installer never touches.


def _candidate_dirs(env_keys, subpaths):
    """Expand (%ENVVAR%, relative subpath) pairs that actually exist."""
    out = []
    for key in env_keys:
        base = os.environ.get(key)
        if not base:
            continue
        for sub in subpaths:
            d = Path(base) / sub
            if d.is_dir():
                out.append(d)
    return out


def _run_version(exe, args, pattern) -> str:
    """Version string if this binary really is what we think it is, else ''."""
    try:
        r = subprocess.run([str(exe)] + list(args), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return ""
    blob = (r.stdout or "") + "\n" + (r.stderr or "")
    m = re.search(pattern, blob)
    return m.group(0).strip() if m else ""


def _windows_roots():
    """Drive letters that exist, so detection is not confined to C:.

    Observed on the machine this system was written on: Godot lived on D: and
    Blender on D:, and every "standard location" lookup missed both. A developer
    with a second drive is the common case, not the exotic one.
    """
    roots = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        d = Path(letter + ":/")
        try:
            if d.is_dir():
                roots.append(d)
        except OSError:
            continue
    return roots


def _dedupe(paths):
    seen, out = set(), []
    for p in paths:
        try:
            key = str(Path(p).resolve()).lower()
        except OSError:
            key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(Path(p))
    return out


def discover_godot() -> list:
    """Every plausible Godot binary on this machine, best first.

    Ordering matters more than completeness: on Windows the `.console.exe` must
    win, because the plain executable detaches from the terminal and the caller
    receives no stdout at all - which presents as a silent hang rather than as
    a misconfiguration, and is the single most confusing failure this system
    can hand a new user.
    """
    hits = []
    for n in ("godot", "godot4", "godot-editor", "Godot"):
        w = shutil.which(n)
        if w:
            hits.append(Path(w))
    if os.name == "nt":
        dirs = _candidate_dirs(
            ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA",
             "USERPROFILE", "ProgramData", "SystemDrive"],
            ["Godot", "GodotEngine", "Programs/Godot", "Programs/GodotEngine",
             "Downloads", "Desktop", "scoop/apps/godot/current",
             "Steam/steamapps/common/Godot Engine",
             "chocolatey/lib/godot/tools"])
        for root in _windows_roots():
            for sub_ in ("Godot", "GodotEngine", "Godot Engine", "godot",
                         "Program Files/Godot", "Program Files/Godot Engine",
                         "Dev/Godot", "Tools/Godot", "Apps/Godot"):
                d = root / sub_
                if d.is_dir():
                    dirs.append(d)
        # Godot ships as a bare executable in a folder the user named, and a
        # scons-built checkout puts its binaries under bin/. Descend one level
        # from each candidate so e.g. `<drive>/Godot/<build>/bin/` is reachable
        # from `<drive>/Godot` without scanning the whole drive.
        for d in list(dirs):
            if (d / "bin").is_dir():
                dirs.append(d / "bin")
            try:
                for child in sorted(d.iterdir())[:40]:
                    if not child.is_dir():
                        continue
                    dirs.append(child)
                    if (child / "bin").is_dir():
                        dirs.append(child / "bin")
            except OSError:
                pass
        for d in _dedupe(dirs):
            for pat in ("godot*.console.exe", "Godot*.console.exe",
                        "godot*.exe", "Godot*.exe"):
                hits += sorted(d.glob(pat))
    elif sys.platform == "darwin":
        for d in (Path("/Applications"), Path.home() / "Applications"):
            if d.is_dir():
                hits += sorted(d.glob("Godot*.app/Contents/MacOS/Godot"))
        hits += [Path("/opt/homebrew/bin/godot"), Path("/usr/local/bin/godot")]
    else:
        hits += [Path("/usr/bin/godot"), Path("/usr/local/bin/godot"),
                 Path("/snap/bin/godot"), Path("/snap/bin/godot4"),
                 Path.home() / ".local/bin/godot",
                 Path("/var/lib/flatpak/exports/bin/org.godotengine.Godot"),
                 Path.home() / ".local/share/flatpak/exports/bin/org.godotengine.Godot"]
        for d in (Path.home() / "Downloads", Path.home() / "Applications",
                  Path("/opt")):
            if d.is_dir():
                hits += sorted(d.glob("Godot*"))
                hits += sorted(d.glob("*/Godot*"))

    def rank(p):
        n = p.name.lower()
        template = any(t in n for t in ("template_debug", "template_release",
                                        "export_template"))
        return (1 if template else 0,          # editor builds only
                0 if "console" in n else 1,    # stdout capture on Windows
                1 if "mono" in n else 0,       # plain build unless it is all there is
                str(p).lower())

    out = [c for c in _dedupe(hits) if c.is_file()]
    return sorted(out, key=rank)


def discover_blender() -> list:
    """Every plausible Blender binary, newest version first."""
    hits = []
    w = shutil.which("blender")
    if w:
        hits.append(Path(w))
    if os.name == "nt":
        dirs = _candidate_dirs(
            ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "USERPROFILE",
             "ProgramData", "SystemDrive"],
            ["Blender Foundation", "Programs/Blender Foundation", "Blender",
             "Steam/steamapps/common/Blender", "scoop/apps/blender/current"])
        for root in _windows_roots():
            for sub_ in ("Blender Foundation", "Blender", "Program Files/Blender Foundation",
                         "Dev/Blender", "Tools/Blender"):
                d = root / sub_
                if d.is_dir():
                    dirs.append(d)
        for d in _dedupe(dirs):
            for pat in ("blender.exe", "*/blender.exe", "*/*/blender.exe"):
                hits += sorted(d.glob(pat))
    elif sys.platform == "darwin":
        for d in (Path("/Applications"), Path.home() / "Applications"):
            if d.is_dir():
                hits += sorted(d.glob("Blender*.app/Contents/MacOS/Blender"))
        hits += [Path("/opt/homebrew/bin/blender")]
    else:
        hits += [Path("/usr/bin/blender"), Path("/usr/local/bin/blender"),
                 Path("/snap/bin/blender"),
                 Path("/var/lib/flatpak/exports/bin/org.blender.Blender"),
                 Path.home() / ".local/share/flatpak/exports/bin/org.blender.Blender"]
        for d in (Path("/opt"), Path.home() / "Downloads"):
            if d.is_dir():
                hits += sorted(d.glob("blender*/blender"))

    def rank(p):
        m = re.findall(r"(\d+)\.(\d+)", str(p))
        v = tuple(int(x) for x in m[-1]) if m else (0, 0)
        return (-v[0], -v[1], str(p).lower())

    out = [c for c in _dedupe(hits)
           if c.is_file() and "launcher" not in c.name.lower()]
    return sorted(out, key=rank)


def _ask(prompt: str) -> str:
    """Prompt only when a human is actually there.

    `gd` is driven by agents far more often than by people, and a blocking read
    on a pipe is indistinguishable from a hung toolchain. With no terminal the
    wizard reports what it found and exits non-zero instead - which an agent
    can read and act on.
    """
    if not sys.stdin or not sys.stdin.isatty():
        return ""
    try:
        return input(prompt).strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        return ""


def _resolve_tool(kind, explicit, candidates, verify_args, verify_pat, hint):
    """(path, version, how) for one tool, or (None, '', reason)."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            return None, "", "the path given does not exist: " + str(p)
        v = _run_version(p, verify_args, verify_pat)
        if not v:
            return None, "", "%s did not identify itself as %s" % (p, kind)
        return p, v, "given"
    for c in candidates[:12]:
        v = _run_version(c, verify_args, verify_pat)
        if v:
            return c, v, "autodetected"
    print("")
    print("  Could not find %s automatically." % kind)
    print("  " + hint)
    if candidates:
        print("  Tried: " + ", ".join(str(c) for c in candidates[:5]))
    ans = _ask("  Full path to the %s executable (blank to skip): " % kind)
    if not ans:
        return None, "", "not found, and no path was supplied"
    p = Path(ans).expanduser()
    if not p.exists():
        return None, "", "no such file: " + str(p)
    v = _run_version(p, verify_args, verify_pat)
    if not v:
        return None, "", "%s did not identify itself as %s" % (p, kind)
    return p, v, "supplied"


def cmd_setup(a) -> int:
    """Detect this machine's toolchain and record it, once.

    Everything written here lives outside the installed system, so
    `python install.py` can be re-run any number of times without disturbing
    it. That separation is the whole point: an upgrade that silently unsets
    the user's Godot path is indistinguishable from a broken release.
    """
    existing = machine_config()
    if a.show:
        emit("setup", {"ok": bool(existing), "action": "show",
                       "path": str(MACHINE_CONFIG), "config": existing})
        print("  machine config  " + str(MACHINE_CONFIG)
              + ("" if MACHINE_CONFIG.exists() else "   (not written yet)"))
        if existing:
            print(json.dumps(existing, indent=2))
        else:
            print("  Nothing recorded yet - run `gd setup`.")
        return 0 if existing else 1

    if MACHINE_CONFIG.exists() and not (a.force or a.godot or a.blender):
        print("  %s already exists; re-detecting." % MACHINE_CONFIG)
        print("  (--godot/--blender set one explicitly, --force skips this note.)")

    print("")
    print("  Gatekeeper setup")
    print("  platform   %s" % sys.platform)
    print("  system     %s" % SYS_DIR)
    print("  writing    %s" % MACHINE_CONFIG)

    godot_c = [] if a.godot else discover_godot()
    blender_c = [] if a.blender else discover_blender()
    if godot_c:
        print("\n  Godot candidates:")
        for c in godot_c[:6]:
            print("    " + str(c))
    if blender_c:
        print("\n  Blender candidates:")
        for c in blender_c[:6]:
            print("    " + str(c))

    gpath, gver, ghow = _resolve_tool(
        "Godot", a.godot, godot_c, ["--headless", "--version"],
        r"\d+\.\d+[^\s]*",
        "Godot 4.4 or newer, from godotengine.org. Unzip it anywhere and give "
        "the path to the executable.")
    bpath, bver, bhow = _resolve_tool(
        "Blender", a.blender, blender_c, ["--version"], r"\d+\.\d+[^\s]*",
        "Blender 4.0 or newer, from blender.org. On Windows it is blender.exe "
        "inside the install folder; on macOS, inside "
        "Blender.app/Contents/MacOS/.")

    notes = []
    conf = dict(existing)
    tc = dict(conf.get("toolchain") or {})

    if gpath:
        console = gpath
        if os.name == "nt" and "console" not in gpath.name.lower():
            sib = gpath.with_name(gpath.stem + ".console" + gpath.suffix)
            if sib.exists():
                console = sib
                notes.append("using the .console build for stdout capture: " + sib.name)
            else:
                notes.append("no .console build beside this binary - on Windows "
                             "some engine output may be lost")
        src = ""
        if a.godot_source:
            src = str(Path(a.godot_source).expanduser()).replace("\\", "/")
        else:
            for up in (gpath.parent, gpath.parent.parent, gpath.parent.parent.parent):
                if (up / "doc" / "classes").is_dir():
                    src = str(up).replace("\\", "/")
                    notes.append("found an engine source tree at " + src)
                    break
        tc["godot"] = {
            "editor": str(gpath).replace("\\", "/"),
            "console": str(console).replace("\\", "/"),
            "version": gver,
            "source_root": src,
            "notes": ("`console` is what every agent-driven invocation uses: on "
                      "Windows the plain .exe detaches from the terminal and the "
                      "caller gets no stdout. `source_root` is optional - when it "
                      "is blank, `gddoc index` has the engine generate its own "
                      "class reference with --doctool."),
        }
    if bpath:
        tc["blender"] = {"exe": str(bpath).replace("\\", "/"), "version": bver}

    conf["toolchain"] = tc
    conf["_doc"] = ("This machine's toolchain, written by `gd setup`. It lives "
                    "outside the installed system on purpose, so re-running "
                    "install.py never destroys it. Per-GAME settings belong in "
                    "that game's .planning/config.json, never here.")
    conf["written"] = now()
    conf["platform"] = sys.platform

    ok = bool(gpath) and bool(bpath)
    if gpath or bpath:
        MACHINE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(MACHINE_CONFIG, conf)

    print("")
    print("  godot     " + (("%s  (%s, %s)" % (tc.get("godot", {}).get("console", "-"),
                                               gver, ghow)) if gpath
                            else "NOT SET - " + ghow))
    print("  blender   " + (("%s  (%s, %s)" % (bpath, bver, bhow)) if bpath
                            else "NOT SET - " + bhow))
    for n in notes:
        print("  note      " + n)
    if gpath or bpath:
        print("  wrote     " + str(MACHINE_CONFIG))

    idx = None
    if gpath and not a.no_index:
        print("")
        print("  Building the Godot API index - this is what stops agents writing")
        print("  Godot 3 code from memory. Takes a minute on a first run.")
        r = run([sys.executable, str(SYS_DIR / "bin" / "gddoc.py"), "index", "--force"],
                timeout=1800)
        m = re.search(r'"classes":\s*(\d+)', r.stdout or "")
        idx = int(m.group(1)) if m else None
        print("  api index " + ("%d classes" % idx if idx else
                                "FAILED\n" + ((r.stdout or "") + (r.stderr or ""))[-800:]))
        if not idx:
            ok = False

    emit("setup", {"ok": ok, "path": str(MACHINE_CONFIG), "godot": str(gpath or ""),
                   "godot_version": gver, "blender": str(bpath or ""),
                   "blender_version": bver, "api_classes": idx, "notes": notes,
                   "godot_candidates": [str(c) for c in godot_c[:8]],
                   "blender_candidates": [str(c) for c in blender_c[:8]]})
    print("")
    if ok:
        print("  Ready. `gd doctor` to confirm, then `/gd:new <your idea>` in the")
        print("  directory you want the game to live in.")
    else:
        print("  Setup is incomplete. Re-run with explicit paths:")
        print("    gd setup --godot <path-to-godot> --blender <path-to-blender>")
    print("")
    return 0 if ok else 1


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

    # The API index is not a nicety. Without it every agent that writes GDScript
    # falls back on Godot 3 recall, which is the largest single source of broken
    # code in this system - and it fails at runtime, not at write time.
    r = run([sys.executable, str(SYS_DIR / "bin" / "gddoc.py"), "stats"], timeout=300)
    m = re.search(r'"classes":\s*(\d+)', r.stdout or "")
    check("api_index", bool(m) and int(m.group(1)) > 100,
          ("%s classes" % m.group(1)) if m else
          "missing - run `gd setup` (or `gddoc index`)")

    check("machine_config", MACHINE_CONFIG.exists(),
          str(MACHINE_CONFIG) if MACHINE_CONFIG.exists()
          else "not written - run `gd setup`. Until then the toolchain is "
               "whatever the shipped defaults say, which is nothing.")

    # The install is shared by every project on this machine. A workspace inside
    # it means one game's contracts sit where `install.py` will eventually
    # overwrite or delete them, and where every other game can see them.
    inside = _is_inside(WORK, SYS_DIR)
    check("work_root_outside_install", not inside,
          ("%s is inside the installed system at %s - move the game somewhere "
           "of its own" % (WORK, SYS_DIR)) if inside else "ok")
    # Working in the system's own source checkout is legitimate (that is how the
    # system itself is developed) but a game scaffolded there gets committed to
    # the system's repo by accident. Say so without failing.
    if not inside and (WORK / "gatekeeper" / "config.json").exists():
        checks.append({"check": "work_root_is_system_repo", "ok": False,
                       "detail": "%s looks like the Gatekeeper source repo. A game "
                                 "created here lands in the system's own history. "
                                 "Work in a directory of its own, or set GD_PROJECT."
                                 % WORK})
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

    # Soft checks describe the workspace, not the toolchain: they are expected
    # to be red before `gd init`, and red in the system's own repo.
    soft = ("planning_dir", "godot_project", "work_root_is_system_repo")
    ok = all(x["ok"] for x in checks if x["check"] not in soft)
    emit("doctor", {"ok": ok, "checks": checks,
                    "system_dir": str(SYS_DIR), "work_root": str(WORK),
                    "work_root_from": ("GD_PROJECT" if os.environ.get("GD_PROJECT")
                                       else ".planning found" if PLANNING.is_dir()
                                       else "git root / cwd")})
    print("  system  " + str(SYS_DIR) + "   (shipped defaults; read-only at runtime)")
    print("  machine " + str(MACHINE_CONFIG)
          + ("" if MACHINE_CONFIG.exists() else "   (not written - run `gd setup`)"))
    print("  work    " + str(WORK) + "   (this game's .planning/ and game/)")
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
    if not slug:
        die("'%s' has no usable characters for a directory name - give the game "
            "a name with letters or digits in it." % name)
    # A game scaffolded inside the installed system would be shared by every
    # project on the machine and destroyed by the next `install.py`. This is the
    # one placement mistake the system cannot recover from, so refuse it.
    if _is_inside(WORK, SYS_DIR):
        die("refusing to create a game inside the installed system (%s).\n"
            "       The system is shared by every project on this machine and is\n"
            "       replaced wholesale on upgrade. cd to the directory you want\n"
            "       the game to live in, or set GD_PROJECT to it." % SYS_DIR)
    if (WORK / "gatekeeper" / "config.json").exists() and not a.force:
        die("%s is the Gatekeeper source repo itself.\n"
            "       A game created here would be committed to the system's own\n"
            "       history. cd to a directory of its own (or set GD_PROJECT), or\n"
            "       pass --force if you genuinely mean to scaffold here." % WORK)
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
        write_json_atomic(stamp, fp)
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
                          and not p.name.endswith(".local")   # our own backups
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
    with FileLock(p):
        return _write_state_locked(p, key, value, touch_only)


def _write_state_locked(p: Path, key: str, value: str, touch_only: bool) -> bool:
    text = p.read_text(encoding="utf-8")
    if not touch_only:
        pat = r"^(-\s+" + re.escape(key) + r":).*$"
        text, n = re.subn(pat, r"\1 " + value, text, count=1, flags=re.M)
        if n == 0:
            text = text.replace("## Now\n", "## Now\n- " + key + ": " + value + "\n", 1)
    text = re.sub(r"^(-\s+updated:).*$", r"\1 " + now(), text, count=1, flags=re.M)
    write_text_atomic(p, text)
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


# The front-ends this system can be driven from. The whole system is
# host-neutral below this line: the harness, the generators, the budget and
# every gate are about Godot and Blender, not about what is holding the
# keyboard. Only three things differ - what a model is called, where the
# commands and agents get installed, and how a job is dispatched.
KNOWN_HOSTS = ("claude", "codex")


def detect_host() -> str:
    """Which front-end this process was launched from, by environment.

    Both CLIs mark their environment. Claude Code sets CLAUDECODE plus a family
    of CLAUDE_CODE_*; Codex sets CODEX_*. Checking the environment beats
    checking which directories exist, because a machine with both installed
    would otherwise answer the same way in both sessions.
    """
    if os.environ.get("CLAUDECODE") or any(k.startswith("CLAUDE_CODE_")
                                           for k in os.environ):
        return "claude"
    if any(k.startswith("CODEX_") for k in os.environ):
        return "codex"
    return ""


def host_name() -> str:
    """The active host: GD_HOST, else config `models.host`, else detected.

    Unresolvable falls back to claude rather than erroring - a wrong host name
    only mis-routes a model, and stopping the run over it would be worse than
    being slightly wrong about which tier to start on.
    """
    h = (os.environ.get("GD_HOST") or "").strip().lower()
    if h in KNOWN_HOSTS:
        return h
    cfgd = str(models_cfg().get("host") or "auto").strip().lower()
    if cfgd in KNOWN_HOSTS:
        return cfgd
    return detect_host() or "claude"


def host_cfg(host: str = "") -> dict:
    """The active host's block, or {} when the config predates hosts.

    An older config.json has no `hosts` key at all. That is not an error: the
    top-level `ladder`/`agents` are Claude's, so an empty block resolves to
    exactly the behaviour that config already had.
    """
    hosts = models_cfg().get("hosts") or {}
    return hosts.get(host or host_name()) or {}


def model_ladder(host: str = "") -> list:
    return (host_cfg(host).get("ladder")
            or models_cfg().get("ladder") or _FALLBACK_LADDER)


def attempts_per_tier() -> int:
    # Host-neutral on purpose: three attempts before climbing is a statement
    # about when to stop trying, not about any particular model.
    return int(models_cfg().get("attempts_per_tier") or _FALLBACK_ATTEMPTS)


def _model_of(entry) -> str:
    """A routing entry is {"model": x, "why": ...} or a bare model string."""
    if isinstance(entry, dict):
        return entry.get("model") or ""
    return entry if isinstance(entry, str) else ""


def agent_why(agent: str) -> str:
    """Why a role sits where it does. Host-neutral, so it lives once.

    A host entry may still carry its own `why` when the reasoning genuinely
    differs; otherwise the shared one is the answer for every host.
    """
    entry = (host_cfg().get("agents") or {}).get(agent)
    if isinstance(entry, dict) and entry.get("why"):
        return entry["why"]
    shared = (models_cfg().get("agents") or {}).get(agent)
    return shared.get("why", "") if isinstance(shared, dict) else ""


def agent_model(agent: str, host: str = "") -> str:
    """Starting model for an agent, on the active host.

    The host's own table wins; without one, the top-level table applies, which
    is what makes a config written before Codex existed still correct.
    """
    m = _model_of((host_cfg(host).get("agents") or {}).get(agent))
    if not m:
        m = _model_of((models_cfg().get("agents") or {}).get(agent))
    if not m:
        # Unknown agent: start one tier below the top rather than guessing high.
        ladder = model_ladder(host)
        m = ladder[max(len(ladder) - 2, 0)]
    return m


# --------------------------------------------------------------------------- #
# roadmap  (the whole game, as stages that stack)
# --------------------------------------------------------------------------- #
PLACEHOLDER_RE = re.compile(r"[<>]|^-$|^$|^TBD$|^\.\.\.$", re.I)


_PLACEHOLDER_RE_PAIR = re.compile(r"<[^<>]*>")


def _unfilled(cell: str) -> bool:
    """True if a table cell is still template boilerplate.

    A cell is boilerplate when nothing survives removing every `<…>` group.
    Testing for a bare angle bracket instead - which is what this did - fails
    the very cells it is meant to protect: real pass conditions are full of
    `>=`, `<` and `->`, so `player walks spawn -> woodline in 22-32 s` was
    reported as an unfilled placeholder. A false failure on correct work is
    worse than a missed one, because it gets designed around.
    """
    c = (cell or "").strip()
    if c in ("", "-", "TBD", "tbd", "...", "…", "?"):
        return True
    # Remove innermost groups repeatedly so a nested `<... <A> ...>` collapses.
    prev = None
    while prev != c:
        prev = c
        c = _PLACEHOLDER_RE_PAIR.sub("", c)
    return not c.strip(" \t-–—.·,;:|`*_")


def parse_roadmap(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    stages = []
    for row in _rows(text, "#"):
        sid = (row.get("#") or "").strip()
        if not re.fullmatch(r"\d+", sid):
            continue
        stages.append({
            "id": "%02d" % int(sid),
            "block": (row.get("block") or "").strip().lower(),
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
    # The targets table is keyed on `stage #`, not `#`, precisely so it does not
    # collide with the Stages table when parsed - two tables whose header starts
    # with the same cell would silently merge into one list of rows.
    targets = [{"id": (r.get("stage #") or "").strip(),
                "target": r.get("target — what this stage is for", ""),
                "pass": r.get("pass conditions — all must hold", "")}
               for r in _rows(text, "stage #")]
    systems = [{"system": r.get("system", ""),
                "effect": r.get("what it does to the loop", ""),
                "greybox": (r.get("greyboxed in") or "").strip(),
                "finish": (r.get("finished in") or "").strip()}
               for r in _rows(text, "system")]
    spaces = [{"space": r.get("space", ""), "size": r.get("size (m)", ""),
               "what": r.get("what happens here", ""),
               "stage": (r.get("blocked out in") or "").strip()}
              for r in _rows(text, "space")]
    m = re.search(r"^-\s+end state:\s*(.+)$", text, re.M)
    cur = re.search(r"^-\s+current stage:\s*(.+)$", text, re.M)
    gb = re.search(r"^-\s+greybox block:\s*(\S+)", text, re.M)
    return {"stages": stages, "coverage": coverage, "placeholders": placeholders,
            "doors": doors, "targets": targets, "systems": systems,
            "spaces": spaces,
            "greybox_last": (gb.group(1).strip() if gb else ""),
            "end_state": (m.group(1).strip() if m else ""),
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


def greybox_state() -> dict:
    """Where this project stands against Law 1, from the roadmap and STATE.

    Law 1 ("the loop before the look") was previously enforced only by prose in
    two command files, which means it was enforced only when the agent reading
    them happened to be thorough. The greybox block makes the rule checkable:
    art may not start until the LAST greybox stage has cleared and a human has
    played it.
    """
    out = {"block": [], "last": "", "done": [], "complete": False,
           "passed_flag": "no", "ok_for_art": False, "reason": ""}
    path = PLANNING / "ROADMAP.md"
    if path.exists():
        try:
            rm = parse_roadmap(path)
        except OSError:
            rm = None
        if rm:
            gb = [x for x in rm["stages"] if x["block"] == "greybox"]
            out["block"] = [x["id"] for x in gb]
            out["last"] = out["block"][-1] if out["block"] else ""
            out["done"] = [x["id"] for x in gb if x["status"] == "done"]
            out["complete"] = bool(out["block"]) and len(out["done"]) == len(out["block"])
    sp = PLANNING / "STATE.md"
    if sp.exists():
        out["passed_flag"] = parse_state(sp.read_text(encoding="utf-8")).get(
            "greybox_passed", "no")
    # Both halves are required. The roadmap knows whether the work is done; only
    # STATE records that a person actually played it, and that flag is set by a
    # human-witnessed playtest, never by the driver.
    if out["passed_flag"] == "yes":
        out["ok_for_art"] = True
    elif not out["block"]:
        out["reason"] = ("the roadmap marks no greybox stages, so there is no "
                         "evidence the loop has been proven")
    elif not out["complete"]:
        remaining = [x for x in out["block"] if x not in out["done"]]
        out["reason"] = ("the greybox block is not finished - stage(s) %s still "
                         "planned" % ", ".join(remaining))
    else:
        out["reason"] = ("every greybox stage is done but `greybox_passed` is "
                         "still no - a person has not played it yet. "
                         "/gd:playtest is what sets that flag.")
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
        # Rewrite that stage's status cell ONLY inside the Stages table, and
        # advance `current stage`.
        #
        # This used to run over every markdown row in the file, so any table
        # keyed on a stage id got its last cell overwritten with "done" -
        # the Risk order table's reason, a coverage row's stage. Data loss in a
        # contract, caused by the tool meant to maintain it.
        in_stages = False

        def fix(mo):
            nonlocal in_stages
            row = mo.group(0)
            cells = row.strip().strip("|").split("|")
            head = cells[0].strip().lower()
            if head == "#":                      # the Stages table header
                in_stages = True
                return row
            if head in ("element", "placeholder", "door", "stage", "date",
                        "stage #", "system", "space", "what",
                        "systems + spaces in the game"):
                in_stages = False                # a different table started
                return row
            if not in_stages:
                return row
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

    # ---- targets and pass conditions ------------------------------------- #
    # Law 4, one level up: a phase whose pass conditions cannot be written is a
    # phase that is not defined yet. Writing them at kickoff is what stops the
    # gate being reverse-engineered from whatever happened to get built.
    tmap = {}
    for t in rm["targets"]:
        tid = t["id"]
        if not re.fullmatch(r"\d+", tid or ""):
            continue
        tmap["%02d" % int(tid)] = t
    for s_ in rm["stages"]:
        t = tmap.get(s_["id"])
        if t is None:
            errors.append("stage %s has no row in Stage targets and pass conditions "
                          "- it has no definition of done" % s_["id"])
            continue
        if _unfilled(t["target"]):
            errors.append("stage %s: target is still a placeholder - say what the "
                          "stage is FOR" % s_["id"])
        if _unfilled(t["pass"]):
            errors.append("stage %s: pass conditions are still a placeholder - this "
                          "is what its phase gate has to assert" % s_["id"])
    for tid in sorted(set(tmap) - {x["id"] for x in rm["stages"]}):
        warnings.append("targets table has a row for stage %s, which is not in the "
                        "Stages table" % tid)

    # ---- the greybox block ------------------------------------------------ #
    gb_rows = [x for x in rm["stages"] if x["block"] == "greybox"]
    gb_ids = [x["id"] for x in gb_rows]
    declared = rm["greybox_last"]
    if not gb_ids:
        errors.append("no stage is marked `greybox` in the block column - stage 01 "
                      "is always the greybox (Law 1)")
    else:
        if gb_ids[0] != ids[0]:
            errors.append("the greybox block does not start at the first stage "
                          "(starts at %s) - nothing may precede the greybox" % gb_ids[0])
        # Contiguity is what makes `greybox_passed` a single well-defined moment.
        # A greybox stage after an art stage means art gets built on an unproven
        # loop, which is the exact failure Law 1 exists to prevent.
        pos = [ids.index(g) for g in gb_ids]
        if pos != list(range(pos[0], pos[0] + len(pos))):
            errors.append("the greybox stages are not contiguous (%s) - a non-greybox "
                          "stage sits inside the block, so art would be built on an "
                          "unproven loop" % ", ".join(gb_ids))
        want_last = gb_ids[-1]
        if declared and re.fullmatch(r"\d+", declared):
            declared = "%02d" % int(declared)
        if not declared:
            errors.append("`- greybox block:` is not set - it must name the LAST "
                          "greybox stage (%s), which is the one that flips "
                          "greybox_passed" % want_last)
        elif declared != want_last:
            errors.append("`- greybox block: %s` disagrees with the block column, "
                          "whose last greybox stage is %s" % (declared, want_last))
        # The last greybox stage is the Law 1 gate. It has to prove the loop
        # closes AND that the player can lose - the second half is forgotten in
        # almost every first pass, so it is checked rather than trusted.
        lastt = tmap.get(want_last)
        blob = ((lastt or {}).get("pass", "") + " "
                + next((x["playable"] for x in rm["stages"] if x["id"] == want_last), "")
                + " " + next((x["gate"] for x in rm["stages"] if x["id"] == want_last), ""))
        if not re.search(r"\blos(e|ing|t)\b|\bfail(ure|s|ed)?\b|can_lose|death|die\b",
                         blob, re.I):
            errors.append("the last greybox stage (%s) says nothing about losing. "
                          "A loop with no reachable failure state is half a loop, "
                          "and it is the half everyone forgets." % want_last)

    # ---- systems inventory ------------------------------------------------ #
    named_systems = [x for x in rm["systems"] if not _unfilled(x["system"])]
    if not named_systems:
        errors.append("the Systems inventory is empty - every game has at least the "
                      "core verb and the thing that makes turn two different")
    for sysrow in named_systems:
        tag = "system '%s'" % sysrow["system"][:40]
        for field, label in (("greybox", "greyboxed in"), ("finish", "finished in")):
            v = sysrow[field]
            if _unfilled(v):
                errors.append("%s names no `%s` stage" % (tag, label))
                continue
            sid = "%02d" % int(v) if v.isdigit() else v
            if sid not in ids:
                errors.append("%s points `%s` at stage '%s', which does not exist"
                              % (tag, label, v))
            elif field == "greybox" and gb_ids and sid not in gb_ids:
                errors.append("%s is greyboxed in stage %s, which is outside the "
                              "greybox block (%s-%s). Every system runs in grey "
                              "before any of them is made to look good."
                              % (tag, sid, gb_ids[0], gb_ids[-1]))

    # ---- levels / spaces --------------------------------------------------- #
    named_spaces = [x for x in rm["spaces"] if not _unfilled(x["space"])]
    if not named_spaces:
        errors.append("the Levels/maps table is empty - the player is somewhere, and "
                      "its size in metres is a decision, not a discovery")
    for sp in named_spaces:
        tag = "space '%s'" % sp["space"][:40]
        if _unfilled(sp["size"]):
            warnings.append("%s has no size in metres - distances decided during a "
                            "build are distances nobody chose" % tag)
        v = sp["stage"]
        if _unfilled(v):
            errors.append("%s names no blockout stage - a space with no blockout "
                          "stage is a space nobody has thought about" % tag)
            continue
        sid = "%02d" % int(v) if v.isdigit() else v
        if sid not in ids:
            errors.append("%s points at stage '%s', which does not exist" % (tag, v))
        elif gb_ids and sid not in gb_ids:
            errors.append("%s is blocked out in stage %s, outside the greybox block "
                          "(%s-%s). The whole map is greyboxed before anything is "
                          "built on it." % (tag, sid, gb_ids[0], gb_ids[-1]))

    # ---- is the greybox block big enough for this game? ------------------- #
    # Advisory, not a failure: the right number depends on how much the stages
    # actually contain. But one stage carrying eight systems and six spaces is a
    # phase whose gate cannot fail usefully, and that is worth saying out loud.
    load = len(named_systems) + len(named_spaces)
    if gb_ids and load > 5 * len(gb_ids):
        warnings.append(
            "the greybox block is %d stage(s) for %d system(s) and %d space(s). "
            "That is a lot for one plan each - consider splitting a stage by space "
            "or by system (see ROADMAP.md 'The greybox block')."
            % (len(gb_ids), len(named_systems), len(named_spaces)))

    done = [s for s in rm["stages"] if s["status"] == "done"]
    ok = not errors
    emit("roadmap", {"ok": ok, "action": "validate", "stages": len(rm["stages"]),
                     "done": len(done), "current": rm["current"],
                     "coverage_rows": len([c for c in rm["coverage"] if not _unfilled(c["element"])]),
                     "core_loop_beats": beats,
                     "placeholders_open": len([p for p in rm["placeholders"]
                                               if not _unfilled(p["placeholder"])]),
                     "greybox_block": gb_ids, "greybox_last": rm["greybox_last"],
                     "systems": len(named_systems), "spaces": len(named_spaces),
                     "errors": errors, "warnings": warnings})

    print("  end state   " + (rm["end_state"][:100] or "(not set)"))
    print("  progress    %d / %d stages done, current %s"
          % (len(done), len(rm["stages"]), rm["current"] or "?"))
    print("  greybox     %s   (%d system(s), %d space(s) to prove in grey)"
          % ("-".join([gb_ids[0], gb_ids[-1]]) if gb_ids else "(none marked)",
             len(named_systems), len(named_spaces)))
    for st in rm["stages"]:
        mark = {"done": "x", "active": ">", "planned": " "}.get(st["status"], "?")
        print("  [%s] %s %-9s %-22s %s"
              % (mark, st["id"], st["block"][:9], st["stage"][:22], st["playable"][:52]))
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
        print("")
        print("  roadmap valid: every stage stacks forward and states its target and")
        print("  pass conditions; the greybox block covers every system and every")
        print("  space and ends in a reachable failure state; every Core Loop beat")
        print("  and every placeholder names the stage that delivers it.")
    else:
        print("\n  Fix ROADMAP.md (see gatekeeper/references/decomposition.md), then re-run.")
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
            "_doc": ("Per-project overrides, deep-merged over gatekeeper/config.json. "
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
    host = host_name()
    emit("config", {"ok": True,
                    "shipped": str(CONFIG),
                    "machine": str(MACHINE_CONFIG) if MACHINE_CONFIG.exists() else None,
                    "project": str(p) if p.exists() else None,
                    "host": host, "host_detected": detect_host(),
                    "host_source": ("GD_HOST" if os.environ.get("GD_HOST")
                                    else "config" if str(models_cfg().get("host")
                                                         or "auto") != "auto"
                                    else "detected"),
                    "ladder": model_ladder(host),
                    "overrides": prov, "effective": eff,
                    "layers": ["shipped defaults", "machine toolchain",
                               "project overrides", "environment"]})
    # Three files, lowest precedence first. Printing them in order is the whole
    # explanation of where a surprising number came from.
    print("  host       %s   (model routing only; everything else is host-neutral)"
          % host)
    print("  1 shipped  " + str(CONFIG) + "   (upgraded in place; no paths, no game data)")
    print("  2 machine  " + (str(MACHINE_CONFIG) if MACHINE_CONFIG.exists()
                             else "(none - `gd setup`)") + "   (this machine's toolchain)")
    print("  3 project  " + (str(p) if p.exists() else "(none - `gd config --init` to add one)")
          + "   (this game's numbers)")
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
    """Show the routing table for a host, and flag drift.

    On Claude two places name a model: `models.agents` in config.json (what
    `gd run` dispatches and escalates with) and the `model:` frontmatter of
    each .claude/agents/*.md (what Claude Code uses when an agent is spawned by
    name with no override). They must agree, and nothing would otherwise tell
    you when they stop agreeing.

    On Codex there is only one place. A Codex agent is a skill, and a skill
    cannot pin a model, so `gd run` passes `-m` at dispatch and there is no
    second surface to drift against. Reporting "no agent file" for all ten
    would be noise dressed as a warning, so hosts declare their agent format
    and only `claude-agents` is drift-checked.
    """
    host = (getattr(a, "host", "") or "").strip().lower() or host_name()
    if host == "all":
        rc = 0
        for h in KNOWN_HOSTS:
            print("\n== %s ==" % h)
            a.host = h
            rc |= cmd_models(a)
        return rc
    if host not in KNOWN_HOSTS:
        die("unknown host %r - known hosts: %s" % (host, ", ".join(KNOWN_HOSTS)))

    hcfg = host_cfg(host)
    fmt = hcfg.get("agent_format") or "claude-agents"
    # Frontmatter is machine-global, so it can only be compared against the
    # MACHINE config. A project override is not drift - it is the feature - so
    # the two are reported separately.
    machine = json.loads(CONFIG.read_text(encoding="utf-8")).get("models") or {}
    m_hosts = (machine.get("hosts") or {}).get(host) or {}
    agents_cfg = m_hosts.get("agents") or machine.get("agents") or {}
    proj_over = {k.split(".", 2)[2]: v for k, v in config_provenance().items()
                 if k.startswith("models.agents.")
                 or k.startswith("models.hosts.%s.agents." % host)}
    rows, drift = [], []
    # Agent files may be project-scoped or installed at user scope; check both.
    agent_dirs = [WORK / ".claude" / "agents",
                  Path.home() / ".claude" / "agents"]
    agent_dir = next((d for d in agent_dirs if d.is_dir()), agent_dirs[0])
    known = set(agents_cfg) | set(machine.get("agents") or {})
    if fmt == "claude-agents":
        known |= {p.stem for p in agent_dir.glob("gd-*.md")}
    for name in sorted(known):
        want = _model_of(agents_cfg.get(name)) or None
        why = agent_why(name)
        fm, defined = None, False
        if fmt == "claude-agents":
            f = agent_dir / (name + ".md")
            defined = f.exists()
            if defined:
                m = re.search(r"^model:\s*(\S+)\s*$",
                              f.read_text(encoding="utf-8"), re.M)
                fm = m.group(1) if m else None
        eff = agent_model(name, host)
        rows.append({"agent": name, "machine": want, "effective": eff,
                     "frontmatter": fm, "why": why, "defined": defined,
                     "overridden": bool(want) and eff != want})
        if fmt != "claude-agents":
            continue
        if want and fm and want != fm:
            drift.append("%s: config=%s frontmatter=%s" % (name, want, fm))
        if want and not defined:
            drift.append("%s: in config but no .claude/agents/%s.md" % (name, name))
        if fm and not want:
            drift.append("%s: agent file exists but no config entry" % name)

    emit("models", {"ok": not drift, "host": host, "agent_format": fmt,
                    "ladder": model_ladder(host),
                    "attempts_per_tier": attempts_per_tier(),
                    "dispatch": hcfg.get("dispatch", ""),
                    "agents": rows, "drift": drift,
                    "project_overrides": proj_over})
    print("  host     %s%s" % (host, "" if getattr(a, "host", "") else "   (detected)"))
    print("  ladder   " + " -> ".join(model_ladder(host))
          + "   (%d attempts per tier before escalating)" % attempts_per_tier())
    if hcfg.get("dispatch"):
        print("  dispatch " + hcfg["dispatch"])
    print("")
    for r in rows:
        mark = " " if (fmt != "claude-agents" or not r["machine"]
                       or r["machine"] == r["frontmatter"]) else "!"
        model = r["effective"] or "-"
        if r["overridden"]:
            model += "*"
        print("%s %-18s %-14s %s" % (mark, r["agent"], model, r["why"][:88]))
    if proj_over:
        print("")
        print("  * = overridden by this project (.planning/config.json)")
    if fmt != "claude-agents":
        print("")
        print("  %s has no per-agent model surface, so there is nothing to drift"
              % host)
        print("  against - the table above is the whole routing decision.")
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


def source_fingerprint(proj: Path) -> str:
    """Hash of everything a gate's result depends on.

    A green phase gate had no expiry: STATE said `phase_gate: green`
    indefinitely while the source moved underneath it. Observed - a gate green
    at 03:03Z, and eleven hours later `gd check` failed on code edited since,
    with STATE still claiming green. A resumed session believes STATE.

    So a gate now records what it was green *against*, the same way the harness
    records what was installed.
    """
    import hashlib
    h = hashlib.sha256()
    if proj is None:
        return ""
    pats = ("*.gd", "*.tscn", "*.tres", "*.py")
    files = []
    for pat in pats:
        files += [f for f in proj.rglob(pat)
                  if ".godot" not in f.parts and ".gd_out" not in f.parts]
    for f in sorted(files):
        try:
            h.update(str(f.relative_to(proj)).replace("\\", "/").encode())
            h.update(f.read_bytes())
        except OSError:
            continue
    lab = proj / "lab"
    if lab.is_dir():
        for f in sorted(lab.glob("*.json")):
            h.update(f.name.encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


def archive_verdict(d: Path, jid: str, attempt: int, src=None, want_plan=None):
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
            found = sorted(list(proj.glob(".gd_out/*/*/verdict.json"))
                            + list(proj.glob(".gd_out/*/verdict.json")),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            # "Most recent" is whoever finished last, which in a parallel wave is
            # usually a wave-mate: one job's `verdicts/04-attempt04.json` turned
            # out to hold another job's `blockout_walk` run. Match the verdict to
            # THIS job's gate instead, and archive nothing rather than something
            # wrong.
            if want_plan:
                for f in found:
                    try:
                        v = json.loads(f.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if want_plan in (str(v.get("plan", "")), str(v.get("plan_name", ""))):
                        cand = f
                        break
            elif found:
                cand = found[0]
    if cand is None:
        return None
    dest = dest_dir / ("%s-attempt%02d.json" % (jid, attempt))
    try:
        shutil.copy2(cand, dest)
    except OSError:
        return None
    return str(dest)


_GATE_TOOL_RE = re.compile(
    r"""(?<![\w/\\.-])                       # not mid-token
        (?:(?:python3?|py)\s+)?               # an optional interpreter
        (?:\.[/\\])?                          # an optional ./
        (?:(?:gatekeeper|gsd-gd)[/\\]bin[/\\])?   # an optional repo-relative dir
        (gd|gddoc)(?:\.py)?                   # the tool itself
        (?=\s|$)""",
    re.X)


def resolve_gate_cmd(cmd: str) -> str:
    """Rewrite a gate command so it runs from any project on any machine.

    Gate lines live in a project's `PLAN.md`, which is that project's contract
    and is committed to that project's repo. They were written as
    `python gatekeeper/bin/gd.py check`, which resolves only when the working
    directory happens to contain the system - i.e. only inside this repo. In
    every real installation the gate failed with `python: can't open file
    .../<game>/gatekeeper/bin/gd.py`, so no phase outside the system's own checkout
    could ever go green.

    Rewriting here rather than at authoring time keeps the contract portable: a
    plan says `gd check`, and the machine it runs on decides where `gd` is. A
    baked absolute path would break the moment the project moved machines - or
    the install did.
    """
    def repl(mo):
        tool = mo.group(1)
        script = SYS_DIR / "bin" / (tool + ".py")
        return '"%s" "%s"' % (sys.executable, script)
    return _GATE_TOOL_RE.sub(repl, cmd)


def run_file(d: Path) -> Path:
    return d / "RUN.json"


# Locks held by this process, released in main()'s finally so a `die()` cannot
# leave one behind. (FileLock also breaks a lock older than its timeout, so even
# a hard kill cannot wedge a phase permanently.)
_HELD_LOCKS: list = []


def acquire_run_lock(d: Path) -> None:
    """Serialise read-modify-write of RUN.json across concurrent agents.

    `/gd:run` dispatches a wave of jobs in parallel and each records its own
    result. Without this, two `run record` calls landing together lose one of
    the two - and a lost `fail` is indistinguishable from a job never attempted,
    which silently grants an extra turn of the escalation ladder.
    """
    lk = FileLock(run_file(d))
    lk.__enter__()
    _HELD_LOCKS.append(lk)


def release_locks() -> None:
    while _HELD_LOCKS:
        _HELD_LOCKS.pop().__exit__(None, None, None)


def load_run(d: Path) -> dict:
    f = run_file(d)
    if not f.exists():
        die("no RUN.json in " + d.name + " - run `gd run init` first")
    return json.loads(f.read_text(encoding="utf-8"))


def save_run(d: Path, r: dict) -> None:
    r["updated"] = now()
    write_json_atomic(run_file(d), r)


# Actions that rewrite RUN.json. `next` and `status` only read it, and taking
# the lock for those would serialise the very polling that watches a wave run.
_RUN_MUTATORS = ("init", "start", "record", "gate", "resolve", "block", "complete")


def cmd_run(a) -> int:
    d = phase_dir(a.phase)
    act = a.action
    if act in _RUN_MUTATORS:
        acquire_run_lock(d)

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
        # Only gd-playtester authors gates. Two projects independently found
        # that a job file could hand a builder its own gate while the builder's
        # brief forbade it, with nothing resolving which wins. Resolve it here,
        # where it cannot be missed.
        for jid, j in sorted(parsed["jobs"].items()):
            if j["agent"] == "gd-playtester":
                continue
            if re.search(r"lab/\S*\.json", j.get("touches", "")):
                problems.append(
                    "job %s (%s) lists a playtest plan in `touches` - only "
                    "gd-playtester authors gates (Law 6b). Move the plan to the "
                    "gates job and leave this job only running it."
                    % (jid, j["agent"]))
        # Law 1, enforced rather than described. Asset work dispatched onto an
        # unproven loop is the characteristic way an AI-built game dies: a folder
        # of beautiful rooms with nothing to do in them, discovered far too late
        # to throw away.
        gbx = greybox_state()
        if not gbx["ok_for_art"]:
            asset_jobs = [jid for jid, j in sorted(parsed["jobs"].items())
                          if j["agent"] == "gd-modeler"
                          or re.search(r"\bgd(?:\.py)?\s+asset\b", j.get("gate", ""))
                          or re.search(r"\bgenerators?/", j.get("touches", ""))]
            if asset_jobs:
                problems.append(
                    "job(s) %s are asset work, but %s (Law 1: the loop before the "
                    "look). Finish the greybox block first, or move these jobs to a "
                    "later stage."
                    % (", ".join(asset_jobs), gbx["reason"]))
        if not parsed["phase_gate"]:
            problems.append("PLAN.md has no `- gate:` lines - the phase has no "
                            "machine-readable definition of done")
        for g in parsed["phase_gate"]:
            if re.search(r"[<>]", g):
                problems.append("phase gate is still a placeholder: " + g)
            # Catch an unrunnable gate now, not when the phase is otherwise done.
            # A gate that cannot start is indistinguishable from a gate that
            # failed, and it surfaces as a shell error nobody reads as a plan bug.
            first = (g.strip().split() or [""])[0]
            if resolve_gate_cmd(g) == g and not shutil.which(first) \
                    and not Path(first).exists():
                problems.append(
                    "phase gate starts with '%s', which is neither a `gd`/`gddoc` "
                    "command nor anything on PATH: %s" % (first, g))
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
             # The host is recorded for the same reason the toolchain is: a job
             # dispatched at `opus` and a job dispatched at `gpt-6-astra` were
             # not graded by the same thing, and a phase resumed under the other
             # front-end would otherwise carry a ladder none of its models are on.
             "host": host_name(),
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
        # The plan this job's gate names, so the archived verdict is provably its
        # own. `gd playtest <name>` / `playtest lab/<name>.json` both reduce to
        # <name>.
        gm = re.search(r"playtest\s+(?:lab/)?([A-Za-z0-9_\-]+)", j.get("gate", ""))
        archived = archive_verdict(d, jid, j["total_attempts"] + 1, a.verdict,
                                   want_plan=(gm.group(1) + ".json") if gm else None)
        if archived is None and not a.verdict:
            print("  [warn] no verdict matching this job's gate was found - nothing "
                  "archived. Pass --verdict <path> to be explicit.")
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
            #
            # The ladder recorded at `run init` wins over the live one. A phase
            # armed under one front-end and resumed under the other would
            # otherwise escalate a job onto a ladder its current model is not on,
            # and the climb would silently restart from the wrong rung.
            ladder = r.get("model_ladder") or model_ladder()
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
            real = resolve_gate_cmd(cmd_s)
            p = subprocess.run(real, shell=True, cwd=str(WORK), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=a.timeout)
            tail = strip_ansi((p.stdout or "") + (p.stderr or ""))[-600:]
            row = {"cmd": cmd_s, "ok": p.returncode == 0,
                   "exit": p.returncode, "tail": tail}
            if real != cmd_s:
                row["resolved"] = real
            results.append(row)
        ok = all(x["ok"] for x in results)
        r["gate_runs"].append({"at": now(), "ok": ok,
                               "source": source_fingerprint(locate_project()),
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
        gbx = greybox_state()
        emit("run", {"ok": True, "action": "status", "phase": d.name,
                     "greybox": gbx,
                     "run_status": r["status"], "stop_reason": r.get("stop_reason"),
                     "system_armed": armed_sys, "system_now": cur_sys,
                     "system_changed_mid_phase": sys_changed,
                     "by_status": by_status,
                     "phase_gate": r.get("phase_gate"),
                     "last_gate": (r.get("gate_runs") or [None])[-1]})
        print("  phase   %s   [%s]" % (d.name, r["status"]))
        if gbx["block"]:
            print("  greybox %s of %s stage(s) done%s"
                  % (len(gbx["done"]), len(gbx["block"]),
                     "; greybox_passed: " + gbx["passed_flag"]))
            if not gbx["ok_for_art"]:
                print("          art work is blocked: " + gbx["reason"])
        _g = (r.get("gate_runs") or [None])[-1]
        if _g and _g.get("ok") and _g.get("source"):
            _now = source_fingerprint(locate_project())
            if _now != _g["source"]:
                print("  GATE    green at %s against source %s, but source is now %s"
                      % (_g["at"], _g["source"], _now))
                print("          That result no longer describes this code. Re-run the gate.")
                write_state("phase_gate", "stale")
        if sys_changed:
            print("  SYSTEM  changed mid-phase: armed on %s, now %s" % (armed_sys, cur_sys))
            print("          Jobs graded before the change used a different toolchain."
                  " `gd version` for what moved.")
        armed_host = r.get("host")
        if armed_host and armed_host != host_name():
            print("  HOST    changed mid-phase: armed under %s, now %s"
                  % (armed_host, host_name()))
            print("          Jobs already recorded ran on the %s ladder; the phase"
                  " keeps it." % armed_host)
            print("          `GD_HOST=%s` to go back, or finish the phase here and"
                  " start the next one fresh." % armed_host)
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

    gates = r.get("gate_runs") or []
    last = gates[-1] if gates else None
    if last and last.get("ok"):
        src_now = source_fingerprint(locate_project())
        if not last.get("source"):
            # A green gate with nothing recorded about what it ran against is
            # unverifiable, not shippable. Absence of evidence must not read as
            # green - observed: a gate green at 03:03Z still reporting ship
            # eleven hours later, with a call to an undefined function in the
            # code since.
            return {"action": "phase_gate",
                    "why": ("the phase gate is green (%s) but recorded no source "
                            "fingerprint, so it cannot be shown to describe this "
                            "code - re-run it to confirm" % last["at"]),
                    "unverifiable": True, "phase_gate": r.get("phase_gate", [])}
        if last["source"] != src_now:
            return {"action": "phase_gate",
                    "why": ("the phase gate was green against source %s, but the "
                            "source is now %s - re-run it"
                            % (last["source"], src_now)),
                    "stale": True, "phase_gate": r.get("phase_gate", [])}
        return {"action": "ship",
                "why": "all jobs passed and the phase gate is green (%s) - this phase "
                       "is done; /gd:playtest for the human pass, then /gd:ship"
                       % last["at"],
                "gate_at": last["at"]}
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

    write_project_gd(proj)
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
    # Scenes to mine for embedded scripts: the whole project when no files were
    # named, otherwise exactly the ones that were.
    #
    # This used to sit behind `if not a.files`, which made the targeted form -
    # `gd check lab/interactables.tscn`, the natural thing to type after editing
    # one scene - a PASS that asserted nothing about the only code in the file.
    # A .tscn handed to `--check-only --script` reports no error because it is
    # not a script. That was a false pass, and I introduced it.
    if a.files:
        scenes = [p for p in targets if p.suffix.lower() in (".tscn", ".tres")]
        targets = [p for p in targets if p.suffix.lower() not in (".tscn", ".tres")]
    else:
        scenes = [p for p in sorted(list(proj.rglob("*.tscn")) + list(proj.rglob("*.tres")))
                  if ".godot" not in p.parts]
    embedded = []
    for scene in scenes:
        for sid, src in embedded_scripts(scene):
            embedded.append((scene, sid, src))
    named_scenes_without_scripts = [p for p in scenes
                                    if not any(e[0] == p for e in embedded)]
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

    for sc in named_scenes_without_scripts:
        results.append({
            "file": "res://" + str(sc.relative_to(proj)).replace("\\", "/"),
            "embedded": True, "ok": True, "engine_errors": [],
            "autoloads_forgiven": [], "godot3_findings": [],
            "note": "no embedded GDScript in this scene - nothing to type-check"})

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
        print("    python gatekeeper/bin/gddoc.py member <Class>.<member>")
        print("    python gatekeeper/bin/gddoc.py class <Class>")
        print("    python gatekeeper/bin/gddoc.py search <keyword>")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# playtest  (the "measure" + "look" gate)
# --------------------------------------------------------------------------- #
def project_budget() -> dict:
    """Budget for THIS game.

    One source of truth: `.planning/config.json` overrides the machine defaults
    in `gatekeeper/config.json`, deep-merged by cfg(). `BUDGET.md` justifies the
    numbers in prose and holds the cost model; it does not carry them, because
    two places holding the same value means the wrong one eventually wins - and
    it did, silently, on the first try.
    """
    b = dict(cfg().get("budget") or {})          # already project-merged
    over = {k.split(".", 1)[1]: v for k, v in config_provenance().items()
            if k.startswith("budget.")}
    return {"budget": b, "overrides": over,
            "source": str(project_config_path()) if over else str(CONFIG)}


# Must match the `match kind:` arms in harness/godot/gd_playtest.gd. When
# `probe_min`/`probe_max`/`probe_at` were added, this set was not updated, so
# `--lint` rejected three kinds the harness itself implements - a false failure
# that pushed plans back to `expr` for things that had a typed kind.
PLAN_CHECK_KINDS = {"moved", "still", "node_exists", "prop_between", "prop_gt",
                    "prop_lt", "prop_eq", "expr",
                    "probe_min", "probe_max", "probe_at"}


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
        if kind in ("probe_min", "probe_max", "probe_at") and c.get("probe") not in probes:
            errors.append("check '%s' references probe '%s', which is not declared"
                          % (name, c.get("probe")))
        if kind == "probe_at" and not c.get("label"):
            errors.append("check '%s' is a probe_at with no `label` - it must name the "
                          "step whose end you mean" % name)
        if kind == "probe_at" and c.get("label"):
            labels = {str(st.get("label")) for st in plan.get("steps", [])
                      if isinstance(st, dict) and st.get("label")}
            if str(c["label"]) not in labels:
                errors.append("check '%s' waits on label '%s', but no step has it. "
                              "Labels present: %s"
                              % (name, c["label"], ", ".join(sorted(labels)) or "(none)"))
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

    # Regenerate the project's compiled-in numbers BEFORE the run, not after.
    #
    # `gd_project.gd` claimed in its own header to be generated by `gd palette`
    # AND `gd playtest`, but playtest never called this - so a project that
    # overrode `min_fps` or `max_shadow_casting_lights` after `gd init` had the
    # gate enforcing the new number while `GDLightingRig.enforce_shadows()` and
    # every `GDProject.budget()` call in game code enforced the old one. The
    # runtime and the gate disagreeing about the budget is the exact fault this
    # generated file was added to prevent, and it survived because nothing
    # compared the two.
    write_project_gd(proj)
    drift_before = harness_drift(proj)
    harness_info = install_harness(proj)
    # Upgrading the instrument that grades you, mid-job, in silence, is not
    # acceptable: a project had its harness replaced under a running job and the
    # only trace was a changed hash. Say so, loudly, in the output and the verdict.
    harness_upgraded = None
    if drift_before.get("project") and drift_before["project"] != harness_info["hash"]:
        harness_upgraded = {"from": drift_before["project"], "to": harness_info["hash"],
                            "was": drift_before.get("status")}
        print("  [warn] harness upgraded %s -> %s (was %s) before this run."
              % (harness_upgraded["from"], harness_upgraded["to"],
                 harness_upgraded["was"]))
        print("         Verdicts from before this run were produced by a different "
              "grader.")
    # install_harness() just rewrote the harness scripts, which makes Godot's
    # global class cache stale - leave it and the run sprays
    # `Could not find type "GDLightingRig"` and fails on runtime_errors.
    cache_state = ensure_class_cache(proj)

    stem = plan_p.stem
    # Output is RUN-scoped, not plan-scoped. Loop 5 made the plan inbox unique
    # per run and left this half of the race in place: two agents running the
    # same plan in one wave wrote shots to the same `.gd_out/<plan>/shots/`, so
    # a critic could be handed another run's frames without either agent
    # noticing. That is a false-pass path - the look pass grading the wrong
    # images - and it was observed: a directory refilling from 1 to 6 files with
    # different bytes while it was being read.
    run_id = "%d-%s" % (os.getpid(), uuid.uuid4().hex[:8])
    outdir = Path(a.out).resolve() if a.out else (proj / ".gd_out" / stem / run_id)
    shutil.rmtree(outdir, ignore_errors=True)
    (outdir / "shots").mkdir(parents=True, exist_ok=True)

    # A UNIQUE inbox per run. The single shared `_inbox/plan.json` made
    # concurrent playtests silently swap plans: two overlapping runs in one
    # parallel wave produced a green PASS reported under the *other* plan's
    # name. A false green is the worst failure this system can produce, and
    # `/gd:run` dispatches parallel waves by design.
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
    # Shots are declared PER STEP (`{"shot": "name"}`), never as a top-level
    # `shots` key - which is what this used to look for. So `want_shots` was
    # always false and every screenshot the system has ever taken was rendered
    # at playtest_resolution (640x360) instead of shot_resolution (1280x720).
    # Every critic look pass was grading half-resolution frames, and pixel-level
    # critiques ("an 8 px sliver", "13 px of fox height") were measured against
    # the wrong ruler. That is the look half of Law 5 quietly mis-calibrated.
    has_shot_step = any(isinstance(st, dict) and (st.get("shot") or st.get("shot_after"))
                        for st in plan.get("steps", []))
    want_shots = (has_shot_step or bool(plan.get("shots"))) and not a.headless
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
            "--out=res://.gd_out/%s/%s" % (stem, run_id)]

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
    declared_n = len([c for c in plan.get("checks", []) if isinstance(c, dict)])
    reported_n = len([c for c in verdict.get("checks", []) if c.get("kind")])
    if declared_n and reported_n < declared_n:
        mismatch.append(
            "plan declares %d check(s) but the verdict reports only %d - checks "
            "went missing during evaluation, so this result describes less than "
            "it appears to" % (declared_n, reported_n))
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
    verdict["resolution"] = res
    _fp = system_fingerprint()
    verdict["system"] = {"version": _fp["version"], "hash": _fp["hash"]}
    if harness_upgraded:
        verdict["harness_upgraded"] = harness_upgraded
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
    # Diagnostics the scene printed for itself. Without this the only way to
    # surface a measured number was to add a check whose real purpose was to
    # print it - which pushes measurement into the gate, where a loose bound is
    # invisible. `GDLAB ` prefixed lines land here verbatim.
    verdict["log"] = [ln.strip()[len("GDLAB "):] for ln in out.splitlines()
                      if ln.strip().startswith("GDLAB ")][:200]
    verdict["runtime_errors"] = runtime_errors
    verdict["budget_fails"] = fails
    verdict["ok"] = bool(verdict.get("passed")) and not fails and not runtime_errors
    write_json_atomic(vfile, verdict)

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
    if verdict["log"]:
        print("  log       %d line(s) from the scene:" % len(verdict["log"]))
        for ln in verdict["log"][:8]:
            print("            " + ln[:150])
        if len(verdict["log"]) > 8:
            print("            ... %d more in verdict.json" % (len(verdict["log"]) - 8))
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
        "## (gatekeeper/config.json overridden by .planning/config.json). Do not edit.",
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
    ap = argparse.ArgumentParser(prog="gd", description="Gatekeeper toolchain CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("setup", help="detect Godot and Blender on this machine and "
                       "record them (run once, before anything else)")
    p.add_argument("--godot", help="path to the Godot executable, if autodetection fails")
    p.add_argument("--blender", help="path to the Blender executable")
    p.add_argument("--godot-source", help="optional: an engine source checkout, for "
                   "reading C++ when the class reference is ambiguous")
    p.add_argument("--show", action="store_true", help="print what is recorded, change nothing")
    p.add_argument("--force", action="store_true", help="overwrite without commenting")
    p.add_argument("--no-index", action="store_true", help="skip building the API index")
    p.set_defaults(fn=cmd_setup)

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

    p = sub.add_parser("models",
                       help="show model routing, and flag config/frontmatter drift")
    p.add_argument("--host", default="",
                   help="claude, codex, or all (default: the detected host)")
    p.set_defaults(fn=cmd_models)

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
    try:
        return a.fn(a)
    finally:
        release_locks()


if __name__ == "__main__":
    raise SystemExit(main())

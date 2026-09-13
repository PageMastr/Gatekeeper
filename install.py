#!/usr/bin/env python3
"""Install GSD-GameDev at user scope, so /gd:* works in any Claude Code session.

    python install.py              # copy into ~/.claude
    python install.py --link       # junction/symlink gsd-gd/ instead of copying
    python install.py --dry-run    # show what would happen, change nothing
    python install.py --no-setup   # skip the toolchain wizard
    python install.py --uninstall  # remove it again

What it installs:

  ~/.claude/gsd-gd/          the system itself - config, templates, lib, harness,
                             bin/gd.py, bin/gddoc.py, references
  ~/.claude/commands/gd/     the slash commands
  ~/.claude/agents/          the gd-* agents
  ~/.claude/skills/          the godot-api skill
  ~/.claude/settings.json    permissions merged in, never overwritten

What it deliberately does NOT touch:

  ~/.claude/gsd-gd.machine.json   this machine's Godot and Blender paths
  ~/.claude/gsd-gd-cache/         the generated API index

Both live outside the payload precisely so that upgrading is safe. An install
that silently unsets the user's engine path is indistinguishable from a broken
release, and re-indexing 1000 classes on every upgrade is pure waste.

Commands and agents are *rewritten* on the way in: every `python gsd-gd/bin/...`
becomes an absolute path, and every `@gsd-gd/references/...` include becomes an
explicit "read this absolute path" instruction. Relative paths only resolve when
the cwd happens to be the repo, which is exactly what a user-scope install is
not.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
HOME_CLAUDE = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))

SYS_NAME = "gsd-gd"
MACHINE_CONFIG = HOME_CLAUDE / "gsd-gd.machine.json"
PAYLOAD = [
    ("commands/gd", SRC / ".claude" / "commands" / "gd"),
    ("agents", SRC / ".claude" / "agents"),
    ("skills/godot-api", SRC / ".claude" / "skills" / "godot-api"),
]
# Only the two entry points. The engine binaries are launched by gd.py as
# subprocesses, so there is nothing machine-specific to allow here - which is
# what lets one settings.json work on every machine.
PERMS = [
    "Bash(python ~/.claude/gsd-gd/bin/gd.py:*)",
    "Bash(python ~/.claude/gsd-gd/bin/gddoc.py:*)",
]


def say(msg: str) -> None:
    print("  " + msg)


def rewrite(text: str, sys_dir: Path) -> str:
    """Make a command/agent file work from any cwd."""
    p = str(sys_dir).replace("\\", "/")
    # 1. CLI invocations -> absolute
    text = text.replace("python gsd-gd/bin/gd.py", 'python "%s/bin/gd.py"' % p)
    text = text.replace("python gsd-gd/bin/gddoc.py", 'python "%s/bin/gddoc.py"' % p)
    # 2. @-includes -> an explicit read of an absolute path. An @-include is
    #    resolved relative to the project, so at user scope it would silently
    #    include nothing - the worst possible failure for a doctrine file.
    def to_read(mo):
        rel = mo.group(1)
        return ("**Read `%s/%s` before continuing** — required reading, not "
                "optional context." % (p, rel))
    text = re.sub(r"^@gsd-gd/(\S+)\s*$", to_read, text, flags=re.M)
    # 3. Any other bare reference to the repo-relative system path
    text = text.replace("`gsd-gd/", "`%s/" % p)
    text = text.replace("(gsd-gd/", "(%s/" % p)
    return text


def copy_system(sys_dir: Path, link: bool, dry: bool) -> str:
    src = SRC / SYS_NAME
    if dry:
        return "would " + ("link" if link else "copy")
    if sys_dir.exists() or sys_dir.is_symlink():
        if sys_dir.is_symlink() or (os.name == "nt" and sys_dir.is_dir()
                                    and not (sys_dir / "config.json").exists()):
            try:
                sys_dir.unlink()
            except OSError:
                shutil.rmtree(sys_dir, ignore_errors=True)
        else:
            shutil.rmtree(sys_dir, ignore_errors=True)
    sys_dir.parent.mkdir(parents=True, exist_ok=True)
    if link:
        # A junction needs no admin rights on Windows and lets edits in the repo
        # take effect immediately - useful while still changing the system.
        if os.name == "nt":
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(sys_dir), str(src)],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return "linked (junction)"
            say("junction failed (%s) - falling back to a copy"
                % (r.stderr or r.stdout).strip()[:120])
        else:
            try:
                sys_dir.symlink_to(src, target_is_directory=True)
                return "linked (symlink)"
            except OSError as e:
                say("symlink failed (%s) - falling back to a copy" % e)
    shutil.copytree(src, sys_dir,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "cache"))
    return "copied"


def merge_settings(sys_dir: Path, dry: bool) -> list:
    """Add our permissions without touching anything else in settings.json."""
    f = HOME_CLAUDE / "settings.json"
    data = {}
    if f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ["settings.json is not valid JSON - left untouched; add "
                    "permissions manually: " + ", ".join(PERMS)]
    perms = data.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    abs_perms = [x.replace("~/.claude/gsd-gd", str(sys_dir).replace("\\", "/"))
                 for x in PERMS]
    added = [x for x in abs_perms if x not in allow]
    notes = []
    if added:
        if not dry:
            if f.exists():
                shutil.copy2(f, f.with_suffix(".json.gd-backup"))
            allow.extend(added)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data, indent=2), encoding="utf-8")
        notes.append(("would add " if dry else "added ") + "%d permission(s)" % len(added))
        if f.exists() and not dry:
            notes.append("backup at " + f.with_suffix(".json.gd-backup").name)
    else:
        notes.append("permissions already present")
    return notes


def toolchain_configured() -> bool:
    """True if `gd setup` has already run and named a Godot binary that exists."""
    if not MACHINE_CONFIG.exists():
        return False
    try:
        c = json.loads(MACHINE_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    g = ((c.get("toolchain") or {}).get("godot") or {})
    b = ((c.get("toolchain") or {}).get("blender") or {})
    return bool(g.get("console") or g.get("editor")) and bool(b.get("exe"))


def run_setup(sys_dir: Path) -> bool:
    """Hand off to the wizard, which owns detection and the machine config.

    Deliberately a subprocess call rather than duplicated logic: detection rules
    change as people report where their engines live, and two copies of them
    would diverge immediately.
    """
    r = subprocess.run([sys.executable, str(sys_dir / "bin" / "gd.py"), "setup"])
    return r.returncode == 0


def install(a) -> int:
    sys_dir = HOME_CLAUDE / SYS_NAME
    print("\nGSD-GameDev -> " + str(HOME_CLAUDE))
    if a.dry_run:
        print("  (dry run - nothing will be written)")
    print("")

    if not (SRC / SYS_NAME / "config.json").exists():
        print("install.py must be run from the GSD-GameDev repo root", file=sys.stderr)
        return 2
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required (found %s)"
              % sys.version.split()[0], file=sys.stderr)
        return 2

    say("system:   " + copy_system(sys_dir, a.link, a.dry_run) + " -> " + str(sys_dir))

    total = 0
    for dest_rel, src_dir in PAYLOAD:
        if not src_dir.is_dir():
            say("SKIP %s (not found in repo)" % dest_rel)
            continue
        dest = HOME_CLAUDE / dest_rel
        n = 0
        for f in sorted(src_dir.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in (".md", ".json"):
                continue
            out = dest / f.relative_to(src_dir)
            if not a.dry_run:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rewrite(f.read_text(encoding="utf-8"), sys_dir),
                               encoding="utf-8")
            n += 1
        total += n
        say("%-18s %d file(s) -> %s" % (dest_rel + ":", n, dest))
    say("rewrote %d file(s) to use absolute paths" % total)

    for note in merge_settings(sys_dir, a.dry_run):
        say("settings: " + note)

    if a.dry_run:
        say("toolchain: would run `gd setup` if %s is absent" % MACHINE_CONFIG.name)
        return 0

    # The machine config is never written by the installer and never deleted by
    # it. It is only *created*, by the wizard, and only when it is not there.
    if toolchain_configured():
        say("toolchain: already configured in %s (left untouched)" % MACHINE_CONFIG)
    elif a.no_setup:
        say("toolchain: not configured - run `gd setup` before using the system")
    else:
        print("")
        print("  The toolchain has not been configured on this machine yet.")
        print("  Running the setup wizard - it looks for Godot and Blender and")
        print("  asks only for what it cannot find.")
        if not run_setup(sys_dir):
            print("")
            print("  Setup did not complete. Run it again when the engines are")
            print("  installed:  python %s setup" % (sys_dir / "bin" / "gd.py"))
            print("  Everything else is installed and will work once it does.")
            return 1

    d = subprocess.run([sys.executable, str(sys_dir / "bin" / "gd.py"), "doctor"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    say("doctor:   " + ("all checks pass" if '"ok": true' in (d.stdout or "")
                        else "FAILED - see below"))
    if '"ok": true' not in (d.stdout or ""):
        print((d.stdout or "")[-1800:])
        print((d.stderr or "")[-500:], file=sys.stderr)

    print("""
Done. In any Claude Code session, from any directory:

    /gd:new     a snowbound cabin at night, one fire, something out there
    /gd:run

`.planning/` and `game/` are created in whatever directory you are working in,
not in the install - so each game keeps its own contracts, and nothing one game
sets can reach another. `gd doctor` prints the resolved system and work roots if
you are ever unsure which is which.

Three config layers, lowest first:
  1. %s
     shipped defaults - replaced on every upgrade, no paths, no game data
  2. %s
     this machine's toolchain - written by `gd setup`, never touched by install
  3. <your game>/.planning/config.json
     that game's numbers - budget, playtest defaults, model routing

To pin the workspace explicitly, set GD_PROJECT to its path.
""" % (sys_dir / "config.json", MACHINE_CONFIG))
    return 0


def uninstall(a) -> int:
    sys_dir = HOME_CLAUDE / SYS_NAME
    print("\nRemoving GSD-GameDev from " + str(HOME_CLAUDE) + "\n")
    targets = [sys_dir, HOME_CLAUDE / "commands" / "gd",
               HOME_CLAUDE / "skills" / "godot-api"]
    for t in targets:
        if t.exists() or t.is_symlink():
            if not a.dry_run:
                try:
                    t.unlink()
                except OSError:
                    shutil.rmtree(t, ignore_errors=True)
            say(("would remove " if a.dry_run else "removed ") + str(t))
    agents = HOME_CLAUDE / "agents"
    n = 0
    if agents.is_dir():
        for f in sorted(agents.glob("gd-*.md")):
            if not a.dry_run:
                f.unlink()
            n += 1
    say(("would remove " if a.dry_run else "removed ") + "%d gd-* agent file(s)" % n)
    # Detection took real effort and the cache took real time. Removing the
    # system should not punish a reinstall, and neither file is harmful if the
    # system never comes back.
    if a.purge:
        for t in (MACHINE_CONFIG, HOME_CLAUDE / "gsd-gd-cache"):
            if t.exists():
                if not a.dry_run:
                    try:
                        t.unlink()
                    except OSError:
                        shutil.rmtree(t, ignore_errors=True)
                say(("would remove " if a.dry_run else "removed ") + str(t))
    else:
        say("kept %s and the API cache (--purge removes them too)"
            % MACHINE_CONFIG.name)
    say("settings.json permissions left in place (harmless); a backup may exist "
        "as settings.json.gd-backup")
    print("")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Install GSD-GameDev at user scope")
    ap.add_argument("--link", action="store_true",
                    help="junction/symlink gsd-gd instead of copying, so repo edits take effect live")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-setup", action="store_true",
                    help="do not run the toolchain wizard")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--purge", action="store_true",
                    help="with --uninstall: also remove the machine config and API cache")
    a = ap.parse_args()
    return uninstall(a) if a.uninstall else install(a)


if __name__ == "__main__":
    raise SystemExit(main())

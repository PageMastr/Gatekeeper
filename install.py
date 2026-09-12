#!/usr/bin/env python3
"""Install GSD-GameDev at user scope, so /gd:* works in any Claude Code session.

    python install.py              # copy into ~/.claude
    python install.py --link       # junction gsd-gd/ instead of copying it
    python install.py --dry-run    # show what would happen, change nothing
    python install.py --uninstall  # remove it again

What it does, and why each step is needed:

  ~/.claude/gsd-gd/          the system itself - config, templates, lib, harness,
                             bin/gd.py, bin/gddoc.py, references, cache
  ~/.claude/commands/gd/     the 17 slash commands
  ~/.claude/agents/          the 10 agents
  ~/.claude/skills/          the godot-api skill
  ~/.claude/settings.json    permissions merged in, never overwritten

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
PAYLOAD = [
    ("commands/gd", SRC / ".claude" / "commands" / "gd"),
    ("agents", SRC / ".claude" / "agents"),
    ("skills/godot-api", SRC / ".claude" / "skills" / "godot-api"),
]
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


def install(a) -> int:
    sys_dir = HOME_CLAUDE / SYS_NAME
    print("\nGSD-GameDev -> " + str(HOME_CLAUDE))
    if a.dry_run:
        print("  (dry run - nothing will be written)")
    print("")

    if not (SRC / SYS_NAME / "config.json").exists():
        print("install.py must be run from the GSD-GameDev repo root", file=sys.stderr)
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

    if not a.dry_run:
        idx = subprocess.run([sys.executable, str(sys_dir / "bin" / "gddoc.py"), "index"],
                             capture_output=True, text=True)
        m = re.search(r'"classes":\s*(\d+)', idx.stdout or "")
        say("api index: " + (m.group(1) + " classes" if m
                             else "FAILED - run gddoc.py index by hand"))
        d = subprocess.run([sys.executable, str(sys_dir / "bin" / "gd.py"), "doctor"],
                           capture_output=True, text=True)
        say("doctor:   " + ("all checks pass" if '"ok": true' in (d.stdout or "")
                            else "FAILED - see below"))
        if '"ok": true' not in (d.stdout or ""):
            print(d.stdout[-1500:])
            print(d.stderr[-500:], file=sys.stderr)

    print("""
Done. In any Claude Code session, from any directory:

    /gd:new     a snowbound cabin at night, one fire, something out there
    /gd:run

`.planning/` and `game/` are created in whatever directory you are working in,
not in the install - so each game keeps its own contracts. `gd doctor` prints
the resolved `system` and `work` roots if you are ever unsure which is which.

To pin the workspace explicitly, set GD_PROJECT to its path.
""")
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
    say("settings.json permissions left in place (harmless); a backup may exist "
        "as settings.json.gd-backup")
    print("")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Install GSD-GameDev at user scope")
    ap.add_argument("--link", action="store_true",
                    help="junction/symlink gsd-gd instead of copying, so repo edits take effect live")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    return uninstall(a) if a.uninstall else install(a)


if __name__ == "__main__":
    raise SystemExit(main())

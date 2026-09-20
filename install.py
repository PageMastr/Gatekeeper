#!/usr/bin/env python3
"""Install Gatekeeper at user scope, for Claude Code and/or Codex.

    python install.py                # whichever front-ends are present
    python install.py --host codex   # just Codex
    python install.py --host both    # both, even if one is not installed yet
    python install.py --link         # junction/symlink gatekeeper/ instead of copying
    python install.py --dry-run      # show what would happen, change nothing
    python install.py --no-setup     # skip the toolchain wizard
    python install.py --uninstall    # remove it again

The system payload is installed ONCE and shared by every front-end: two copies
would mean two `gd version` fingerprints on one machine, and a verdict could
then name a toolchain the other host had already moved past.

What it installs:

  ~/.claude/gatekeeper/          the system itself - config, templates, lib, harness,
                             bin/gd.py, bin/gddoc.py, references
  ~/.claude/commands/gd/     the slash commands
  ~/.claude/agents/          the gd-* agents
  ~/.claude/skills/          the godot-api skill
  ~/.claude/settings.json    permissions merged in, never overwritten

What it deliberately does NOT touch:

  ~/.claude/gatekeeper.machine.json   this machine's Godot and Blender paths
  ~/.claude/gatekeeper-cache/         the generated API index

Both live outside the payload precisely so that upgrading is safe. An install
that silently unsets the user's engine path is indistinguishable from a broken
release, and re-indexing 1000 classes on every upgrade is pure waste.

Commands and agents are *rewritten* on the way in: every `python gatekeeper/bin/...`
becomes an absolute path, and every `@gatekeeper/references/...` include becomes an
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
HOME_CODEX = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))

SYS_NAME = "gatekeeper"
MACHINE_CONFIG = HOME_CLAUDE / "gatekeeper.machine.json"
PAYLOAD = [
    ("commands/gd", SRC / ".claude" / "commands" / "gd"),
    ("agents", SRC / ".claude" / "agents"),
    ("skills/godot-api", SRC / ".claude" / "skills" / "godot-api"),
]

# ---------------------------------------------------------------------------
# Codex front-end.
#
# `.claude/` stays the only place a command or an agent is *written*. Codex
# gets the same files rendered into its own shape at install time, because two
# hand-maintained copies of the same doctrine is how they drift - and doctrine
# that drifts silently is worse than doctrine that is missing.
#
# Two shapes differ, so two names differ:
#   command  X.md      ->  skills/gd-X          typed as  $gd-X
#   agent    gd-Y.md   ->  skills/gd-agent-Y    dispatched, rarely typed
# The qualifier is on the agents because `perf` exists as both a command and an
# agent, and the user types commands.
CODEX_CMD_PREFIX = "gd-"
CODEX_AGENT_PREFIX = "gd-agent-"


def codex_skill_name(stem: str, kind: str) -> str:
    if kind == "agent":
        return CODEX_AGENT_PREFIX + stem[3:] if stem.startswith("gd-") else \
            CODEX_AGENT_PREFIX + stem
    return CODEX_CMD_PREFIX + stem
# Only the two entry points. The engine binaries are launched by gd.py as
# subprocesses, so there is nothing machine-specific to allow here - which is
# what lets one settings.json work on every machine.
PERMS = [
    "Bash(python ~/.claude/gatekeeper/bin/gd.py:*)",
    "Bash(python ~/.claude/gatekeeper/bin/gddoc.py:*)",
]


def say(msg: str) -> None:
    print("  " + msg)


def rewrite(text: str, sys_dir: Path) -> str:
    """Make a command/agent file work from any cwd."""
    p = str(sys_dir).replace("\\", "/")
    # 1. CLI invocations -> absolute
    text = text.replace("python gatekeeper/bin/gd.py", 'python "%s/bin/gd.py"' % p)
    text = text.replace("python gatekeeper/bin/gddoc.py", 'python "%s/bin/gddoc.py"' % p)
    # 2. @-includes -> an explicit read of an absolute path. An @-include is
    #    resolved relative to the project, so at user scope it would silently
    #    include nothing - the worst possible failure for a doctrine file.
    def to_read(mo):
        rel = mo.group(1)
        return ("**Read `%s/%s` before continuing** — required reading, not "
                "optional context." % (p, rel))
    text = re.sub(r"^@gatekeeper/(\S+)\s*$", to_read, text, flags=re.M)
    # 3. Any other bare reference to the repo-relative system path
    text = text.replace("`gatekeeper/", "`%s/" % p)
    text = text.replace("(gatekeeper/", "(%s/" % p)
    return text


def split_frontmatter(text: str) -> tuple:
    """(dict-ish frontmatter, body). Values stay strings; nothing here needs YAML."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head, body = text[3:end], text[end + 4:].lstrip("\n")
    fm, key = {}, None
    for line in head.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            fm[key] = m.group(2).strip()
        elif key:                       # a folded continuation line
            fm[key] += " " + line.strip()
    return fm, body


# What a Codex session needs to know that a Claude session does not. Injected
# once per skill rather than rewritten through the doctrine text: the laws are
# quoted verbatim in a dozen places, and a regex confident enough to rewrite
# them is a regex confident enough to corrupt them.
CODEX_NOTE = """\
> **Host note — Codex.** This system is written host-neutral and installed for
> both Codex and Claude Code. Where the text below says:
>
> - `/gd:<name>` — invoke `$gd-<name>` instead.
> - a `gd-<role>` agent (gd-mechanics, gd-critic, …) — that is the skill
>   `$gd-agent-<role>`. Its starting model and the escalation ladder come from
>   `gd models --host codex`, never from your own judgement (Law 10).
> - "the Task tool" / "spawn a subagent" — start a **fresh `codex exec` session**
>   with the job file and its gate, at the model `gd run next` names:
>   `codex exec -m <model> "<job prompt>"`. One job, one fresh session (Law 2) is
>   the point of this, and it holds identically here.
> - "AskUserQuestion" — just ask, in the conversation, and wait.
> - `$ARGUMENTS` — whatever you typed after the skill name.
>
> Everything else — the gates, the harness, the budget, the Color Bible — is the
> same system and the same numbers. `gd` is the single source of truth on both
> hosts.
"""


def render_codex_skill(text: str, stem: str, kind: str, sys_dir: Path) -> str:
    """One Claude command or agent, as a Codex SKILL.md."""
    fm, body = split_frontmatter(text)
    name = codex_skill_name(stem, kind)
    desc = fm.get("description", "").strip()
    if kind == "agent" and fm.get("model"):
        # The Claude frontmatter model is Claude's. Saying so beats deleting it
        # silently and letting a reader assume Codex inherits it.
        body = ("*(Routing for this role on Codex comes from "
                "`gd models --host codex`, not from any frontmatter.)*\n\n") + body
    out = ["---", "name: " + name, "description: " + desc, "---", ""]
    out.append(CODEX_NOTE)
    out.append("")
    out.append(body)
    text = "\n".join(out)
    # Cross-references between our own commands, so `$gd-run` resolves.
    text = re.sub(r"/gd:([a-z]+)", lambda m: "$gd-" + m.group(1), text)
    return rewrite(text, sys_dir)


def install_codex(sys_dir: Path, dry: bool) -> int:
    """Render the .claude/ command and agent files into ~/.codex/skills."""
    skills = HOME_CODEX / "skills"
    jobs = [(SRC / ".claude" / "commands" / "gd", "command"),
            (SRC / ".claude" / "agents", "agent")]
    n = 0
    for src_dir, kind in jobs:
        if not src_dir.is_dir():
            say("SKIP %s (not found in repo)" % src_dir.name)
            continue
        for f in sorted(src_dir.glob("*.md")):
            name = codex_skill_name(f.stem, kind)
            out = skills / name / "SKILL.md"
            if not dry:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    render_codex_skill(f.read_text(encoding="utf-8"),
                                       f.stem, kind, sys_dir),
                    encoding="utf-8")
            n += 1
    # The one real skill ships as-is; its frontmatter is already the shape
    # Codex wants, so rendering it would only risk changing it.
    ga = SRC / ".claude" / "skills" / "godot-api"
    if ga.is_dir():
        for f in sorted(ga.rglob("*")):
            if not f.is_file():
                continue
            out = skills / "godot-api" / f.relative_to(ga)
            if not dry:
                out.parent.mkdir(parents=True, exist_ok=True)
                if f.suffix.lower() == ".md":
                    out.write_text(rewrite(f.read_text(encoding="utf-8"), sys_dir),
                                   encoding="utf-8")
                else:
                    shutil.copy2(f, out)
            n += 1
    say("%-18s %d file(s) -> %s" % ("codex skills:", n, skills))
    return n


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
    abs_perms = [x.replace("~/.claude/gatekeeper", str(sys_dir).replace("\\", "/"))
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


def hosts_present() -> list:
    """Which front-ends look installed on this machine."""
    out = []
    if HOME_CLAUDE.is_dir():
        out.append("claude")
    if HOME_CODEX.is_dir():
        out.append("codex")
    return out


def system_home(hosts: list) -> Path:
    """Where the one shared system payload lives.

    One payload, however many front-ends: two copies would mean two
    `gd version` fingerprints on one machine, and a verdict could then name a
    toolchain the other front-end had already moved past.

    An existing install wins over any preference. Installing the Codex
    front-end on a machine that already has the system under ~/.claude must
    *reuse* it, not plant a second copy next door - which is the whole point of
    the rule, and the easiest place to break it.
    """
    for home in (HOME_CLAUDE, HOME_CODEX):
        if (home / SYS_NAME / "config.json").exists():
            return home
    return HOME_CLAUDE if "claude" in hosts else HOME_CODEX


def resolve_hosts(want: str) -> list:
    if want in ("claude", "codex"):
        return [want]
    if want == "both":
        return ["claude", "codex"]
    found = hosts_present()
    # Nothing detected is not an error: Claude is the historical default, and a
    # first install on a clean machine should still land somewhere sensible.
    return found or ["claude"]


def install(a) -> int:
    hosts = resolve_hosts(getattr(a, "host", "auto"))
    sys_home = system_home(hosts)
    sys_dir = sys_home / SYS_NAME
    print("\nGatekeeper -> " + ", ".join(hosts))
    print("  system:  " + str(sys_dir) + "   (shared by every front-end)")
    if a.dry_run:
        print("  (dry run - nothing will be written)")
    print("")

    if not (SRC / SYS_NAME / "config.json").exists():
        print("install.py must be run from the Gatekeeper repo root", file=sys.stderr)
        return 2
    if sys.version_info < (3, 10):
        print("Python 3.10 or newer is required (found %s)"
              % sys.version.split()[0], file=sys.stderr)
        return 2

    say("system:   " + copy_system(sys_dir, a.link, a.dry_run) + " -> " + str(sys_dir))

    total = 0
    if "claude" in hosts:
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
    if "codex" in hosts:
        total += install_codex(sys_dir, a.dry_run)
    say("rewrote %d file(s) to use absolute paths" % total)

    if "claude" in hosts:
        for note in merge_settings(sys_dir, a.dry_run):
            say("settings: " + note)
    if "codex" in hosts:
        # Codex approves commands through its own sandbox policy, not through a
        # permissions list we could merge, so there is nothing to write here -
        # and writing to config.toml would be editing a file the user owns.
        say("settings: codex approves commands through its own sandbox policy; "
            "nothing written to config.toml")

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

    how = []
    if "claude" in hosts:
        how.append("  Claude Code:   /gd:new  a snowbound cabin at night, "
                   "one fire, something out there\n"
                   "                 /gd:run")
    if "codex" in hosts:
        how.append("  Codex:         $gd-new  a snowbound cabin at night, "
                   "one fire, something out there\n"
                   "                 $gd-run")
    print("""
Done. From any directory:

%s

Both front-ends drive the same `gd`, the same harness and the same gates.
`gd models --host all` shows what each one routes to; `gd config` prints which
host is active and why.
""" % "\n".join(how))
    print("""\

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
    hosts = resolve_hosts(getattr(a, "host", "auto"))
    sys_home = system_home(hosts)
    sys_dir = sys_home / SYS_NAME
    print("\nRemoving Gatekeeper (%s) from %s\n" % (", ".join(hosts), sys_home))
    # Removing one front-end must not take the shared payload with it, or the
    # other front-end is left with commands pointing at nothing.
    other = {"claude", "codex"} - set(hosts)
    targets = [] if other else [sys_dir]
    if other:
        say("system:   kept at %s (still used by %s)"
            % (sys_dir, ", ".join(sorted(other))))
    if "claude" in hosts:
        targets += [HOME_CLAUDE / "commands" / "gd",
                    HOME_CLAUDE / "skills" / "godot-api"]
    if "codex" in hosts:
        skills = HOME_CODEX / "skills"
        targets.append(skills / "godot-api")
        if skills.is_dir():
            targets += [d for d in sorted(skills.iterdir())
                        if d.is_dir() and d.name.startswith("gd-")]
    for t in targets:
        if t.exists() or t.is_symlink():
            if not a.dry_run:
                try:
                    t.unlink()
                except OSError:
                    shutil.rmtree(t, ignore_errors=True)
            say(("would remove " if a.dry_run else "removed ") + str(t))
    n = 0
    agents = HOME_CLAUDE / "agents"
    if "claude" in hosts and agents.is_dir():
        for f in sorted(agents.glob("gd-*.md")):
            if not a.dry_run:
                f.unlink()
            n += 1
    say(("would remove " if a.dry_run else "removed ") + "%d gd-* agent file(s)" % n)
    # Detection took real effort and the cache took real time. Removing the
    # system should not punish a reinstall, and neither file is harmful if the
    # system never comes back.
    if a.purge:
        for t in (MACHINE_CONFIG, HOME_CLAUDE / "gatekeeper-cache"):
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
    ap = argparse.ArgumentParser(description="Install Gatekeeper at user scope")
    ap.add_argument("--link", action="store_true",
                    help="junction/symlink gatekeeper instead of copying, so repo edits take effect live")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-setup", action="store_true",
                    help="do not run the toolchain wizard")
    ap.add_argument("--host", default="auto",
                    choices=["auto", "claude", "codex", "both"],
                    help="which front-end(s) to install for "
                         "(default: auto - whichever are present)")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--purge", action="store_true",
                    help="with --uninstall: also remove the machine config and API cache")
    a = ap.parse_args()
    return uninstall(a) if a.uninstall else install(a)


if __name__ == "__main__":
    raise SystemExit(main())

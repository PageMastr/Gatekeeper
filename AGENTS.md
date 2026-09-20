# Gatekeeper — Codex entry point

**Read `CLAUDE.md` in this directory, then `gatekeeper/references/laws.md`.**
That is the system. This file exists only because Codex looks for `AGENTS.md`
and Claude Code looks for `CLAUDE.md`, and the doctrine must not be written
twice — two copies of a rulebook drift, and a rulebook that drifts silently is
worse than one that is missing.

Everything in `CLAUDE.md` applies here unchanged. The laws, the gates, the
harness, the budget, the Color Bible and every number in them are about Godot
and Blender, not about what is driving the keyboard.

## The only differences

| `CLAUDE.md` says | under Codex |
|---|---|
| `/gd:run`, `/gd:new`, `/gd:plan` … | `$gd-run`, `$gd-new`, `$gd-plan` … |
| the `gd-mechanics` agent | the skill `$gd-agent-mechanics` |
| "the Task tool", "spawn a subagent" | a fresh `codex exec -m <model> "<job>"` |
| `model:` frontmatter on an agent file | nothing — a skill cannot pin a model |
| `~/.claude/gatekeeper/` | wherever `gd doctor` says the system root is |

The command and agent skills under `~/.codex/skills/` are **rendered from
`.claude/` at install time**, not authored separately. Do not hand-edit them:
the next `python install.py` overwrites them, and the edit is lost without a
record. Change the file in `.claude/` and re-run the installer.

## Model routing

`gd run` owns the escalation ladder and picks the model. No agent picks its own
(Law 10). On Codex:

```
gpt-5.6-luna → gpt-5.6-terra → gpt-5.6-sol → gpt-6-astra
3 attempts at the job's tier → climb → 3 more → … → 3 at the top → stop
```

```bash
python gatekeeper/bin/gd.py models --host codex   # the table and the reasons
python gatekeeper/bin/gd.py config                # which host is active, and why
```

Because a Codex skill has no `model:` surface, there is no second place for a
routing decision to live and nothing for `gd models` to drift-check. The config
table is the whole decision — which makes it the only thing to keep honest.

## One job, one fresh session

`codex exec` starting a new process per job is not a workaround for a missing
Task tool. It is Law 2 with a different spelling, and the reason behind it is
unchanged: a session carrying nine other jobs reads more, holds more, and makes
more mistakes — and when it fails you cannot tell which of the ten broke.

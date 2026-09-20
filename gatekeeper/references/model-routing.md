# Model routing

Different models are good at different parts of a game. Routing by role is
cheaper *and* better than sending everything to one model: the planner keeps a
clean context because it never builds, and the aesthetic work goes to whichever
model actually has taste.

## Where the routing lives

**`gatekeeper/config.json` → `models` is the single source of truth.** Each agent's
starting model is stored there *with the reason it was chosen*, because a routing
decision without a reason gets changed back by the next person who looks at the
bill.

```bash
python gatekeeper/bin/gd.py models              # the active host's table
python gatekeeper/bin/gd.py models --host all   # every host, side by side
```

Two places name a model and they must agree: `models.agents` in the config (what
`gd run` dispatches and escalates with) and the `model:` frontmatter of each
`.claude/agents/*.md` (what Claude Code uses when an agent is spawned by name
with no override). `gd models` exits non-zero when they drift — nothing else
would tell you.

A `model` column in a phase's `PLAN.md` overrides the default for one job. Leave
it blank unless you have a reason.

## Two hosts, one routing decision

The system runs under **Claude Code** and **Codex**. Almost nothing differs: the
gates, the harness, the budget, the Color Bible and every law are about Godot
and Blender, not about what is holding the keyboard. Three things do.

| | Claude Code | Codex |
|---|---|---|
| a command | `/gd:run` | `$gd-run` |
| an agent | `.claude/agents/gd-mechanics.md` | the skill `$gd-agent-mechanics` |
| dispatching a job | Task tool, `subagent_type` | `codex exec -m <model> "<job>"` |
| per-agent model | `model:` frontmatter | **none — a skill cannot pin a model** |

That last row is the one with consequences. On Claude two surfaces name a model
and they can disagree, so `gd models` checks them. On Codex there is one, so
there is nothing to drift against — and `gd models --host codex` says exactly
that, rather than reporting ten agents as "missing a file", which would be noise
dressed as a warning.

**The roles and their reasons are host-neutral and stored once.** Only the tier
names differ, under `models.hosts.<host>`:

```
claude   haiku        -> sonnet        -> opus         -> fable
codex    gpt-5.6-luna -> gpt-5.6-terra -> gpt-5.6-sol  -> gpt-6-astra
```

The active host is `GD_HOST`, else `models.host` in config, else detected from
the environment (`CLAUDECODE` / `CODEX_*`). `gd config` prints which, and why.

**Codex's ladder is a first pass.** It was mapped by matching each role's
*capability need*, not by lining the two ladders up rung for rung — the four
taste roles sit at the top on both hosts, but the engine roles start at
`gpt-5.6-terra` with two rungs above them rather than at the third rung. Tune it
against real escalation counts, and write the reason into the config when you do.

**A Codex session is still one job, one fresh session.** `codex exec` starting a
new process per job is not a workaround for a missing Task tool; it is Law 2
with a different spelling, and the context-hygiene argument below applies
unchanged.

## The roles

The `model` column is Claude's. `gd models --host codex` prints the same table
with Codex's tiers; the **why** is the same sentence on both, because it is a
statement about the role, not about the model.

| role | agent | model | why |
|---|---|---|---|
| Decompose, decide, judge | `gd-planner` | `fable` | Every job downstream inherits its mistakes, and it runs once per phase, so the cost is small. Never builds — that is what keeps its context clean through job forty. |
| Palette, lighting, coherence | `gd-art-director` | `fable` | Aesthetic contracts are taste, and taste is where models differ most visibly. |
| Independent critique of frames | `gd-critic` | `fable` | Pure visual judgement. A weak critic silently lowers the ceiling of every gauntlet round it accepts. Must never be the model that built the thing. |
| Blender generators, art assets | `gd-modeler` | `fable` | Asset work is an aesthetic task disguised as a scripting task. |
| Gameplay mechanics, engine code | `gd-mechanics` | `opus` | Correctness-critical *and* the highest-volume role — so not the place for the priciest tier. |
| Rigging, animation, gait | `gd-rigger` | `opus` | Precise iterative math across many attempts. |
| Performance triage | `gd-perf` | `opus` | A wrong bisection wastes the session, but the triage order is already written down. |
| Playtest harness + verdicts | `gd-playtester` | `sonnet` | Mechanical: write the plan, run it, report the numbers. No judgement, and it runs constantly. |
| Engine/API research | `gd-researcher` | `sonnet` | Volume reading, summary out, and every claim is checked against the local API index anyway. |
| Docs + learnings extraction | `gd-scribe` | `sonnet` | Reads a lot, writes prose, makes no engine judgements. |

Nothing defaults to `haiku`. It sits on the ladder as a floor for future cheap
roles; no current agent's job is mechanical enough to justify it, and a wrong
answer from a gate-facing agent costs more than the tier saves.

## The escalation ladder

`gd run` owns this, so no agent can talk itself into one more attempt:

```
claude   haiku → sonnet → opus → fable
codex    gpt-5.6-luna → gpt-5.6-terra → gpt-5.6-sol → gpt-6-astra

3 attempts at the job's tier → climb → 3 more → … → 3 at the top → stop
```

The number of attempts is host-neutral: three tries before climbing is a
statement about when to stop trying, not about any particular model.

A job that exhausts the ladder is **not** a model problem. Three failures at the
top tier means the job is underspecified or its gate asserts the wrong thing —
re-cut the job, or send it to `/gd:gauntlet` if the target is aesthetic.

## Why the split pays for itself

**Cache reads dominate the bill on a long build.** Hundreds of millions of cached
tokens at a fraction of a cent each add up to more than the output tokens do.
A more expensive model with cheaper cache reads can finish a week-long project
for *less* than a cheaper one — so per-token headline price is close to the
wrong number to optimise. Route on capability, and watch cache-read pricing, not
the input price.

**Fresh context beats a good model with a full one.** A mid-tier model on job one
of a clean session outperforms the best model on job twelve of a stuffed one.
This is the entire reason for one-job-one-session; model choice is a smaller
lever than context hygiene.

## Rules

1. **The orchestrator does not build.** If the planning session starts writing
   GDScript, the plan degrades from that point on. Hand it out.
2. **The critic is never the builder.** Non-negotiable. A model reviewing its own
   frames sees what it meant to make.
3. **One job, one fresh session.** Regardless of model.
4. **When a model runs out of budget mid-job, hand the job over — not the
   project.** The job file and its gate are the handoff; that is what they are
   for.
5. **Run the same job on two models when the output is a matter of taste** (a
   room, a creature, a light). Compare, keep one, record why in `CONTEXT.md`.
   This is the cheapest quality win available and costs one extra session.
6. **Do not route by price on aesthetic work.** It is the one place where the
   gap between models is visible to the player.

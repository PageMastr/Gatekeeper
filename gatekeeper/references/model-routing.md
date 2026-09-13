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
python gatekeeper/bin/gd.py models      # the table, plus drift detection
```

Two places name a model and they must agree: `models.agents` in the config (what
`gd run` dispatches and escalates with) and the `model:` frontmatter of each
`.claude/agents/*.md` (what Claude Code uses when an agent is spawned by name
with no override). `gd models` exits non-zero when they drift — nothing else
would tell you.

A `model` column in a phase's `PLAN.md` overrides the default for one job. Leave
it blank unless you have a reason.

## The roles

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
haiku → sonnet → opus → fable
3 attempts at the job's tier → climb → 3 more → … → 3 at the top → stop
```

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

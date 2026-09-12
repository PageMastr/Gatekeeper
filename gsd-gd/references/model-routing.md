# Model routing

Different models are good at different parts of a game. Routing by role is
cheaper *and* better than sending everything to one model: the planner keeps a
clean context because it never builds, and the aesthetic work goes to whichever
model actually has taste.

## The roles

| role | agent | model | why |
|---|---|---|---|
| Orchestrate, decide, judge | `gd-planner`, `gd-art-director` | `fable` | Hard calls and aesthetic judgement. Never builds — that is what keeps its context clean through job forty. |
| Gameplay mechanics, engine code | `gd-mechanics` | `opus` | Systems work, physics, state, shaders. |
| Blender generators, art assets | `gd-modeler` | `fable` | Asset work is an aesthetic task disguised as a scripting task. |
| Rigging, animation, gait | `gd-rigger` | `opus` | Precise, iterative, measurable. |
| Independent critique of frames | `gd-critic` | `fable` | Judges screenshots. Must never be the model that built them. |
| Playtest harness + verdicts | `gd-playtester` | `sonnet` | Mechanical: write the plan, run it, report. Cheap and repeatable. |
| Performance triage | `gd-perf` | `opus` | Measurement and bisection. |
| Docs/API research | `gd-researcher` | `sonnet` | Volume reading, summary out. |

Set with the Agent tool's `model` parameter. The agent definitions in
`.claude/agents/` already carry these defaults; override per job only with a
reason.

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

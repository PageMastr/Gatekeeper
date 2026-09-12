# System findings — {{NAME}}

> **Faults in the GSD-GameDev *system*, found while building this game.** Not
> bugs in the game — those are deviations, and they go in the job's Result.
>
> This file exists because a project inventing it spontaneously out-performed a
> dedicated observation loop. In one wave it caught a playtest race that
> produced a **green PASS filed under the wrong plan's name**, a gate that
> false-failed on autoloads (and had already bent that project's architecture
> into a workaround), and a `prop_eq` that could not compare integers. All three
> were real, all three are now fixed, and none would have been found by testing
> the system against itself.
>
> You are the only thing that uses this system under real load. Write down what
> you hit.

## How to file one

Append a row. Take the next `E.n`. Then **carry on with your job** — filing a
finding is not a licence to fix the system (Law 6b: never modify the instrument
that grades you). If it blocks you, say so in your Result and stop.

```bash
python <gd> now        # the timestamp - never type one from memory
```

**What makes a finding useful:**

- **The symptom, exactly as it appeared.** Paste the error. "Fails" is not a
  finding.
- **The mechanism, if you found it.** The best entries here cite engine source:
  *"`Main::start()` returns at `main.cpp:4372`, before autoloads register at
  `main.cpp:4509`"* is worth ten paragraphs of speculation. `gddoc` and the
  engine tree at the configured `source_root` are both available to you.
- **Whether it is a false pass or a false failure.** A false *pass* is an
  emergency — it means a gate certified something that was not true.
- **The workaround you used**, if any — so the fix can remove it later, and so
  nobody mistakes the workaround for the intended design.

## Findings

| # | finding | mechanism / evidence | severity | status |
|---|---|---|---|---|
| E.1 | | | | open |

**severity:** `false-pass` (a gate certified something untrue — highest),
`false-fail` (a gate rejected correct work), `blocks` (cannot proceed),
`friction` (works, costs time), `docs` (the system is right, its docs are not).

**status:** `open` → `reported` → `fixed in <version/commit>` / `wontfix: <why>`.

## Engine knowledge

Godot or Blender behaviour you had to discover, that the references did not
cover. `/gd:ship` folds these into `references/gdscript-4x.md`,
`godot-patterns.md` or `blender-patterns.md` so the next project starts with
them.

| # | behaviour | citation |
|---|---|---|
| | | |

## Workarounds currently in force

Anything this project does *because* the system is wrong. Each one is a debt:
when the finding is fixed, the workaround should come out, and it will not
unless it is written down here.

| finding | what we do instead | remove when |
|---|---|---|

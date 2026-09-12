# Core Loop — {{NAME}}

> The most common way an AI-built game dies: it looks right and has no loop.
> A pile of beautiful rooms is not a game. This file is the answer to "what is
> the player *doing*, over and over, and why do they want to do it again?"
>
> **Nothing past `/gd:greybox` gets built until the Minute One test below passes
> on grey boxes.** Art on top of a missing loop is wasted art.

## One sentence

<The player does X in order to get Y, at the risk of Z.>

Example shape: *The player goes out into the snow to gather wood so the fire
keeps burning, at the risk of freezing or being found.*

## The loop

| beat | player action | game response | why they repeat it |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | back to 1, but changed by… | | |

The loop is only real if beat 4 changes the state of beat 1. If the loop
returns to exactly the same starting conditions, it is a treadmill, not a loop.

## Tension

- **The pressure:** <what gets worse while the player does nothing>
- **The release:** <what the player can do about it>
- **The choice:** <the tradeoff that makes two players play differently>

A loop with no pressure is a chore list. A loop with pressure and no choice is
a timer.

## Minute One

What the player does in their first 60 seconds, written as a testable sequence.
This becomes the first playtest plan (`lab/minute_one.json`) and it must pass on
grey boxes before any asset work starts.

| t | what happens | how it is verified |
|---|---|---|
| 0–5s | | |
| 5–20s | | |
| 20–45s | | |
| 45–60s | | |

## Verticality check

Before art: can the player complete one **whole** turn of the loop, start to
finish, in the greybox? Not a slice of it — all of it.

- [ ] Loop completable in greybox
- [ ] Failure state reachable (you can lose)
- [ ] Loop verified by `gd playtest lab/minute_one.json`

## Scope fence

Named explicitly so it can be defended. Anything here is **not** in the first
milestone, no matter how cheap it looks mid-build.

- Not doing: <…>
- Not doing: <…>
- Not doing: <…>

## Change log

| date | change | why |
|---|---|---|
| {{DATE}} | created | |

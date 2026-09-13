# Core Loop — {{NAME}}

> The most common way an AI-built game dies: it looks right and has no loop.
> A pile of beautiful rooms is not a game. This file is the answer to "what is
> the player *doing*, over and over, and why do they want to do it again?"
>
> **Nothing past the greybox block gets built until one whole turn of this loop
> is playable on grey boxes, including losing.** Art on top of a missing loop is
> wasted art, and it is wasted late.

## One sentence

<The player does X in order to get Y, at the risk of Z.>

Example shape: *The player goes out into the snow to gather wood so the fire
keeps burning, at the risk of freezing or being found.*

If this takes a paragraph, it is several loops. Name the one the game is about;
the others are systems that feed it, and they belong in the roadmap's systems
inventory, not here.

## The loop

| beat | player action | game response | why they repeat it |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | back to 1, but changed by… | | |

**The loop is only real if beat 4 changes the state of beat 1.** If the loop
returns to exactly the same starting conditions it is a treadmill, not a loop —
and a treadmill passes every automated gate while staying unplayable.

Name the state that carries between turns, and where it lives:

- **What changes:** <the number/flag/world state that makes turn two different>
- **Where it lives:** <the node, the autoload, the texture>
- **How the player reads it:** <what they see; a change nobody can perceive is
  not a change>

## Tension

- **The pressure:** <what gets worse while the player does nothing>
- **The release:** <what the player can do about it>
- **The choice:** <the tradeoff that makes two players play differently>

A loop with no pressure is a chore list. A loop with pressure and no choice is
a timer.

## The failure state

Half of every loop, and the half almost every first pass forgets. `gd roadmap`
checks that the last greybox stage says something about losing.

- **How the player loses:** <…>
- **What warns them first:** <the tell, and how long before it is too late>
- **What happens on loss:** <restart, lose progress, wake up somewhere>
- **How it is proved:** `lab/can_lose.json` drives the player into it deliberately

## Minute One

What the player does in their first 60 seconds, as a testable sequence. This
becomes `lab/minute_one.json` and must pass on grey boxes before any asset work
starts, so write it specifically enough to script.

| t | what happens | how it is verified |
|---|---|---|
| 0–5s | | |
| 5–20s | | |
| 20–45s | | |
| 45–60s | | |

## Partial input — what the player does that the plan will not

A playtest plan presses exactly the keys it lists, so it proves the *machine's*
input path, never the player's. Every interaction needing more than one press
gets a row here, and `lab/partial_input.json` presses only the first half.

This exists because a phase once passed a green gate on 220 checks across 18
plans and then failed a five-minute human playtest in three ways — every one
invisible to every gate, because asking a crew member took two presses and no
plan modelled the player who pressed one.

| interaction | the full input | what pressing only part of it must NOT do |
|---|---|---|
| <…> | <…> | <charge no cost, apply no state, claim nothing in the UI> |

## Verticality check

Before art: can the player complete one **whole** turn of the loop, start to
finish, in the greybox? Not a slice of it — all of it.

- [ ] Loop completable in greybox
- [ ] Beat 4 measurably changes beat 1
- [ ] Failure state reachable (you can lose)
- [ ] Partial input does not lie
- [ ] A person has played it and would press start again

## Change log

| date | change | why |
|---|---|---|
| {{DATE}} | created | |

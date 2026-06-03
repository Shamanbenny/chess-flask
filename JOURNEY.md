# Journey

This document captures the reasoning behind the current direction of the project. It is not a changelog. It exists to explain why the backend is shaped the way it is, why certain work is being deferred, and what standard the chess bot is actually being judged against.

## The Real Constraint

A chess bot that needs more than `30` seconds to produce a single move is not practical for real play.

In any timed match, that kind of response time is a liability. Even if the move quality is acceptable, the clock loss alone will eventually lose games. That makes runtime a core part of engine quality, not a side concern.

This aligns with the current Vercel setup, where [`vercel.json`](/home/benny/Desktop/_gitrepo/chess-flask/vercel.json:1) uses a `30` second duration limit. That ceiling is useful right now because it prevents obviously runaway requests and still gives the current backend room to function.

But `30` seconds is not the target.

The real target is much tighter: the bot should be able to make a reasonable move in about `1` second or less. Ideally, for the kind of iterative work planned here, the practical bar should get closer to `100ms` for decent move selection.

## What The Current Versions Prove

The historical engine line in [`api/v1/__init__.py`](/home/benny/Desktop/_gitrepo/chess-flask/api/v1/__init__.py:1) currently represents a manual/reference phase:

- `v1`: minimax
- `v1.1`: minimax with alpha-beta pruning
- `v1.2`: alpha-beta pruning with move ordering
- `v1.3`: alpha-beta pruning with move ordering and quiescence-style leaf extension
- `v1.4`: `v1.3` plus an endgame mop-up heuristic and a tighter pruned quiescence search

At the moment, the rough runtime picture is:

- `v1` at depth `2`
- `v1.1` at depth `3`
- `v1.2` at depth `3`

These variants take about `5` seconds to make a move in the current setup.

That is much better than crashing into a `30` second limit, but it is still too slow for the actual direction of the project. Beating a bad ceiling is not the same thing as meeting a good target.

There is now also a clearer controlled comparison from:

- `python3 local_v1_tests/puzzle_1.py --versions v1 v1.1 v1.2 --depth 4`

On the same tactical position at depth `4`, the result was:

- `v1`: `97,229` positions searched, about `22.96s` total, and it still missed the second expected move
- `v1.1`: `14,496` positions searched, about `3.34s` total, and it found both expected moves
- `v1.2`: `7,812` positions searched, about `1.94s` total, and it found both expected moves

That matters because it demonstrates exactly what the search changes are supposed to do:

- alpha-beta pruning can reduce the search cost by a very large margin without weakening the line quality on this test
- move ordering improves that pruning further by cutting the search tree down again

So the progression from `v1` to `v1.1` to `v1.2` is not just a theoretical cleanup. It is already producing a substantial practical efficiency gain.

There is now a follow-up comparison for the later search line:

- `python3 local_v1_tests/puzzle_1.py --versions v1 v1.1 v1.2 v1.3 --depth 4`

On that same tactical position at depth `4`, the new point of interest was `v1.3`:

- `v1.3`: `12,084` positions searched, about `3.38s` total, and it found both expected moves

That matters because it sharpens the interpretation of the earlier results:

- compared with what was already established for `v1.2`, `v1.3` gives back some of that raw efficiency because quiescence-style extension intentionally searches beyond the nominal depth in tactically unstable positions
- compared with what was already established for `v1.1`, `v1.3` still remains in the same general performance band while adding a more tactically stable leaf evaluation
- the point of `v1.3` is not to beat `v1.2` on pure speed in every position, but to make the engine less likely to mis-score hanging material near the horizon

So the progression from `v1.2` to `v1.3` should be understood as a stability improvement. It accepts some extra search cost in exchange for more trustworthy tactical evaluation near the horizon.

The next manual step, `v1.4`, addresses a different weakness. Even with quiescence search, a depth-limited engine can easily reach a winning endgame where mate still lies beyond the current horizon. In those positions, pure material scoring is often too indifferent: the engine knows it is better, but not how to tighten the win. So `v1.4` adds a guarded mop-up heuristic for low-material positions where one side is already clearly ahead and still has plausible forcing mating material. The intent is not to fake a mate score. The intent is to make the engine behave more like it understands conversion: push the weaker king outward, bring the stronger king closer, and make later shallow searches more likely to finally see the finish.

`v1.4` also had to diverge slightly from `v1.3`'s quiescence behavior. In queen endgames, allowing quiet checking continuations to spill through qsearch created long search tails that were too expensive for a version that is supposed to help with endgame conversion. So `v1.4` now keeps qsearch focused on captures when the side to move is not in check, and applies simple pruning there as well. On the evaluation side, `v1.4` no longer treats every winning ending like a pure lone-king mop-up either: advanced defender pawns near promotion and repetition in already won endgames are now scored much more aggressively. That still does not fully solve queen-versus-advanced-pawn conversion by itself, but it does make the engine's priorities closer to the real problem.

This also reinforces why `v1.2` had to exist before `v1.3`. The note on [Limiting Quiescence](https://www.chessprogramming.org/Quiescence_Search#Limiting_Quiescence) explicitly warns that quiescence search is vulnerable to search explosion without move ordering, and recommends simple capture ordering such as `MVV-LVA` before adding qsearch. That is broadly the same path taken here: first improve alpha-beta efficiency with move ordering, then extend the leaf search. In other words, `v1.2` was not just a nice optimization before `v1.3`; it was part of the practical groundwork that made `v1.3` reasonable to add at all.

## Why Simulation Is Not The Immediate Focus

Large-scale engine-vs-engine simulation only becomes useful when individual move generation is already cheap enough.

Right now, if one move takes about `5` seconds and a typical game averages roughly `70` to `80` plies, then one game can easily take around `350` to `400` seconds. That is about `5.8` to `6.66` minutes per game.

At that rate, a `1000` game simulation can take well over `100` hours.

That is not a practical inner loop.

So even though the repo now has local tooling for simulation and direct engine evaluation, that is not yet the main development path. Running giant match batches too early would spend most of the project time waiting on weak and still-slow engines.

## Why The Current `30` Second Vercel Limit Still Exists

The current deployment limit should be understood as an operational allowance, not a design objective.

It exists because:

- the engine is still immature
- the backend still needs enough room to return a move at all
- the hosted path is serving a website integration, not a final engine benchmark environment

The correct interpretation is:

- `30` seconds is acceptable as a temporary upper bound
- `30` seconds is not acceptable as a product target
- increasing the limit further would move the project in the wrong direction

The right fix is not “allow slower thinking.” The right fix is “make the engine think faster while staying useful.”

## The Current Development Priority

The immediate goal is not to run massive automated gauntlets.

The immediate goal is to manually work toward an algorithm that is strong enough to choose decent moves within roughly a `100ms` budget.

That changes the order of operations:

1. Improve the search approach manually.
2. Get runtime down to something that is actually usable.
3. Establish a stronger baseline engine.
4. Only then lean harder on automated simulation and `autoresearch`-style evaluation loops.

Until the engine is cheap enough per move, large simulation campaigns are mostly an expensive way to confirm that the current setup is too slow.

## Why Coding Adventure Is The Reference Path For Now

For the current phase, the project will follow the broad implementation path shown in Coding Adventure's chess-bot video.

The reason is straightforward:

- it provides a practical staged path from naive minimax toward more usable search
- it prioritizes obvious search-efficiency improvements first
- it gives a clearer manual route toward a respectable baseline before automation is introduced

This does not mean copying that work blindly or treating it as the final architecture. It means using it as a concrete guide to reach the next useful stage faster.

The point of this phase is to reach a bot that is both:

- strong enough to be worth testing seriously
- fast enough that repeated testing is not absurdly expensive

## Where `autoresearch` Fits

The long-term plan still includes an `autoresearch`-style workflow for `v2+`.

But that only makes sense once the engine is strong enough and fast enough that automated comparisons can run on a reasonable timescale.

So `autoresearch` is not being rejected. It is being delayed until the baseline conditions are good enough:

- move generation is materially faster
- the search is no longer obviously wasteful
- simulation can run in a practical timeframe
- candidate-vs-baseline comparison becomes cheap enough to repeat often

Only after that does automated promotion/rejection become a good use of time.

## Summary

The project direction is intentionally conservative right now:

- keep the current Vercel `30` second ceiling as a temporary deployment constraint
- do not mistake that ceiling for the real performance goal
- treat `1` second or less as the practical direction for real play
- treat roughly `100ms` as the kind of move budget worth targeting for serious iteration
- improve the engine manually before relying heavily on large simulation batches
- use Coding Adventure's staged search improvements as the near-term guide
- accept that shallow search sometimes needs positional conversion guidance in winning endgames before a mate sequence becomes directly visible
- begin the real `autoresearch` loop only after the baseline is fast enough to make that loop practical

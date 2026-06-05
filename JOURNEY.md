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
- `v1.5`: `v1.4` adapted into iterative deepening with a fixed think-time budget, plus a transposition table reused across passes for search optimization

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

There is now also an early `v1.5` result from the same `puzzle_1.py` position, but this one should be interpreted differently because it is no longer a fixed-depth test:

- `python3 local_v1_tests/puzzle_1.py --versions v1.5 --depth 4`
- `v1.5` ran with a `1.000s` limit per white move rather than a fixed depth
- on both white moves, it found the expected continuation: `Nf4+` and then `Nxd5`
- it searched `3,223` positions on the first move and `3,014` on the second, for `6,237` total
- each move used essentially the full budget and reported `completed_depth=3` with `timed_out=True`
- the first move ended with `444` TT entries, `1306` probes, `139` hits, a `10.6%` hit rate, and `6` TT cutoffs
- the second move ended with `354` TT entries, `1071` probes, `118` hits, a `11.0%` hit rate, and `3` TT cutoffs

That gives a cleaner picture of what `v1.5` is actually adding. The big structural change is iterative deepening under a fixed time limit, which is a more practical search model than demanding a fixed depth from every position. The second change is the transposition table, and the console output now shows that it is active rather than ornamental: the search is probing it often and getting some reuse back.

At the same time, this specific run does not suggest that the table is carrying the search yet. A hit rate around `10%` to `11%`, with only a few direct TT cutoffs, looks more like modest help than a major collapse of the tree. That is still useful, especially because `v1.5` is only completing depth `3` before the `1` second limit expires, but it also means the current result should be read as “the TT is contributing” rather than “the TT is already highly effective.”

So the immediate lesson from `v1.5` is fairly simple: the engine can now return the right tactical move inside a fixed time budget, and it is beginning to benefit from transposition-table reuse while doing so. The next question is not whether the TT exists, but whether the overall implementation can process enough nodes per second for iterative deepening and TT reuse to pay off more strongly. That is where the language question becomes more concrete. At this stage, the point is not to conclude that the engine must leave Python or that another language automatically solves the problem. The point is to recognize that once the budget is fixed, raw execution speed becomes much more visible. A faster language such as C# could, in principle, complete deeper iterations within the same time limit and create more opportunities for the transposition table to matter.

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

## Why Python Serves And C# Develops

The repo now makes this distinction explicit:

- Python remains the Flask and Vercel runtime.
- C# becomes the local-development target for the `v1.*` search family.

The reason Python stays in the repo is much simpler than that: the project needed a backend that could be hosted on Vercel so the chess bot could interact with users on the portfolio site. That is the job Flask is doing here.

That hosted backend requirement is not the same thing as the local engine-development requirement.

The real pressure in engine development is how many positions can be searched inside a fixed think-time budget. That cost sits in:

- move generation loops
- recursive search
- repeated board copying and mutation
- transposition-table probing
- the general node-per-second ceiling of the engine

Once the engine is judged by time instead of fixed depth, raw execution speed becomes much harder to ignore. A faster language such as C# could, in principle, complete deeper iterations within the same time limit and create more opportunities for the transposition table to matter. That is the real reason to set the project up this way early.

The practical concern is not just that Python might be slower. The practical concern is uncertainty. If the engine is underperforming, the project should be able to say with more confidence:

- the algorithm is the limiting factor
- the evaluation is weak
- the move ordering is weak
- the pruning is weak
- or the transposition-table reuse is weak

What the project should not have to keep wondering is whether the current result is mostly a language ceiling.

So the architectural choice here is to remove that ambiguity as early as possible. It is better to make the split while the engine family is still young than to wait until `v2+`, when more tooling, more tests, more blog-post narrative, and more version history would have to be rewritten around a late-stage migration.

That does not mean Flask should call the C# engine in production. For this repo, the cleaner rule is:

- C# is the local research and testing language
- Python is the deployed Flask/Vercel language
- if a final `v1.*` engine is worth exposing publicly, it gets rewritten into Python at that point

Python owns:

- request validation
- route-level error mapping
- deployment-facing concerns

The C# local engine workspace owns:

- versioned move search
- evaluation logic
- time-budgeted search behavior
- low-level performance work

This also fits the blog-post story better. The project can explain, clearly and honestly, that:

- Python remained because the website project needed a Vercel-hosted backend for user interaction
- C# was chosen early so deeper same-budget search could be pursued without constant doubt about Python throughput
- the architecture was split before the repo became too version-heavy to revamp cleanly
- the goal was to separate algorithm limits from language limits as soon as practical

In other words, the decision is not “Python bad, C# good.” The decision is that engine research becomes much easier to reason about when the project stops wondering whether the language is the main bottleneck.

## Why `v1.6` Exists

`v1.6` exists because the first local C# `v1.5` rewrite still behaved much more slowly (like, REALLY slowly) than the staged engine work in [`Chess-Coding-Adventure`](https://github.com/SebLague/Chess-Coding-Adventure/tree/Chess-V1-Unity), especially in forcing endgames where depth gained inside the same time budget matters a lot more.

The important realization was that the broad search recipe was not the main problem anymore.

Both sides were already using the recognizable chess-engine stack:

- iterative deepening
- negamax with alpha-beta pruning
- quiescence search
- transposition-table reuse

So the next bottleneck was not “missing alpha-beta” or “missing a TT.” The bottleneck was the cost of each node.

### What The Python Version Missed

The original Python `v1.5` had the same structural blind spots that later showed up in the first C# rewrite:

- move ordering was too expensive for the amount of search benefit it produced
- evaluation repeatedly asked the board for derived state in ways that were acceptable for clarity but not for high node throughput
- terminal and repetition logic were cheap enough for experimentation but not cheap enough for aggressive time-budgeted search
- the implementation leaned on a general-purpose board library rather than a purpose-built incremental board/search substrate

That made the Python engine useful as a reference implementation, but a poor ceiling for serious same-budget depth comparisons.

### What The Early C# Port Still Missed

Moving from Python to C# did not automatically fix those issues.

The first C# `v1.5` port kept too much of the same cost profile:

- it still paid too much per node for state management
- it still let move ordering do work that looked more like mini-search than cheap ordering
- it still made evaluation and terminal logic more allocation-heavy than they needed to be
- it still used a TT implementation that was technically correct but not especially cheap

That is the key reason the early local C# port could still feel much slower than expected even after the language migration.

### What Cross-Referencing `Chess-Coding-Adventure` Changed

Cross-referencing Sebastian Lague's `Chess-Coding-Adventure` was useful here not because this repository needed to copy it line by line, but because it forced a harder question:

- if the broad search ideas are already similar, why is this engine still so much slower?

The answer was mostly in the hot path:

- cheaper board-state bookkeeping
- cheaper move ordering
- cheaper transposition-table probing
- cheaper terminal checks
- cheaper evaluation passes

That is the practical shift behind `v1.6`. The goal was to stop treating all nodes as if they cost roughly the same regardless of implementation details.

### What `v1.6` Changes

`v1.6` makes the C# search path more performance-conscious in several specific ways:

- repetition history now uses hashed position keys instead of string history comparisons
- position hashing no longer rescans the full board to rebuild Zobrist state after every `Push` and `Pop`
- move ordering no longer pushes and pops each candidate move just to score it
- the transposition table is now a fixed-size indexed structure instead of a dictionary-backed table
- terminal checks can ask whether any legal move exists without forcing a full `ToList()` allocation
- endgame evaluation now works from a lighter one-pass snapshot instead of repeated board scans and clone-based helper calls
- mate-distance pruning is now applied so known shorter mates can collapse obviously longer branches

None of that changes the broad identity of the engine. It changes how much work the engine pays to express that identity.

### What That Meant In Practice

The first local `puzzle-1` comparison at `1.0` second per move already showed the intended direction clearly:

- the early C# `v1.5` path completed depth `2` on White 1 and searched `784` nodes
- `v1.6` completed depth `3` on White 1 and searched `6,090` nodes
- `v1.6` also pushed TT hit rate and TT cutoff usage much higher on that run, which is exactly the kind of payoff that only appears once per-node overhead drops enough

That does not mean `v1.6` solves every endgame conversion line yet.

It means the engine is starting to buy more real search with the same clock budget, which is the prerequisite for later improvements to matter.

There is now a much clearer picture of what that improvement did and did not solve.

If you look at [`engine_scenarios/console_output.md`](/home/benny/Desktop/_gitrepo/chess-flask/engine_scenarios/console_output.md:55), `v1.6` was able to process depth `5` in about `2.93s` on the tactical `puzzle_1` line. That is better than the earlier versions, and it does prove that moving to C# plus a more careful search path helped. But it is still nowhere near the practical target. The real standard here is not "can it eventually reach depth 5?" The real standard is closer to "can it do roughly that much useful work in something like `100ms`?"

So even after `v1.6`, the project was still very far from where it needed to be.

That is also why the move to C# happened early instead of late. The point was not just to speed the engine up in the abstract. The point was to get into a development environment where [`autoresearch`](https://github.com/karpathy/autoresearch) could start testing low-hanging performance and search hypotheses without constant doubt that Python itself was the dominant ceiling. In that sense, the early migration did exactly what it was supposed to do: it created a cleaner lab for experimentation even before it created a fast enough engine.

## What The First `v2.0` Actually Proved

At first, that looked very promising.

The original `v2.0`, recorded and approved under commit [`db423ca`](https://github.com/Shamanbenny/chess-flask/commit/db423caf1b8d3e0f89df051e0ab2777127195a77) and [`583348d`](https://github.com/Shamanbenny/chess-flask/commit/583348d4340f55faa0855e3035b63b1284b613b1), passed the evaluator on the very first experiment. That mattered for two reasons:

- it showed that the [evaluator](https://github.com/Shamanbenny/chess-flask/blob/main/autoresearch/EVALUATE.md) could approve a real improvement rather than serving only as a rejection machine
- it showed that the [`autoresearch`](https://github.com/Shamanbenny/chess-flask/tree/main/autoresearch) workflow itself could work the way this project hoped it would

That was a meaningful milestone. It meant the general experiment loop was viable.

So the natural next step was to keep running `autoresearch` and let the engine try to climb from there.

## What Repeated Rejections Revealed

That optimism did not last for long.

The later attempts, also documented in [`autoresearch/ATTEMPTS.md`](https://github.com/Shamanbenny/chess-flask/blob/8fc86540289d1fb09196b755ddf379a93b45edaa/autoresearch/ATTEMPTS.md), kept getting rejected. Looking at the game results, the pattern was hard to miss: too many games were ending by `max_plies`. In practice, that meant the competing engines were often not converting advantages into checkmate within the fixed budget.

That pointed to a deeper issue than "this pruning tweak was weak" or "that move-order bonus was not helpful enough."

It suggested that the engine simply was not getting enough real search done per move.

The evaluator was running at `250ms` per move. If the earlier console runs were any indication, that was still too little time for the engine to search and evaluate positions deeply enough to make the later search tweaks matter reliably. But increasing the evaluator's time limit was not the real answer either. That would only hide the underlying bottleneck, and it would make each experiment much more expensive. For example, if `250ms` supports `100` games in a reasonable experiment window, then raising that to `1000ms` would force a proportional cut in game count just to keep the runtime practical. That would weaken the experiment loop instead of strengthening it.

So the repeated rejections did not really say "the search ideas are exhausted." They said "the engine is still paying too much just to exist at each node."

## The Real Breakthrough

That is what led to the next major shift.

The key realization was that a custom board representation and custom move generation were not just matters of code ownership or portability. They were performance tools. A chess engine that controls its own board state, legal move generation, make/unmake flow, hashing, and attack checks can remove a large amount of general-purpose library overhead from the hot path.

To test that directly, Codex was asked to build a new `v2.0` around an in-house board representation and in-house move generation while preserving the same broad underlying search algorithm as `v1.6`.

The result was not a small incremental gain. It was a dramatic one.

The new `v2.0` showed that the real blocker over the previous `48` hours had not primarily been the search ideas being tested by `autoresearch`. The real blocker was the amount of overhead being incurred every time the engine had to generate moves, update board state, and evaluate another position. Once that cost dropped, the engine's node throughput changed sharply.

That changed the interpretation of the previous failed experiments. Those attempts were not useless. They helped expose that the project had started `autoresearch` one layer too early. The engine was being asked to self-optimize search behavior before its board representation and move-generation substrate were cheap enough for those search improvements to pay off consistently.

## The Current Development Priority

The immediate goal is to automatically, build through experiment loops, on the new `v2.0` baseline now that the engine can buy far more search inside the same budget.

That changes the order of operations:

1. Keep the stronger `v2.0` board representation and move-generation path as the new baseline.
2. Confirm that the engine can search enough nodes per move for the fixed-time evaluator to be meaningful. This was proven with the update made to [`engine_scenarios/console_output.md`](https://github.com/Shamanbenny/chess-flask/blob/main/engine_scenarios/console_output.md)
3. Resume `autoresearch` from a position where algorithmic improvements have room to show up.
4. Improve the engine bit by bit through controlled promotion/rejection instead of trying to brute-force quality with a slower substrate.

The important difference is that the project now has much more confidence in both parts of the loop:

- the `autoresearch` paradigm itself has already shown that it can approve real gains
- the engine is now much closer to being fast enough that those gains can compound instead of disappearing into per-node overhead

## Summary

The project direction is intentionally conservative right now:

- keep the current Vercel `30` second ceiling as a temporary deployment constraint
- do not mistake that ceiling for the real performance goal
- treat `1` second or less as the practical direction for real play
- treat roughly `100ms` as the kind of move budget worth targeting for serious iteration
- move away from treating fixed depth as the main benchmark and toward iterative deepening under fixed time limits
- treat programming-language speed as a legitimate part of the investigation once the engine is judged by fixed time instead of fixed depth
- recognize that early C# migration helped create a usable experiment environment even before it solved the core speed problem
- treat the original `v2.0` approval as proof that the evaluator and `autoresearch` loop can work
- treat the repeated `max_plies` rejections as evidence that the previous engine substrate was still too expensive per node
- use the new `v2.0` board representation and move-generation path as the real baseline for future `autoresearch`
- accept that search optimization only becomes meaningfully testable once board-state and move-generation overhead are low enough

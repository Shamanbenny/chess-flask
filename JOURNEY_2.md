# Journey on Autonomous Iterations for Chess Engine (via `autoresearch`)

This document picks up from the point where [`JOURNEY_1.md`](JOURNEY_1.md#L1) leaves off.

That earlier phase was about getting the engine to a point where tighter time budgets were no longer purely aspirational. The key breakthrough was `v2.0`: once the engine could produce meaningful results inside the fixed `100ms` evaluator budget, autonomous iteration stopped being a novelty and became a practical development path.

That distinction matters.

Before that point, too many experiments would have risked collapsing into games dominated by the evaluator's `max_plies` cutoff rather than by actual move quality. But the first `autoresearch` runs recorded in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md#L1) already show the environment behaving more like a useful engine lab than a timing failure generator:

- `v2.2` was approved with `max_plies=0`
- `v2.5` was approved with `max_plies=0`
- even the rejected `v2.6` and `v2.7` runs also finished with `max_plies=0`

So the important change after `v2.0` was not just that the engine had become "faster." The important change was that the experiment loop had become informative enough to trust overnight.

## What The First Autonomous Loop Actually Looked Like

The first hypothesis after `v2.0` did not produce a positive result.

That attempt became `v2.1`, and it was eventually manually interrupted by me and rejected in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md#L81). The relevant point is not merely that it had failed. The relevant point is why I stopped it early: this was the first time I was preparing to let the machine run autonomously overnight, and I wanted at least some sign that the loop was capable of producing visible improvement before committing an entire night of runtime to it.

Once that interrupted run was logged automatically through the `autoresearch` workflow, I started the next sequence of experiments. That sequence took the engine from `v2.2` through `v2.7`, and if counted from the interrupted `v2.1` start to the `v2.7` result, it stretched across roughly seven hours of unattended runtime recorded in the attempt log:

- `v2.1` at `2026-06-05T18:39:57Z`
- `v2.2` at `2026-06-05T19:44:30Z`
- `v2.3` at `2026-06-05T20:56:06Z`
- `v2.4` at `2026-06-05T22:04:03Z`
- `v2.5` at `2026-06-05T23:14:22Z`
- `v2.6` at `2026-06-06T00:21:40Z`
- `v2.7` at `2026-06-06T01:28:59Z`

That was also the point where I stopped actively tweaking the system, left the host machine running overnight, and went to bed.

When I came back the next morning, the interesting result was not just that `autoresearch` had kept running. The more important result was that the overnight loop had produced two approved versions:

- `v2.2`, the first approved successor after `v2.0`
- `v2.5`, which later became the latest approved in-repo seed in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md#L19)

That was the first moment where the system had proven it could keep running without my supervision, reject weak ideas in between, and still return multiple approved engine versions by morning.

## Why That Result Mattered

That outcome was exciting for a fairly specific reason.

The original [`autoresearch`](https://github.com/karpathy/autoresearch) came from a workflow commonly associate with training AI models (thus the [`train.py`](https://github.com/karpathy/autoresearch/blob/master/train.py) as the modifiable artifact of the project). What made this interesting was that it had been reshaped into something else: a constrained problem-solving loop for a chess engine, where each change could be tested and judged against a fixed evaluator:

- one active hypothesis at a time
- fixed promotion criteria
- fixed evaluator contract
- persistent attempt logging
- automatic rejection of weak or invalid candidates

That is a better description of what happened than simply saying the engine was "self-improving." It was not open-ended self-improvement. It was a constrained autonomous improvement loop built around a measurable benchmark, as defined by [`autoresearch/PROGRAM.md`](autoresearch/PROGRAM.md#L1) and [`autoresearch/EVALUATE.md`](autoresearch/EVALUATE.md#L1).

The fact that the loop could keep running while I slept, reject weak ideas, and still return approved versions by morning was the proof that this workflow was real enough to keep investing in.

## Why The Approved Versions Still Weren't Enough

That said, the immediate follow-up reaction should not have been celebration alone.

Looking at the approved results in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md#L107), both successful versions were still very draw-heavy:

- `v2.2`: `117` wins, `350` draws, `33` losses
- `v2.5`: `118` wins, `315` draws, `67` losses

In both cases, draws outnumbered wins and losses combined.

That does not mean the approvals were fake. They were legitimate approvals under the fixed evaluator, and `v2.5` did clear the promotion rule. But it does suggest something important about the current strength profile of the engine.

The search is now good enough to operate within the time budget. That part is no longer the immediate blocker.

What still looks limited is the engine's ability to convert small advantages into decisive outcomes. In other words:

- the search can now reach playable positions within `100ms`
- the evaluation is still not consistently strong enough to exploit many of the slight advantages it reaches
- the result is a large number of drawn games even in approved versions

So the next meaningful direction was not "search harder at any cost." The next meaningful direction was to guide future `autoresearch` runs toward improving the evaluation layer of the engine.

## Why Self-Play Alone Needed More Structure

Around that time, I was also thinking through a criticism raised by a friend with [reinforcement-learning](https://en.wikipedia.org/wiki/Reinforcement_learning) experience.

The basic warning was simple: _self-play metrics can be misleading because the goalposts keep moving. If a system is judged primarily against itself, it can end up optimizing for narrow patterns, exploiting quirks of its current environment, or overfitting to behaviors that do not generalize well._ In that framing, better self-play performance does not automatically mean better chess.

That criticism does not map perfectly onto this repository, because `autoresearch` is not doing weight updates or unconstrained training. Each run is hypothesis-guided, code-level, and evaluator-bounded.

But the concern still matters.

Even in a hand-guided optimization loop, it is possible to make changes that look better only because the comparison target is too narrow or too unstable. So before starting the next major loop, I decided the right move was not to push harder into experimentation immediately. The right move was to make the evaluation structure more concrete.

## Why `stockfish-1350` Became The Fixed Yardstick

The first structural improvement was to make a weaker Stockfish level the fixed baseline opponent for `autoresearch`, rather than treating the previous in-repo engine version as the main approval target.

That choice is now reflected directly in:

The reasoning is straightforward.

If each candidate is judged only against the immediately previous in-repo engine, then improvement can become too local. A version can look "better than the last one" without giving much confidence that it is better in a broader or more stable sense.

Using a fixed external opponent is a cleaner anchor.

It also lines up with a point Sebastian Lague makes in [Coding Adventure: Making a Better Chess Bot](https://www.youtube.com/watch?v=_vqlIPDR2TU): "improving against one opponent doesn't necessarily guarantee" better play against another. That is exactly the concern being addressed here.

So the baseline choice does two useful things at once:

- it gives `autoresearch` a more stable target than pure in-repo succession
- it makes the engine easier to reason about in rating-like terms instead of only as a chain of version numbers

## Why Multi-Worker Evaluation Was The Next Obvious Upgrade

The next structural improvement was not in the engine itself. It was in the speed of the experiment harness.

The local evaluator now supports a `--workers` flag for concurrent game processing, and the benefit is simple:

- evaluation time drops significantly when paired openings are processed concurrently
- the host machine's physical cores can be used much more fully
- more completed experiments fit into an overnight run window

That is the practical side of the story: once the engine itself became fast enough for `100ms` tests to mean something, the new bottleneck shifted toward how many full evaluations could be completed before morning.

So multi-worker evaluation was not just a convenience tweak. It directly increased the throughput of the autonomous research loop.

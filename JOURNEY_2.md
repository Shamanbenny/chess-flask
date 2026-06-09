# Journey on Autonomous Iterations for Chess Engine (via `autoresearch`)

This document picks up from the point where [`JOURNEY_1.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/JOURNEY_1.md#L1) leaves off.

That earlier phase was about getting the engine to a point where tighter time budgets were no longer purely aspirational. The key breakthrough was `v2.0`: once the engine could produce meaningful results inside the fixed `100ms` evaluator budget, autonomous iteration stopped being a novelty and became a practical development path.

That distinction matters.

Before that point, too many experiments would have risked collapsing into games dominated by the evaluator's `max_plies` cutoff rather than by actual move quality. But the first `autoresearch` runs recorded in [`autoresearch/ATTEMPTS.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/autoresearch/ATTEMPTS.md#L1) already show the environment behaving more like a useful engine lab than a timing failure generator:

- `v2.2` was approved with `max_plies=0`
- `v2.5` was approved with `max_plies=0`
- even the rejected `v2.6` and `v2.7` runs also finished with `max_plies=0`

So the important change after `v2.0` was not just that the engine had become "faster." The important change was that the experiment loop had become informative enough to trust overnight.

## What The First Autonomous Loop Actually Looked Like

The first hypothesis after `v2.0` did not produce a positive result.

That attempt became `v2.1`, and it was eventually manually interrupted by me and rejected in [`autoresearch/ATTEMPTS.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/autoresearch/ATTEMPTS.md#L81). The relevant point is not merely that it had failed. The relevant point is why I stopped it early: this was the first time I was preparing to let the machine run autonomously overnight, and I wanted at least some sign that the loop was capable of producing visible improvement before committing an entire night of runtime to it.

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
- `v2.5`, which later became the latest approved in-repo seed in [`autoresearch/ATTEMPTS.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/autoresearch/ATTEMPTS.md#L19)

That was the first moment where the system had proven it could keep running without my supervision, reject weak ideas in between, and still return multiple approved engine versions by morning.

## Why That Result Mattered

That outcome was exciting for a fairly specific reason.

The original [`autoresearch`](https://github.com/karpathy/autoresearch) came from a workflow commonly associate with training AI models (thus the [`train.py`](https://github.com/karpathy/autoresearch/blob/master/train.py) as the modifiable artifact of the project). What made this interesting was that it had been reshaped into something else: a constrained problem-solving loop for a chess engine, where each change could be tested and judged against a fixed evaluator:

- one active hypothesis at a time
- fixed promotion criteria
- fixed evaluator contract
- persistent attempt logging
- automatic rejection of weak or invalid candidates

That is a better description of what happened than simply saying the engine was "self-improving." It was not open-ended self-improvement. It was a constrained autonomous improvement loop built around a measurable benchmark, as defined by [`autoresearch/PROGRAM.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/autoresearch/PROGRAM.md#L1) and [`autoresearch/EVALUATE.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/autoresearch/EVALUATE.md#L1).

The fact that the loop could keep running while I slept, reject weak ideas, and still return approved versions by morning was the proof that this workflow was real enough to keep investing in.

## Why The Approved Versions Still Weren't Enough

That said, the immediate follow-up reaction should not have been celebration alone.

Looking at the approved results in [`autoresearch/ATTEMPTS.md`](https://github.com/Shamanbenny/chess-flask/blob/f3d3ef9ac59177c9a2e1389426cade1e1e45feaf/autoresearch/ATTEMPTS.md#L107), both successful versions were still very draw-heavy:

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

- [`autoresearch/PROGRAM.md`](autoresearch/PROGRAM.md)
- [`autoresearch/EVALUATE.md`](autoresearch/EVALUATE.md)
- [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md)

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

## The Surprise From Re-Running Approved Versions Against Stockfish

After both changes were in place, I ran the new `stockfish-1350` evaluation against the three approved versions that mattered for the current `v2` story: `v2.0`, `v2.2`, and `v2.5`.

The updated reference summary is now recorded at the end of [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md). The minimal result is:

- `v2.0`: `160` wins, `94` draws, `246` losses, `score_rate=0.4140`
- `v2.2`: `258` wins, `110` draws, `132` losses, `score_rate=0.6260`
- `v2.5`: `239` wins, `122` draws, `139` losses, `score_rate=0.6000`

This was a shock because it directly addressed the problem I was worried about earlier in this document.

The earlier self-play-style approved runs were still mostly draws. Against the fixed `stockfish-1350` baseline, that changed: the games were no longer dominated by drawn outcomes. That means that, at minimum, one side of the matchup was able to convert advantageous positions into decisive wins often enough for the evaluator to produce much clearer signal.

That matters for future `autoresearch` loops. It makes the results easier to interpret, reduces the risk of over-reading tiny differences inside draw-heavy logs, and gives each experiment a better chance of producing a conclusive inference instead of just another ambiguous marginal score.

## Why I Stopped Letting Autoresearch Choose Every Direction

From there, I let `autoresearch` run a bit further.

That next stretch produced two more approved `v2` versions recorded in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md):

- `v2.8`, which added rook open-file and semi-open-file bonuses
- `v2.9`, which added a targeted knight outpost bonus

By that point, the autonomous loop was still doing useful work. The pattern was clear enough: constrained static-evaluation changes could keep finding small, real gains against the fixed `stockfish-1350` baseline. But that was also the point where I felt the need to step back and ask a different question.

Not just "what can the loop improve next?"

More specifically: _what do I actually want this engine to become better at structurally?_

The two ideas that stayed in my mind were:

- a persistent transposition table between moves
- an opening-book lookup table that could both avoid unnecessary search in early positions and introduce some opening variety

Those were not just incremental evaluation tweaks. They were architecture-level changes that seemed likely to matter more as the engine's search kept improving. In that sense, they felt less like additive improvements and more like multiplicative ones: the kind of change that might not maximize immediate benchmark gain, but could increase the value of later search improvements built on top of them.

That decision became [`v3.0`](autoresearch/ATTEMPTS.md).

According to the attempt log, `v3.0` was explicitly approved by me even though its `stockfish-1350` score rate (`0.6110`) was lower than `v2.9` (`0.6480`). I did notice that drop. It just was not the part I cared about most at that moment.

What mattered more was that `v3.0` established a new structural base:

- a per-game search context that can keep the transposition table alive across moves
- an opening lookup path keyed before the normal search
- a clean `v3` engine lineage built around those ideas

That is why I did not treat the temporary benchmark loss as a reason to abandon the direction. If the long-term objective is a stronger searcher under tight time limits, then memory reuse across moves and cheap opening handling look like the kind of infrastructure that should pay off more as the engine gets better elsewhere.

After `v3.0`, I resumed `autoresearch` within that new lineage.

The next sequence in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md) shows `v3.1`, `v3.2`, and `v3.3` being rejected before `v3.4` was finally approved.

## Why I Moved The Workflow Out Of A Pure Codex Infinite Loop

That was also the point where I started noticing a deeper inconsistency in the original setup.

The early modified `autoresearch` workflow depended too heavily on a pure Codex infinite loop. In theory, that sounded attractive: let the agent keep operating autonomously, keep evaluating candidates, and keep appending history without my involvement.

In practice, there was a reliability problem.

Some evaluator runs took a long time, especially at the full `500`-game contract. And during those long runs, there were cases where Codex would decide on its own to halt, interrupt itself, or otherwise stop behaving like a truly persistent autonomous loop, even though the instructions were explicit that it should _not_ do that. I could make `autoresearch/PROGRAM.md` say "never halt" as clearly as I wanted, but that still did not guarantee consistent behavior. Context-window drift, partial instruction recall, or simple agent inconsistency could still break the loop at the exact point where reliability mattered most.

That was the core limitation.

The problem was not that Codex could not produce useful engine changes. It clearly could. The problem was that I did not want core workflow guarantees such as version control, evaluator execution, approval rules, and attempt logging to depend on whether the agent happened to remain obedient and context-stable across a very long-running session.

That is what led to the current Python-script workflow now documented in [`autoresearch/README.md`](autoresearch/README.md).

The advantages of that shift are fairly concrete:

- Python now owns the strict parts of the workflow: sandbox setup, version selection, evaluator execution, approval or rejection, changelog updates, attempt logging, and local git commits
- Codex no longer has to carry the full protocol in context for hours at a time
- each experiment runs inside a fresh sandbox with a generated `PROGRAM.md`, a copied `ATTEMPTS.md`, the candidate engine file, and `RETURN.json`
- Codex is only responsible for the candidate engine edit and its own short structured summary fields

That makes the overall system more reliable and also cheaper in the ways that matter operationally:

- less context to maintain
- less token usage to burn on workflow bookkeeping
- less room for inconsistent decisions around evaluator handling
- a more repeatable contract between "agent proposes a change" and "system evaluates and records it"

So the transition away from a fully Codex-owned loop was not a retreat from `autoresearch`.

It was the opposite. It was an attempt to make `autoresearch` stricter, more reproducible, and less dependent on long-horizon agent behavior for the parts of the loop that should really be deterministic.

## Where This Phase Actually Ends Now

At the time of writing this update, that structural rewrite has already justified itself.

The important result is not a single approved version. The important result is that the new workflow has now sustained more than a dozen experiments in sequence without the experiment loop itself becoming the problem. The loop kept spawning candidates, evaluating them, rejecting weak ones, approving stronger ones, and recording the outcomes cleanly.

The concrete numbers, version-by-version outcomes, and evaluator summaries are all in [`autoresearch/ATTEMPTS.md`](autoresearch/ATTEMPTS.md). That file is the place to inspect the actual stats. The point that matters for this narrative is simpler: the structural changes worked, and they worked under repeated use rather than only as a one-off success case.

That does not mean I think the workflow is "solved."

The next likely limitation is conceptual rather than operational. Right now each experiment is constrained to a small number of hypotheses. That is good for interpretability, but it may become a bottleneck later. Some improvements may only emerge when a third prerequisite idea is already in place. Hypotheses `A` and `B` together may look neutral or weak unless hypothesis `C` has already landed first. A workflow that mostly explores isolated or paired ideas can miss that kind of dependency chain.

There is also a second concern I take seriously: the growing attempt history may start to bias future runs too strongly against revisiting rejected ideas. In some cases that is exactly what we want. In other cases, a rejected hypothesis may only have failed because it was tried too early, paired with the wrong companion change, or tested before the engine had the right surrounding structure. If the hydrated context implicitly teaches Codex that those ideas are "settled," then the workflow may discourage useful retests that would make sense later.

Regardless of these concerns, however, I think the pattern has demonstrated clearly enough to be useful beyond this chess engine. This workflow will especially be well-suited to systems where:

- meaningful improvements can be argued for at a hypothesis or theory level before implementation
- each candidate can be evaluated by a stable quantitative benchmark
- the benchmark is good enough to tell whether the change was actually an improvement

That is where this phase of the story ends: not with uncertainty about whether the modified workflow works, but with a clearer sense of both its strengths and the kinds of future experiments it may struggle to discover on its own.

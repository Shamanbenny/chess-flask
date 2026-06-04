# Fixed Evaluation Contract

This file defines the fixed evaluation harness contract for chess-engine `autoresearch` runs.

Do not modify this file during experiments.

## Purpose

Every candidate engine is evaluated only by playing it head-to-head against the latest approved engine under fixed conditions.

The evaluator decides whether the candidate is approved. Diagnostic information can support the write-up, but it does not replace the approval rule.

## Fixed Match Rules

- Candidate opponent: the latest approved engine recorded in `autoresearch/ATTEMPTS.md`
- Move time limit: `1000ms` per move
- Total games: `50`
- Color split: `25` games with the candidate as White, `25` games with the candidate as Black
- Opening policy: use the fixed curated `Book.txt` opening-book positions checked into the repo, exclude the fresh starting board, randomize the sampled positions for the run, and use the same sampled position for the immediate color-swapped paired game
- Draw cutoff: use a fixed `max_plies` constant enforced by the evaluator
- Evaluation transport: direct local engine-vs-engine evaluation inside the engine workspace, not the legacy Python HTTP simulator
- No depth argument: evaluation is time-limited, not depth-limited

Every candidate must be judged under exactly the same rules.

## CLI Command

The evaluator is run through the local C# runner.

Before running evaluation, replace:

- `<candidate_engine_file>` with the newly cloned and modified engine file being tested
- `<approved_engine_file>` with the latest approved engine file recorded in `autoresearch/ATTEMPTS.md`

Run exactly:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match \
  --engine-a-file <candidate_engine_file> \
  --engine-b-file <approved_engine_file> \
  --games 100 \
  --time-limit-ms 500 \
  --max-plies 200
```

Example:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-match \
  --engine-a-file engine_csharp/src/Engine.Core/V2/V2_0Engine.cs \
  --engine-b-file engine_csharp/src/Engine.Core/V1/V1_6Engine.cs \
  --games 50 \
  --time-limit-ms 500 \
  --max-plies 200
```

Do not change the evaluator flags during normal experiments. The opening source defaults to `Book.txt` automatically and should not be overridden unless the workflow contract is intentionally revised outside the experiment loop.

## Required Evaluator Output

The evaluator must print these exact signatures:

- `=== EVALUATION START ===`
- `=== EVALUATION DONE ===`

If either signature is missing, treat the evaluation as failed until proven otherwise.

## Required Logged Artifacts

The evaluator writes run artifacts under `autoresearch/logs/<run_id>/`.

Required artifacts:

- raw console log
- machine-readable per-game results
- machine-readable aggregate summary

Optional artifacts are allowed if they help analysis, for example model-generated CSV summaries of positions evaluated or other diagnostics, but they are not part of the approval decision.

`autoresearch/logs/` should remain untracked by git.

## Required Reported Metrics

Every completed evaluation must expose at least:

- candidate engine version/file
- baseline engine version/file
- total wins, draws, losses
- total score
- score rate
- average plies per game
- timeout count
- crash / invalid-move / harness-failure counts

If available, also record:

- average processing time per move
- average positions evaluated or nodes searched per move

These additional metrics are diagnostic only.

## Approval Formula

The approval decision must be based on paired opening results, not just raw aggregate score.

For each opening pair `i`, define:

- one game with candidate as White
- one game with candidate as Black

Assign single-game score:

- win = `1.0`
- draw = `0.5`
- loss = `0.0`

For pair `i`, compute the candidate paired score:

`p_i = (score_as_white_i + score_as_black_i) / 2`

With `n = 250` opening pairs, compute:

- `mean = (1 / n) * sum(p_i)`
- `sd = sample standard deviation of the p_i values`
- `lcb95 = mean - t_(0.95, n-1) * sd / sqrt(n)`

Where `t_(0.95, n-1)` is the one-sided 95% Student-t critical value with `n - 1` degrees of freedom.

## Approval Rule

Approve the candidate only if all of the following are true:

1. The candidate builds successfully.
2. The evaluator completes and prints both required signatures.
3. The candidate records no crash, illegal move, or harness failure.
4. `lcb95 > 0.5`.

Otherwise reject the candidate.

Interpretation:

- `0.5` is the paired no-improvement baseline.
- `lcb95 > 0.5` means the lower 95% confidence bound still indicates the candidate outscored the approved baseline across paired openings.

## Rejection Conditions

Reject the candidate if any of the following happen:

- build failure
- evaluator crash
- missing start or end signature
- illegal move
- broken logging output
- harness failure
- `lcb95 <= 0.5`

Rejected candidates still get logged in `autoresearch/ATTEMPTS.md` with an inferred conclusion.

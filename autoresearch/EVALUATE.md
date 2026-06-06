# Fixed Evaluation Contract

This file defines the fixed evaluation harness contract for chess-engine `autoresearch` runs.

Do not modify this file during experiments.

## Purpose

Every candidate engine is evaluated only by playing it head-to-head against a fixed `Stockfish` opponent under fixed conditions.

The evaluator decides whether the candidate is approved. Diagnostic information can support the write-up, but it does not replace the approval rule.

## Fixed Match Rules

- Candidate opponent: local `Stockfish` configured with `UCI_LimitStrength=true` and `UCI_Elo=1350`
- Move time limit: `100ms` per move
- Total games: `500`
- Color split: `250` games with the candidate as White, `250` games with the candidate as Black
- Opening policy: use the fixed curated `Book.txt` opening-book positions checked into the repo, exclude the fresh starting board, randomize the sampled positions for the run, and use the same sampled position for the immediate color-swapped paired game
- Draw cutoff: use a fixed `max_plies` constant enforced by the evaluator
- Evaluation transport: direct local engine-vs-engine evaluation inside the engine workspace, not the legacy Python HTTP simulator
- No depth argument: evaluation is time-limited, not depth-limited

Every candidate must be judged under exactly the same rules.

## CLI Command

The evaluator is run through the local C# runner.

Before running evaluation, replace:

- `<candidate_engine_file>` with the newly cloned and modified engine file being tested
- `<stockfish_path>` with the local Stockfish executable path, preferably provided through `$STOCKFISH_PATH`

Run exactly:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock \
  --engine-file <candidate_engine_file> \
  --stockfish-path <stockfish_path> \
  --stockfish-elo 1350 \
  --games 500 \
  --time-limit-ms 100 \
  --max-plies 200 \
  --log \
  --short-sha <short_sha>
```

Example:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock \
  --engine-file engine_csharp/src/Engine.Core/V2/V2_5Engine.cs \
  --stockfish-path "$STOCKFISH_PATH" \
  --stockfish-elo 1350 \
  --games 500 \
  --time-limit-ms 100 \
  --max-plies 200 \
  --log \
  --short-sha 1a2b3c4
```

The caller must provide `<short_sha>` explicitly. Do not make the runner infer git state on behalf of the experiment loop.

Do not change the evaluator flags during normal experiments. The opening source defaults to `Book.txt` automatically and should not be overridden unless the workflow contract is intentionally revised outside the experiment loop.
The in-repo approved engine recorded in `autoresearch/ATTEMPTS.md` still matters as the seed file for the next candidate, but it is no longer the evaluation opponent.

## Git Recording Contract

Run the evaluator from the active experiment branch, where the candidate commit exists.

After the evaluation is successful, halted, or failed:

1. Capture the candidate short SHA and evaluation outcome.
2. Check out `main`.
3. Update `autoresearch/ATTEMPTS.md` on `main`.
4. Commit the attempts-log update on `main`.
5. Push `main` to the remote.
6. Return to the experiment branch.

If the candidate was approved, keep the candidate commit and continue the experiment branch from that commit. If the candidate was rejected, halted without approval, or failed, reset the experiment branch back to the previously approved in-repo engine commit before starting the next hypothesis.

## Required Evaluator Output

The evaluator must print these exact signatures:

- `=== EVALUATION START ===`
- `=== EVALUATION DONE ===`

If either signature is missing, treat the evaluation as failed until proven otherwise.

## Early Rejection Stop

An autoresearch run may forcibly stop the evaluator before `=== EVALUATION DONE ===` only when the observed partial result already makes promotion impossible under this contract.

Valid early-stop reasons include:

- `max_plies_count` has already reached or exceeded the rejection threshold for the configured game count. For the standard `--games 100` run with `max_plies_rate < 0.10`, the candidate is irreversibly rejected once `5` games terminate by `max_plies`.
- A crash, illegal move, broken logging output, or harness failure has already occurred.
- The remaining unplayed games cannot mathematically lift the paired-score lower confidence bound above the required approval threshold.

Early stopping is only a rejection convenience. It can never approve a candidate, and it does not weaken any approval requirement.

When an early stop is used:

- Preserve the partial canonical CSV if one was produced.
- Check out `main`, record the attempt in `autoresearch/ATTEMPTS.md` as `rejected`, commit that attempts-log update on `main`, and push `main` to the remote.
- State that `=== EVALUATION DONE ===` was intentionally absent due to early rejection.
- Report partial metrics from the games completed so far and identify the irreversible rejection condition.
- Return to the experiment branch and reset back to the previously approved in-repo engine seed commit as with any rejected candidate.

## Required Logged Artifacts

When `--log --short-sha <short_sha>` is supplied, the evaluator creates `autoresearch/logs/` on demand and writes its canonical per-game results file to:

`autoresearch/logs/<short_sha>-result.csv`

That CSV is the stable machine-readable artifact for per-game analysis. The console output must still be printed normally to stdout during the run so progress remains visible in real time.

The fixed CSV columns are owned by `engine_csharp/src/LocalTesting/Program.cs` and must stay stable across experiments unless this contract is intentionally revised outside the loop.

The Chess Engine written is allowed to produce optional additional artifacts within the same directory, for example `autoresearch/logs/<short_sha>-extra_info.csv`, but they are diagnostic only and do not replace the canonical result CSV. Here, you are free to track additional experiment unique information (E.g. Average number of depth evaluated per plier per game, Total transposition table utilization, etc) by generating the artifact from WITHIN the Engine code (NOT by altering `engine_csharp/src/LocalTesting/Program.cs`).

`autoresearch/logs/` should remain untracked by git.

## Required Reported Metrics

Every completed or halted evaluation must expose at least:

- candidate engine version/file
- evaluator baseline: `stockfish-1350`
- in-repo seed engine version/file
- total wins, draws, losses
- total score
- score rate
- average plies per game
- max_plies game count
- max_plies game rate
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

With `n = games / 2` opening pairs, compute:

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
5. `max_plies_rate < 0.10`.

Otherwise reject the candidate.

Interpretation:

- `0.5` is the paired no-improvement baseline.
- `lcb95 > 0.5` means the lower 95% confidence bound still indicates the candidate outscored the fixed `stockfish-1350` baseline across paired openings.
- `max_plies_rate < 0.10` means fewer than 5% of the games may terminate only because the fixed ply cap was reached. If more than 5% of the sample hits `max_plies`, the candidate is treated as insufficiently decisive for promotion even if its raw score is competitive.

## Rejection Conditions

Reject the candidate if any of the following happen:

- build failure
- evaluator crash
- missing start or end signature
- illegal move
- broken logging output
- harness failure
- `max_plies_rate >= 0.10`
- `lcb95 <= 0.5`

Rejected candidates still get logged in `autoresearch/ATTEMPTS.md` with an inferred conclusion.

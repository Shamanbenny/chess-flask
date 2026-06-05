# Autoresearch Attempts

This file is append-only during `autoresearch` runs and is updated on `main` after each evaluated outcome.

It serves two purposes:

- experiment log for approved and rejected candidates
- authoritative source of the latest approved baseline

Do not rewrite or delete prior entries (Except for the `## Latest Approved Baseline`). Add new entries at the end. Historical entries may use older branch naming conventions; keep them as recorded.

## Latest Approved Baseline (Adjust accordingly ONLY WHEN experiment is approved by evaluator)

- approved_version: `v2.2`
- approved_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- approved_commit: `765feb6`
- approved_recorded_at: `2026-06-05`
- notes: `Current v2.2 baseline after adding contained piece-square positional evaluation to the v2.0 in-house board engine.`

## Entry Template

Use this exact structure for each appended attempt:

```md
## Attempt: <timestamp> - <candidate_version>

- branch: `autoresearch/<MONTH_IN_3_CHARS><DAY><LETTER>`
- commit: `<short_sha>`
- status: `approved` | `rejected`
- baseline_version: `<version>`
- baseline_file: `<path>`
- candidate_version: `<version>`
- candidate_file: `<path>`
- version_bump: `minor` | `major`
- hypotheses:
  - `<hypothesis 1>`
  - `<hypothesis 2>`
  - `<hypothesis 3>`
- implementation_summary: `<short summary of what changed>`
- evaluation_log_path: `autoresearch/logs/<short_sha>-result.csv`
- extra_log_paths: `<optional additional csv/log files or n/a>`
- wins: `<int>`
- draws: `<int>`
- losses: `<int>`
- score: `<float>`
- score_rate: `<float>`
- average_plies: `<float>`
- average_processing_time_ms: `<float or n/a>`
- average_positions_or_nodes: `<float or n/a>`
- failure_counts: `<crash/illegal_move/timeout/harness counts>`
- verdict: `<why approved or rejected under EVALUATE.md>`
- inferred_conclusion: `<what future experiments should learn from this result>`
```

## Logging Rules

- Log every completed, halted, or failed evaluation.
- If evaluation does not complete cleanly enough to produce a valid result, record the failure reason once the cause is understood.
- The inferred conclusion is mandatory even for failures.
- If an attempt is approved, its entry becomes the new effective latest approved baseline for future runs.
- Update this file only after checking out `main`.
- Commit the attempts-log update on `main`, then push `main` to the remote before returning to the experiment branch.
- New experiment branches use the format `autoresearch/<MONTH_IN_3_CHARS><DAY><LETTER>`, for example `autoresearch/Jun6a`, then `autoresearch/Jun6b` if the first branch already exists.

## Initial Notes

- The current starting baseline is `v2.0`.
- Early experiments should bias toward contained changes that are easy to evaluate and easy to explain from the resulting metrics.
- Repeating a rejected idea is allowed only when the new attempt clearly differs in mechanism or scope.

## Attempt: 2026-06-05T18:39:57Z - v2.1

- branch: `autoresearch/Jun6a`
- commit: `6aee088`
- status: `rejected`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_1Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A lightweight quiet-history move-ordering table will improve alpha-beta cutoffs at 100ms per move without changing evaluation.`
- implementation_summary: `Cloned v2.0 into v2.1, renamed the public type/search entrypoint, and added a per-search quiet history table that rewards quiet beta-cutoff moves by side/from/to square.`
- evaluation_log_path: `autoresearch/logs/6aee088-result.csv`
- extra_log_paths: `n/a`
- wins: `n/a`
- draws: `n/a`
- losses: `n/a`
- score: `n/a`
- score_rate: `n/a`
- average_plies: `n/a`
- average_processing_time_ms: `n/a`
- average_positions_or_nodes: `n/a`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=1 incomplete/interrupted evaluation`
- verdict: `Rejected because the required 500-game evaluator run did not complete with the required === EVALUATION DONE === signature and the canonical CSV artifact is not a valid 500-game result. A prior partial run was draw-heavy and was interrupted by the user; a later diagnostic/retry overwrote the CSV to an invalid header-only artifact, so no fixed-contract metrics are recorded for approval.`
- inferred_conclusion: `The quiet-history ordering hypothesis did not produce enough visible early separation to justify continuing this interrupted run. Future attempts should prefer changes that alter decisive move choice or endgame conversion rather than only same-evaluation ordering tweaks, unless they include a mechanism likely to affect paired scores rather than mostly mirrored draws.`

## Attempt: 2026-06-05T19:44:30Z - v2.2

- branch: `autoresearch/Jun6a`
- commit: `765feb6`
- status: `approved`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.2`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A compact piece-square positional evaluation term will improve direct move choice at 100ms per move more reliably than search-only ordering tweaks.`
- implementation_summary: `Cloned v2.0 into v2.2, renamed the public type/search entrypoint, and added static piece-square tables for pawns, knights, bishops, rooks, queens, and phase-blended kings to the local evaluation.`
- evaluation_log_path: `autoresearch/logs/765feb6-result.csv` moved to `autoresearch/approved_logs/V2_2Engine-765feb6-result.csv`
- extra_log_paths: `n/a`
- wins: `117`
- draws: `350`
- losses: `33`
- score: `292.0/500`
- score_rate: `0.5840`
- average_plies: `67.93`
- average_processing_time_ms: `103.171`
- average_positions_or_nodes: `13705.48`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=0`
- verdict: `Approved under EVALUATE.md because the build succeeded, the evaluator printed both required signatures, failures were 0, max_plies_rate was 0.0000, and paired lcb95 was 0.5641 > 0.5.`
- inferred_conclusion: `A small direct positional evaluation layer is a strong improvement over pure material plus endgame/repetition terms for the v2.0 engine. Future attempts should build on v2.2 and tune or extend evaluation terms carefully, while watching for any added per-node cost that could reduce the current node rate advantage.`

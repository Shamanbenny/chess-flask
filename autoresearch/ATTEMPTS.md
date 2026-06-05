# Autoresearch Attempts

This file is append-only during `autoresearch` runs and is updated on `main` after each evaluated outcome.

It serves two purposes:

- experiment log for approved and rejected candidates
- authoritative source of the latest approved baseline

Do not rewrite or delete prior entries (Except for the `## Latest Approved Baseline`). Add new entries at the end. Historical entries may use older branch naming conventions; keep them as recorded.

## Latest Approved Baseline (Adjust accordingly ONLY WHEN experiment is approved by evaluator)

- approved_version: `v2.0`
- approved_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- approved_commit: `9090a86`
- approved_recorded_at: `2026-06-05`
- notes: `Current v2.0 baseline after the in-house board representation and move-generation revamp.`

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

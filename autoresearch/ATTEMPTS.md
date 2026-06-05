# Autoresearch Attempts

This file is append-only during `autoresearch` runs.

It serves two purposes:

- experiment log for approved and rejected candidates
- authoritative source of the latest approved baseline

Do not rewrite or delete prior entries (Except for the `## Latest Approved Baseline`). Add new entries at the end.

## Latest Approved Baseline (Adjust accordingly ONLY WHEN experiment is approved by evaluator)

- approved_version: `v2.0`
- approved_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- approved_commit: `db423ca`
- approved_recorded_at: `2026-06-05`
- notes: `Promoted after aspiration-window + PVS search candidate cleared lcb95 > 0.5 against v1.6.`

## Entry Template

Use this exact structure for each appended attempt:

```md
## Attempt: <timestamp> - <candidate_version>

- branch: `autoresearch/<tag>`
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

- Log every completed evaluation, including rejected candidates.
- If evaluation does not complete cleanly enough to produce a valid result, record the failure reason once the cause is understood.
- The inferred conclusion is mandatory even for failures.
- If an attempt is approved, its entry becomes the new effective latest approved baseline for future runs.

## Initial Notes

- The current starting baseline is `v1.6`.
- Early experiments should bias toward contained changes that are easy to evaluate and easy to explain from the resulting metrics.
- Repeating a rejected idea is allowed only when the new attempt clearly differs in mechanism or scope.

## Attempt: 2026-06-05 11:55:46 +08 - v2.0

- branch: `autoresearch-jun5a`
- commit: `db423ca`
- status: `approved`
- baseline_version: `v1.6`
- baseline_file: `engine_csharp/src/Engine.Core/V1/V1_6Engine.cs`
- candidate_version: `v2.0`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- version_bump: `major`
- hypotheses:
  - `Principal variation search will reduce repeated full-window searches after the first move and improve effective search efficiency under a fixed 250ms move budget.`
  - `A narrow aspiration window between completed iterative-deepening passes will reduce root search work while preserving tactical strength, with occasional full-window fallback only when needed.`
- implementation_summary: `Cloned v1.6 into v2.0, kept the same evaluation and TT design, and changed only the search loop by adding PVS-style zero-window searches for non-PV moves plus aspiration windows with full-window fallback at the root.`
- evaluation_log_path: `autoresearch/logs/db423ca-result.csv`
- extra_log_paths: `n/a`
- wins: `26`
- draws: `69`
- losses: `5`
- score: `60.5`
- score_rate: `0.6050`
- average_plies: `135.84`
- average_processing_time_ms: `285.238`
- average_positions_or_nodes: `885.26`
- failure_counts: `crash=0, illegal_move=0, timeout=0, harness=0`
- verdict: `Approved. The candidate built successfully, the evaluator printed both required signatures, no failures were recorded, and lcb95 = 0.5653 > 0.5.`
- inferred_conclusion: `Search-loop efficiency changes alone can materially improve match results against v1.6. The next useful angle should stay in search ordering or pruning rather than evaluation tuning, because this result improved conversion without changing evaluation heuristics.`

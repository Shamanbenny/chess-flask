# Autoresearch Attempts

This file is append-only during `autoresearch` runs and is updated on `main` after each evaluated outcome.

It serves two purposes:

- experiment log for approved and rejected candidates
- authoritative source of the latest approved baseline

Do not rewrite or delete prior entries (Except for the `## Latest Approved Baseline`). Add new entries at the end. Historical entries may use older branch naming conventions; keep them as recorded.

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
- evaluation_log_path: `autoresearch/approved_logs/V2_0Engine-db423ca-result.csv`
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

## Attempt: 2026-06-05 13:06:19 +08 - v2.1

- branch: `autoresearch-jun5a`
- commit: `146b093`
- status: `rejected`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_1Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `Adding killer-move and history-heuristic ordering for quiet moves will improve PVS cutoff efficiency and let the engine search more decisive lines within the fixed 250ms budget.`
- implementation_summary: `Cloned v2.0 into v2.1 and kept the same evaluation and PVS/aspiration structure, but added killer-move tracking plus a simple side/from/to history table to reprioritize quiet moves after beta cutoffs.`
- evaluation_log_path (Local ONLY): `autoresearch/logs/146b093-result.csv`
- extra_log_paths: `n/a`
- wins: `7`
- draws: `35`
- losses: `10`
- score: `24.5`
- score_rate: `0.4712`
- average_plies: `161.46`
- average_processing_time_ms: `n/a`
- average_positions_or_nodes: `n/a`
- failure_counts: `crash=0, illegal_move=0, timeout=0, harness=1 (evaluation interrupted by user after 52 games)`
- verdict: `Rejected. The build succeeded, but the evaluation was interrupted before completion and therefore did not satisfy the required end-signature contract. The partial 52-game sample was also already non-promotable: score_rate = 0.4712 and max_plies_count = 28/52 (53.85%), which exceeds the updated decisiveness threshold in EVALUATE.md.`
- inferred_conclusion: `This simple killer/history weighting did not make the search meaningfully more decisive against v2.0 and likely over-prioritized quiet refutation patterns that increase drawish max-plies games. The next search-efficiency hypothesis should bias toward selective pruning or reduction rather than stronger quiet-move bonuses alone.`

## Attempt: 2026-06-05 14:11:45 +08 - v2.1

- branch: `autoresearch/jun5-efficiency`
- commit: `769d639`
- status: `rejected`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_1Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `Late-move reductions for quiet non-checking moves in deeper non-root nodes will improve effective search depth under the fixed 250ms budget without repeating the rejected killer/history quiet-move weighting approach.`
- implementation_summary: `Cloned v2.0 into v2.1 and added a one-ply late-move reduction for quiet non-promotion, non-capture moves after the first few ordered moves, with full-depth re-search when the reduced zero-window search raised alpha.`
- evaluation_log_path (partial, Local ONLY): `autoresearch/logs/769d639-result.csv`
- extra_log_paths: `n/a`
- wins: `18`
- draws: `35`
- losses: `10`
- score: `35.5`
- score_rate: `0.5635`
- average_plies: `159.52`
- average_processing_time_ms: `284.383`
- average_positions_or_nodes: `864.83`
- failure_counts: `crash=0, illegal_move=0, timeout=0, harness=1 (evaluation intentionally stopped after 63 games; end signature absent)`
- verdict: `Rejected. The build succeeded and no engine crash or illegal move was observed, but the evaluator was stopped after 63/100 games once rejection was already clear: max_plies_count = 25/63 (39.68%), far above the max_plies_rate < 0.05 promotion requirement. The run did not print the required done signature and therefore cannot approve the candidate.`
- inferred_conclusion: `This blunt LMR rule increased searched nodes per move and did not solve decisiveness; it produced many max-plies games and unstable tactical outcomes despite a positive partial score. Future search-efficiency attempts should avoid broad late quiet-move reduction unless guarded by stronger tactical conditions, and should prefer safer ordering, check extensions, or mate-conversion mechanisms.`

## Attempt: 2026-06-05 15:10:21 +08 - v2.1

- branch: `autoresearch/Jun5a`
- commit: `42027ea`
- status: `rejected`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_1Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `Remembering completed root move scores between iterative-deepening passes will improve PVS root ordering and reduce wasted zero-window re-searches within the fixed 250ms budget.`
- implementation_summary: `Cloned v2.0 into v2.1 and kept evaluation, quiescence, TT behavior, PVS, and aspiration windows unchanged, but added root-score memory from the previous completed iteration to reorder root moves in the next iteration while preserving the TT move bonus.`
- evaluation_log_path: `autoresearch/logs/42027ea-result.csv`
- extra_log_paths: `n/a`
- wins: `5`
- draws: `17`
- losses: `10`
- score: `13.5/32`
- score_rate: `0.4219`
- average_plies: `150.88`
- average_processing_time_ms: `302.682`
- average_positions_or_nodes: `798.55`
- failure_counts: `crash=0, illegal_move=0, timeout=0, harness=1 (evaluation halted/rejected after 32 logged games; end signature absent)`
- verdict: `Rejected. The build succeeded and the evaluator printed the start signature, but the candidate became non-promotable once max_plies_count reached 5. The partial CSV contains 9 max_plies games in 32 logged games (28.13%), far above the max_plies_rate < 0.05 approval requirement; the run did not produce the required done signature and cannot approve.`
- inferred_conclusion: `Root reordering based on shallow prior-iteration scores did not improve effective search efficiency against v2.0. It trailed in score and produced many long max-plies games, so future search-efficiency attempts should not let previous root scores override the baseline's static/TT ordering without a much stricter guard such as only pinning the prior PV move.`

## Attempt: 2026-06-05 20:17:27 +08 - v2.1

- branch: `autoresearch/Jun5b`
- commit: `e6ab03a`
- status: `rejected`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_1Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A bounded one-ply check extension will make forcing and mating lines visible earlier under the fixed 250ms budget, improving decisiveness without using the previously rejected quiet-move history, broad LMR, or root-score reordering ideas.`
- implementation_summary: `Cloned v2.0 into v2.1, renamed the engine entrypoint, and changed only SearchChild so moves that give check preserve one extra ply of depth up to ply 12. Evaluation, TT behavior, quiescence, PVS, and aspiration windows were otherwise unchanged.`
- evaluation_log_path: `autoresearch/logs/e6ab03a-result.csv`
- extra_log_paths: `n/a`
- wins: `3`
- draws: `9`
- losses: `6`
- score: `7.5/18`
- score_rate: `0.4167`
- average_plies: `123.39`
- average_processing_time_ms: `314.943`
- average_positions_or_nodes: `944.27`
- failure_counts: `crash=0, illegal_move=0, timeout=0, harness=1 (evaluation intentionally stopped after 18 logged games; end signature absent)`
- verdict: `Rejected. The build succeeded and the evaluator printed the start signature, but the candidate became non-promotable once max_plies_count reached 5. The partial CSV contains 5 max_plies games in 18 logged games (27.78%), far above the max_plies_rate < 0.05 approval requirement; the run did not produce the required done signature and cannot approve.`
- inferred_conclusion: `Bounded check extension increased tactical visibility in some short wins but did not improve match strength or decisiveness against v2.0. It slowed candidate moves relative to the fixed budget and still produced many max-plies games, so future search-efficiency work should not add extensions without a stronger guard such as only extending evasions, recaptures near the king, or TT-supported forcing moves.`

## Attempt: 2026-06-05 20:34:27 +08 - v2.1

- branch: `autoresearch/Jun5b`
- commit: `c3a1841`
- status: `rejected`
- baseline_version: `v2.0`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_1Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `Caching the current check-state inside quiescence and capture-only move generation will reduce repeated board/legal-state work without changing intended search decisions, improving effective speed under the fixed 250ms budget.`
- implementation_summary: `Cloned v2.0 into v2.1, renamed the engine entrypoint, and threaded a cached inCheck value through OrderedSearchMoves and quiescence pruning. Search depth, evaluation, TT behavior, PVS, aspiration windows, and move-order scores were otherwise unchanged.`
- evaluation_log_path: `autoresearch/logs/c3a1841-result.csv`
- extra_log_paths: `n/a`
- wins: `6`
- draws: `11`
- losses: `2`
- score: `11.5/19`
- score_rate: `0.6053`
- average_plies: `137.89`
- average_processing_time_ms: `305.076`
- average_positions_or_nodes: `988.51`
- failure_counts: `crash=0, illegal_move=0, timeout=0, harness=1 (evaluation intentionally stopped after 19 logged games; end signature absent)`
- verdict: `Rejected. The build succeeded and the evaluator printed the start signature, but the candidate became non-promotable once max_plies_count reached 5. The partial CSV contains 7 max_plies games in 19 logged games (36.84%), far above the max_plies_rate < 0.05 approval requirement; the run did not produce the required done signature and cannot approve.`
- inferred_conclusion: `Pure quiescence overhead cleanup may be tactically competitive, but it does not address the current evaluator bottleneck: too many games still drift to the fixed ply cap. Future attempts should prioritize decisiveness mechanisms that convert winning positions or avoid sterile repetition, rather than relying only on small per-node speedups.`

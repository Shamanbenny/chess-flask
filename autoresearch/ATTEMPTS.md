# Autoresearch Attempts

This file is append-only during `autoresearch` runs and is updated on `main` after each evaluated outcome.

It serves two purposes:

- experiment log for approved and rejected candidates
- authoritative source of the latest approved in-repo engine seed

Do not rewrite or delete prior entries (Except for the `## Latest Approved Engine Seed`). Add new entries at the end. Historical entries may use older branch naming conventions; keep them as recorded.

## Fixed Evaluator Baseline

- evaluator_opponent: `stockfish-1350`
- evaluator_command: `dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock --stockfish-path "$STOCKFISH_PATH" --stockfish-elo 1350 --games 500 --time-limit-ms 100 --max-plies 200 --log --short-sha <short_sha>`
- notes: `This is the fixed external opponent for autoresearch approval. Do not swap it for the previous approved in-repo engine during normal experiment runs.`

## Latest Approved Engine Seed (Adjust accordingly ONLY WHEN experiment is approved by evaluator)

- approved_version: `v3.0`
- approved_file: `engine_csharp/src/Engine.Core/V3/V3_0Engine.cs`
- approved_commit: `5417662`
- approved_recorded_at: `2026-06-07`
- approved_reference_score_rate_vs_stockfish_1350: `0.6110`
- approved_reference_score_source: `autoresearch/approved_logs/V3_0Engine-5417662-result.csv`
- notes: `Current v3.0 baseline after adding an opening-book lookup before search and an optional per-game search context that persists the native transposition table across moves. New candidates must beat the approved seed's recorded stockfish-1350 reference score rate.`

## Entry Template

Use this exact structure for each appended attempt:

```md
## Attempt: <timestamp> - <candidate_version>

- branch: `autoresearch/<MONTH_IN_3_CHARS><DAY><LETTER>`
- commit: `<short_sha>`
- status: `approved` | `rejected`
- evaluator_baseline: `stockfish-1350`
- seed_version: `<version>`
- seed_file: `<path>`
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
- If an attempt is approved, its entry becomes the new effective latest approved in-repo engine seed for future runs.
- Update this file only after checking out `main`.
- Commit the attempts-log update on `main`, then push `main` to the remote before returning to the experiment branch.
- New experiment branches use the format `autoresearch/<MONTH_IN_3_CHARS><DAY><LETTER>`, for example `autoresearch/Jun6a`, then `autoresearch/Jun6b` if the first branch already exists.

## Initial Notes

- The fixed evaluator baseline is `stockfish-1350`.
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

## Attempt: 2026-06-05T20:56:06Z - v2.3

- branch: `autoresearch/Jun6a`
- commit: `d178e81`
- status: `rejected`
- baseline_version: `v2.2`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- candidate_version: `v2.3`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_3Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `Caching the endgame phase for king piece-square scoring will preserve v2.2 evaluation semantics while increasing searched nodes enough to improve paired results.`
- implementation_summary: `Cloned v2.2 into v2.3, renamed the public type/search entrypoint, and changed evaluation snapshot construction to compute endgame phase once, collect king squares during the existing board scan, and score king PSTs from the cached phase instead of rescanning the board.`
- evaluation_log_path: `autoresearch/logs/d178e81-result.csv`
- extra_log_paths: `n/a`
- wins: `65`
- draws: `359`
- losses: `76`
- score: `244.5/500`
- score_rate: `0.4890`
- average_plies: `79.41`
- average_processing_time_ms: `103.207`
- average_positions_or_nodes: `16057.04`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=1`
- verdict: `Rejected under EVALUATE.md because paired lcb95 was 0.4758 <= 0.5, despite a clean build, completed evaluator signatures, failures=0, and max_plies_rate=0.0020.`
- inferred_conclusion: `The cached king-phase cleanup did increase candidate nodes versus v2.2 (16057.04 vs 14956.35 average positions/nodes), but the timing/search perturbation did not translate into strength and slightly underperformed. Future work should not promote pure semantics-preserving micro-optimizations unless they also demonstrate a move-choice or search-depth advantage in paired results.`

## Attempt: 2026-06-05T22:04:03Z - v2.4

- branch: `autoresearch/Jun6a`
- commit: `b00b540`
- status: `rejected`
- baseline_version: `v2.2`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- candidate_version: `v2.4`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_4Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A small bishop-pair bonus will improve positional decisions on top of v2.2 with negligible extra evaluation cost.`
- implementation_summary: `Cloned v2.2 into v2.4, renamed the public type/search entrypoint, and added a 35 centipawn bishop-pair bonus to each side's existing positional total after bishop counts are collected.`
- evaluation_log_path: `autoresearch/logs/b00b540-result.csv`
- extra_log_paths: `n/a`
- wins: `80`
- draws: `348`
- losses: `72`
- score: `254.0/500`
- score_rate: `0.5080`
- average_plies: `76.55`
- average_processing_time_ms: `103.299`
- average_positions_or_nodes: `14658.04`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=0`
- verdict: `Rejected under EVALUATE.md because paired lcb95 was 0.4909 <= 0.5, despite a clean build, completed evaluator signatures, failures=0, raw score_rate=0.5080, and max_plies_rate=0.0000.`
- inferred_conclusion: `The bishop-pair bonus was directionally positive on raw score but too noisy and not statistically reliable against v2.2. Future evaluation changes should either be broader than a single small static bonus or targeted at specific conversion/draw problems, since small generic bonuses may add variance without clearing the paired confidence threshold.`

## Attempt: 2026-06-05T23:14:22Z - v2.5

- branch: `autoresearch/Jun6a`
- commit: `519f5a3`
- status: `approved`
- baseline_version: `v2.2`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- candidate_version: `v2.5`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A modest passed-pawn advancement bonus will improve conversion and pawn-structure decisions beyond v2.2's indirect endgame pawn-danger term.`
- implementation_summary: `Cloned v2.2 into v2.5, renamed the public type/search entrypoint, and added rank-scaled passed-pawn bonuses for pawns with no opposing pawn ahead on the same or adjacent files.`
- evaluation_log_path: `autoresearch/logs/519f5a3-result.csv` moved to `autoresearch/approved_logs/V2_5Engine-519f5a3-result.csv`
- extra_log_paths: `n/a`
- wins: `118`
- draws: `315`
- losses: `67`
- score: `275.5/500`
- score_rate: `0.5510`
- average_plies: `79.30`
- average_processing_time_ms: `103.412`
- average_positions_or_nodes: `14199.67`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=0`
- verdict: `Approved under EVALUATE.md because the build succeeded, the evaluator printed both required signatures, failures were 0, max_plies_rate was 0.0000, and paired lcb95 was 0.5315 > 0.5.`
- inferred_conclusion: `Passed-pawn advancement scoring is a statistically reliable improvement over v2.2 despite slightly lower node throughput. Future work should build from v2.5 and prefer targeted pawn/conversion evaluation refinements over isolated generic bonuses.`

## Attempt: 2026-06-06T00:21:40Z - v2.6

- branch: `autoresearch/Jun6a`
- commit: `a48fbf4`
- status: `rejected`
- baseline_version: `v2.5`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- candidate_version: `v2.6`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_6Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `Protected passed pawns should be valued slightly more than bare passed pawns because they are harder to blockade and more likely to convert.`
- implementation_summary: `Cloned v2.5 into v2.6, renamed the public type/search entrypoint, and added a 14 centipawn bonus when a passed pawn is defended from behind by a friendly pawn on an adjacent file.`
- evaluation_log_path: `autoresearch/logs/a48fbf4-result.csv`
- extra_log_paths: `n/a`
- wins: `93`
- draws: `322`
- losses: `85`
- score: `254.0/500`
- score_rate: `0.5080`
- average_plies: `75.00`
- average_processing_time_ms: `103.387`
- average_positions_or_nodes: `13999.47`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=0`
- verdict: `Rejected under EVALUATE.md because paired lcb95 was 0.4931 <= 0.5, despite a clean build, completed evaluator signatures, failures=0, raw score_rate=0.5080, and max_plies_rate=0.0000.`
- inferred_conclusion: `A protected-passed-pawn bonus on top of v2.5 was directionally positive but not statistically reliable. Future pawn work should avoid simply stacking small passed-pawn bonuses and should instead target clearer pawn-race, blockade, or promotion-conversion features.`

## Attempt: 2026-06-06T01:28:59Z - v2.7

- branch: `autoresearch/Jun6a`
- commit: `5188d75`
- status: `rejected`
- baseline_version: `v2.5`
- baseline_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- candidate_version: `v2.7`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_7Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A small doubled-pawn penalty may improve pawn-structure decisions without stacking more passed-pawn bonuses on top of v2.5.`
- implementation_summary: `Cloned v2.5 into v2.7, renamed the public type/search entrypoint, counted pawns per file during evaluation, and subtracted a 12 centipawn penalty for each extra same-color pawn on a file.`
- evaluation_log_path: `autoresearch/logs/5188d75-result.csv`
- extra_log_paths: `n/a`
- wins: `93`
- draws: `311`
- losses: `96`
- score: `248.5/500`
- score_rate: `0.4970`
- average_plies: `75.10`
- average_processing_time_ms: `103.441`
- average_positions_or_nodes: `14137.95`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=0`
- verdict: `Rejected under EVALUATE.md because paired lcb95 was 0.4760 <= 0.5, despite a clean build, completed evaluator signatures, failures=0, and max_plies_rate=0.0000.`
- inferred_conclusion: `A generic doubled-pawn penalty slightly underperformed v2.5 and did not improve the passed-pawn baseline. Future pawn-structure work should be more tactical or conversion-specific, such as blockade detection, pawn-race promotion distance, or king proximity to advanced passers, rather than adding broad static structure penalties.`

## Reference: 2026-06-06 - approved-log scoreboard vs stockfish-1350

- status: `reference_summary`
- evaluator_baseline: `stockfish-1350`
- source_logs:
  - `autoresearch/approved_logs/V2_0Engine-cbddf0e-result.csv`
  - `autoresearch/approved_logs/V2_2Engine-765feb6-result.csv`
  - `autoresearch/approved_logs/V2_5Engine-519f5a3-result.csv`
- excluded_logs:
  - `autoresearch/approved_logs/V2_2Engine-765feb6-result_old.csv`
  - `autoresearch/approved_logs/V2_5Engine-519f5a3-result_old.csv`
- extraction_notes: `Each listed CSV contains 500 games / 250 paired openings against stockfish-1350. Scores use engine_a_score, where engine_a is the named V2 engine. Average processing time and average positions/nodes use the named V2 engine side for each game. The V2_0 filename records cbddf0e, but the CSV rows record commit_short_sha=1234567 (Just ignore this discrepency as I hadn't gotten the sha_short at the time of running the manual evaluation).`
- quick_scores:
  - `V2_0Engine: file_sha=cbddf0e; csv_sha=1234567; wins=160; draws=94; losses=246; score=207.0/500; score_rate=0.4140; average_plies=85.68; average_processing_time_ms=103.566; average_positions_or_nodes=14483.78; max_plies=22; failures=0; terminations=checkmate:406, claimable_draw:64, max_plies:22, draw:8`
  - `V2_2Engine: file_sha=765feb6; csv_sha=765feb6; wins=258; draws=110; losses=132; score=313.0/500; score_rate=0.6260; average_plies=91.82; average_processing_time_ms=103.953; average_positions_or_nodes=11931.82; max_plies=35; failures=0; terminations=checkmate:390, claimable_draw:65, max_plies:35, draw:10`
  - `V2_5Engine: file_sha=519f5a3; csv_sha=519f5a3; wins=239; draws=122; losses=139; score=300.0/500; score_rate=0.6000; average_plies=91.72; average_processing_time_ms=104.102; average_positions_or_nodes=11603.15; max_plies=28; failures=0; terminations=checkmate:378, claimable_draw:85, max_plies:28, draw:9`
- ranking_by_raw_score_rate: `V2_2Engine 0.6260 > V2_5Engine 0.6000 > V2_0Engine 0.4140`
- inferred_conclusion: `For direct stockfish-1350 comparison from these approved-log CSVs, both v2.2 and v2.5 are materially ahead of v2.0, while v2.2 has the highest raw score in this specific log set. This reference is for fast future orientation only; candidate approval still follows the fixed autoresearch evaluator contract and the latest approved seed remains the section above.`

## Attempt: 2026-06-06T07:57:17Z - v2.8

- branch: `autoresearch/Jun6b`
- commit: `acdf45c` evaluated; `90def44` cherry-picked on `main`
- status: `approved`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.5`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- candidate_version: `v2.8`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_8Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A modest rook open-file and semi-open-file bonus will improve rook activity and conversion decisions beyond v2.5 without materially slowing evaluation.`
- implementation_summary: `Cloned v2.5 into v2.8, renamed the public type/search entrypoint, counted pawn files during evaluation, and added 18 centipawns for rooks on open files or 9 centipawns for rooks on semi-open files.`
- evaluation_log_path: `autoresearch/logs/acdf45c-result.csv` moved to `autoresearch/approved_logs/V2_8Engine-acdf45c-result.csv`
- extra_log_paths: `n/a`
- wins: `247`
- draws: `110`
- losses: `143`
- score: `302.0/500`
- score_rate: `0.6040`
- average_plies: `91.29`
- average_processing_time_ms: `104.166`
- average_positions_or_nodes: `12100.18`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=33`
- verdict: `Approved under EVALUATE.md because the build succeeded, the evaluator printed both required signatures, failures were 0, score_rate=0.6040 exceeded the approved seed reference 0.6000, paired lcb95 was 0.5708 > 0.5, and max_plies_rate was 0.0660 < 0.10.`
- inferred_conclusion: `Rook file activity scoring is a small but statistically reliable improvement on top of v2.5. Future work should build from v2.8 and can consider similarly targeted piece-activity terms, but the very narrow margin over v2.5 means new static evaluation terms still need full paired validation rather than relying on raw chess intuition.`

## Attempt: 2026-06-06T08:37:12Z - v2.9

- branch: `autoresearch/Jun6c`
- commit: `66b524e` evaluated; `fcb62a2` cherry-picked on `main`
- status: `approved`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.8`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_8Engine.cs`
- candidate_version: `v2.9`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_9Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A modest knight outpost bonus will improve minor-piece activity decisions on top of v2.8 without materially slowing evaluation.`
  - `Using pawn-defended and not enemy-pawn-attacked advanced knight squares is more targeted than another broad pawn-structure bonus.`
- implementation_summary: `Cloned v2.8 into v2.9, renamed the public type/search entrypoint, and added a 14 centipawn bonus for knights on advanced outpost ranks when defended by a friendly pawn and not attacked by an enemy pawn.`
- evaluation_log_path: `autoresearch/logs/66b524e-result.csv` moved to `autoresearch/approved_logs/V2_9Engine-66b524e-result.csv`
- extra_log_paths: `n/a`
- wins: `271`
- draws: `106`
- losses: `123`
- score: `324.0/500`
- score_rate: `0.6480`
- average_plies: `91.84`
- average_processing_time_ms: `104.111`
- average_positions_or_nodes: `12267.83`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=33`
- verdict: `Approved under EVALUATE.md because the build succeeded, the evaluator printed both required signatures, failures were 0, score_rate=0.6480 exceeded the approved seed reference 0.6040, paired lcb95 was 0.6178 > 0.5, and max_plies_rate was 0.0660 < 0.10.`
- inferred_conclusion: `A small targeted knight outpost term is a statistically reliable improvement on top of v2.8 and did not reduce throughput materially. Future work should build from v2.9 and continue with similarly specific piece-activity or king-safety features rather than generic pawn penalties.`

## Attempt: 2026-06-06T08:56:26Z - v2.10

- branch: `autoresearch/Jun6c`
- commit: `db46c34`
- status: `rejected`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.9`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_9Engine.cs`
- candidate_version: `v2.10`
- candidate_file: `engine_csharp/src/Engine.Core/V2/V2_10Engine.cs`
- version_bump: `minor`
- hypotheses:
  - `A small rook-on-seventh-rank activity bonus may improve conversion and attacking pressure on top of v2.9's open-file rook logic.`
- implementation_summary: `Cloned v2.9 into v2.10, renamed the public type/search entrypoint, and added a 16 centipawn bonus for rooks on the opponent's second rank.`
- evaluation_log_path: `autoresearch/logs/db46c34-result.csv`
- extra_log_paths: `n/a`
- wins: `256`
- draws: `97`
- losses: `147`
- score: `304.5/500`
- score_rate: `0.6090`
- average_plies: `91.39`
- average_processing_time_ms: `104.754`
- average_positions_or_nodes: `11534.74`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; max_plies=32`
- verdict: `Rejected under EVALUATE.md because score_rate=0.6090 did not exceed the approved seed reference 0.6480, despite a clean build, completed evaluator signatures, failures=0, paired lcb95=0.5766 > 0.5, and max_plies_rate=0.0640 < 0.10.`
- inferred_conclusion: `A generic rook-seventh-rank bonus degraded the stronger v2.9 baseline and reduced node throughput. Future rook activity work should not simply stack another static rook placement bonus on top of open-file scoring; it needs tighter conditions such as trapped king, targets on the seventh rank, or demonstrated conversion-specific compensation.`

## Attempt: 2026-06-07T09:53:14Z - v3.0

- branch: `main`
- commit: `5417662`
- status: `explicitly approved by user`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.9`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_9Engine.cs`
- candidate_version: `v3.0`
- candidate_file: `engine_csharp/src/Engine.Core/V3/V3_0Engine.cs`
- version_bump: `major`
- hypotheses:
  - `Persisting the native transposition table across moves within a game should reuse prior search work and improve move ordering/cutoffs compared with v2.9's per-move fresh TT allocation.`
  - `Checking a normalized FEN opening lookup before native search should avoid spending the 100ms move budget on early-book positions while preserving legal SAN output through the existing BoardState move path.`
- implementation_summary: `Forked the v2.9 search lineage into V3_0Engine, added an optional V3_0SearchContext with a shared TtEntry array that SearchModels can keep alive for a game and reset between games, and added an OpeningBook.TryGetMove pre-search path keyed by normalized FEN for full-piece opening positions. The v3.0 native search otherwise keeps the v2.9 evaluation lineage, including rook open/semi-open file scoring and knight outpost scoring.`
- evaluation_log_path: `autoresearch/approved_logs/V3_0Engine-5417662-result.csv`
- extra_log_paths: `n/a`
- wins: `254`
- draws: `103`
- losses: `143`
- score: `305.5/500`
- score_rate: `0.6110`
- average_plies: `100.21`
- average_processing_time_ms: `99.666`
- average_positions_or_nodes: `11522.13`
- failure_counts: `crash=0; illegal_move=0; timeout=0; harness=0; total=0`
- verdict: `Approved as the new v3.0 seed after a completed 500-game stockfish-1350 run with failures=0, score_rate=0.6110, paired mean=0.6110, paired sd=0.3055, and paired lcb95=0.5792 > 0.5. This is a major-version promotion focused on persistent per-game TT state and opening lookup behavior rather than a direct static-evaluation gain over v2.9.`
- inferred_conclusion: `The persistent TT plus opening-lookup architecture is stable enough to become the new approved seed, but its 0.6110 stockfish-1350 score rate is lower than v2.9's 0.6480 reference result. Future v3 experiments should build on the new per-game context/book infrastructure while measuring whether TT reuse, book coverage, and any later search/evaluation changes recover or exceed the previous v2.9 strength.`

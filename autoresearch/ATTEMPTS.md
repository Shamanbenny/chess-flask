# Autoresearch Attempts

This file is append-only during `autoresearch` runs and is updated after each evaluated outcome.

It serves as an experiment log for approved and rejected candidates.

Add new entries at the end. Do NOT delete any historical entries recorded here!

## Entry Template

Use this exact structure for each appended attempt:

```md
## Attempt: <timestamp> - <candidate_version>

- status: `approved` | `rejected`
- commit: `<short_sha>` if approved, otherwise `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `<version>`
- seed_file: `<path>`
- candidate_version: `<version>`
- version_bump: `minor` | `major`
- hypotheses:
  - `<hypothesis 1>`
  - `<hypothesis 2>`
  - `<hypothesis 3>`
- implementation_summary: `<short summary of what changed>`
- evaluation_log_path: `autoresearch/approved_logs/<short_sha>-result.csv` or `<n/a>`
- wins/draws/losses: `<int>/<int>/<int>`
- score: `<float>`
- score_rate: `<float>`
- average_plies: `<float>`
- average_processing_time_ms: `<float or n/a>`
- average_positions_or_nodes: `<float or n/a>`
- inferred_conclusion: `<what future experiments should learn from this result>`
```




## Attempt: 2026-06-05T18:39:57Z - v2.1

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.0`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.1`
- version_bump: `minor`
- hypotheses:
  - `A lightweight quiet-history move-ordering table will improve alpha-beta cutoffs at 100ms per move without changing evaluation.`
- implementation_summary: `Cloned v2.0 into v2.1, renamed the public type/search entrypoint, and added a per-search quiet history table that rewards quiet beta-cutoff moves by side/from/to square.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `n/a/n/a/n/a`
- score: `n/a`
- score_rate: `n/a`
- average_plies: `n/a`
- average_processing_time_ms: `n/a`
- average_positions_or_nodes: `n/a`
- inferred_conclusion: `The quiet-history ordering hypothesis did not produce enough visible early separation to justify continuing this interrupted run. Future attempts should prefer changes that alter decisive move choice or endgame conversion rather than only same-evaluation ordering tweaks, unless they include a mechanism likely to affect paired scores rather than mostly mirrored draws.`


## Attempt: 2026-06-05T19:44:30Z - v2.2

- status: `approved`
- commit: `765feb6`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.0`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_0Engine.cs`
- candidate_version: `v2.2`
- version_bump: `minor`
- hypotheses:
  - `A compact piece-square positional evaluation term will improve direct move choice at 100ms per move more reliably than search-only ordering tweaks.`
- implementation_summary: `Cloned v2.0 into v2.2, renamed the public type/search entrypoint, and added static piece-square tables for pawns, knights, bishops, rooks, queens, and phase-blended kings to the local evaluation.`
- evaluation_log_path: `autoresearch/approved_logs/V2_2Engine-765feb6-result.csv`
- wins/draws/losses: `117/350/33`
- score: `292.0`
- score_rate: `0.5840`
- average_plies: `67.93`
- average_processing_time_ms: `103.171`
- average_positions_or_nodes: `13705.48`
- inferred_conclusion: `A small direct positional evaluation layer is a strong improvement over pure material plus endgame/repetition terms for the v2.0 engine. Future attempts should build on v2.2 and tune or extend evaluation terms carefully, while watching for any added per-node cost that could reduce the current node rate advantage.`


## Attempt: 2026-06-05T20:56:06Z - v2.3

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.2`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- candidate_version: `v2.3`
- version_bump: `minor`
- hypotheses:
  - `Caching the endgame phase for king piece-square scoring will preserve v2.2 evaluation semantics while increasing searched nodes enough to improve paired results.`
- implementation_summary: `Cloned v2.2 into v2.3, renamed the public type/search entrypoint, and changed evaluation snapshot construction to compute endgame phase once, collect king squares during the existing board scan, and score king PSTs from the cached phase instead of rescanning the board.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `65/359/76`
- score: `244.5`
- score_rate: `0.4890`
- average_plies: `79.41`
- average_processing_time_ms: `103.207`
- average_positions_or_nodes: `16057.04`
- inferred_conclusion: `The cached king-phase cleanup did increase candidate nodes versus v2.2 (16057.04 vs 14956.35 average positions/nodes), but the timing/search perturbation did not translate into strength and slightly underperformed. Future work should not promote pure semantics-preserving micro-optimizations unless they also demonstrate a move-choice or search-depth advantage in paired results.`


## Attempt: 2026-06-05T22:04:03Z - v2.4

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.2`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- candidate_version: `v2.4`
- version_bump: `minor`
- hypotheses:
  - `A small bishop-pair bonus will improve positional decisions on top of v2.2 with negligible extra evaluation cost.`
- implementation_summary: `Cloned v2.2 into v2.4, renamed the public type/search entrypoint, and added a 35 centipawn bishop-pair bonus to each side's existing positional total after bishop counts are collected.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `80/348/72`
- score: `254.0`
- score_rate: `0.5080`
- average_plies: `76.55`
- average_processing_time_ms: `103.299`
- average_positions_or_nodes: `14658.04`
- inferred_conclusion: `The bishop-pair bonus was directionally positive on raw score but too noisy and not statistically reliable against v2.2. Future evaluation changes should either be broader than a single small static bonus or targeted at specific conversion/draw problems, since small generic bonuses may add variance without clearing the paired confidence threshold.`


## Attempt: 2026-06-05T23:14:22Z - v2.5

- status: `approved`
- commit: `519f5a3`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.2`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_2Engine.cs`
- candidate_version: `v2.5`
- version_bump: `minor`
- hypotheses:
  - `A modest passed-pawn advancement bonus will improve conversion and pawn-structure decisions beyond v2.2's indirect endgame pawn-danger term.`
- implementation_summary: `Cloned v2.2 into v2.5, renamed the public type/search entrypoint, and added rank-scaled passed-pawn bonuses for pawns with no opposing pawn ahead on the same or adjacent files.`
- evaluation_log_path: `autoresearch/approved_logs/V2_5Engine-519f5a3-result.csv`
- wins/draws/losses: `118/315/67`
- score: `275.5`
- score_rate: `0.5510`
- average_plies: `79.30`
- average_processing_time_ms: `103.412`
- average_positions_or_nodes: `14199.67`
- inferred_conclusion: `Passed-pawn advancement scoring is a statistically reliable improvement over v2.2 despite slightly lower node throughput. Future work should build from v2.5 and prefer targeted pawn/conversion evaluation refinements over isolated generic bonuses.`


## Attempt: 2026-06-06T00:21:40Z - v2.6

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.5`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- candidate_version: `v2.6`
- version_bump: `minor`
- hypotheses:
  - `Protected passed pawns should be valued slightly more than bare passed pawns because they are harder to blockade and more likely to convert.`
- implementation_summary: `Cloned v2.5 into v2.6, renamed the public type/search entrypoint, and added a 14 centipawn bonus when a passed pawn is defended from behind by a friendly pawn on an adjacent file.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `93/322/85`
- score: `254.0`
- score_rate: `0.5080`
- average_plies: `75.00`
- average_processing_time_ms: `103.387`
- average_positions_or_nodes: `13999.47`
- inferred_conclusion: `A protected-passed-pawn bonus on top of v2.5 was directionally positive but not statistically reliable. Future pawn work should avoid simply stacking small passed-pawn bonuses and should instead target clearer pawn-race, blockade, or promotion-conversion features.`


## Attempt: 2026-06-06T01:28:59Z - v2.7

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.5`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- candidate_version: `v2.7`
- version_bump: `minor`
- hypotheses:
  - `A small doubled-pawn penalty may improve pawn-structure decisions without stacking more passed-pawn bonuses on top of v2.5.`
- implementation_summary: `Cloned v2.5 into v2.7, renamed the public type/search entrypoint, counted pawns per file during evaluation, and subtracted a 12 centipawn penalty for each extra same-color pawn on a file.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `93/311/96`
- score: `248.5`
- score_rate: `0.4970`
- average_plies: `75.10`
- average_processing_time_ms: `103.441`
- average_positions_or_nodes: `14137.95`
- inferred_conclusion: `A generic doubled-pawn penalty slightly underperformed v2.5 and did not improve the passed-pawn baseline. Future pawn-structure work should be more tactical or conversion-specific, such as blockade detection, pawn-race promotion distance, or king proximity to advanced passers, rather than adding broad static structure penalties.`


## Attempt: 2026-06-06T07:57:17Z - v2.8

- status: `approved`
- commit: `90def44`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.5`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_5Engine.cs`
- candidate_version: `v2.8`
- version_bump: `minor`
- hypotheses:
  - `A modest rook open-file and semi-open-file bonus will improve rook activity and conversion decisions beyond v2.5 without materially slowing evaluation.`
- implementation_summary: `Cloned v2.5 into v2.8, renamed the public type/search entrypoint, counted pawn files during evaluation, and added 18 centipawns for rooks on open files or 9 centipawns for rooks on semi-open files.`
- evaluation_log_path: `autoresearch/approved_logs/V2_8Engine-acdf45c-result.csv`
- wins/draws/losses: `247/110/143`
- score: `302.0`
- score_rate: `0.6040`
- average_plies: `91.29`
- average_processing_time_ms: `104.166`
- average_positions_or_nodes: `12100.18`
- inferred_conclusion: `Rook file activity scoring is a small but statistically reliable improvement on top of v2.5. Future work should build from v2.8 and can consider similarly targeted piece-activity terms, but the very narrow margin over v2.5 means new static evaluation terms still need full paired validation rather than relying on raw chess intuition.`


## Attempt: 2026-06-06T08:37:12Z - v2.9

- status: `approved`
- commit: `fcb62a2`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.8`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_8Engine.cs`
- candidate_version: `v2.9`
- version_bump: `minor`
- hypotheses:
  - `A modest knight outpost bonus will improve minor-piece activity decisions on top of v2.8 without materially slowing evaluation.`
  - `Using pawn-defended and not enemy-pawn-attacked advanced knight squares is more targeted than another broad pawn-structure bonus.`
- implementation_summary: `Cloned v2.8 into v2.9, renamed the public type/search entrypoint, and added a 14 centipawn bonus for knights on advanced outpost ranks when defended by a friendly pawn and not attacked by an enemy pawn.`
- evaluation_log_path: `autoresearch/approved_logs/V2_9Engine-66b524e-result.csv`
- wins/draws/losses: `271/106/123`
- score: `324.0`
- score_rate: `0.6480`
- average_plies: `91.84`
- average_processing_time_ms: `104.111`
- average_positions_or_nodes: `12267.83`
- inferred_conclusion: `A small targeted knight outpost term is a statistically reliable improvement on top of v2.8 and did not reduce throughput materially. Future work should build from v2.9 and continue with similarly specific piece-activity or king-safety features rather than generic pawn penalties.`


## Attempt: 2026-06-06T08:56:26Z - v2.10

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.9`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_9Engine.cs`
- candidate_version: `v2.10`
- version_bump: `minor`
- hypotheses:
  - `A small rook-on-seventh-rank activity bonus may improve conversion and attacking pressure on top of v2.9's open-file rook logic.`
- implementation_summary: `Cloned v2.9 into v2.10, renamed the public type/search entrypoint, and added a 16 centipawn bonus for rooks on the opponent's second rank.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `256/97/147`
- score: `304.5`
- score_rate: `0.6090`
- average_plies: `91.39`
- average_processing_time_ms: `104.754`
- average_positions_or_nodes: `11534.74`
- inferred_conclusion: `A generic rook-seventh-rank bonus degraded the stronger v2.9 baseline and reduced node throughput. Future rook activity work should not simply stack another static rook placement bonus on top of open-file scoring; it needs tighter conditions such as trapped king, targets on the seventh rank, or demonstrated conversion-specific compensation.`


## Attempt: 2026-06-07T09:53:14Z - v3.0

- status: `explicitly approved by user`
- commit: `5417662`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v2.9`
- seed_file: `engine_csharp/src/Engine.Core/V2/V2_9Engine.cs`
- candidate_version: `v3.0`
- version_bump: `major`
- hypotheses:
  - `Persisting the native transposition table across moves within a game should reuse prior search work and improve move ordering/cutoffs compared with v2.9's per-move fresh TT allocation.`
  - `Checking a normalized FEN opening lookup before native search should avoid spending the 100ms move budget on early-book positions while preserving legal SAN output through the existing BoardState move path.`
- implementation_summary: `Forked the v2.9 search lineage into V3_0Engine, added an optional V3_0SearchContext with a shared TtEntry array that SearchModels can keep alive for a game and reset between games, and added an OpeningBook.TryGetMove pre-search path keyed by normalized FEN for full-piece opening positions. The v3.0 native search otherwise keeps the v2.9 evaluation lineage, including rook open/semi-open file scoring and knight outpost scoring.`
- evaluation_log_path: `autoresearch/approved_logs/V3_0Engine-5417662-result.csv`
- wins/draws/losses: `254/103/143`
- score: `305.5`
- score_rate: `0.6110`
- average_plies: `100.21`
- average_processing_time_ms: `99.666`
- average_positions_or_nodes: `11522.13`
- inferred_conclusion: `The persistent TT plus opening-lookup architecture is stable enough to become the new approved seed, but its 0.6110 stockfish-1350 score rate is lower than v2.9's 0.6480 reference result. Future v3 experiments should build on the new per-game context/book infrastructure while measuring whether TT reuse, book coverage, and any later search/evaluation changes recover or exceed the previous v2.9 strength.`


## Attempt: 2026-06-08T04:41:43Z - v3.1

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.0`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_0Engine.cs`
- candidate_version: `v3.1`
- version_bump: `minor`
- hypotheses:
  - `A targeted king-shelter term that rewards a real pawn shield in front of a home-rank king and penalizes open or semi-open nearby files will improve middlegame king safety and move choice on top of v3.0.`
- implementation_summary: `Cloned v3.0 into v3.1, renamed the public type and search-context entrypoints, and added a middlegame-scaled king-shelter evaluation bonus that inspects the pawn shield directly in front of a back-rank king and penalizes missing shelter on nearby open or semi-open files.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `140/56/129`
- score: `188.0`
- score_rate: `0.5785`
- average_plies: `98.73`
- average_processing_time_ms: `99.904`
- average_positions_or_nodes: `7514.65`
- inferred_conclusion: `This king-shelter term did not show a clear partial edge over the v3.0 approval bar before the repeated evaluator termination, and it also reduced average node throughput materially versus the v3.0 approved reference. Future v3 work should prefer simpler targeted activity or search-control changes over additional king-safety evaluation unless the mechanism is both cheap per node and robust under the full evaluator contract.`


## Attempt: 2026-06-08T04:44:58Z - v3.2

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.0`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_0Engine.cs`
- candidate_version: `v3.2`
- version_bump: `minor`
- hypotheses:
  - `A generation-aware transposition-table replacement policy will preserve fresher entries in the persistent v3 table and improve move quality at 100ms without adding much per-node cost.`
- implementation_summary: `Added v3.2 as a focused transposition-table experiment that changes TT storage to prefer same-generation updates instead of blindly replacing persistent entries.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `245/91/164`
- score: `290.5`
- score_rate: `0.5810`
- average_plies: `98.59`
- average_processing_time_ms: `100.874`
- average_positions_or_nodes: `8166.80`
- inferred_conclusion: `The TT generation replacement policy produced a stable full run and remained above break-even versus stockfish-1350, but it was still weaker than the approved v3.0 seed and searched fewer positions on average. Future v3 work should treat TT replacement tuning as insufficient on its own and focus on changes that recover throughput or improve move quality more directly.`


## Attempt: 2026-06-08T06:00:46Z - v3.3

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.0`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_0Engine.cs`
- candidate_version: `v3.3`
- version_bump: `minor`
- hypotheses:
  - `A cheap bishop safe-mobility term will improve minor-piece activity decisions on top of v3.0 without the high per-node cost seen in the rejected v3.1 king-shelter scan.`
  - `Rewarding bounded diagonal reach to non-edge squares that are not controlled by enemy pawns is more targeted than retrying a generic bishop-pair bonus or another broad static piece-placement term.`
- implementation_summary: `Cloned v3.0 into v3.3, renamed the public type and search-context entrypoints, and added a capped bishop safe-mobility evaluation bonus that counts diagonal reachable non-edge squares not attacked by enemy pawns.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `251/103/146`
- score: `302.5`
- score_rate: `0.6050`
- average_plies: `100.47`
- average_processing_time_ms: `99.615`
- average_positions_or_nodes: `11980.85`
- inferred_conclusion: `The bounded bishop safe-mobility term recovered some throughput versus the approved v3.0 reference (11980.85 vs 11522.13 average positions/nodes) and remained statistically above break-even, but it weakened raw score slightly and pushed max_plies close to the rejection threshold. Future v3 evaluation work should not add bishop mobility in this form; stronger candidates likely need either better opening/context use or a move-quality change that reduces long capped games while beating the 0.6110 v3.0 score-rate bar.`


## Attempt: 2026-06-08T06:21:42Z - v3.4

- status: `approved`
- commit: `e45c109`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.0`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_0Engine.cs`
- candidate_version: `v3.4`
- version_bump: `minor`
- hypotheses:
  - `Making draw/repetition contempt material-aware will improve score by letting materially worse positions prefer repetition or 50-move draw chances instead of steering away from saves.`
  - `Keeping the existing draw-avoidance penalties for equal-or-better positions should preserve v3.0's decisiveness while reducing avoidable losses.`
- implementation_summary: `Cloned v3.0 into v3.4, renamed the public type and search-context entrypoints, and changed RepetitionDrawAdjustment so materially worse positions receive bounded draw-saving bonuses while equal-or-better positions retain the existing repetition and draw penalties.`
- evaluation_log_path: `autoresearch/approved_logs/V3_4Engine-0398feb-result.csv`
- wins/draws/losses: `277/92/131`
- score: `323.0`
- score_rate: `0.6460`
- average_plies: `97.87`
- average_processing_time_ms: `99.675`
- average_positions_or_nodes: `11335.12`
- inferred_conclusion: `The prior v3.0 draw/repetition contempt was too aggressive when materially worse. Making draw-saving material-aware produced a large raw-score improvement, fewer losses, and stayed under the max-plies threshold despite more willingness to save bad positions. Future v3 work should build from v3.4 and preserve material-aware draw behavior; further improvements should target opening/context use or similarly cheap policies that improve conversion without increasing max_plies_rate beyond 0.10.`


## Attempt: 2026-06-08T17:22:22Z - v3.5

- status: `approved`
- commit: `8b24935`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.4`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_4Engine.cs`
- candidate_version: `v3.5`
- version_bump: `minor`
- hypotheses:
  - `A principal-variation search pass on non-first moves will let v3.5 search more narrowly behind the existing TT move ordering, improving effective depth at 100ms without adding evaluation overhead.`
  - `Applying the same narrow-window re-search policy at the root should preserve move quality while reducing wasted full-window work on clearly inferior alternatives.`
- implementation_summary: `Cloned v3.4 into v3.5 and changed the root and recursive negamax loops to use principal-variation style zero-window searches on non-first ordered moves, with full re-search only when a narrow probe beats the current alpha/best score.`
- evaluation_log_path: `autoresearch/approved_logs/8b24935-result.csv`
- wins/draws/losses: `320/73/107`
- score: `356.5`
- score_rate: `0.7130`
- average_plies: `84.1620`
- average_processing_time_ms: `98.1941`
- average_positions_or_nodes: `11576.6619`
- inferred_conclusion: `The principal-variation zero-window re-search policy produced a large strength gain over v3.4 while keeping failures at zero and reducing capped games, so v3 search should continue to build around cheap search-control improvements that exploit existing move ordering rather than adding heavier per-node evaluation work.`


## Attempt: 2026-06-08T17:59:54Z - v3.6

- status: `approved`
- commit: `62e5166`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.5`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_5Engine.cs`
- candidate_version: `v3.6`
- version_bump: `minor`
- hypotheses:
  - `Root aspiration windows around the previous iteration score will reduce full-window work on stable positions and improve effective depth at 100ms, while fail-low and fail-high re-search keeps the result exact when the window is wrong.`
- implementation_summary: `Cloned v3.5 into v3.6 and wrapped iterative deepening root searches in aspiration windows centered on the previous iteration score, with a factored root-search helper and automatic widening re-search on fail-low or fail-high before storing the exact root result.`
- evaluation_log_path: `autoresearch/approved_logs/62e5166-result.csv`
- wins/draws/losses: `343/49/108`
- score: `367.5`
- score_rate: `0.7350`
- average_plies: `84.2260`
- average_processing_time_ms: `97.8252`
- average_positions_or_nodes: `10700.0111`
- inferred_conclusion: `Root aspiration windows produced another meaningful v3 search-strength gain over the already strong v3.5 seed while keeping failures at zero and further lowering capped games. Future experiments should continue prioritizing cheap root and move-ordering search-control improvements that exploit iterative-deepening score stability, rather than adding heavier per-node evaluation terms.`

## Attempt: 2026-06-08T18:03:52Z - v3.7

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.6`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_6Engine.cs`
- candidate_version: `v3.7`
- version_bump: `minor`
- hypotheses:
  - `A persistent quiet-move ordering layer built from killer moves and quiet history will improve v3.6's PVS and aspiration-window cutoffs at 100ms without adding per-node evaluation cost.`
- implementation_summary: `Cloned v3.6 into v3.7 and extended the search context with persistent killer-move and quiet-history tables, then fed those heuristics into quiet move ordering and updated them on quiet beta cutoffs at the root and recursive negamax nodes.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `n/a/n/a/n/a`
- score: `n/a`
- score_rate: `n/a`
- average_plies: `n/a`
- average_processing_time_ms: `n/a`
- average_positions_or_nodes: `n/a`
- inferred_conclusion: `This attempt failed before evaluation because the move-ordering refactor introduced a build-breaking API mismatch in the sandbox candidate, so it provides no strength signal against v3.6. Future search-control experiments should keep the change surface equally narrow but verify helper accessibility and static-versus-instance call boundaries before handing control back to the orchestrator.`

## Attempt: 2026-06-08T18:09:45Z - v3.8

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.6`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_6Engine.cs`
- candidate_version: `v3.8`
- version_bump: `minor`
- hypotheses:
  - `Persistent killer-move ordering for quiet beta cutoffs will improve v3.6's PVS and aspiration-window searches at 100ms by getting strong refutations to the front faster in later sibling nodes.`
  - `A side-aware quiet-history table keyed by from/to squares will reinforce repeatedly successful quiet cutoffs across positions without changing evaluation cost, giving better move ordering than transposition-table moves alone.`
- implementation_summary: `Cloned v3.6 into v3.8 and added persistent primary/secondary killer moves plus a side-aware quiet-history table to the search context, then used those heuristics to score quiet move ordering and reward quiet beta cutoffs at the root and recursive negamax nodes while keeping the change self-contained in the engine file.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `n/a/n/a/n/a`
- score: `n/a`
- score_rate: `n/a`
- average_plies: `n/a`
- average_processing_time_ms: `n/a`
- average_positions_or_nodes: `n/a`
- inferred_conclusion: `This attempt produced no strength signal because the killer-move and quiet-history ordering changes failed at build time before evaluation. Future search-control experiments should keep the move-ordering surface narrow, verify all new helper signatures and call sites against the board API before return, and prefer compile-checked incremental additions over broader heuristic rewiring.`

## Attempt: 2026-06-08T18:25:38Z - v3.9

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.6`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_6Engine.cs`
- candidate_version: `v3.9`
- version_bump: `minor`
- hypotheses:
  - `Internal iterative deepening at deeper non-check nodes with no transposition-table move will seed a useful hash move for v3.6's existing PVS ordering, improving cutoffs at 100ms without adding evaluation cost.`
- implementation_summary: `Cloned v3.6 into v3.9 and added a contained internal-iterative-deepening fallback in negamax so deeper non-check nodes without a TT move first run a reduced-depth probe to populate and reuse a transposition-table move for the main ordered search.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `329/76/95`
- score: `367.0`
- score_rate: `0.7340`
- average_plies: `87.7500`
- average_processing_time_ms: `98.1286`
- average_positions_or_nodes: `10684.7203`
- inferred_conclusion: `Internal iterative deepening as a TT-move seeding fallback was effectively neutral on top of v3.6: it preserved stability and a strong paired lower bound, but slightly underperformed the approved seed on score_rate while also trimming nodes a bit. Future v3 search-control experiments should avoid spending extra work on generic reduced-depth bootstrap probes unless they produce a clearer move-ordering gain, and should instead target higher-leverage ordering or pruning changes that more directly improve root move selection within the same 100ms budget.`

## Attempt: 2026-06-09T05:47:08Z - v3.10

- status: `approved`
- commit: `41846bf`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.6`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_6Engine.cs`
- candidate_version: `v3.10`
- version_bump: `minor`
- hypotheses:
  - `Late-move reductions for quiet, later-ordered moves should let v3.10 search deeper on low-priority branches without weakening principal-variation re-search when a reduced move proves interesting.`
  - `A narrow killer-move ordering layer for quiet beta cutoffs should improve v3.10's existing PVS move ordering enough to make those late-move reductions safer and more effective at 100ms.`
- implementation_summary: `Cloned v3.6 into v3.10 and added quiet-move killer ordering plus a contained late-move reduction path for later-ordered quiet moves, with full PVS re-search whenever a reduced probe still raises alpha.`
- evaluation_log_path: `autoresearch/approved_logs/V3_10Engine-41846bf-result.csv`
- wins/draws/losses: `682/130/188`
- score: `747.0`
- score_rate: `0.7470`
- average_plies: `86.9570`
- average_processing_time_ms: `98.9572`
- average_positions_or_nodes: `8168.5526`
- inferred_conclusion: `The contained quiet-move killer ordering plus late-move reduction policy produced a real improvement over v3.6 under the full 1000-game Stockfish-1350 contract, clearing the prior 0.7350 score_rate while keeping capped games low and failures at zero. Future v3 work should keep building on cheap search-control changes that improve move ordering and reduce wasted work on low-priority branches, while being careful not to overextend reduction heuristics in ways that increase tactical misses or long drawn games.`

## Attempt: 2026-06-09T06:33:00Z - v3.11

- status: `approved`
- commit: `8214d59`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.10`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_10Engine.cs`
- candidate_version: `v3.11`
- version_bump: `minor`
- hypotheses:
  - `Adding a lightweight bishop mobility term will improve piece-activity move selection more reliably than another generic one-off static bonus.`
  - `Rewarding king-supported advanced passed pawns and penalizing directly blockaded passed pawns in endgames will improve conversion and reduce wasted winning lines.`
- implementation_summary: `Added bishop mobility scoring, added an endgame passed-pawn escort/blockade evaluation term based on king proximity to the square in front of advanced passers, and refactored king PST scoring to use the already-computed endgame phase inside the evaluation snapshot.`
- evaluation_log_path: `autoresearch/approved_logs/V3_11Engine-8214d59-result.csv`
- wins/draws/losses: `685/143/172`
- score: `756.5`
- score_rate: `0.7565`
- average_plies: `86.7240`
- average_processing_time_ms: `98.0551`
- average_positions_or_nodes: `10445.0749`
- inferred_conclusion: `The combined bishop-mobility and king-supported passed-pawn endgame evaluation changes produced a statistically reliable improvement over v3.10 while keeping failures at zero and max-plies safely below the threshold. Future experiments should continue exploring targeted low-cost activity and conversion terms, especially endgame features that change practical winning technique rather than broad generic structure bonuses.`

## Attempt: 2026-06-09T07:01:36Z - v3.12

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.11`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_11Engine.cs`
- candidate_version: `v3.12`
- version_bump: `minor`
- hypotheses:
  - `A modest rook-on-seventh-rank activity bonus should improve practical attacking and conversion move choice with minimal evaluation overhead.`
  - `Rewarding connected advanced passed pawns in endgames should improve promotion-race and winning-line conversion beyond the existing single-passer escort/blockade term.`
- implementation_summary: `Added a rook-on-seventh-rank activity bonus with an extra incentive when the opposing king is stuck on the back rank, and added an endgame-weighted connected passed-pawn bonus for adjacent advanced passers while reusing the evaluator's existing passed-pawn tracking.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `677/151/172`
- score: `752.5`
- score_rate: `0.7525`
- average_plies: `84.6120`
- average_processing_time_ms: `97.8991`
- average_positions_or_nodes: `10439.0495`
- inferred_conclusion: `The added rook-on-seventh and connected-passed-pawn bonuses were directionally plausible but slightly underperformed the v3.11 seed, so stacking more small generic activity/conversion bonuses on top of v3.11 is not enough by itself. Future v3 experiments should favor more selective evaluation terms or search changes that materially alter tactical move choice, rather than broad static bonuses that mostly preserve existing plans.`

## Attempt: 2026-06-09T08:09:15Z - v3.13

- status: `approved`
- commit: `49960e8`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.11`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_11Engine.cs`
- candidate_version: `v3.13`
- version_bump: `minor`
- hypotheses:
  - `Conservative null-move pruning at deeper non-check nodes with non-pawn material should reduce wasted search on clearly safe fail-high branches and improve tactical move selection within the 100ms budget.`
- implementation_summary: `Added a guarded null-move pruning path to negamax with no-null-reply recursion control, a pawns-and-king-only endgame exclusion to reduce zugzwang risk, and native-board null-move make/unmake helpers while preserving the existing LMR/PVS framework.`
- evaluation_log_path: `autoresearch/approved_logs/V3_13Engine-49960e8-result.csv`
- wins/draws/losses: `708/139/153`
- score: `777.5`
- score_rate: `0.7775`
- average_plies: `86.3960`
- average_processing_time_ms: `98.3980`
- average_positions_or_nodes: `11407.9374`
- inferred_conclusion: `The guarded null-move pruning change was a clear improvement over v3.11, raising score_rate from 0.7565 to 0.7775 while keeping failures at zero and max-plies comfortably within the approval threshold. Future v3 experiments should continue exploring selective search-control changes with explicit zugzwang and endgame safety guards, since this branch benefited more from a contained pruning improvement than from stacking additional small static evaluation bonuses.`

## Attempt: 2026-06-09T08:36:59Z - v3.14

- status: `approved`
- commit: `ec54e97`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.13`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_13Engine.cs`
- candidate_version: `v3.14`
- version_bump: `minor`
- hypotheses:
  - `Adding shallow reverse futility pruning at non-check nodes with remaining non-pawn material should cut clearly fail-high branches near the horizon and improve root move selection within the 100ms budget.`
- implementation_summary: `Added guarded reverse futility pruning in negamax for shallow non-check nodes, using the existing static evaluation only when the side to move still has non-pawn material and the margin over beta is comfortably large.`
- evaluation_log_path: `autoresearch/approved_logs/V3_14Engine-ec54e97-result.csv`
- wins/draws/losses: `752/113/135`
- score: `808.5`
- score_rate: `0.8085`
- average_plies: `83.9430`
- average_processing_time_ms: `98.1973`
- average_positions_or_nodes: `12580.9138`
- inferred_conclusion: `The guarded shallow reverse futility pruning change was a strong improvement over v3.13, raising score_rate from 0.7775 to 0.8085 with zero failures and a comfortably acceptable max-plies rate. Future v3 experiments should keep exploring selective shallow pruning and move-filtering ideas that save search on clearly safe branches, while preserving the existing endgame and zugzwang guards that keep aggressive pruning from backfiring.`

## Attempt: 2026-06-09T09:04:13Z - v3.15

- status: `approved`
- commit: `901cf13`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.14`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_14Engine.cs`
- candidate_version: `v3.15`
- version_bump: `minor`
- hypotheses:
  - `Guarded shallow quiet-move futility pruning on later-ordered moves should save search at depth 1-2 in clearly non-improving non-check nodes, improving root move selection within the 100ms budget without changing evaluation.`
- implementation_summary: `Added a shallow quiet-move futility pruning path in negamax for later-ordered quiet moves at depths up to 2, reusing static evaluation when already available from reverse futility pruning and keeping the existing non-check and pawns-and-king-only safety guards.`
- evaluation_log_path: `autoresearch/approved_logs/V3_15Engine-901cf13-result.csv`
- wins/draws/losses: `788/99/113`
- score: `837.5`
- score_rate: `0.8375`
- average_plies: `80.3900`
- average_processing_time_ms: `98.6030`
- average_positions_or_nodes: `10260.1696`
- inferred_conclusion: `The guarded shallow quiet-move futility pruning change was a strong improvement over v3.14, raising score_rate from 0.8085 to 0.8375 while keeping failures at zero and reducing capped games to a low 0.0330 max_plies_rate. Future v3 experiments should continue exploring tightly guarded shallow move-pruning and search-selectivity ideas that trim clearly unpromising quiet branches without relaxing the existing endgame and tactical safety checks.`

## Attempt: 2026-06-09T09:31:57Z - v3.16

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.15`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_15Engine.cs`
- candidate_version: `v3.16`
- version_bump: `minor`
- hypotheses:
  - `A middlegame king-shield bonus that rewards pawns in front of the king and penalizes missing cover will improve defensive move choice more reliably than another search-only heuristic tweak.`
  - `A connected-passed-pawn bonus for adjacent advanced passers will improve endgame conversion beyond the existing single-passer and king-escort terms.`
- implementation_summary: `Added a tapered king-shield evaluation around each king that scores nearby pawn cover only outside pure endgames, and added a connected passed pawn bonus for adjacent advanced passers on neighboring files with similar ranks.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `756/111/133`
- score: `811.5`
- score_rate: `0.8115`
- average_plies: `83.8490`
- average_processing_time_ms: `99.0042`
- average_positions_or_nodes: `10068.7432`
- inferred_conclusion: `The added king-shield and connected-passed-pawn terms preserved stability and remained strong, but they reduced score_rate versus the approved v3.15 baseline and did not justify replacing it. Future v3.x attempts should avoid stacking broad static evaluation bonuses unless they target a clearly missing decision pattern with tighter conditions or are paired with a search change that converts the extra evaluation signal into stronger move selection.`

## Attempt: 2026-06-10T08:11:56Z - v3.17

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.15`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_15Engine.cs`
- candidate_version: `v3.17`
- version_bump: `minor`
- hypotheses:
  - `A conservative depth-1 razoring shortcut at quiet non-check nodes will skip clearly hopeless full move generation while still searching captures through quiescence, improving effective search selectivity on top of v3.15's futility pruning.`
- implementation_summary: `Added a guarded depth-1 razoring check in negamax that reuses static evaluation, excludes check and pawns-and-king-only positions, and falls back to quiescence when static evaluation is safely below alpha.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `778/102/120`
- score: `829.0`
- score_rate: `0.8290`
- average_plies: `83.5790`
- average_processing_time_ms: `98.9151`
- average_positions_or_nodes: `10486.3856`
- inferred_conclusion: `The depth-1 razoring shortcut remained stable with zero crashes, illegal moves, or timeouts, but it underperformed the v3.15 seed at 0.8290 versus 0.8375 and slightly increased capped games to 0.0450. Future v3 attempts should avoid adding this broad pre-move-generation razoring layer on top of the existing futility pruning, and should instead target more selective pruning conditions or move-ordering changes that preserve v3.15's tactical coverage.`

## Attempt: 2026-06-11T07:06:10Z - v3.18

- status: `approved`
- commit: `99698ba`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.15`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_15Engine.cs`
- candidate_version: `v3.18`
- version_bump: `minor`
- hypotheses:
  - `A capped side-aware quiet-history table for quiet beta-cutoff moves will improve v3.15-style killer/LMR/futility search ordering without changing evaluation or adding broad pruning risk.`
- implementation_summary: `Added a persistent quiet-history table to the v3.18 search context, scored quiet moves with a small capped history bonus below TT/capture/killer priority, and rewarded quiet beta cutoffs by remaining-depth-squared history increments while preserving the existing evaluation and pruning guards.`
- evaluation_log_path: `autoresearch/approved_logs/V3_18Engine-99698ba-result.csv`
- wins/draws/losses: `796/92/112`
- score: `842.0`
- score_rate: `0.8420`
- average_plies: `80.3890`
- average_processing_time_ms: `98.9959`
- average_positions_or_nodes: `9776.6691`
- inferred_conclusion: `Approved: the capped side-aware quiet-history ordering layer produced a small but real improvement over v3.15, raising score_rate from 0.8375 to 0.8420 with lcb95=0.8246, zero crash/illegal/timeout/harness failures, and max_plies_rate=0.0390. Future v3 experiments should continue favoring narrow move-ordering and search-selectivity changes that improve the existing LMR/futility stack without broadening pruning risk or adding evaluation cost.`

## Attempt: 2026-06-11T07:32:35Z - v3.19

- status: `rejected`
- commit: `<n/a>`
- evaluator_baseline: `stockfish-1350`
- seed_version: `v3.18`
- seed_file: `engine_csharp/src/Engine.Core/V3/V3_18Engine.cs`
- candidate_version: `v3.19`
- version_bump: `minor`
- hypotheses:
  - `Adding a bounded quiet-history malus for quiet moves that fail low will prevent stale refuted quiet moves from staying over-prioritized, improving move ordering on top of v3.18 without changing evaluation or broadening pruning.`
- implementation_summary: `Added a negative quiet-history floor, clamped quiet-history ordering scores on both sides, and penalized quiet non-raising moves by a small depth-squared amount while preserving the existing quiet beta-cutoff reward path.`
- evaluation_log_path: `<n/a>`
- wins/draws/losses: `775/97/128`
- score: `823.5`
- score_rate: `0.8235`
- average_plies: `80.6790`
- average_processing_time_ms: `98.9502`
- average_positions_or_nodes: `9512.5126`
- inferred_conclusion: `Rejected: the bounded quiet-history fail-low malus was stable with zero crash/illegal/timeout/harness failures and max_plies_rate=0.0380, but it reduced score_rate to 0.8235 versus the approved v3.18 seed at 0.8420. Future attempts should not add broad negative quiet-history feedback on top of v3.18's capped reward-only history table; the malus likely demoted useful quiet tries or made ordering less stable across iterative deepening. Prefer narrower move-ordering changes that only affect clearly bad quiet moves, or tune positive history/killer interactions without penalizing all non-raising quiet moves.`
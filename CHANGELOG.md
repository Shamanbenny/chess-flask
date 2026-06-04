# Changelog

This file tracks the accepted algorithm history of the chess bots in this repository.

The `v1.x` family is heavily informed by Sebastian Lague's [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk). That reference should be read as implementation guidance for the search progression, not as a claim that this repository is a line-by-line copy of his engine.

Architecture note: the repository may change how local development and serving are organized, but this file should only record accepted engine-version behavior. Workspace or language splits are documented in `README.md` and `JOURNEY.md`, not as standalone engine versions.

## v1.6

- C#-specific follow-up to `v1.5` focused on search throughput after cross-referencing Sebastian Lague's [`Chess-Coding-Adventure`](https://github.com/SebLague/Chess-Coding-Adventure/tree/Chess-V1-Unity) implementation path and recognizing how much slower this repository's search was under the same kind of endgame pressure.
- Search: retained the `v1.5` shape of iterative deepening, alpha-beta, quiescence, and transposition-table reuse, but changed several hot-path costs that were suppressing node throughput.
- Board-state and hash changes in the C# port:
  - replaced full-board Zobrist recomputation on every `Push`/`Pop` with a deterministic hash over the normalized FEN position key already being cached for repetition logic
  - switched repetition history from string keys to hashed position keys so repetition checks stop paying string-comparison costs on every probe
  - added direct `HasAnyLegalMoves()` and `LegalMoveCount()` helpers so terminal checks no longer need `LegalMoves().ToList()` allocations
- Transposition-table changes in `v1.6`:
  - replaced the dictionary-backed TT used by the early C# `v1.5` path with a fixed-size indexed table
  - kept best-move, depth, bound, and age replacement semantics, but removed avoidable dictionary and allocation overhead from every probe/store
- Move-ordering changes in `v1.6`:
  - stopped scoring every legal move by pushing it on the board, checking derived state, and popping it again
  - now uses a cheaper static ordering mix of TT move priority, MVV-LVA-style capture scoring, promotion bonuses, and pawn-danger penalties
- Evaluation changes in `v1.6`:
  - replaced repeated piece-count scans and clone-based king-mobility checks with a lighter single-pass snapshot of material and endgame structure
  - preserved the `v1.4` / `v1.5` endgame-conversion ideas, but made them cheaper to apply per node
- Search-bound changes in `v1.6`:
  - added mate-distance pruning so once a shorter mating line is known, obviously longer mates do not keep expanding the tree
  - moved time checks onto `Stopwatch` timestamps in the new search path while still keeping periodic timeout safety
- Observed local effect during the first C# `puzzle-1` comparison at `1.0s` per move:
  - `v1.5` completed depth `2` and searched `784` nodes on White 1
  - `v1.6` completed depth `3` and searched `6,090` nodes on White 1
  - `v1.6` also raised TT reuse materially on that run, from a very low-hit `v1.5` baseline to a much more active cutoff-producing table
- Intended improvement over `v1.5`:
  - make each searched node meaningfully cheaper before attempting more ambitious pruning ideas
  - align the local C# engine more closely with the performance-conscious style seen in `Chess-Coding-Adventure`
  - improve the odds that iterative deepening and TT reuse actually pay off inside a `1` second budget instead of being drowned out by board-management overhead

### References

- Sebastian Lague's [`Chess-Coding-Adventure`](https://github.com/SebLague/Chess-Coding-Adventure/tree/Chess-V1-Unity)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Mate Distance Pruning](https://www.chessprogramming.org/Mate_Distance_Pruning)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Move Ordering](https://www.chessprogramming.org/Move_Ordering)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Transposition Table](https://www.chessprogramming.org/Transposition_Table)

## v1.5b

- C#-specific `engine_csharp` follow-up to `v1.5`; this is not a new cross-repo historical engine version for the Python path.
- Search: retained the `v1.5` iterative-deepening, alpha-beta, and quiescence structure, but corrected several performance-costly local implementation choices in the C# port.
- Transposition table changes in the C# port:
  - replaced FEN-string dictionary keys with a deterministic [Zobrist hash](https://www.chessprogramming.org/Zobrist_Hashing) over piece placement, side to move, castling rights, and en-passant file
  - kept TT probing and bound cutoffs in the main negamax search
  - removed TT probing from quiescence because the local C# `v1.5` implementation was not storing quiescence entries and was paying lookup overhead for little or no reuse
- Time-management changes in the C# port:
  - wall-clock timeout checks are now throttled to periodic node intervals instead of calling `DateTime.UtcNow` at every searched node
  - this preserves iterative-deepening timeout safety while improving node throughput under short think times
- Local testing output changes in the C# port:
  - `positions=` now reports searched nodes for `v1.5` when that metric is available, instead of reusing `MovesEvaluated` as a proxy
  - detailed output also exposes both `moves_evaluated` and `nodes_searched` so C# `v1.5` runs can be compared more honestly against fixed-depth versions
- Intended improvement over the initial C# `v1.5` port:
  - reduce avoidable hashing and clock-check overhead that was suppressing search depth under a 1-second budget
  - make the TT more aligned with normal engine practice and more likely to pay for itself at short time controls
  - make local benchmark output reflect actual search effort instead of a root/edge-count proxy

### References

- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Zobrist Hashing](https://www.chessprogramming.org/Zobrist_Hashing)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Transposition Table](https://www.chessprogramming.org/Transposition_Table)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Time Management](https://www.chessprogramming.org/Time_Management)

## v1.5

- Search: `v1.4`-style alpha-beta plus quiescence, but the root search is now driven by a think-time budget instead of a fixed depth.
- Added [iterative deepening](https://www.chessprogramming.org/Iterative_Deepening) so the engine always keeps the best fully searched root move from the latest completed iteration and can return immediately when the clock expires.
- Added a bounded [transposition table](https://www.chessprogramming.org/Transposition_Table) with:
  - position verification via python-chess transposition keys when available
  - stored best move for hash-move ordering
  - stored depth, score, and node-bound type (`exact`, `lower`, `upper`)
  - depth/age-aware replacement inside a fixed-size indexed table
- Transposition table use in `v1.5`:
  - probe before searching a node to allow exact and bound-based cutoffs
  - search the stored hash move first for stronger move ordering
  - retain entries across iterative-deepening passes within the same move search
- Intended improvement over `v1.4`:
  - make move generation controllable by wall-clock budget instead of a hard depth knob
  - spend available time on progressively deeper searches instead of risking one unfinished deep pass
  - reuse earlier search work inside the same move search to cut redundant computation

### References

- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Transposition Table](https://www.chessprogramming.org/Transposition_Table)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Iterative Deepening](https://www.chessprogramming.org/Iterative_Deepening)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Zobrist Hashing](https://www.chessprogramming.org/Zobrist_Hashing)

## v1.4

- Search: `v1.3`-style alpha-beta pruning and move ordering, but with a more constrained quiescence search for `v1.4`.
- Evaluation: material balance plus repetition and draw penalties, with a new endgame mop-up heuristic for clearly winning low-material positions.
- Added an endgame conversion bonus that rewards:
  - pushing the losing king away from the center and toward the edge/corner
  - bringing the stronger king closer to help cut off escape squares
- Refined the `v1.4` endgame conversion eval further:
  - mop-up scoring now follows a Chess 4.x-style weighted center-distance and king-distance term
  - dangerous advanced pawns for the losing side are scored explicitly, especially near promotion
  - repetition is penalized much more heavily when the winning side still has mating material in a late endgame
- Adjusted `v1.4` quiescence behavior so it no longer expands every checking continuation in quiet positions:
  - when not in check, quiescence now follows captures only
  - simple losing-capture filtering and delta pruning are applied to reduce search blowups
- The new bonus is intentionally gated:
  - it only activates in low non-pawn-material positions
  - it only activates when the stronger side is already materially ahead
  - it only activates when that side still has plausible forcing mating material
- Intended improvement over `v1.3`:
  - make the engine more purposeful in winning endgames that are outside the current mate-search horizon
  - prevent queen-heavy endgames from spending extreme time in quiescence on chains of checks
  - reduce aimless shuffling in converted positions where the engine is already winning but cannot yet see mate
  - improve the odds that a future shallow search will finally bring the mating sequence inside the searched depth

### References

- [Sebastian Lague](https://www.youtube.com/@SebastianLague), [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Mop-up Evaluation](https://www.chessprogramming.org/Mop-up_Evaluation)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Limiting Quiescence Search](https://www.chessprogramming.org/Quiescence_Search#Limiting_Quiescence)

## v1.3

- Search: minimax with alpha-beta pruning, move ordering, and capture-search extension at leaf nodes.
- Evaluation: material balance plus repetition and draw penalties, but leaf evaluation is no longer allowed to stop before resolving immediate capture sequences.
- Added a [quiescence-style follow-up search](https://www.chessprogramming.org/Quiescence_Search) so unstable positions are evaluated after forcing captures instead of at the first depth cutoff.
- Local C# port note: the `engine_csharp` `v1.3` rewrite now applies a defensive quiescence bound and draw-claim stop in local testing so quiet-check tails cannot recurse indefinitely under the `Gera.Chess` port.
- Historical engine files are now split under `api/v1/` instead of being kept together in one `api/v1.py`.
- Intended improvement over `v1.2`:
  - reduce horizon-effect mistakes where hanging material still counts as if it were safe
  - correctly value simple sequences like capturing a free queen to reach a drawish ending
  - preserve the existing pruning and move-ordering gains while making leaf evaluation tactically less naive

### References

- [Sebastian Lague](https://www.youtube.com/@SebastianLague), [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Quiescence Search](https://www.chessprogramming.org/Quiescence_Search)

## v1.2

- Search: minimax with alpha-beta pruning and move ordering.
- Evaluation: material balance plus repetition and draw penalties.
- Move ordering priorities:
  - captures are scored with a simple MVV-LVA style preference
  - promotions are prioritized
  - checking and mating moves are boosted
  - moves that walk into obvious pawn recaptures are penalized
- Intended improvement over `v1.1`:
  - reduce the number of explored positions before alpha-beta can cut
  - make promising tactical moves appear earlier in the search
  - keep the same basic evaluation model while improving search efficiency

### References

- [Sebastian Lague](https://www.youtube.com/@SebastianLague), [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk)
- Wikipedia on [Heuristic Improvements for Alpha-Beta Pruning](https://en.wikipedia.org/wiki/Alpha%E2%80%93beta_pruning#Heuristic_improvements)

## v1.1

- Search: minimax with alpha-beta pruning.
- Evaluation: material balance plus repetition and draw penalties.
- Added alpha-beta bounds to the plain minimax structure from `v1`.
- Intended improvement over `v1`:
  - prune branches that cannot affect the final decision
  - search the same nominal depth with materially less work
  - preserve the same broad scoring logic while improving runtime

### References

- [Sebastian Lague](https://www.youtube.com/@SebastianLague), [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk)
- Wikipedia on [Alpha-Beta Pruning](https://en.wikipedia.org/wiki/Alpha%E2%80%93beta_pruning)

## v1.0

- Search: plain minimax.
- Evaluation: material balance plus repetition and draw penalties.
- Piece values:
  - pawn `100`
  - knight `300`
  - bishop `300`
  - rook `500`
  - queen `900`
- Draw handling:
  - repeated positions are penalized
  - threefold-claimable positions are penalized
  - draw-claimable positions are penalized
  - terminal draws are penalized more heavily when the side to evaluate has material edge
- Intended role:
  - first deterministic search baseline beyond random play
  - historical reference point for later pruning and ordering improvements

### References

- [Sebastian Lague](https://www.youtube.com/@SebastianLague), [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk)
- [Chess Programming Wiki](https://www.chessprogramming.org/Main_Page) on [Minimax](https://www.chessprogramming.org/Minimax)

## v0

- Search: none.
- Move selection: random legal move from the current board position.
- Intended role:
  - baseline HTTP bot
  - sanity check for move generation and endpoint plumbing

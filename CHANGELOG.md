# Changelog

This file tracks the accepted algorithm history of the chess bots in this repository.

The `v1.x` family is heavily informed by Sebastian Lague's [Coding Adventure: Chess](https://www.youtube.com/watch?v=U4ogK0MIzqk). That reference should be read as implementation guidance for the search progression, not as a claim that this repository is a line-by-line copy of his engine.

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

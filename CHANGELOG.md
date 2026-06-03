# Changelog

All accepted chess bot versions should be recorded here.

The goal is to keep a clear history of what changed, why it was accepted, and what benchmark result justified promotion.

## Unreleased

- No accepted unreleased changes yet.

## v1.2

- Added alpha-beta pruning with move ordering.
- Kept the API contract as `POST /chess_v1-2` with `fen` input.
- Intended to improve search efficiency over `v1.1`.

## v1.1

- Added alpha-beta pruning on top of the minimax search.
- Kept the API contract as `POST /chess_v1-1` with `fen` input.
- Added `processing_time` and `moves_evaluated` response metadata.

## v1.0

- Introduced the first minimax-based search version.
- Exposed as `POST /chess_v1`.
- Returns SAN move output and search metadata.

## v0

- Introduced the baseline random legal-move bot.
- Exposed as `POST /chess_v0`.

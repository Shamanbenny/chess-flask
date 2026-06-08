# V3 Scenario Console Output

These runs use the current V3+ `LocalTesting` engine-file workflow. Each scenario starts at a `0.1s` move budget. If the scenario target failed, the run was retried at `0.5s`; no scenario needed `1.0s`.

# `puzzle_1`
![Puzzle #1](img/puzzle_1.png)
> White to Move

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --time-limit-seconds 0.1
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 0.1
```

```text
=== V3_0Engine puzzle_1 local test at time_limit=0.100s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_0Engine.cs
Search method: SearchMoveV3_0
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=446 | positions=18432 | elapsed=0.114243s
White 1 detail: completed_depth=4 | timed_out=True | tt_entries=1215 | tt_probes=1715 | tt_hits=493 | tt_hit_rate=0.287 | tt_cutoffs=117 | moves_evaluated=11213 | nodes_searched=18432
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=544 | positions=18432 | elapsed=0.102826s
White 2 detail: completed_depth=4 | timed_out=True | tt_entries=1617 | tt_probes=2523 | tt_hits=893 | tt_hit_rate=0.354 | tt_cutoffs=380 | moves_evaluated=11761 | nodes_searched=18432
White total: positions=36864 | elapsed=0.217069s

=== V3_4Engine puzzle_1 local test at time_limit=0.100s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_4Engine.cs
Search method: SearchMoveV3_4
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=446 | positions=18432 | elapsed=0.114139s
White 1 detail: completed_depth=4 | timed_out=True | tt_entries=1198 | tt_probes=1686 | tt_hits=483 | tt_hit_rate=0.286 | tt_cutoffs=110 | moves_evaluated=11239 | nodes_searched=18432
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=544 | positions=18432 | elapsed=0.102415s
White 2 detail: completed_depth=4 | timed_out=True | tt_entries=1617 | tt_probes=2523 | tt_hits=893 | tt_hit_rate=0.354 | tt_cutoffs=380 | moves_evaluated=11761 | nodes_searched=18432
White total: positions=36864 | elapsed=0.216554s
```

# `puzzle_2`
![Puzzle #2](img/puzzle_2.png)
> White to Move

Both engines missed the target first move at `0.1s`, so these recorded outputs use `0.5s`.

```bash
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --time-limit-seconds 0.5 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 0.5 --max-plies 70
```

```text
=== V3_0Engine puzzle_2 local self-play at time_limit=0.500s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_0Engine.cs
Search method: SearchMoveV3_0
Start FEN: 3k4/8/3p4/p2P1p2/P2P1P2/8/3K4/8 w - - 10 6
Start turn: white | max_plies=70
White 1: Kc3 (d2c3) | expected=Kc3 | match=True | score=252 | positions=125952 | elapsed=0.509087s
White 1 detail: completed_depth=16 | timed_out=True | tt_entries=8065 | tt_probes=75012 | tt_hits=66550 | tt_hit_rate=0.887 | tt_cutoffs=42429 | moves_evaluated=101220 | nodes_searched=125952
...
Ply 57: white plays Qg3# (e1g3) | score=999999 | positions=125952 | elapsed=0.503108s
Ply 57 detail: completed_depth=4 | timed_out=True | tt_entries=994 | tt_probes=5081 | tt_hits=1632 | tt_hit_rate=0.321 | tt_cutoffs=413 | moves_evaluated=86487 | nodes_searched=125952

Final FEN: 7Q/8/3pK3/3P2k1/3P4/6Q1/8/8 b - - 4 34
Total positions: 6393739
Total elapsed: 28.656131s
Total TT probes: 2449180
Total TT hits: 1997636
Total TT cutoffs: 1236568
Outcome: checkmate
Winner: white
Repetition detected: False
White delivered mate within ply limit: True

=== V3_4Engine puzzle_2 local self-play at time_limit=0.500s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_4Engine.cs
Search method: SearchMoveV3_4
Start FEN: 3k4/8/3p4/p2P1p2/P2P1P2/8/3K4/8 w - - 10 6
Start turn: white | max_plies=70
White 1: Kc3 (d2c3) | expected=Kc3 | match=True | score=252 | positions=132096 | elapsed=0.510239s
White 1 detail: completed_depth=16 | timed_out=True | tt_entries=8377 | tt_probes=78958 | tt_hits=70136 | tt_hit_rate=0.888 | tt_cutoffs=44759 | moves_evaluated=106319 | nodes_searched=132096
...
Ply 49: white plays Qb6# (d8b6) | score=999999 | positions=174080 | elapsed=0.502116s
Ply 49 detail: completed_depth=10 | timed_out=True | tt_entries=2092 | tt_probes=37127 | tt_hits=24185 | tt_hit_rate=0.651 | tt_cutoffs=15214 | moves_evaluated=146929 | nodes_searched=174080

Final FEN: 8/8/kQKp4/p2P4/P2P4/8/8/8 b - - 12 30
Total positions: 6609084
Total elapsed: 24.636141s
Total TT probes: 2697659
Total TT hits: 2189500
Total TT cutoffs: 1379372
Outcome: checkmate
Winner: white
Repetition detected: False
White delivered mate within ply limit: True
```

# `endgame_1`
![Endgame #1](img/endgame_1.png)
> Black to Move

```bash
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --time-limit-seconds 0.1
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 0.1
```

```text
=== V3_0Engine endgame local self-play at time_limit=0.100s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_0Engine.cs
Search method: SearchMoveV3_0
Start FEN: 3r4/3r4/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black plays Ke7+ (d6e7) | score=1185 | positions=13312 | elapsed=0.107168s
...
Ply 13: black plays Rf1# (f8f1) | score=999999 | positions=21504 | elapsed=0.104855s

Final FEN: 8/3r4/8/8/8/3k4/8/3K1r2 w - - 14 8
Total positions: 302041
Total elapsed: 1.337219s
Total TT probes: 34255
Total TT hits: 18900
Total TT cutoffs: 5648
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate without repetition: True

=== V3_4Engine endgame local self-play at time_limit=0.100s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_4Engine.cs
Search method: SearchMoveV3_4
Start FEN: 3r4/3r4/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black plays Ke7+ (d6e7) | score=1185 | positions=13312 | elapsed=0.108553s
...
Ply 13: black plays Rf1# (f8f1) | score=999999 | positions=21504 | elapsed=0.106223s

Final FEN: 8/3r4/8/8/8/3k4/8/3K1r2 w - - 14 8
Total positions: 303824
Total elapsed: 1.348931s
Total TT probes: 32767
Total TT hits: 18514
Total TT cutoffs: 5321
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate without repetition: True
```

# `endgame_2`
![Endgame #2](img/endgame_2.png)
> Black to Move

```bash
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_0Engine.cs --time-limit-seconds 0.1
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2 --engine-file engine_csharp/src/Engine.Core/V3/V3_4Engine.cs --time-limit-seconds 0.1
```

```text
=== V3_0Engine endgame local self-play at time_limit=0.100s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_0Engine.cs
Search method: SearchMoveV3_0
Start FEN: 3r4/8/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black plays Re8 (d8e8) | score=700 | positions=14336 | elapsed=0.108717s
...
Ply 25: black plays Re1# (e2e1) | score=999999 | positions=23552 | elapsed=0.101658s

Final FEN: 8/8/8/8/8/1k6/8/1K2r3 w - - 26 14
Total positions: 574196
Total elapsed: 2.560821s
Total TT probes: 77514
Total TT hits: 51507
Total TT cutoffs: 19456
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate without repetition: True

=== V3_4Engine endgame local self-play at time_limit=0.100s ===
Engine source: /home/benny/Desktop/_gitrepo/chess-flask/engine_csharp/src/Engine.Core/V3/V3_4Engine.cs
Search method: SearchMoveV3_4
Start FEN: 3r4/8/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black plays Re8 (d8e8) | score=700 | positions=14336 | elapsed=0.109725s
...
Ply 23: black plays Rf1# (f2f1) | score=999999 | positions=22528 | elapsed=0.101042s

Final FEN: 8/8/8/8/8/1k6/8/1K3r2 w - - 24 13
Total positions: 543546
Total elapsed: 2.355006s
Total TT probes: 73176
Total TT hits: 47825
Total TT cutoffs: 17394
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate without repetition: True
```

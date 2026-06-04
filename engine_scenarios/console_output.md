# `puzzle_1.py` for v1.x
![Puzzle #1](img/puzzle_1.png)
> White to Move
```
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1.5 --time-limit-seconds 2.7
```

```
=== v1 local test at depth 4 ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=-100 | positions=53034 | elapsed=5.868635s
Black forced: Kg7 (g6g7)
White 2: Kc2 (b2c2) | expected=Nxd5 | match=False | score=-100 | positions=44195 | elapsed=4.349277s
White total: positions=97229 | elapsed=10.217911s

=== v1.1 local test at depth 4 ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=400 | positions=6768 | elapsed=0.949762s
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=500 | positions=6499 | elapsed=0.960204s
White total: positions=13267 | elapsed=1.909966s

=== v1.2 local test at depth 4 ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=400 | positions=4801 | elapsed=1.539055s
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=500 | positions=3130 | elapsed=1.203581s
White total: positions=7931 | elapsed=2.742637s

=== v1.3 local test at depth 4 ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=400 | positions=7422 | elapsed=4.033918s
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=500 | positions=4835 | elapsed=3.145556s
White total: positions=12257 | elapsed=7.179474s

=== v1.4 local test at depth 4 ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=400 | positions=5404 | elapsed=2.785468s
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=500 | positions=3402 | elapsed=1.829545s
White total: positions=8806 | elapsed=4.615013s

=== v1.5 local test at time_limit=2.700s ===
Start FEN: 8/8/6kp/3b4/1p1p4/1P1P3P/PK2N3/8 w - - 0 2
White 1: Nf4+ (e2f4) | expected=Nf4+ | match=True | score=400 | positions=4819 | elapsed=2.886224s
White 1 detail: completed_depth=3 | timed_out=True | tt_entries=431 | tt_probes=539 | tt_hits=104 | tt_hit_rate=0.193 | tt_cutoffs=3 | moves_evaluated=2857 | nodes_searched=4819
Black forced: Kg7 (g6g7)
White 2: Nxd5 (f4d5) | expected=Nxd5 | match=True | score=500 | positions=7916 | elapsed=2.985325s
White 2 detail: completed_depth=4 | timed_out=True | tt_entries=673 | tt_probes=1052 | tt_hits=374 | tt_hit_rate=0.356 | tt_cutoffs=63 | moves_evaluated=4866 | nodes_searched=7916
White total: positions=12735 | elapsed=5.871549s
```

# `endgame_1.py` for v1.4
![End Game #1](img/endgame_1.png)
> Black to Move
```
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1
```

```
=== v1.4 endgame local self-play at depth 4 ===
Start FEN: 3r4/3r4/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black to move | legal_moves=18 | depth=4 | search started
Ply 1: black plays Ke6+ (d6e6) | score=1134 | positions=3150 | elapsed=4.723562s
Ply 2: white to move | legal_moves=5 | depth=4 | search started
Ply 2: white plays Ke3 (d4e3) | score=-1150 | positions=5950 | elapsed=2.868440s
Ply 3: black to move | legal_moves=27 | depth=4 | search started
Ply 3: black plays Kf5 (e6f5) | score=1150 | positions=3643 | elapsed=4.446135s
Ply 4: white to move | legal_moves=3 | depth=4 | search started
Ply 4: white plays Kf3 (e3f3) | score=-1179 | positions=3523 | elapsed=1.544930s
Ply 5: black to move | legal_moves=25 | depth=4 | search started
Ply 5: black plays Rd2 (d7d2) | score=1179 | positions=5910 | elapsed=7.033898s
Ply 6: white to move | legal_moves=2 | depth=4 | search started
Ply 6: white plays Kg3 (f3g3) | score=-1000000000 | positions=184 | elapsed=0.086730s
Ply 7: black to move | legal_moves=31 | depth=4 | search started
Ply 7: black plays R8d3+ (d8d3) | score=1000000000 | positions=5343 | elapsed=6.053802s
Ply 8: white to move | legal_moves=1 | depth=4 | search started
Ply 8: white plays Kh4 (g3h4) | score=-1000000000 | positions=2 | elapsed=0.000926s
Ply 9: black to move | legal_moves=26 | depth=4 | search started
Ply 9: black plays Rh2# (d2h2) | score=1000000000 | positions=1502 | elapsed=1.623343s

Final FEN: 8/8/8/5k2/7K/3r4/7r/8 w - - 10 6
Total positions: 29207
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate without repetition: True
```

# `endgame_2.py` for v1.4
![End Game #2](img/endgame_2.png)
> Black to Move
```
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2
```

```
=== v1.4 endgame local self-play at depth 4 ===
Start FEN: 3r4/8/3k4/8/3K4/8/8/8 b - - 1 1
Start turn: black | max_plies=60
Ply 1: black to move | legal_moves=13 | depth=4 | search started
Ply 1: black plays Re8 (d8e8) | score=672 | positions=1829 | elapsed=2.223313s
Ply 2: white to move | legal_moves=3 | depth=4 | search started
Ply 2: white plays Kc3 (d4c3) | score=-691 | positions=2942 | elapsed=1.140416s
Ply 3: black to move | legal_moves=22 | depth=4 | search started
Ply 3: black plays Kc5 (d6c5) | score=687 | positions=3303 | elapsed=2.366990s
Ply 4: white to move | legal_moves=5 | depth=4 | search started
Ply 4: white plays Kd3 (c3d3) | score=-717 | positions=3190 | elapsed=1.219016s
Ply 5: black to move | legal_moves=20 | depth=4 | search started
Ply 5: black plays Kd5 (c5d5) | score=696 | positions=2412 | elapsed=1.906752s
Ply 6: white to move | legal_moves=3 | depth=4 | search started
Ply 6: white plays Kc3 (d3c3) | score=-720 | positions=2510 | elapsed=0.951550s
Ply 7: black to move | legal_moves=20 | depth=4 | search started
Ply 7: black plays Re3+ (e8e3) | score=703 | positions=2414 | elapsed=1.696461s
Ply 8: white to move | legal_moves=4 | depth=4 | search started
Ply 8: white plays Kc2 (c3c2) | score=-726 | positions=2426 | elapsed=0.865571s
Ply 9: black to move | legal_moves=22 | depth=4 | search started
Ply 9: black plays Kc4 (d5c4) | score=719 | positions=2859 | elapsed=1.889988s
Ply 10: white to move | legal_moves=5 | depth=4 | search started
Ply 10: white plays Kd2 (c2d2) | score=-755 | positions=2730 | elapsed=0.849643s
Ply 11: black to move | legal_moves=20 | depth=4 | search started
Ply 11: black plays Re8 (e3e8) | score=737 | positions=1760 | elapsed=1.153618s
Ply 12: white to move | legal_moves=3 | depth=4 | search started
Ply 12: white plays Kc1 (d2c1) | score=-767 | positions=1540 | elapsed=0.506498s
Ply 13: black to move | legal_moves=22 | depth=4 | search started
Ply 13: black plays Kc3 (c4c3) | score=781 | positions=2196 | elapsed=1.520087s
Ply 14: white to move | legal_moves=2 | depth=4 | search started
Ply 14: white plays Kd1 (c1d1) | score=-1000000000 | positions=207 | elapsed=0.065502s
Ply 15: black to move | legal_moves=20 | depth=4 | search started
Ply 15: black plays Re3 (e8e3) | score=1000000000 | positions=946 | elapsed=0.707928s
Ply 16: white to move | legal_moves=1 | depth=4 | search started
Ply 16: white plays Kc1 (d1c1) | score=-1000000000 | positions=2 | elapsed=0.000634s
Ply 17: black to move | legal_moves=16 | depth=4 | search started
Ply 17: black plays Re1# (e3e1) | score=1000000000 | positions=908 | elapsed=0.572590s

Final FEN: 8/8/8/8/8/2k5/8/2K1r3 w - - 18 10
Total positions: 34174
Outcome: checkmate
Winner: black
Repetition detected: False
Black delivered mate without repetition: True
```
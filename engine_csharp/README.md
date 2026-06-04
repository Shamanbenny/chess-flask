# C# Engine Workspace

This directory contains direct C# rewrites of the Python `api/v1/*.py` reference engines and the local puzzle/endgame runners.

## Intent

- Keep Flask and the public HTTP surface in Python.
- Move search and evaluation development toward C# for better runtime than Python.
- Keep the C# side local-only.
- Rewrite any final public `v1.*` engine back into Python when it is ready for Vercel.

## Current State

- `Engine.Core` contains shared board/search infrastructure.
- `Engine.Core/V1` contains the direct `v1.*` engine rewrites with one C# file per version plus `Shared.cs`.
- `LocalTesting` contains local runner commands mirroring the Python scripts under `local_v1_tests/`.
- The Python files remain in the repo as historical reference implementations.

## Planned Commands

```bash
dotnet build engine_csharp/ChessEngine.sln
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1 v1.1 v1.2 v1.3 v1.4 --depth 4
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-1 --versions v1.5 --time-limit-seconds 1.0
dotnet run --project engine_csharp/src/LocalTesting -- puzzle-2 --time-limit-seconds 1.0 --max-plies 70
dotnet run --project engine_csharp/src/LocalTesting -- endgame-1
dotnet run --project engine_csharp/src/LocalTesting -- endgame-2
```

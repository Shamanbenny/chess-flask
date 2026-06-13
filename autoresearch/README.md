# Chess Autoresearch

This directory adapts Andrej Karpathy's `autoresearch` idea to a constrained
C# chess-engine improvement loop: clone the latest approved engine, let Codex
modify only that candidate in a temporary sandbox, evaluate it against a fixed
baseline, and keep the candidate only when the measured result clears the
approval rule.

The current workflow is Python-owned. Spawned Codex agents do not handle git,
version selection, evaluator execution, approval decisions, or attempt-log
updates.

## Run

Before running autoresearch on a fresh clone, make sure Git LFS is installed
and the repo-local Stockfish payload has been fetched:

```bash
git lfs install
git lfs pull --include="autoresearch/stockfish/**"
```

If Git LFS was already installed when you cloned, the folder should usually be
materialized automatically. Run the explicit `git lfs pull` command when
`autoresearch/stockfish/` contains pointer files instead of the actual binary
and source tree.

Then create and activate a repo-local Python virtual environment first (Run the
following in the Root Repo Directory):

- For Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r autoresearch/requirements.txt
```

- For Windows (Using PowerShell equivalents):

```bash
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r autoresearch\requirements.txt
```

Then run the orchestrator from the activated venv:

```bash
python autoresearch/run_autoresearch.py
```

The script prepares a fresh ignored `autoresearch-sandbox/V*_*/` directory,
launches Codex with a generated `PROGRAM.md`, then evaluates and records the
result after Codex returns. Experiment direction is optional for normal minor
runs and can be supplied with `--prompt`.

For later shells, reactivate the same venv before running autoresearch:

```bash
source .venv/bin/activate
```

The Stockfish evaluator uses the bundled repo-local binary at
`autoresearch/stockfish/stockfish-ubuntu-x86-64-avx2`.

## Command Arguments

`--prompt "<text>"` supplies optional experiment direction. The text is embedded
into the generated sandbox `PROGRAM.md`; it is not the first Codex chat message.
Codex always starts with:

```text
Start by looking at `PROGRAM.md`, and let's kick off the experiment loop!
```

Without `--prompt`, normal minor-version runs do not ask for terminal input and
the generated sandbox `PROGRAM.md` omits the user-input section.

`--version v3.5` forces a candidate version for exceptional/manual recovery.
Without it, the script uses `next_candidate_version` from
`autoresearch/state.json`. After every real attempt, including rejected
candidates, Python advances this value, so versions keep increasing. For
example, if `v3.5` and `v3.6` are rejected, the next candidate is still `v3.7`.
`--dry-run` never advances state.

`--major` starts a new major-version candidate, such as `v4.0` from a latest
approved `v3.x` seed. It requires `--prompt`; without a prompt, the script exits
safely because a major experiment needs explicit direction. The generated
sandbox instructions remind Codex that a major version must use the matching
namespace, for example `namespace Engine.Core.V4;` for `v4.0`.

`--dry-run` prepares the sandbox and exits before Codex, build, evaluation, state
updates, or git commits. Use it to inspect generated `PROGRAM.md`, `RETURN.json`,
the copied `ATTEMPTS.md`, and the cloned candidate engine file.

`--once` stops after one completed attempt instead of entering the KDialog
continue loop.

`--smoke-games <N>` is only a script-development diagnostic. It runs a short,
non-approving evaluator pass with `N` games to check that the candidate builds,
the evaluator launches, and CSV parsing works. Smoke results are always rejected
because they do not use the fixed 500-game contract.

`--soc-cc` enables School of Computing Compute Cluster mode. In this mode:

- the post-attempt KDialog prompt is skipped and the loop auto-continues
- the evaluator uses a script constant of `12` workers instead of the normal
  `state.json` value
- the finalized autoresearch commit is pushed to `origin/<current-branch>` after
  each attempt
- the script reads a repo-local `.env` file and sends Gmail notifications when
  Codex requires login credentials, when Codex reports usage/token exhaustion,
  and when an experiment completes

The repo-local `.env` file must define:

```dotenv
SOC_CC_GMAIL_USERNAME=your-gmail-address@gmail.com
SOC_CC_GMAIL_APP_PASSWORD=your-gmail-app-password
SOC_CC_NOTIFY_EMAIL_TO=destination@example.com
# Optional; defaults to SOC_CC_GMAIL_USERNAME when omitted
SOC_CC_NOTIFY_EMAIL_FROM=your-gmail-address@gmail.com
```

Completion emails attach:

- a text attachment containing the first 100 and last 100 lines from the latest
  experiment slice of the mirrored console log
- the rejected `result.csv` when the attempt was rejected

Approved attempts do not attach the CSV because the approved log is already
tracked and pushed by the finalized commit.

For a safe setup check:

```bash
python autoresearch/run_autoresearch.py --dry-run --prompt "Try a small contained improvement."
```

## Files

- `run_autoresearch.py`: orchestrates sandbox setup, Codex calls, build,
  evaluation, approval/rejection, history appends, state updates, and local git
  commits.
- `state.json`: machine-readable evaluator constants, latest approved metadata,
  next candidate version, and agent configuration.
- `ATTEMPTS.md`: human-readable attempt history. The orchestrator appends this
  after evaluation and the second Codex prompt.
- `../CHANGELOG.json`: V2+ engine metadata contract for the HTTP metadata
  endpoint and frontend. Evaluated candidates are appended or updated here
  automatically.
- `requirements.txt`: Python dependency list for the Codex SDK.
- `approved_logs/`: tracked CSV logs for approved engines.
- `logs/`: temporary evaluator logs for active or rejected runs.

The static `PROGRAM.md` and `EVALUATE.md` files were intentionally removed. The
orchestrator now generates a compact sandbox `PROGRAM.md` for each experiment,
and the evaluator contract lives here plus in `state.json`.

## Sandbox Contract

Every attempt gets a fresh ignored directory such as
`autoresearch-sandbox/V3_5/`. Existing directories for the same candidate are
deleted before recreation.

The sandbox contains only:

- generated `PROGRAM.md`
- copied `ATTEMPTS.md`
- candidate engine source, such as `V3_5Engine.cs`
- editable `RETURN.json`

Codex may edit only the candidate engine file and `RETURN.json`. It must not run
git commands, run the evaluator, add dependencies, add extra source files, edit
`ATTEMPTS.md`, or edit generated `PROGRAM.md`.

The generated `PROGRAM.md` tells Codex to:

1. Read `PROGRAM.md` and `ATTEMPTS.md`.
2. Form at most the configured number of hypotheses from `state.json`.
3. Modify only the candidate engine file.
4. Update `RETURN.json` with `hypotheses` and `implementation_summary`.
5. Stop and return control to Python.

After Python evaluates the candidate, it sends a second prompt in the same Codex
session with the evaluation summary and approval status. Codex then updates only
`RETURN.json` with `inferred_conclusion` and stops.

The generated `RETURN.json` template is:

```json
{
  "candidate_version": "v3.5",
  "hypotheses": [],
  "implementation_summary": "",
  "inferred_conclusion": ""
}
```

## Engine Contract

The sandbox candidate is copied into the matching major-version folder only when
Python is ready to build and evaluate it.

For candidate `vX.Y`, the engine file must be:

```text
engine_csharp/src/Engine.Core/VX/VX_YEngine.cs
```

It must expose the matching API shape:

```csharp
namespace Engine.Core.VX;

public static class VX_YEngine
{
    public static SearchResult SearchMoveVX_Y(
        BoardState board,
        double timeLimitSeconds = 1.0,
        int? maxDepth = null,
        VX_YSearchContext? searchContext = null)

    public static VX_YSearchContext CreateSearchContextVX_Y()
}
```

The candidate must stay self-contained in its engine file. Do not add shared
helpers, package dependencies, or evaluator changes as part of an experiment.

## Evaluation

Every normal candidate is evaluated by the local C# runner against a fixed local
Stockfish opponent:

- opponent: `stockfish-1350`
- Stockfish setting: `UCI_LimitStrength=true`, `UCI_Elo=1350`
- move time limit: `100ms`
- games: `500`
- color split: `250` candidate-as-White games and `250` candidate-as-Black games
- max plies: `200`
- workers: `6`
- transport: direct local engine-vs-Stockfish evaluation through
  `engine_csharp/src/LocalTesting`
- no depth argument; the match is time-limited

SOC CC mode overrides the worker count with a script constant of `12` without
editing `state.json`.

The command shape is:

```bash
dotnet run --project engine_csharp/src/LocalTesting -- evaluate-stock \
  --engine-file <candidate_engine_file> \
  --stockfish-path autoresearch/stockfish/stockfish-ubuntu-x86-64-avx2 \
  --stockfish-elo 1350 \
  --games 500 \
  --time-limit-ms 100 \
  --max-plies 200 \
  --workers 6 \
  --log \
  --short-sha <attempt_id>
```

`run_autoresearch.py` supplies the concrete candidate path and attempt id from
its current state, and it resolves the bundled repo-local Stockfish binary.
Do not change these constants during normal experiments; edit `state.json` only
when intentionally revising the workflow outside an active candidate run.

The evaluator must produce a canonical CSV at:

```text
autoresearch/logs/<attempt_id>-result.csv
```

When `--workers` is greater than `1`, `LocalTesting` now writes temporary
per-worker CSV files during the run:

```text
autoresearch/logs/<attempt_id>-result-<worker_id>.csv
```

After all workers finish, the main `LocalTesting` process merges those files
into the canonical `autoresearch/logs/<attempt_id>-result.csv`. Downstream
autoresearch parsing and approval logic must continue to treat only the
canonical merged CSV as the contract output. All per-worker CSV files will be 
deleted after merging to reduce clutter (The canonical file stays untouched).

Approved logs are moved to `autoresearch/approved_logs/` and recorded in
`state.json`, `ATTEMPTS.md`, and `CHANGELOG.json`. Rejected candidate files are
removed from the tracked engine tree and remain only in the ignored sandbox.

## Frontend Metadata Contract

`CHANGELOG.json` replaces the old markdown changelog as the machine-readable
source of version metadata for V2+ C# engines. The web backend serves this file
from:

```text
GET /api/chess/metadata
```

Each version entry should include:

- `version`: display version such as `v3.4`
- `api_version`: route token such as `v3_4`
- `engine_file`: source file under `engine_csharp/src/Engine.Core/`
- `served`: whether `Engine.Functions` currently exposes this version
- `summary`: frontend display summary copied from `implementation_summary`
- `implementation_summary`: raw autoresearch implementation summary from `RETURN.json`
- `hypotheses`: the experiment hypotheses used for the version
- `stockfish_1350.text`: standardized display text for the frontend
- `limitations`: frontend-facing limitations, defaulting to an empty list

After every attempt, `run_autoresearch.py` appends or updates the candidate's
`CHANGELOG.json` entry using the same `RETURN.json` and any evaluator data
already used for `ATTEMPTS.md`. The `summary` and `implementation_summary`
fields both come from `RETURN.json`'s `implementation_summary` value. New
approved candidates are written with `"served": false` by default. Rejected
candidates remain in `CHANGELOG.json` with `status: "rejected"` so downstream
consumers can inspect experiment history without serving or displaying those
versions publicly. If an attempt never reaches a final evaluator result, its
`stockfish_1350` numeric fields are recorded as `null` so frontend code can
ignore those points cleanly. Change `"served"` to `true` only when the HTTP
serving switch and endpoint documentation have also been updated for that
version.

## Approval Rule

A candidate is approved only when all of these are true:

- the C# solution builds successfully
- the evaluator completes and writes the canonical CSV
- the candidate records no crash, illegal move, timeout, or harness failure
- `score_rate > latest_approved.approved_reference_score_rate_vs_stockfish_1350`
- `lcb95 > 0.5`
- `max_plies_rate < 0.10`

Otherwise the candidate is rejected.

The approval decision is based on paired color-swapped results. For each pair
`i`, define one candidate-as-White game and one candidate-as-Black game. Assign
single-game score as win `1.0`, draw `0.5`, loss `0.0`, then compute:

```text
p_i = (score_as_white_i + score_as_black_i) / 2
```

With `n = games / 2` pairs:

```text
mean = (1 / n) * sum(p_i)
sd = sample standard deviation of p_i
lcb95 = mean - t_(0.95, n-1) * sd / sqrt(n)
score_rate = total_score / games
```

For the standard 500-game run, `state.json` records the one-sided 95%
Student-t critical value for `df = 249`.

## Attempt Recording

After the second Codex prompt, Python reads sandbox `RETURN.json` plus evaluator
metrics and appends a compact entry to `ATTEMPTS.md`.

Approved entries record the commit and approved CSV path. Rejected entries use
`<n/a>` for commit and evaluation log path. The Python script creates a local
commit with a standardized message such as `Approve V3.5 via autoresearch` or
`Reject V3.5 via autoresearch`, then amends the attempt entry with the recorded
commit information.

`state.json` tracks both:

- `latest_approved`: the approved seed version/file/score used for future
  candidates
- `next_candidate_version`: the next version number to try, advanced after every
  real attempt whether approved or rejected

`--dry-run` must not alter `state.json`.

## Continue Loop

After each attempt, Python prompts through KDialog:

- `Continue`: start the next experiment
- `Stop`: exit the loop
- `Snooze 5 minutes`: sleep for five minutes, then prompt again

If there is no response within 60 seconds, Python assumes the user is away from
the keyboard and continues automatically. If KDialog is unavailable, Python also
continues automatically.

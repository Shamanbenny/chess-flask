# autoresearch

This is an experiment to have the LLM run a constrained chess-engine improvement loop.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (for example `jun5`). The branch `autoresearch/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from the current accepted branch tip.
3. **Read the in-scope files**: read these files for full context:
   - `autoresearch/PROGRAM.md` - this workflow contract.
   - `autoresearch/EVALUATE.md` - fixed evaluation rules. Read-only.
   - `autoresearch/ATTEMPTS.md` - previous attempts, outcomes, conclusions, and latest approved metadata.
4. **Identify the latest approved baseline**: read `autoresearch/ATTEMPTS.md`, find the latest **approved** engine version/file, and review recent approved and rejected conclusions before choosing a new hypothesis.
5. **Clone the approved engine into a new candidate**: copy the latest approved engine file to the next versioned file name, using a minor or major bump based on change scope, and place it under the corresponding major folder (for example `V2/` or `V3/`).
6. **Confirm and go**: confirm the baseline, candidate target name, and active hypotheses look coherent before beginning the loop.

Once setup is complete, begin experimenting.

## Experimentation

Every experiment works against the current latest approved engine, not against an arbitrary older version.

Before changing code:

- read the most recent attempts and inferred conclusions
- inspect the latest approved engine file itself
- form at most `1` active hypotheses at one time

Example hypotheses:

- the engine would benefit from a transposition-table change
- search is slowed by avoidable board-state hashing overhead
- move ordering is paying too much work per legal move
- a winning-endgame heuristic is too expensive for the gain it provides

Hypotheses should be concrete enough that the resulting code change can be described and later evaluated.

**What you CAN do:**

- Modify your current newly cloned engine file with the incremented version number.
- Treat everything inside that new engine file as fair game: search, evaluation, move ordering, time management, hashing, transposition-table logic, constants local to that engine, and internal helpers.
- For `Version 2+`, keep all functions used by that engine inside that file itself. Do not create util/shared support files for the active experiment engine.
- Append to `autoresearch/ATTEMPTS.md` after each completed evaluation so later runs can build on the recorded conclusion.

**What you CANNOT do:**

- Modify `autoresearch/PROGRAM.md` or `autoresearch/EVALUATE.md`. They are read-only workflow and evaluation contracts.
- Modify the evaluation harness.
- Install new packages or add dependencies.
- Change the fixed evaluation constants that the evaluator enforces.
- Intentionally "cheat" the system (E.g. Internally ignore the `time_limit_seconds` within the Chess Engine)
- Make the decision to "halt" the experiment loop

## Goal

The goal is to produce a candidate chess engine that is measurably better than the latest approved engine under the fixed evaluation defined in `autoresearch/EVALUATE.md`.

The decision is based on the fixed head-to-head evaluator (aka match simulation), not on isolated puzzle success, not on subjective code preference, and not on a single anecdotal game.

Speed, plies per game, positions evaluated, and similar diagnostics are useful supporting evidence, but they do not override the promotion rule.

## Output Format

Every completed experiment, whether approved or rejected, must append a structured entry to `autoresearch/ATTEMPTS.md`.

Each entry must include enough information for future runs to answer:

- what baseline was used
- what candidate file/version was created (E.g. `engine_csharp/src/Engine.Core/V2/V2_3Engine-<UID>.cs`)
- what hypotheses were tested
- what the evaluator measured
- whether the candidate was approved or rejected
- what conclusion can be infer from the result, so that future runs can learn from or take note of

The attempts log is append-only (Append at tail end) during the run. It is the authoritative source for the latest approved baseline and for prior experiment conclusions.

## The Experiment Loop

The experiment runs on a dedicated branch for the run, for example `autoresearch/jun5` or `autoresearch/<tag>`.

Loop forever:
1. Create and track in your todo-list feature the following steps, making sure that the last task acts as a reminder to rehydrate your context where necessary, but **most importantly as a reminder to re-loop!**
2. Look at the git state: current branch, current commit, and whether you are still positioned at the latest approved commit.
3. Read `autoresearch/ATTEMPTS.md`, identify the latest approved engine, and choose `1` active hypotheses grounded in the latest approved code plus prior attempt conclusions.
4. Clone the latest approved engine file into the next versioned candidate file, choosing minor versus major bump based on the complexity of the change. (New versions must be ATLEAST V2+)
5. Modify only that newly cloned candidate engine file with the improvement, optimization, or fix.
6. Check that the code builds successfully.
7. Commit the candidate.
8. Run the fixed evaluation from `autoresearch/EVALUATE.md`.
   The evaluation command must include `--log --short-sha <short_sha>` so the canonical per-game CSV lands under `autoresearch/logs/`.
9. Reduce the number of "check on terminal" requests while evaluation is running. Let the evaluator run and poll infrequently.
10. Verify the evaluation output contains both required signatures:
   - `=== EVALUATION START ===`
   - `=== EVALUATION DONE ===`
11. If those signatures are missing, determine whether evaluation is still running, the build failed, or the evaluator crashed or terminated mid-run.
12. If evaluation completed properly, append the result and inferred conclusion to `autoresearch/ATTEMPTS.md`.
   Include the canonical CSV path `autoresearch/logs/<short_sha>-result.csv` and mention any optional extra log files separately if they were produced.
13. If the evaluation is a positive improvement according to `autoresearch/EVALUATE.md`, keep the commit and advance the branch baseline.
14. If the evaluation is equal or worse, or if the evaluator fails, reset back to where the experiment started: the previously approved commit.

The branch should only advance when the fixed evaluator says the candidate is better.

The idea is that you are a completely autonomous researcher trying things out. If they work, keep. If they don't, discard. And you're advancing the branch so that you can iterate. If you feel like you're getting stuck in some way, you can rewind but you should probably do this very very sparingly (if ever).

**NEVER STOP**: Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep, or gone from a computer and expects you to continue working *indefinitely* until you are manually stopped. You are autonomous. If you run out of ideas, think harder — read papers referenced in the code, re-read the in-scope files for new angles, try combining previous near-misses, try more radical architectural changes. The loop runs until the human interrupts you, period.

As an example use case, a user might leave you running while they sleep. If each experiment takes you ~60 minutes then you can run approx 1 experiment per hour, for a total of about 10 over the duration of the average human sleep. The user then wakes up to experimental results, all completed by you while they slept!

## Failure Handling

- If the candidate does not build, reject it.
- If evaluation fails to complete, reject it unless the failure is a trivial operator issue that can be immediately corrected without changing the experiment itself.
- If the candidate crashes, returns illegal moves, times out incorrectly, or breaks the evaluator contract, reject it.
- If `--log` is requested but the canonical CSV is missing or malformed, reject it as an evaluator-contract failure.
- If a hypothesis repeatedly fails, record the inferred conclusion clearly so later runs do not waste time retrying the same weak idea without a new angle.

## Simplicity Criterion

All else being equal, prefer the simpler engine.

- A tiny gain that adds ugly complexity is usually not worth keeping.
- A small gain with a clean contained change may be worth keeping.
- Equal performance with simpler code is a meaningful outcome.
- A rejected attempt can still be useful if it produces a strong conclusion about what not to try next.

This does not mean that major architectural changes in the Chess Engine is discouraged. It just means that if that change does not yield significant advantage, then it might not be worth keeping.

#!/usr/bin/env python3
"""Python-owned autoresearch orchestration for C# chess engine experiments."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "autoresearch" / "state.json"
ATTEMPTS_PATH = REPO_ROOT / "autoresearch" / "ATTEMPTS.md"
SANDBOX_ROOT = REPO_ROOT / "autoresearch-sandbox"
ENGINE_VERSION_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    version: str
    major: int
    minor: int
    version_bump: str
    stem: str
    engine_file: Path
    sandbox_dir: Path
    sandbox_engine_file: Path


@dataclass
class EvaluationMetrics:
    wins: int
    draws: int
    losses: int
    score: float
    score_rate: float
    average_plies: float
    average_processing_time_ms: float
    average_positions_or_nodes: float
    max_plies_count: int
    max_plies_rate: float
    failure_counts: dict[str, int]
    pair_mean: float
    pair_sd: float
    lcb95: float
    games: int


def main() -> int:
    args = parse_args()
    if args.major and not args.prompt:
        raise SystemExit("A major improvement requires additional information about what to modify, so --prompt is required.")

    state = load_state()
    if not args.dry_run:
        ensure_clean_worktree()

    user_input = args.prompt or ""
    candidate = next_candidate(state, args.version, args.major)
    prepare_sandbox(state, candidate, user_input)

    if args.dry_run:
        print(f"Dry run complete. Sandbox: {candidate.sandbox_dir.relative_to(REPO_ROOT)}")
        print(f"Candidate: {candidate.version} -> {candidate.engine_file.relative_to(REPO_ROOT)}")
        return 0

    while True:
        codex_session = run_codex_implementation(candidate)
        copy_candidate_to_repo(candidate)
        attempt_id = make_attempt_id(candidate)
        build_ok = run_build()

        metrics: EvaluationMetrics | None = None
        status = "rejected"
        verdict_reason = "Build failed before evaluator run."
        log_path = REPO_ROOT / "autoresearch" / "logs" / f"{attempt_id}-result.csv"
        approved_log_path: Path | None = None

        if build_ok:
            evaluator_ok = run_evaluator(candidate, state, attempt_id, args.smoke_games)
            if evaluator_ok and log_path.exists():
                metrics = parse_evaluation_csv(log_path, state)
                status, verdict_reason = decide_candidate(metrics, state)
                if args.smoke_games is not None:
                    status = "rejected"
                    verdict_reason = (
                        "Rejected because this was an explicit smoke run, not the fixed 500-game approval run."
                    )
                if status == "approved":
                    approved_log_path = move_approved_log(candidate, log_path, attempt_id)
            else:
                verdict_reason = "Evaluator failed or did not produce the canonical CSV."

        evaluation_summary = build_evaluation_summary(candidate, status, verdict_reason, metrics, state)
        run_codex_result_update(candidate, codex_session, evaluation_summary)
        attempt_note = read_return_json(candidate)

        update_state_and_attempts(
            state,
            candidate,
            attempt_id,
            status,
            verdict_reason,
            attempt_note,
            metrics,
            log_path,
            approved_log_path,
        )
        persist_state(state)
        cleanup_rejected_candidate(candidate, status)
        commit_sha = commit_attempt(candidate, status)
        if commit_sha:
            finalize_attempt_commit(candidate, status, commit_sha, approved_log_path)

        choice = prompt_continue(status, candidate, verdict_reason)
        if choice == "stop":
            return 0

        state = load_state()
        user_input = args.prompt or ""
        candidate = next_candidate(state, args.version, args.major)
        prepare_sandbox(state, candidate, user_input)
        if args.once:
            return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Python-owned autoresearch loop.")
    parser.add_argument("--prompt", help="Optional experiment direction embedded into the sandbox PROGRAM.md.")
    parser.add_argument("--version", help="Force candidate version, for example v3.5.")
    parser.add_argument("--major", action="store_true", help="Start a new major version experiment. Requires --prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare sandbox only; do not call Codex or evaluate.")
    parser.add_argument("--once", action="store_true", help="Exit after one attempt instead of prompting for another.")
    parser.add_argument(
        "--smoke-games",
        type=int,
        help="Run a non-approving evaluator smoke test with this game count.",
    )
    return parser.parse_args()


def load_state() -> dict[str, Any]:
    with STATE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def persist_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def ensure_clean_worktree() -> None:
    result = run(["git", "status", "--porcelain"], check=True, capture=True)
    if result.stdout.strip():
        raise SystemExit("Working tree must be clean before running autoresearch.")


def next_candidate(state: dict[str, Any], forced_version: str | None, major: bool) -> Candidate:
    version_bump = "major" if major else "minor"
    version = forced_version or (
        bump_major(state["latest_approved"]["version"])
        if major
        else state.get("next_candidate_version") or bump_minor(state["latest_approved"]["version"])
    )
    match = ENGINE_VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"Invalid candidate version: {version}")

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    stem = f"V{major}_{minor}Engine"
    engine_file = REPO_ROOT / "engine_csharp" / "src" / "Engine.Core" / f"V{major}" / f"{stem}.cs"
    sandbox_dir = SANDBOX_ROOT / f"V{major}_{minor}"
    sandbox_engine_file = sandbox_dir / f"{stem}.cs"
    return Candidate(version, major, minor, version_bump, stem, engine_file, sandbox_dir, sandbox_engine_file)


def bump_minor(version: str) -> str:
    match = ENGINE_VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"Invalid approved version in state.json: {version}")
    return f"v{int(match.group('major'))}.{int(match.group('minor')) + 1}"


def bump_major(version: str) -> str:
    match = ENGINE_VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"Invalid approved version in state.json: {version}")
    return f"v{int(match.group('major')) + 1}.0"


def prepare_sandbox(state: dict[str, Any], candidate: Candidate, user_input: str) -> None:
    if candidate.engine_file.exists():
        raise SystemExit(f"Candidate target already exists: {candidate.engine_file.relative_to(REPO_ROOT)}")

    if candidate.sandbox_dir.exists():
        shutil.rmtree(candidate.sandbox_dir)
    candidate.sandbox_dir.mkdir(parents=True)

    seed_file = REPO_ROOT / state["latest_approved"]["engine_file"]
    if not seed_file.exists():
        raise SystemExit(f"Approved seed file is missing: {seed_file}")

    seed_text = seed_file.read_text(encoding="utf-8")
    renamed = rename_engine_source(seed_text, state["latest_approved"]["version"], candidate.version)
    candidate.sandbox_engine_file.write_text(renamed, encoding="utf-8")

    shutil.copy2(ATTEMPTS_PATH, candidate.sandbox_dir / "ATTEMPTS.md")
    (candidate.sandbox_dir / "PROGRAM.md").write_text(agent_program(state, candidate, user_input), encoding="utf-8")
    (candidate.sandbox_dir / "RETURN.json").write_text(return_template(state, candidate), encoding="utf-8")
    init_sandbox_git(candidate.sandbox_dir)


def rename_engine_source(source: str, old_version: str, new_version: str) -> str:
    old_major, old_minor = parse_version(old_version)
    new_major, new_minor = parse_version(new_version)
    replacements = {
        f"V{old_major}_{old_minor}": f"V{new_major}_{new_minor}",
        f"v{old_major}.{old_minor}": f"v{new_major}.{new_minor}",
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    source = re.sub(r"namespace Engine\.Core\.V\d+;", f"namespace Engine.Core.V{new_major};", source)
    return source


def parse_version(version: str) -> tuple[int, int]:
    match = ENGINE_VERSION_RE.match(version)
    if not match:
        raise SystemExit(f"Invalid version: {version}")
    return int(match.group("major")), int(match.group("minor"))


def agent_program(state: dict[str, Any], candidate: Candidate, user_input: str) -> str:
    latest = state["latest_approved"]
    evaluator = state["evaluator"]
    max_hypotheses = state.get("agent", {}).get("max_hypotheses_per_experiment", 2)
    program = textwrap.dedent(
        f"""\
        # Autoresearch Sandbox Program

        You are working within a temporary sandbox, explicitly to improve the Chess Engine built in C#.
        Other than modifying the files, you are highly encouraged to not be verbose, so as to reduce token usage.

        ## Files

        - `PROGRAM.md`: this instruction file.
        - `{candidate.sandbox_engine_file.name}`: source file where you will be implementing the hypotheses.
        - `ATTEMPTS.md`: prior attempt history and their inferred conclusion
        - `RETURN.json`: machine-readable summary you must update.
        """
    )

    if user_input.strip():
        program += textwrap.dedent(
            f"""\

            ## User Input (To help guide your hypotheses)

            {user_input.strip()}
            """
        )

    program += textwrap.dedent(
        f"""\

        ## Candidate

        - candidate_version: `{candidate.version}`
        - candidate_engine_file: `{candidate.sandbox_engine_file.name}`
        - latest_approved_version: `{latest['version']}`
        - latest_approved_reference_score_rate_vs_stockfish_1350: `{latest['approved_reference_score_rate_vs_stockfish_1350']:.4f}`
        - version_bump: `{candidate.version_bump}`

        ## Engine API

        The file will be copied into `engine_csharp/src/Engine.Core/V{candidate.major}/` after you return.
        It must expose:

        - `namespace Engine.Core.V{candidate.major};`
        - `public static class {candidate.stem}`
        - `public static SearchResult SearchMoveV{candidate.major}_{candidate.minor}(BoardState board, double timeLimitSeconds = 1.0, int? maxDepth = null, V{candidate.major}_{candidate.minor}SearchContext? searchContext = null)`
        - `public static V{candidate.major}_{candidate.minor}SearchContext CreateSearchContextV{candidate.major}_{candidate.minor}()`

        If this is a `major` version bump, pay special attention to the namespace.
        A `v{candidate.major}.{candidate.minor}` candidate must use `namespace Engine.Core.V{candidate.major};`;
        leaving the copied seed namespace in place will break the compiled engine resolver.

        ## Allowed Changes

        - Modify `{candidate.sandbox_engine_file.name}`.
        - Modify `RETURN.json`.

        ## Forbidden Changes

        - Do not run git commands.
        - You are not expected to and not allowed to run the evaluator.
        - Do not edit `ATTEMPTS.md` or `PROGRAM.md`. (These files will be deleted regardless)
        - Do not add package dependencies or extra source files in your solution. (Everything should be self-contained)
        - Do not change the public engine API shape above.

        ## Required Work

        1. Read `PROGRAM.md` and `ATTEMPTS.md`.
        2. Form at most `{max_hypotheses}` concrete hypotheses.
        3. Edit only `{candidate.sandbox_engine_file.name}`.
        4. Update `RETURN.json` with:
           - `hypotheses`
           - `implementation_summary`
           - leave `inferred_conclusion` empty until Python sends evaluation results in a follow-up prompt.
        5. Stop your work. Do not keep looping.

        ## Evaluation Context

        A Python script will run the fixed evaluator after you stop:

        - opponent: `{evaluator['opponent']}`
        - games: `{evaluator['games']}`
        - stockfish_elo: `{evaluator['stockfish_elo']}`
        - time_limit_ms: `{evaluator['time_limit_ms']}`
        - max_plies: `{evaluator['max_plies']}`

        A candidate is approved only if it builds, has no evaluator failures,
        has `score_rate` greater than the latest approved score rate, has `lcb95 > 0.5`,
        and has `max_plies_rate < 0.10`.

        A later prompt will include the evaluation result in this same Codex session.
        At that point, update `RETURN.json` with `inferred_conclusion`, and then stop.

        ## Approval Formula

        The approval decision is based on paired color-swapped results, not just raw aggregate score.

        For each paired starting-position match `i`, define:

        - one game with candidate as White
        - one game with candidate as Black

        Assign single-game score:

        - win = `1.0`
        - draw = `0.5`
        - loss = `0.0`

        For pair `i`, compute the candidate paired score:

        `p_i = (score_as_white_i + score_as_black_i) / 2`

        With `n = games / 2` pairs, compute:

        - `mean = (1 / n) * sum(p_i)`
        - `sd = sample standard deviation of the p_i values`
        - `lcb95 = mean - t_(0.95, n-1) * sd / sqrt(n)`

        Where `t_(0.95, n-1)` is the one-sided 95% Student-t critical value with `n - 1` degrees of freedom.

        Therefore:
        - `score_rate = total_score / games`
        - `approved_seed_score_rate = the latest approved seed's recorded stockfish-1350 reference score rate from autoresearch/ATTEMPTS.md`
        """
    )
    return program


def return_template(state: dict[str, Any], candidate: Candidate) -> str:
    latest = state["latest_approved"]
    template = {
        "candidate_version": candidate.version,
        "hypotheses": [],
        "implementation_summary": "",
        "inferred_conclusion": "",
    }
    return json.dumps(template, indent=2) + "\n"


def init_sandbox_git(path: Path) -> None:
    run(["git", "init"], cwd=path, check=True, capture=True)
    run(["git", "add", "."], cwd=path, check=True, capture=True)
    run(["git", "commit", "-m", "Prepare autoresearch sandbox"], cwd=path, check=False, capture=True)


@dataclass
class CodexSession:
    manager: Any
    thread: Any


def run_codex_implementation(candidate: Candidate) -> CodexSession:
    try:
        from openai_codex import Codex, Sandbox
    except ImportError as exc:
        raise SystemExit("Install autoresearch/requirements.txt before running Codex.") from exc

    manager = Codex()
    previous_cwd = Path.cwd()
    os.chdir(candidate.sandbox_dir)
    try:
        codex = manager.__enter__()
        thread = codex.thread_start(sandbox=Sandbox.workspace_write)
        result = thread.run("Start by looking at `PROGRAM.md`, and let's kick off the experiment loop!")
        final_response = result.final_response
    finally:
        os.chdir(previous_cwd)

    (candidate.sandbox_dir / "CODEX_RESULT.md").write_text(final_response, encoding="utf-8")
    return CodexSession(manager, thread)


def run_codex_result_update(candidate: Candidate, session: CodexSession, evaluation_summary: str) -> None:
    previous_cwd = Path.cwd()
    os.chdir(candidate.sandbox_dir)
    try:
        result = session.thread.run(
            f"Here's your evaluation result for {candidate.version} Engine.\n\n"
            f"{evaluation_summary}\n\n"
            "Reminder: update `RETURN.json` with your inferred conclusion, and thank you for your help!"
        )
        final_response = result.final_response
    finally:
        os.chdir(previous_cwd)
        session.manager.__exit__(None, None, None)

    (candidate.sandbox_dir / "CODEX_EVALUATION_RESULT.md").write_text(final_response, encoding="utf-8")


def copy_candidate_to_repo(candidate: Candidate) -> None:
    candidate.engine_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate.sandbox_engine_file, candidate.engine_file)


def make_attempt_id(candidate: Candidate) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%m%d%H%M%S")
    return f"{candidate.stem}-{stamp}".lower().replace("engine", "")


def run_build() -> bool:
    result = run(["dotnet", "build", "engine_csharp/ChessEngine.sln"], cwd=REPO_ROOT, check=False)
    return result.returncode == 0


def run_evaluator(
    candidate: Candidate,
    state: dict[str, Any],
    attempt_id: str,
    smoke_games: int | None,
) -> bool:
    stockfish_path = os.environ.get("STOCKFISH_PATH")
    if not stockfish_path:
        print("STOCKFISH_PATH is required for evaluation.", file=sys.stderr)
        return False

    evaluator = state["evaluator"]
    games = smoke_games or evaluator["games"]
    command = [
        "dotnet",
        "run",
        "--project",
        "engine_csharp/src/LocalTesting",
        "--",
        "evaluate-stock",
        "--engine-file",
        str(candidate.engine_file.relative_to(REPO_ROOT)),
        "--stockfish-path",
        stockfish_path,
        "--stockfish-elo",
        str(evaluator["stockfish_elo"]),
        "--games",
        str(games),
        "--time-limit-ms",
        str(evaluator["time_limit_ms"]),
        "--max-plies",
        str(evaluator["max_plies"]),
        "--workers",
        str(evaluator["workers"]),
        "--log",
        "--short-sha",
        attempt_id,
    ]
    result = run(command, cwd=REPO_ROOT, check=False)
    return result.returncode == 0


def parse_evaluation_csv(path: Path, state: dict[str, Any]) -> EvaluationMetrics:
    rows: list[dict[str, str]]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"Evaluation CSV is empty: {path}")

    games = len(rows)
    wins = sum(1 for row in rows if float(row["engine_a_score"]) == 1.0)
    draws = sum(1 for row in rows if float(row["engine_a_score"]) == 0.5)
    losses = sum(1 for row in rows if float(row["engine_a_score"]) == 0.0)
    score = sum(float(row["engine_a_score"]) for row in rows)
    plies = sum(int(row["plies"]) for row in rows)
    max_plies_count = sum(1 for row in rows if row["termination_reason"] == "max_plies")

    engine_move_ms = []
    engine_positions = []
    failure_counts = {"crash": 0, "illegal_move": 0, "timeout": 0, "harness": 0, "max_plies": max_plies_count}
    pair_scores: dict[int, float] = {}
    for row in rows:
        engine_a_was_white = row["engine_a_was_white"].strip().lower() == "true"
        engine_move_ms.append(float(row["white_average_move_ms" if engine_a_was_white else "black_average_move_ms"]))
        engine_positions.append(float(row["white_average_positions" if engine_a_was_white else "black_average_positions"]))
        pair = int(row["pair_number"])
        pair_scores[pair] = pair_scores.get(pair, 0.0) + float(row["engine_a_score"]) / 2.0
        failure_engine = row.get("failure_engine", "").strip()
        if failure_engine:
            reason = row["termination_reason"]
            if reason == "illegal_move":
                failure_counts["illegal_move"] += 1
            elif reason == "timeout":
                failure_counts["timeout"] += 1
            elif reason == "engine_exception":
                failure_counts["crash"] += 1
            else:
                failure_counts["harness"] += 1

    pair_values = list(pair_scores.values())
    pair_mean = sum(pair_values) / len(pair_values)
    pair_sd = sample_sd(pair_values, pair_mean)
    df = len(pair_values) - 1
    t_critical = state["evaluator"]["approval"]["t_critical_one_sided_95_by_df"].get(str(df), 1.650996)
    lcb95 = pair_mean - t_critical * pair_sd / math.sqrt(len(pair_values))

    return EvaluationMetrics(
        wins=wins,
        draws=draws,
        losses=losses,
        score=score,
        score_rate=score / games,
        average_plies=plies / games,
        average_processing_time_ms=sum(engine_move_ms) / len(engine_move_ms),
        average_positions_or_nodes=sum(engine_positions) / len(engine_positions),
        max_plies_count=max_plies_count,
        max_plies_rate=max_plies_count / games,
        failure_counts=failure_counts,
        pair_mean=pair_mean,
        pair_sd=pair_sd,
        lcb95=lcb95,
        games=games,
    )


def sample_sd(values: list[float], mean: float) -> float:
    if len(values) <= 1:
        return 0.0
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def decide_candidate(metrics: EvaluationMetrics, state: dict[str, Any]) -> tuple[str, str]:
    approved_score = state["latest_approved"]["approved_reference_score_rate_vs_stockfish_1350"]
    approval = state["evaluator"]["approval"]
    failures = sum(metrics.failure_counts[key] for key in ("crash", "illegal_move", "timeout", "harness"))
    if failures > 0:
        return "rejected", "Rejected because evaluator failures were recorded."
    if metrics.score_rate <= approved_score:
        return "rejected", f"Rejected because score_rate={metrics.score_rate:.4f} did not exceed approved seed {approved_score:.4f}."
    if metrics.lcb95 <= approval["lcb95_min_exclusive"]:
        return "rejected", f"Rejected because lcb95={metrics.lcb95:.4f} did not exceed 0.5."
    if metrics.max_plies_rate >= approval["max_plies_rate_max_exclusive"]:
        return "rejected", f"Rejected because max_plies_rate={metrics.max_plies_rate:.4f} was at least 0.10."
    return "approved", (
        f"Approved because score_rate={metrics.score_rate:.4f} exceeded {approved_score:.4f}, "
        f"lcb95={metrics.lcb95:.4f} > 0.5, max_plies_rate={metrics.max_plies_rate:.4f} < 0.10, and failures=0."
    )


def move_approved_log(candidate: Candidate, log_path: Path, attempt_id: str) -> Path:
    approved_dir = REPO_ROOT / "autoresearch" / "approved_logs"
    approved_dir.mkdir(parents=True, exist_ok=True)
    target = approved_dir / f"{candidate.stem}-{attempt_id}-result.csv"
    shutil.move(str(log_path), target)
    return target


def read_return_json(candidate: Candidate) -> dict[str, Any]:
    return_path = candidate.sandbox_dir / "RETURN.json"
    if not return_path.exists():
        return {
            "hypotheses": ["Codex did not leave RETURN.json in the sandbox."],
            "implementation_summary": "n/a",
            "inferred_conclusion": "No inferred conclusion was recorded.",
        }

    try:
        data = json.loads(return_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "hypotheses": ["Codex left malformed RETURN.json."],
            "implementation_summary": "n/a",
            "inferred_conclusion": "No inferred conclusion was recorded because RETURN.json was malformed.",
        }

    hypotheses = data.get("hypotheses")
    if not isinstance(hypotheses, list):
        hypotheses = []
    hypotheses = [str(item).strip() for item in hypotheses if str(item).strip()]
    return {
        "hypotheses": hypotheses or ["Codex did not fill in hypotheses in RETURN.json."],
        "implementation_summary": str(data.get("implementation_summary") or "n/a").strip(),
        "inferred_conclusion": str(data.get("inferred_conclusion") or "No inferred conclusion was recorded.").strip(),
    }


def build_evaluation_summary(
    candidate: Candidate,
    status: str,
    verdict_reason: str,
    metrics: EvaluationMetrics | None,
    state: dict[str, Any],
) -> str:
    approved_score = state["latest_approved"]["approved_reference_score_rate_vs_stockfish_1350"]
    if metrics is None:
        return textwrap.dedent(
            f"""\
            Candidate version: {candidate.version}
            Approval status: {status}
            Previously approved score_rate: {approved_score:.4f}
            Candidate score_rate: n/a
            Verdict: {verdict_reason}
            """
        )

    return textwrap.dedent(
        f"""\
        Candidate version: {candidate.version}
        Approval status: {status}
        Previously approved score_rate: {approved_score:.4f}
        Candidate score_rate: {metrics.score_rate:.4f}
        Candidate lcb95: {metrics.lcb95:.4f}
        Candidate max_plies_rate: {metrics.max_plies_rate:.4f}
        Wins/draws/losses: {metrics.wins}/{metrics.draws}/{metrics.losses}
        Average plies: {metrics.average_plies:.2f}
        Average move time ms: {metrics.average_processing_time_ms:.3f}
        Average positions or nodes: {metrics.average_positions_or_nodes:.2f}
        Failure counts: {metrics.failure_counts}
        Verdict: {verdict_reason}
        """
    )


def update_state_and_attempts(
    state: dict[str, Any],
    candidate: Candidate,
    attempt_id: str,
    status: str,
    verdict_reason: str,
    attempt_note: dict[str, Any],
    metrics: EvaluationMetrics | None,
    log_path: Path,
    approved_log_path: Path | None,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    seed = state["latest_approved"]
    attempt = {
        "timestamp": now,
        "commit": "<pending>",
        "status": status,
        "evaluator_baseline": state["evaluator"]["opponent"],
        "seed_version": seed["version"],
        "seed_file": seed["engine_file"],
        "candidate_version": candidate.version,
        "version_bump": candidate.version_bump,
        "hypotheses": attempt_note["hypotheses"],
        "implementation_summary": attempt_note["implementation_summary"],
        "evaluation_log_path": "<pending>" if status == "approved" else "<n/a>",
        "inferred_conclusion": attempt_note["inferred_conclusion"],
        "metrics": metrics_to_dict(metrics),
    }
    if status == "approved" and metrics is not None:
        state["latest_approved"] = {
            "version": candidate.version,
            "engine_file": str(candidate.engine_file.relative_to(REPO_ROOT)),
            "commit": attempt_id,
            "approved_recorded_at": now[:10],
            "approved_reference_score_rate_vs_stockfish_1350": round(metrics.score_rate, 4),
            "approved_reference_score_source": "<pending>",
            "notes": attempt_note["implementation_summary"],
        }
        update_latest_approved_markdown(state["latest_approved"])
    state["next_candidate_version"] = bump_minor(candidate.version)
    append_attempt_markdown(attempt)


def metrics_to_dict(metrics: EvaluationMetrics | None) -> dict[str, Any]:
    if metrics is None:
        return {}
    return {
        "wins": metrics.wins,
        "draws": metrics.draws,
        "losses": metrics.losses,
        "score": metrics.score,
        "score_rate": metrics.score_rate,
        "average_plies": metrics.average_plies,
        "average_processing_time_ms": metrics.average_processing_time_ms,
        "average_positions_or_nodes": metrics.average_positions_or_nodes,
        "failure_counts": metrics.failure_counts,
        "pair_mean": metrics.pair_mean,
        "pair_sd": metrics.pair_sd,
        "lcb95": metrics.lcb95,
        "games": metrics.games,
    }


def append_attempt_markdown(attempt: dict[str, Any]) -> None:
    metrics = attempt["metrics"]
    hypotheses = "\n".join(f"  - `{item}`" for item in attempt["hypotheses"])
    text = textwrap.dedent(
        f"""

        ## Attempt: {attempt['timestamp']} - {attempt['candidate_version']}

        - status: `{attempt['status']}`
        - commit: `{attempt['commit']}`
        - evaluator_baseline: `{attempt['evaluator_baseline']}`
        - seed_version: `{attempt['seed_version']}`
        - seed_file: `{attempt['seed_file']}`
        - candidate_version: `{attempt['candidate_version']}`
        - version_bump: `{attempt['version_bump']}`
        - hypotheses:
        {hypotheses}
        - implementation_summary: `{attempt['implementation_summary']}`
        - evaluation_log_path: `{attempt['evaluation_log_path']}`
        - wins/draws/losses: `{format_wdl(metrics)}`
        - score: `{format_score(metrics)}`
        - score_rate: `{format_float(metrics.get('score_rate'))}`
        - average_plies: `{format_float(metrics.get('average_plies'))}`
        - average_processing_time_ms: `{format_float(metrics.get('average_processing_time_ms'))}`
        - average_positions_or_nodes: `{format_float(metrics.get('average_positions_or_nodes'))}`
        - inferred_conclusion: `{attempt['inferred_conclusion']}`
        """
    )
    with ATTEMPTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(text)


def update_latest_approved_markdown(latest: dict[str, Any]) -> None:
    text = ATTEMPTS_PATH.read_text(encoding="utf-8")
    heading = "## Latest Approved Engine Seed"
    start = text.find(heading)
    if start == -1:
        return
    next_heading = text.find("\n## ", start + len(heading))
    if next_heading == -1:
        next_heading = len(text)

    replacement = textwrap.dedent(
        f"""\
        ## Latest Approved Engine Seed (Adjusted by `autoresearch/run_autoresearch.py` when evaluator approves)

        - approved_version: `{latest['version']}`
        - approved_file: `{latest['engine_file']}`
        - approved_commit: `{latest['commit']}`
        - approved_recorded_at: `{latest['approved_recorded_at']}`
        - approved_reference_score_rate_vs_stockfish_1350: `{latest['approved_reference_score_rate_vs_stockfish_1350']:.4f}`
        - approved_reference_score_source: `{latest['approved_reference_score_source']}`
        - notes: `{latest['notes']}`
        """
    )
    ATTEMPTS_PATH.write_text(text[:start] + replacement.rstrip() + "\n" + text[next_heading:], encoding="utf-8")


def current_branch() -> str:
    result = run(["git", "branch", "--show-current"], check=True, capture=True)
    return result.stdout.strip()


def format_score(metrics: dict[str, Any]) -> str:
    if "score" not in metrics:
        return "n/a"
    return f"{metrics['score']:.1f}"


def format_wdl(metrics: dict[str, Any]) -> str:
    if "wins" not in metrics:
        return "n/a/n/a/n/a"
    return f"{metrics['wins']}/{metrics['draws']}/{metrics['losses']}"


def format_float(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def cleanup_rejected_candidate(candidate: Candidate, status: str) -> None:
    if status == "rejected" and candidate.engine_file.exists():
        candidate.engine_file.unlink()


def commit_attempt(candidate: Candidate, status: str) -> str | None:
    run(["git", "add", "autoresearch/state.json", "autoresearch/ATTEMPTS.md"], check=True)
    if status == "approved":
        run(["git", "add", str(candidate.engine_file.relative_to(REPO_ROOT)), "autoresearch/approved_logs"], check=True)
    run(["git", "add", "-u", "engine_csharp/src/Engine.Core"], check=True)
    message = f"{'Approve' if status == 'approved' else 'Reject'} {candidate.version.upper()} via autoresearch"
    result = run(["git", "commit", "-m", message], check=False)
    if result.returncode != 0:
        print(f"No commit created for {candidate.version}; git commit returned {result.returncode}.", file=sys.stderr)
        return None
    sha = run(["git", "rev-parse", "--short", "HEAD"], check=True, capture=True)
    return sha.stdout.strip()


def finalize_attempt_commit(
    candidate: Candidate,
    status: str,
    commit_sha: str,
    approved_log_path: Path | None,
) -> None:
    approved_reference_source: str | None = None
    if status == "approved" and approved_log_path is not None and approved_log_path.exists():
        target = approved_log_path.with_name(f"{commit_sha}-result.csv")
        approved_log_path.rename(target)
        approved_reference_source = str(target.relative_to(REPO_ROOT))

    recorded_commit = commit_sha if status == "approved" else "<n/a>"
    replace_latest_attempt_placeholders(recorded_commit, approved_reference_source)
    if approved_reference_source is not None:
        replace_latest_approved_placeholders(commit_sha, approved_reference_source)

    run(["git", "add", "autoresearch/state.json", "autoresearch/ATTEMPTS.md"], check=True)
    if approved_reference_source is not None:
        run(["git", "add", "autoresearch/approved_logs"], check=True)
    run(["git", "commit", "--amend", "--no-edit"], check=True)


def replace_latest_attempt_placeholders(commit_sha: str, approved_reference_source: str | None) -> None:
    text = ATTEMPTS_PATH.read_text(encoding="utf-8")
    marker = "\n## Attempt:"
    start = text.rfind(marker)
    if start == -1:
        return
    head = text[:start]
    tail = text[start:]
    tail = tail.replace("- commit: `<pending>`", f"- commit: `{commit_sha}`", 1)
    if approved_reference_source is not None:
        tail = tail.replace("- evaluation_log_path: `<pending>`", f"- evaluation_log_path: `{approved_reference_source}`", 1)
    else:
        tail = tail.replace("- evaluation_log_path: `<pending>`", "- evaluation_log_path: `<n/a>`", 1)
    ATTEMPTS_PATH.write_text(head + tail, encoding="utf-8")


def replace_latest_approved_placeholders(commit_sha: str, approved_reference_source: str) -> None:
    state = load_state()
    state["latest_approved"]["commit"] = commit_sha
    state["latest_approved"]["approved_reference_score_source"] = approved_reference_source
    persist_state(state)
    update_latest_approved_markdown(state["latest_approved"])


def prompt_continue(status: str, candidate: Candidate, verdict: str) -> str:
    message = f"{candidate.version} {status}: {verdict}"
    while True:
        choice = run_kdialog(message)
        if choice == "snooze":
            time.sleep(300)
            continue
        return choice


def run_kdialog(message: str) -> str:
    if shutil.which("kdialog") is None or shutil.which("timeout") is None:
        print("KDialog or timeout is unavailable; continuing automatically.")
        return "continue"
    command = [
        "timeout",
        "60s",
        "kdialog",
        "--title",
        "Autoresearch",
        "--menu",
        message,
        "continue",
        "Continue",
        "stop",
        "Stop",
        "snooze",
        "Snooze 5 minutes",
    ]
    result = run(command, check=False, capture=True)
    if result.returncode == 124:
        print("No KDialog response within 60 seconds; continuing automatically.")
        return "continue"
    if result.returncode != 0:
        return "stop"
    choice = result.stdout.strip()
    return choice if choice in {"continue", "stop", "snooze"} else "continue"


def run(
    command: list[str],
    cwd: Path = REPO_ROOT,
    check: bool = False,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr or ""
        stdout = result.stdout or ""
        raise SystemExit(f"Command failed: {' '.join(command)}\n{stdout}{stderr}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())

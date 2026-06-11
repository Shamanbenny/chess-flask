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
import smtplib
import subprocess
import sys
import textwrap
import threading
import time
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = REPO_ROOT / "autoresearch" / "state.json"
ATTEMPTS_PATH = REPO_ROOT / "autoresearch" / "ATTEMPTS.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.json"
SANDBOX_ROOT = REPO_ROOT / "autoresearch-sandbox"
TEXT_LOG_DIR = REPO_ROOT / "autoresearch" / "console-logs"
LOCAL_ENV_PATH = REPO_ROOT / ".env"
ENGINE_VERSION_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)$", re.IGNORECASE)
SOC_CC_EVALUATOR_WORKERS = 12
SOC_CC_SMTP_HOST = "smtp.gmail.com"
SOC_CC_SMTP_PORT = 465
CURRENT_TEXT_LOG: Path | None = None


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


class CodexTurnTimeoutError(RuntimeError):
    pass


class CodexAuthRequiredError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        browser_auth_url: str | None = None,
        device_code_url: str | None = None,
        device_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.browser_auth_url = browser_auth_url
        self.device_code_url = device_code_url
        self.device_code = device_code


class CodexUsageLimitError(RuntimeError):
    pass


class SocCcConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SocCcConfig:
    email_username: str
    email_password: str
    email_to: str
    email_from: str


@dataclass(frozen=True)
class ExperimentNotificationArtifacts:
    log_attachment_name: str
    log_attachment_bytes: bytes


def log_phase(message: str) -> None:
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    emit_console(f"[autoresearch {stamp}] {message}\n", flush=True)


def emit_console(message: str, *, stream: Any = sys.stdout, flush: bool = False) -> None:
    stream.write(message)
    if flush:
        stream.flush()
    if CURRENT_TEXT_LOG is not None:
        with CURRENT_TEXT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(message)
            if flush:
                handle.flush()


def format_elapsed_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes:d}m {secs:02d}s"
    return f"{secs:d}s"


def log_experiment_duration(candidate: Candidate, started_at: dt.datetime, started_monotonic: float) -> None:
    ended_at = dt.datetime.now()
    elapsed = time.monotonic() - started_monotonic
    log_phase(
        "Experiment timing for "
        f"{candidate.version}: start={started_at.strftime('%Y-%m-%d %H:%M:%S')}, "
        f"end={ended_at.strftime('%Y-%m-%d %H:%M:%S')}, "
        f"elapsed={format_elapsed_duration(elapsed)}."
    )


def main() -> int:
    args = parse_args()
    if args.major and not args.prompt:
        raise SystemExit("A major improvement requires additional information about what to modify, so --prompt is required.")

    start_text_log()
    try:
        soc_cc = load_soc_cc_config() if args.soc_cc else None
    except SocCcConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    state = load_state()
    if not args.dry_run:
        ensure_clean_worktree()

    user_input = args.prompt or ""
    candidate = next_candidate(state, args.version, args.major)
    log_phase(f"Preparing sandbox for {candidate.version} from seed {state['latest_approved']['version']}.")
    prepare_sandbox(state, candidate, user_input)
    log_phase(f"Sandbox ready at {candidate.sandbox_dir.relative_to(REPO_ROOT)}.")

    if args.dry_run:
        emit_console(f"Dry run complete. Sandbox: {candidate.sandbox_dir.relative_to(REPO_ROOT)}\n")
        emit_console(f"Candidate: {candidate.version} -> {candidate.engine_file.relative_to(REPO_ROOT)}\n")
        return 0

    while True:
        experiment_started_at = dt.datetime.now()
        experiment_started_monotonic = time.monotonic()
        experiment_log_start_line = current_text_log_line_count()
        log_phase(f"Starting attempt for {candidate.version}.")
        try:
            codex_session = run_codex_implementation(
                state,
                candidate,
                soc_cc_enabled=args.soc_cc,
                soc_cc_config=soc_cc,
                experiment_log_start_line=experiment_log_start_line,
            )
        except CodexTurnTimeoutError as exc:
            reason = str(exc)
            log_phase(reason)
            cleanup_timed_out_attempt(candidate)
            log_experiment_duration(candidate, experiment_started_at, experiment_started_monotonic)
            choice = prompt_continue("timed out", candidate, reason, soc_cc_enabled=args.soc_cc)
            if choice == "stop":
                return 0
            state = load_state()
            user_input = args.prompt or ""
            log_phase(f"Re-preparing sandbox for retry of {candidate.version}.")
            prepare_sandbox(state, candidate, user_input)
            log_phase(f"Sandbox ready at {candidate.sandbox_dir.relative_to(REPO_ROOT)}.")
            continue
        except (CodexAuthRequiredError, CodexUsageLimitError) as exc:
            log_phase(str(exc))
            emit_console(format_auth_resolution(exc), flush=True)
            if soc_cc is not None:
                send_soc_cc_blocker_email(
                    soc_cc,
                    candidate,
                    exc,
                    experiment_log_start_line=experiment_log_start_line,
                )
            return 1

        log_phase(f"Copying {candidate.sandbox_engine_file.name} back into the repository.")
        copy_candidate_to_repo(candidate)
        attempt_id = make_attempt_id(candidate)
        log_phase(f"Running solution build for {candidate.version} (attempt {attempt_id}).")
        build_ok = run_build()

        metrics: EvaluationMetrics | None = None
        status = "rejected"
        verdict_reason = "Build failed before evaluator run."
        log_path = REPO_ROOT / "autoresearch" / "logs" / f"{attempt_id}-result.csv"
        approved_log_path: Path | None = None

        if build_ok:
            log_phase("Build succeeded. Starting evaluator run.")
            evaluator_ok = run_evaluator(
                candidate,
                state,
                attempt_id,
                args.smoke_games,
                soc_cc_enabled=args.soc_cc,
            )
            if evaluator_ok and log_path.exists():
                log_phase(f"Evaluator finished. Parsing results from {log_path.relative_to(REPO_ROOT)}.")
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
                log_phase(verdict_reason)
        else:
            log_phase("Build failed. Skipping evaluator.")

        evaluation_summary = build_evaluation_summary(candidate, status, verdict_reason, metrics, state)
        log_phase("Sending evaluation summary back into the existing Codex session.")
        try:
            run_codex_result_update(state, candidate, codex_session, evaluation_summary)
        except CodexTurnTimeoutError as exc:
            reason = str(exc)
            log_phase(reason)
            cleanup_timed_out_attempt(
                candidate,
                log_path=log_path if log_path.exists() else None,
                approved_log_path=approved_log_path,
            )
            log_experiment_duration(candidate, experiment_started_at, experiment_started_monotonic)
            choice = prompt_continue("timed out", candidate, reason, soc_cc_enabled=args.soc_cc)
            if choice == "stop":
                return 0
            state = load_state()
            user_input = args.prompt or ""
            log_phase(f"Re-preparing sandbox for retry of {candidate.version}.")
            prepare_sandbox(state, candidate, user_input)
            log_phase(f"Sandbox ready at {candidate.sandbox_dir.relative_to(REPO_ROOT)}.")
            continue
        except (CodexAuthRequiredError, CodexUsageLimitError) as exc:
            log_phase(str(exc))
            emit_console(format_auth_resolution(exc), flush=True)
            if soc_cc is not None:
                send_soc_cc_blocker_email(
                    soc_cc,
                    candidate,
                    exc,
                    experiment_log_start_line=experiment_log_start_line,
                )
            return 1
        log_phase("Reading structured sandbox result from RETURN.json.")
        attempt_note = read_return_json(candidate)

        log_phase(f"Persisting attempt outcome: {status}.")
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
        push_error: str | None = None
        commit_sha = commit_attempt(candidate, status)
        if commit_sha:
            commit_sha = finalize_attempt_commit(candidate, status, commit_sha, approved_log_path)
            log_phase(f"Recorded git commit {commit_sha} for {candidate.version}.")
            if args.soc_cc:
                try:
                    push_current_branch()
                except RuntimeError as exc:
                    push_error = str(exc)
                    log_phase(push_error)

        log_experiment_duration(candidate, experiment_started_at, experiment_started_monotonic)
        if soc_cc is not None:
            send_soc_cc_completion_email(
                soc_cc,
                candidate,
                status,
                verdict_reason if push_error is None else f"{verdict_reason} Push status: {push_error}",
                commit_sha,
                metrics,
                rejected_csv_path=log_path if status == "rejected" and log_path.exists() else None,
                experiment_log_start_line=experiment_log_start_line,
            )
        if push_error is not None:
            return 1
        choice = prompt_continue(status, candidate, verdict_reason, soc_cc_enabled=args.soc_cc)
        if choice == "stop":
            return 0
        if args.once:
            return 0

        state = load_state()
        user_input = args.prompt or ""
        candidate = next_candidate(state, args.version, args.major)
        log_phase(f"Preparing sandbox for next candidate {candidate.version}.")
        prepare_sandbox(state, candidate, user_input)
        log_phase(f"Sandbox ready at {candidate.sandbox_dir.relative_to(REPO_ROOT)}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Python-owned autoresearch loop.")
    parser.add_argument("--prompt", help="Optional experiment direction embedded into the sandbox PROGRAM.md.")
    parser.add_argument("--version", help="Force candidate version, for example v3.5.")
    parser.add_argument("--major", action="store_true", help="Start a new major version experiment. Requires --prompt.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare sandbox only; do not call Codex or evaluate.")
    parser.add_argument("--once", action="store_true", help="Exit after one attempt instead of prompting for another.")
    parser.add_argument(
        "--soc-cc",
        action="store_true",
        help=(
            "Enable School of Computing Compute Cluster mode: auto-continue without KDialog, "
            "use 12 evaluator workers, push after each finalized commit, and send Gmail notifications "
            "using credentials from the repo-local .env file."
        ),
    )
    parser.add_argument(
        "--smoke-games",
        type=int,
        help="Run a non-approving evaluator smoke test with this game count.",
    )
    return parser.parse_args()


def start_text_log() -> None:
    global CURRENT_TEXT_LOG
    TEXT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    CURRENT_TEXT_LOG = TEXT_LOG_DIR / f"{stamp}-log.txt"
    emit_console(f"[autoresearch {dt.datetime.now().strftime('%H:%M:%S')}] Mirroring console output to {CURRENT_TEXT_LOG.relative_to(REPO_ROOT)}.\n", flush=True)


def load_soc_cc_config() -> SocCcConfig:
    env = load_local_env(LOCAL_ENV_PATH)
    username = env.get("SOC_CC_GMAIL_USERNAME", "").strip()
    password = env.get("SOC_CC_GMAIL_APP_PASSWORD", "").strip()
    recipient = env.get("SOC_CC_NOTIFY_EMAIL_TO", "").strip()
    sender = env.get("SOC_CC_NOTIFY_EMAIL_FROM", "").strip() or username

    missing = [
        key
        for key, value in (
            ("SOC_CC_GMAIL_USERNAME", username),
            ("SOC_CC_GMAIL_APP_PASSWORD", password),
            ("SOC_CC_NOTIFY_EMAIL_TO", recipient),
        )
        if not value
    ]
    if missing:
        raise SocCcConfigurationError(
            "SOC CC mode requires the repo-local .env file to define: " + ", ".join(missing)
        )

    return SocCcConfig(
        email_username=username,
        email_password=password,
        email_to=recipient,
        email_from=sender,
    )


def load_local_env(path: Path) -> dict[str, str]:
    if not path.exists():
        raise SocCcConfigurationError(f"SOC CC mode requires a repo-local .env file at {path}.")

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def current_text_log_line_count() -> int:
    if CURRENT_TEXT_LOG is None or not CURRENT_TEXT_LOG.exists():
        return 0
    with CURRENT_TEXT_LOG.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def latest_experiment_log_lines(start_line: int) -> list[str]:
    if CURRENT_TEXT_LOG is None or not CURRENT_TEXT_LOG.exists():
        return []
    with CURRENT_TEXT_LOG.open(encoding="utf-8") as handle:
        lines = handle.readlines()
    return lines[start_line:]


def build_experiment_log_attachment(candidate: Candidate, start_line: int) -> ExperimentNotificationArtifacts:
    lines = latest_experiment_log_lines(start_line)
    first_chunk = lines[:100]
    last_chunk = lines[-100:] if len(lines) > 100 else []
    body = [
        f"# Latest Experiment Log Slice for {candidate.version}",
        "",
        "## First 100 Lines",
        "",
        *(line.rstrip("\n") for line in first_chunk),
    ]
    if last_chunk:
        body.extend(
            [
                "",
                "## Last 100 Lines",
                "",
                *(line.rstrip("\n") for line in last_chunk),
            ]
        )

    attachment_name = f"{candidate.stem}-console-log-head-tail.txt"
    return ExperimentNotificationArtifacts(
        log_attachment_name=attachment_name,
        log_attachment_bytes=("\n".join(body) + "\n").encode("utf-8"),
    )


def send_soc_cc_email(
    config: SocCcConfig,
    *,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.email_from
    message["To"] = config.email_to
    message.set_content(body)

    for filename, payload, mime_type in attachments or []:
        maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)

    with smtplib.SMTP_SSL(SOC_CC_SMTP_HOST, SOC_CC_SMTP_PORT) as smtp:
        smtp.login(config.email_username, config.email_password)
        smtp.send_message(message)


def send_soc_cc_blocker_email(
    config: SocCcConfig,
    candidate: Candidate,
    exc: Exception,
    *,
    experiment_log_start_line: int,
) -> None:
    blocker_type = "login required" if isinstance(exc, CodexAuthRequiredError) else "usage limit reached"
    attachments: list[tuple[str, bytes, str]] = []
    log_artifacts = build_experiment_log_attachment(candidate, experiment_log_start_line)
    attachments.append((log_artifacts.log_attachment_name, log_artifacts.log_attachment_bytes, "text/plain"))
    resolution = format_auth_resolution(exc) if isinstance(exc, CodexAuthRequiredError) else ""
    send_soc_cc_email(
        config,
        subject=f"[autoresearch][soc-cc] {candidate.version} blocked: {blocker_type}",
        body=(
            f"Candidate: {candidate.version}\n"
            f"Blocker: {blocker_type}\n"
            f"Detail: {exc}\n"
            f"Console log: {CURRENT_TEXT_LOG.relative_to(REPO_ROOT) if CURRENT_TEXT_LOG is not None else 'n/a'}\n"
            f"{resolution}"
        ),
        attachments=attachments,
    )


def send_soc_cc_completion_email(
    config: SocCcConfig,
    candidate: Candidate,
    status: str,
    verdict_reason: str,
    commit_sha: str | None,
    metrics: EvaluationMetrics | None,
    *,
    rejected_csv_path: Path | None,
    experiment_log_start_line: int,
) -> None:
    log_artifacts = build_experiment_log_attachment(candidate, experiment_log_start_line)
    attachments: list[tuple[str, bytes, str]] = [
        (log_artifacts.log_attachment_name, log_artifacts.log_attachment_bytes, "text/plain")
    ]
    if rejected_csv_path is not None and rejected_csv_path.exists():
        attachments.append((rejected_csv_path.name, rejected_csv_path.read_bytes(), "text/csv"))

    metrics_lines = "n/a"
    if metrics is not None:
        metrics_lines = (
            f"wins/draws/losses: {metrics.wins}/{metrics.draws}/{metrics.losses}\n"
            f"score_rate: {metrics.score_rate:.4f}\n"
            f"lcb95: {metrics.lcb95:.4f}\n"
            f"max_plies_rate: {metrics.max_plies_rate:.4f}\n"
            f"average_plies: {metrics.average_plies:.2f}\n"
            f"average_processing_time_ms: {metrics.average_processing_time_ms:.3f}\n"
            f"average_positions_or_nodes: {metrics.average_positions_or_nodes:.2f}"
        )

    send_soc_cc_email(
        config,
        subject=f"[autoresearch][soc-cc] {candidate.version} {status}",
        body=(
            f"Candidate: {candidate.version}\n"
            f"Status: {status}\n"
            f"Verdict: {verdict_reason}\n"
            f"Commit: {commit_sha or 'n/a'}\n"
            f"Console log: {CURRENT_TEXT_LOG.relative_to(REPO_ROOT) if CURRENT_TEXT_LOG is not None else 'n/a'}\n"
            f"Rejected CSV attached: {'yes' if rejected_csv_path is not None and rejected_csv_path.exists() else 'no'}\n"
            f"Metrics:\n{metrics_lines}\n"
        ),
        attachments=attachments,
    )


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
        - You are NOT expected to and NOT allowed to run the evaluator. (THIS IS OF UTMOST IMPORTANCE)
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


@dataclass
class CodexTurnStreamResult:
    final_response: str
    usage: Any | None


def format_codex_usage(usage: Any | None) -> str:
    if usage is None:
        return "n/a"
    if hasattr(usage, "model_dump"):
        return json.dumps(usage.model_dump(exclude_none=True), sort_keys=True)
    if hasattr(usage, "dict"):
        return json.dumps(usage.dict(exclude_none=True), sort_keys=True)
    return str(usage)


def codex_turn_timeout_seconds(state: dict[str, Any]) -> int:
    minutes = int(state.get("agent", {}).get("codex_turn_timeout_minutes", 15))
    return max(minutes, 1) * 60


def turn_error_text(turn_error: Any) -> str:
    message = getattr(turn_error, "message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()
    return str(turn_error)


def error_payload_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(by_alias=True, exclude_none=True), sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def is_usage_limit_error_text(text: str) -> bool:
    lowered = text.lower()
    return any(
        fragment in lowered
        for fragment in (
            "usagelimitexceeded",
            "usage limit exceeded",
            "usage limit",
            "token limit",
            "token budget",
            "quota",
        )
    )


def format_auth_resolution(exc: Exception) -> str:
    if not isinstance(exc, CodexAuthRequiredError):
        return ""

    lines = ["", "Resolution:"]
    if exc.browser_auth_url:
        lines.extend(
            [
                "- Finish signing in via your browser using this URL:",
                f"  {exc.browser_auth_url}",
            ]
        )
    if exc.device_code_url and exc.device_code:
        lines.extend(
            [
                "- On a remote or headless machine, use device code login:",
                f"  verification_url: {exc.device_code_url}",
                f"  user_code: {exc.device_code}",
            ]
        )
    if len(lines) == 2:
        lines.append("- No interactive login URL or device code was available from the SDK.")
    lines.append("")
    return "\n".join(lines)


def classify_turn_failure(turn_error: Any) -> Exception:
    message = turn_error_text(turn_error)
    payload_text = error_payload_text(getattr(turn_error, "codex_error_info", None))
    combined = f"{message}\n{payload_text}"
    lowered = combined.lower()

    if "unauthorized" in lowered or "requiresopenaiauth" in lowered or "login" in lowered:
        return CodexAuthRequiredError(f"Codex requires login credentials: {message}")
    if is_usage_limit_error_text(lowered):
        return CodexUsageLimitError(f"Codex usage limit reached: {message}")
    return RuntimeError(message)


def classify_codex_exception(exc: Exception) -> Exception:
    combined = error_payload_text(exc)
    lowered = combined.lower()
    if "unauthorized" in lowered or "requiresopenaiauth" in lowered:
        return CodexAuthRequiredError(f"Codex requires login credentials: {exc}")
    if is_usage_limit_error_text(lowered):
        return CodexUsageLimitError(f"Codex usage limit reached: {exc}")
    return exc


def ensure_codex_account_ready(
    codex: Any,
    *,
    soc_cc_enabled: bool,
    soc_cc_config: SocCcConfig | None,
    candidate: Candidate,
    experiment_log_start_line: int,
) -> None:
    account = codex.account(refresh_token=True)
    if not getattr(account, "requires_openai_auth", False):
        return

    browser_auth_url: str | None = None
    device_code_url: str | None = None
    device_code: str | None = None
    login_handle: Any | None = None

    if soc_cc_enabled:
        login_handle = codex.login_chatgpt_device_code()
        device_code_url = login_handle.verification_url
        device_code = login_handle.user_code
    else:
        login_handle = codex.login_chatgpt()
        browser_auth_url = login_handle.auth_url

    auth_error = CodexAuthRequiredError(
        "Codex account state reports that OpenAI authentication is required before the experiment can continue.",
        browser_auth_url=browser_auth_url,
        device_code_url=device_code_url,
        device_code=device_code,
    )
    log_phase(str(auth_error))
    emit_console(format_auth_resolution(auth_error), flush=True)

    if soc_cc_config is not None:
        send_soc_cc_blocker_email(
            soc_cc_config,
            candidate,
            auth_error,
            experiment_log_start_line=experiment_log_start_line,
        )

    log_phase("Waiting for Codex login completion.")
    completed = login_handle.wait()
    if not getattr(completed, "success", False):
        error = getattr(completed, "error", None) or "login did not complete successfully"
        raise CodexAuthRequiredError(
            f"Codex login failed: {error}",
            browser_auth_url=browser_auth_url,
            device_code_url=device_code_url,
            device_code=device_code,
        )

    account = codex.account(refresh_token=True)
    if getattr(account, "requires_openai_auth", False):
        log_phase(
            "Codex login completed, but account refresh still reports requiresOpenaiAuth=true; "
            "continuing so the next Codex operation can validate the session."
        )
        return
    log_phase("Codex login completed; continuing experiment.")


def run_codex_turn(
    thread: Any,
    *,
    state: dict[str, Any],
    prompt: str,
    label: str,
    sandbox_cwd: Path,
) -> CodexTurnStreamResult:
    emit_console(f"\n[codex prompt: {label}]\n{prompt}\n\n", flush=True)
    turn = thread.turn(prompt, cwd=str(sandbox_cwd))
    turn_state: dict[str, Any] = {
        "error": None,
        "completed_status": None,
        "completed_usage": None,
        "completed_texts": [],
        "printed_response_prefix": False,
        "completed_turn_error": None,
    }

    def worker() -> None:
        try:
            for event in turn.stream():
                if event.method == "turn/started":
                    log_phase(f"Codex turn started: {label}.")
                    continue

                if event.method == "item/agentMessage/delta":
                    delta = event.payload.delta
                    if delta:
                        if not turn_state["printed_response_prefix"]:
                            emit_console(f"[codex response: {label}] ", flush=True)
                            turn_state["printed_response_prefix"] = True
                        emit_console(delta, flush=True)
                    continue

                if event.method == "item/completed":
                    root = event.payload.item.root
                    if getattr(root, "type", None) == "agentMessage":
                        turn_state["completed_texts"].append(root.text)
                    continue

                if event.method == "turn/completed":
                    turn_state["completed_status"] = event.payload.turn.status.value
                    turn_state["completed_usage"] = getattr(event.payload.turn, "usage", None)
                    turn_state["completed_turn_error"] = getattr(event.payload.turn, "error", None)
        except Exception as exc:
            turn_state["error"] = exc

    worker_thread = threading.Thread(target=worker, name=f"codex-turn-{label}", daemon=True)
    worker_thread.start()
    timeout_seconds = codex_turn_timeout_seconds(state)
    deadline = time.monotonic() + timeout_seconds

    while worker_thread.is_alive():
        worker_thread.join(timeout=0.5)
        if time.monotonic() < deadline:
            continue

        try:
            turn.interrupt()
        except Exception as exc:
            log_phase(f"Codex turn timeout interrupt failed for {label}: {exc}")
        worker_thread.join(timeout=5)
        raise CodexTurnTimeoutError(
            f"Codex turn '{label}' exceeded {timeout_seconds // 60} minutes."
        )

    if turn_state["printed_response_prefix"]:
        emit_console("\n", flush=True)

    if turn_state["error"] is not None:
        raise classify_codex_exception(turn_state["error"])

    if turn_state["completed_status"] == "failed" and turn_state["completed_turn_error"] is not None:
        raise classify_turn_failure(turn_state["completed_turn_error"])

    final_response = turn_state["completed_texts"][-1].strip() if turn_state["completed_texts"] else ""
    log_phase(f"Codex turn completed: {label} ({turn_state['completed_status'] or 'unknown'}).")
    log_phase(f"Codex turn usage ({label}): {format_codex_usage(turn_state['completed_usage'])}")
    return CodexTurnStreamResult(final_response=final_response, usage=turn_state["completed_usage"])


def run_codex_implementation(
    state: dict[str, Any],
    candidate: Candidate,
    *,
    soc_cc_enabled: bool,
    soc_cc_config: SocCcConfig | None,
    experiment_log_start_line: int,
) -> CodexSession:
    try:
        from openai_codex import Codex, Sandbox
    except ImportError as exc:
        raise SystemExit("Install autoresearch/requirements.txt before running Codex.") from exc

    log_phase(f"Creating new Codex manager for sandbox {candidate.sandbox_dir.name}.")
    manager = Codex()
    previous_cwd = Path.cwd()
    os.chdir(candidate.sandbox_dir)
    codex = None
    try:
        log_phase("Opening new Codex session.")
        codex = manager.__enter__()
        log_phase("Checking Codex account state.")
        ensure_codex_account_ready(
            codex,
            soc_cc_enabled=soc_cc_enabled,
            soc_cc_config=soc_cc_config,
            candidate=candidate,
            experiment_log_start_line=experiment_log_start_line,
        )
        log_phase("Creating workspace-write Codex thread.")
        thread = codex.thread_start(sandbox=Sandbox.workspace_write, cwd=str(candidate.sandbox_dir))
        log_phase("Waiting for Codex to finish the initial implementation pass.")
        result = run_codex_turn(
            thread,
            state=state,
            prompt="Start by looking at `PROGRAM.md`, and let's kick off the experiment loop!",
            label=f"{candidate.version} implementation",
            sandbox_cwd=candidate.sandbox_dir,
        )
        final_response = result.final_response
        log_phase("Codex finished the initial implementation pass.")
    except Exception as exc:
        if codex is not None:
            manager.__exit__(None, None, None)
        raise classify_codex_exception(exc)
    finally:
        os.chdir(previous_cwd)

    (candidate.sandbox_dir / "CODEX_RESULT.md").write_text(final_response, encoding="utf-8")
    return CodexSession(manager, thread)


def run_codex_result_update(
    state: dict[str, Any],
    candidate: Candidate,
    session: CodexSession,
    evaluation_summary: str,
) -> None:
    previous_cwd = Path.cwd()
    os.chdir(candidate.sandbox_dir)
    try:
        log_phase("Waiting for Codex to process the evaluation follow-up prompt.")
        result = run_codex_turn(
            session.thread,
            state=state,
            prompt=(
                f"Here's your evaluation result for {candidate.version} Engine.\n\n"
                f"{evaluation_summary}\n\n"
                "Reminder: update `RETURN.json` with your inferred conclusion, and thank you for your help!"
            ),
            label=f"{candidate.version} evaluation follow-up",
            sandbox_cwd=candidate.sandbox_dir,
        )
        final_response = result.final_response
        log_phase("Codex finished the evaluation follow-up prompt.")
    except Exception as exc:
        raise classify_codex_exception(exc)
    finally:
        os.chdir(previous_cwd)
        log_phase("Closing Codex session.")
        session.manager.__exit__(None, None, None)

    (candidate.sandbox_dir / "CODEX_EVALUATION_RESULT.md").write_text(final_response, encoding="utf-8")


def copy_candidate_to_repo(candidate: Candidate) -> None:
    candidate.engine_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate.sandbox_engine_file, candidate.engine_file)


def cleanup_timed_out_attempt(
    candidate: Candidate,
    *,
    log_path: Path | None = None,
    approved_log_path: Path | None = None,
) -> None:
    if approved_log_path is not None and approved_log_path.exists():
        approved_log_path.unlink()
    if log_path is not None and log_path.exists():
        log_path.unlink()
    if candidate.engine_file.exists():
        candidate.engine_file.unlink()
    if candidate.sandbox_dir.exists():
        shutil.rmtree(candidate.sandbox_dir)


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
    *,
    soc_cc_enabled: bool,
) -> bool:
    stockfish_path = os.environ.get("STOCKFISH_PATH")
    if not stockfish_path:
        emit_console("STOCKFISH_PATH is required for evaluation.\n", stream=sys.stderr, flush=True)
        return False

    evaluator = state["evaluator"]
    games = smoke_games or evaluator["games"]
    workers = SOC_CC_EVALUATOR_WORKERS if soc_cc_enabled else evaluator["workers"]
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
        str(workers),
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
    upsert_changelog_version(
        candidate,
        status,
        attempt_note,
        metrics,
        approved_log_path,
        commit="<pending>" if status == "approved" else "<n/a>",
    )
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
    lines = [
        "",
        "",
        f"## Attempt: {attempt['timestamp']} - {attempt['candidate_version']}",
        "",
        f"- status: `{attempt['status']}`",
        f"- commit: `{attempt['commit']}`",
        f"- evaluator_baseline: `{attempt['evaluator_baseline']}`",
        f"- seed_version: `{attempt['seed_version']}`",
        f"- seed_file: `{attempt['seed_file']}`",
        f"- candidate_version: `{attempt['candidate_version']}`",
        f"- version_bump: `{attempt['version_bump']}`",
        "- hypotheses:",
    ]
    lines.extend(f"  - `{item}`" for item in attempt["hypotheses"])
    lines.extend(
        [
            f"- implementation_summary: `{attempt['implementation_summary']}`",
            f"- evaluation_log_path: `{attempt['evaluation_log_path']}`",
            f"- wins/draws/losses: `{format_wdl(metrics)}`",
            f"- score: `{format_score(metrics)}`",
            f"- score_rate: `{format_float(metrics.get('score_rate'))}`",
            f"- average_plies: `{format_float(metrics.get('average_plies'))}`",
            f"- average_processing_time_ms: `{format_float(metrics.get('average_processing_time_ms'))}`",
            f"- average_positions_or_nodes: `{format_float(metrics.get('average_positions_or_nodes'))}`",
            f"- inferred_conclusion: `{attempt['inferred_conclusion']}`",
        ]
    )
    text = "\n".join(lines)
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


def upsert_changelog_version(
    candidate: Candidate,
    status: str,
    attempt_note: dict[str, Any],
    metrics: EvaluationMetrics | None,
    approved_log_path: Path | None,
    commit: str,
) -> None:
    changelog = load_changelog()
    versions = changelog.setdefault("versions", [])
    if not isinstance(versions, list):
        raise SystemExit("CHANGELOG.json must contain a versions array.")

    has_metrics = metrics is not None
    evaluator = changelog_evaluator_metadata()
    opponent_key = evaluator_opponent_key(evaluator)

    version_entry = {
        "version": candidate.version,
        "api_version": candidate.version.replace(".", "_"),
        "engine_file": str(candidate.engine_file.relative_to(REPO_ROOT)),
        "served": False,
        "status": status,
        "commit": commit,
        "hypotheses": attempt_note["hypotheses"],
        "summary": attempt_note["implementation_summary"],
        "implementation_summary": attempt_note["implementation_summary"],
        "evaluation_log_path": (
            str(approved_log_path.relative_to(REPO_ROOT))
            if approved_log_path is not None
            else "<pending>" if status == "approved" else "<n/a>"
        ),
        "evaluation_opponents": {
            opponent_key: {
                "games": metrics.games if has_metrics else None,
                "wins": metrics.wins if has_metrics else None,
                "draws": metrics.draws if has_metrics else None,
                "losses": metrics.losses if has_metrics else None,
                "score": round(metrics.score, 1) if has_metrics else None,
                "score_rate": round(metrics.score_rate, 4) if has_metrics else None,
                "text": (
                    evaluator_score_text(candidate.version, metrics, evaluator)
                    if has_metrics
                    else f"No final {evaluator['name']} ({evaluator['elo']} Elo) result was recorded for this rejected attempt."
                ),
            },
        },
        "limitations": [],
    }

    existing_index = next(
        (index for index, item in enumerate(versions) if item.get("version") == candidate.version),
        None,
    )
    if existing_index is None:
        versions.append(version_entry)
    else:
        existing = versions[existing_index]
        if isinstance(existing, dict) and "served" in existing:
            version_entry["served"] = bool(existing["served"])
        versions[existing_index] = version_entry

    versions.sort(key=lambda item: parse_version(str(item["version"])))
    changelog["schema_version"] = max(int(changelog.get("schema_version", 1)), 2)
    changelog.setdefault("evaluation_opponents", {})[opponent_key] = evaluator
    changelog.pop("stockfish_baseline", None)
    write_changelog(changelog)


def changelog_evaluator_metadata() -> dict[str, Any]:
    state = load_state()
    evaluator = state["evaluator"]
    opponent = str(evaluator["opponent"])
    name = "Stockfish" if opponent.lower().startswith("stockfish") else opponent
    return {
        "name": name,
        "elo": evaluator["stockfish_elo"],
    }


def evaluator_opponent_key(evaluator: dict[str, Any]) -> str:
    return f"{str(evaluator['name']).lower().replace(' ', '-')}-{evaluator['elo']}"


def evaluator_score_text(version: str, metrics: EvaluationMetrics, evaluator: dict[str, Any]) -> str:
    return (
        f"C# {version} scored {metrics.score:.1f}/{metrics.games} against {evaluator['name']} ({evaluator['elo']} Elo): "
        f"{metrics.wins} wins, {metrics.draws} draws, {metrics.losses} losses, "
        f"score rate {metrics.score_rate:.4f}."
    )


def load_changelog() -> dict[str, Any]:
    if not CHANGELOG_PATH.exists():
        return {
            "schema_version": 2,
            "generated_from": "autoresearch/ATTEMPTS.md and autoresearch/approved_logs",
            "evaluation_opponents": {
                "stockfish-1350": {
                    "name": "Stockfish",
                    "elo": 1350,
                },
            },
            "versions": [],
        }

    with CHANGELOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_changelog(changelog: dict[str, Any]) -> None:
    CHANGELOG_PATH.write_text(json.dumps(changelog, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def current_branch() -> str:
    result = run(["git", "branch", "--show-current"], check=True, capture=True)
    return result.stdout.strip()


def push_current_branch() -> None:
    branch = current_branch()
    if not branch:
        raise RuntimeError("Cannot push autoresearch commit because the current branch is unknown.")
    log_phase(f"Pushing latest autoresearch commit to origin/{branch}.")
    result = run(["git", "push", "origin", branch], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git push origin {branch} failed with exit code {result.returncode}.")


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
    run(["git", "add", "autoresearch/state.json", "autoresearch/ATTEMPTS.md", "CHANGELOG.json"], check=True)
    if status == "approved":
        run(["git", "add", str(candidate.engine_file.relative_to(REPO_ROOT)), "autoresearch/approved_logs"], check=True)
    run(["git", "add", "-u", "engine_csharp/src/Engine.Core"], check=True)
    message = f"{'Approve' if status == 'approved' else 'Reject'} {candidate.version.upper()} via autoresearch"
    result = run(["git", "commit", "-m", message], check=False)
    if result.returncode != 0:
        emit_console(
            f"No commit created for {candidate.version}; git commit returned {result.returncode}.\n",
            stream=sys.stderr,
            flush=True,
        )
        return None
    sha = run(["git", "rev-parse", "--short", "HEAD"], check=True, capture=True)
    return sha.stdout.strip()


def finalize_attempt_commit(
    candidate: Candidate,
    status: str,
    commit_sha: str,
    approved_log_path: Path | None,
) -> str:
    approved_reference_source: str | None = None
    if status == "approved" and approved_log_path is not None and approved_log_path.exists():
        target = approved_log_path.with_name(f"{candidate.stem}-{commit_sha}-result.csv")
        approved_log_path.rename(target)
        approved_reference_source = str(target.relative_to(REPO_ROOT))

    recorded_commit = commit_sha if status == "approved" else "<n/a>"
    replace_latest_attempt_placeholders(recorded_commit, approved_reference_source)
    if approved_reference_source is not None:
        replace_latest_approved_placeholders(commit_sha, approved_reference_source)
        replace_latest_changelog_placeholders(commit_sha, approved_reference_source)

    run(["git", "add", "autoresearch/state.json", "autoresearch/ATTEMPTS.md", "CHANGELOG.json"], check=True)
    if approved_reference_source is not None:
        run(["git", "add", "autoresearch/approved_logs"], check=True)
    run(["git", "commit", "--amend", "--no-edit"], check=True)
    amended = run(["git", "rev-parse", "--short", "HEAD"], check=True, capture=True)
    return amended.stdout.strip()


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


def replace_latest_changelog_placeholders(commit_sha: str, approved_reference_source: str) -> None:
    changelog = load_changelog()
    versions = changelog.get("versions")
    if not isinstance(versions, list):
        return

    for item in versions:
        if not isinstance(item, dict):
            continue
        if item.get("commit") != "<pending>":
            continue
        item["commit"] = commit_sha
        item["evaluation_log_path"] = approved_reference_source

    write_changelog(changelog)


def prompt_continue(status: str, candidate: Candidate, verdict: str, *, soc_cc_enabled: bool) -> str:
    if soc_cc_enabled:
        log_phase(f"SOC CC mode auto-continues after {candidate.version} {status}.")
        return "continue"
    message = f"{candidate.version} {status}: {verdict}"
    while True:
        choice = run_kdialog(message)
        if choice == "snooze":
            time.sleep(300)
            continue
        return choice


def run_kdialog(message: str) -> str:
    if shutil.which("kdialog") is None or shutil.which("timeout") is None:
        emit_console("KDialog or timeout is unavailable; continuing automatically.\n", flush=True)
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
        emit_console("No KDialog response within 60 seconds; continuing automatically.\n", flush=True)
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
    if not capture:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            streamed_output: list[str] = []
            assert process.stdout is not None
            for line in process.stdout:
                streamed_output.append(line)
                emit_console(line, flush=False)
            returncode = process.wait()
        finally:
            if process.stdout is not None:
                process.stdout.close()
        stdout = "".join(streamed_output)
        if check and returncode != 0:
            raise SystemExit(f"Command failed: {' '.join(command)}\n{stdout}")
        return subprocess.CompletedProcess(command, returncode, stdout, None)

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

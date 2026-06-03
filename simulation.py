import argparse
import csv
import io
import json
import multiprocessing
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

import chess

from api.endpoint import timed_engine_response


DEFAULT_BASE_URL = "http://localhost:3000"
DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Historical note:
# Only v0 is currently exposed over Flask routes. The simulation code remains
# here because it may be useful again once historical engine-vs-engine
# simulation becomes part of the active workflow.
VERSION_TO_PATH = {
    "0": "/chess_v0",
    "v0": "/chess_v0",
}


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def resolve_endpoint(version: str) -> str:
    try:
        return VERSION_TO_PATH[version.lower()]
    except KeyError as exc:
        valid_versions = ", ".join(sorted(VERSION_TO_PATH))
        raise ValueError(f"Unsupported version '{version}'. Use one of: {valid_versions}") from exc


def post_move_request(base_url: str, endpoint: str, fen: str, timeout: float) -> tuple[int, dict, float]:
    url = f"{normalize_base_url(base_url)}{endpoint}"
    payload = json.dumps({"fen": fen}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            elapsed = time.perf_counter() - start_time
            return response.status, json.loads(body), elapsed
    except urllib.error.HTTPError as error:
        elapsed = time.perf_counter() - start_time
        body = error.read().decode("utf-8")
        try:
            parsed_body = json.loads(body)
        except json.JSONDecodeError:
            parsed_body = {"error": body or str(error)}
        return error.code, parsed_body, elapsed
    except (TimeoutError, socket.timeout) as error:
        elapsed = time.perf_counter() - start_time
        return 408, {"error": str(error) or "Request timed out"}, elapsed


def request_move_http(base_url: str, version: str, fen: str, timeout: float) -> dict:
    endpoint = resolve_endpoint(version)
    status, body, elapsed = post_move_request(base_url, endpoint, fen, timeout)
    return {
        "version": version,
        "endpoint": endpoint,
        "status": status,
        "body": body,
        "elapsed": elapsed,
    }


def request_move_direct(version: str, fen: str) -> dict:
    body, status = timed_engine_response(version, fen)
    return {
        "version": version,
        "endpoint": f"direct:{version.lower()}",
        "status": status,
        "body": body,
        "elapsed": metric_value(body, "processing_time") or 0.0,
    }


def request_move(base_url: str, version: str, fen: str, timeout: float, transport: str) -> dict:
    if transport == "direct":
        return request_move_direct(version, fen)
    return request_move_http(base_url, version, fen, timeout)


def run_single_request(base_url: str, version: str, fen: str, timeout: float) -> int:
    result = request_move_http(base_url, version, fen, timeout)

    print(f"Endpoint: {result['endpoint']}")
    print(f"HTTP status: {result['status']}")
    print(f"Round-trip time: {result['elapsed']:.3f}s")
    print(json.dumps(result["body"], indent=2, sort_keys=True))

    return 0 if result["status"] < 400 else 1


def run_benchmark(base_url: str, version: str, fen: str, timeout: float, requests: int, concurrency: int) -> int:
    endpoint = resolve_endpoint(version)

    latencies = []
    status_counts: dict[int, int] = {}
    error_payloads = []

    started_at = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(post_move_request, base_url, endpoint, fen, timeout)
            for _ in range(requests)
        ]

        for future in as_completed(futures):
            try:
                status, body, elapsed = future.result()
            except Exception as exc:  # pragma: no cover
                error_payloads.append({"error": str(exc)})
                continue

            latencies.append(elapsed)
            status_counts[status] = status_counts.get(status, 0) + 1
            if status >= 400:
                error_payloads.append(body)

    total_elapsed = time.perf_counter() - started_at
    completed = sum(status_counts.values())
    success_count = sum(count for status, count in status_counts.items() if status < 400)

    print(f"Endpoint: {endpoint}")
    print(f"Requests: {requests}")
    print(f"Concurrency: {concurrency}")
    print(f"Completed: {completed}")
    print(f"Successful: {success_count}")
    print(f"Status counts: {json.dumps(status_counts, sort_keys=True)}")

    if latencies:
        average_latency = sum(latencies) / len(latencies)
        print(f"Average round-trip time: {average_latency:.3f}s")
        print(f"Min round-trip time: {min(latencies):.3f}s")
        print(f"Max round-trip time: {max(latencies):.3f}s")
        print(f"Approx requests/sec: {completed / total_elapsed:.2f}")

    if error_payloads:
        print("Sample errors:")
        for payload in error_payloads[:3]:
            print(json.dumps(payload, indent=2, sort_keys=True))

    return 0 if success_count == requests else 1


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def version_slug(version: str) -> str:
    return version.lower().replace(".", "_")


def matchup_slug(white_version: str, black_version: str) -> str:
    return f"{version_slug(white_version)}_vs_{version_slug(black_version)}"


def ensure_directory(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class TeeWriter(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase):
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            try:
                stream.write(data)
            except ValueError:
                continue
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            try:
                stream.flush()
            except ValueError:
                continue


def load_opening_fens(openings_file: str | None, fallback_fen: str) -> list[str]:
    if not openings_file:
        chess.Board(fallback_fen)
        return [fallback_fen]

    openings: list[str] = []
    with open(openings_file, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                chess.Board(line)
            except ValueError as exc:
                raise ValueError(f"Invalid FEN in {openings_file} line {line_number}: {exc}") from exc
            openings.append(line)

    if not openings:
        raise ValueError(f"No usable FEN entries found in {openings_file}")

    return openings


def append_csv_row(path: str, fieldnames: list[str], row: dict) -> None:
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def metric_value(body: dict, key: str):
    value = body.get(key)
    return value if isinstance(value, (int, float)) else None


def build_engine_stats(version: str) -> dict:
    return {
        "version": version,
        "moves": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "timeouts": 0,
        "http_errors": 0,
        "invalid_moves": 0,
        "latency_total": 0.0,
        "processing_time_total": 0.0,
        "moves_evaluated_total": 0,
    }


def extract_result_label(result: str) -> tuple[str, str]:
    if result == "1-0":
        return "white", "win"
    if result == "0-1":
        return "black", "win"
    return "none", "draw"


def simulate_game(
    base_url: str,
    white_version: str,
    black_version: str,
    opening_fen: str,
    timeout: float,
    max_plies: int,
    transport: str,
    run_id: str,
    game_index: int,
) -> dict:
    board = chess.Board(opening_fen)
    started_at = time.perf_counter()
    white_stats = build_engine_stats(white_version)
    black_stats = build_engine_stats(black_version)
    move_number = 0
    termination_reason = ""
    failure_side = ""
    failure_version = ""
    failure_status = None
    move_records = []

    move_fieldnames = [
        "run_id",
        "game_id",
        "game_index",
        "ply",
        "fullmove_number",
        "turn",
        "version",
        "endpoint",
        "san",
        "uci",
        "fen_before",
        "fen_after",
        "http_status",
        "round_trip_seconds",
        "processing_time_seconds",
        "moves_evaluated",
    ]

    while not board.is_game_over() and move_number < max_plies:
        turn = "white" if board.turn == chess.WHITE else "black"
        version = white_version if board.turn == chess.WHITE else black_version
        active_stats = white_stats if board.turn == chess.WHITE else black_stats
        fen_before = board.fen()

        try:
            result = request_move(base_url, version, fen_before, timeout, transport)
        except urllib.error.URLError as exc:
            termination_reason = f"url_error:{exc.reason}"
            failure_side = turn
            failure_version = version
            active_stats["http_errors"] += 1
            failure_status = 0
            break

        body = result["body"]
        status = result["status"]
        elapsed = result["elapsed"]

        active_stats["moves"] += 1
        active_stats["latency_total"] += elapsed

        processing_time = metric_value(body, "processing_time")
        if processing_time is not None:
            active_stats["processing_time_total"] += processing_time

        moves_evaluated = metric_value(body, "moves_evaluated")
        if moves_evaluated is not None:
            active_stats["moves_evaluated_total"] += int(moves_evaluated)

        if status >= 400:
            termination_reason = "http_error"
            failure_side = turn
            failure_version = version
            active_stats["http_errors"] += 1
            if status == 408:
                active_stats["timeouts"] += 1
            failure_status = status
            break

        san_move = body.get("move")
        if not isinstance(san_move, str):
            termination_reason = "missing_move"
            failure_side = turn
            failure_version = version
            active_stats["invalid_moves"] += 1
            failure_status = status
            break

        try:
            move = board.parse_san(san_move)
        except ValueError:
            termination_reason = "invalid_san"
            failure_side = turn
            failure_version = version
            active_stats["invalid_moves"] += 1
            failure_status = status
            break

        uci_move = move.uci()
        board.push(move)
        move_number += 1

        move_records.append(
            {
                "run_id": run_id,
                "game_id": f"{run_id}_g{game_index:04d}",
                "game_index": game_index,
                "ply": move_number,
                "fullmove_number": board.fullmove_number,
                "turn": turn,
                "version": version,
                "endpoint": result["endpoint"],
                "san": san_move,
                "uci": uci_move,
                "fen_before": fen_before,
                "fen_after": board.fen(),
                "http_status": status,
                "round_trip_seconds": f"{elapsed:.6f}",
                "processing_time_seconds": "" if processing_time is None else f"{processing_time:.6f}",
                "moves_evaluated": "" if moves_evaluated is None else int(moves_evaluated),
            }
        )

    if not termination_reason:
        if board.is_game_over():
            outcome = board.outcome(claim_draw=True)
            termination_reason = outcome.termination.name.lower() if outcome else "game_over"
        else:
            termination_reason = "max_plies"

    if board.is_game_over():
        result_text = board.result(claim_draw=True)
    elif failure_side == "white":
        result_text = "0-1"
    elif failure_side == "black":
        result_text = "1-0"
    else:
        result_text = "1/2-1/2"

    winner_side, outcome_label = extract_result_label(result_text)

    if winner_side == "white":
        white_stats["wins"] += 1
        black_stats["losses"] += 1
    elif winner_side == "black":
        black_stats["wins"] += 1
        white_stats["losses"] += 1
    else:
        white_stats["draws"] += 1
        black_stats["draws"] += 1

    game_duration = time.perf_counter() - started_at
    game_record = {
        "run_id": run_id,
        "game_id": f"{run_id}_g{game_index:04d}",
        "game_index": game_index,
        "white_version": white_version,
        "black_version": black_version,
        "matchup": matchup_slug(white_version, black_version),
        "opening_fen": opening_fen,
        "result": result_text,
        "winner_side": winner_side,
        "outcome": outcome_label,
        "termination_reason": termination_reason,
        "failure_side": failure_side,
        "failure_version": failure_version,
        "failure_status": "" if failure_status is None else failure_status,
        "plies": move_number,
        "game_duration_seconds": f"{game_duration:.6f}",
        "white_moves": white_stats["moves"],
        "black_moves": black_stats["moves"],
        "white_avg_round_trip_seconds": f"{(white_stats['latency_total'] / white_stats['moves']) if white_stats['moves'] else 0.0:.6f}",
        "black_avg_round_trip_seconds": f"{(black_stats['latency_total'] / black_stats['moves']) if black_stats['moves'] else 0.0:.6f}",
        "white_avg_processing_time_seconds": f"{(white_stats['processing_time_total'] / white_stats['moves']) if white_stats['moves'] else 0.0:.6f}",
        "black_avg_processing_time_seconds": f"{(black_stats['processing_time_total'] / black_stats['moves']) if black_stats['moves'] else 0.0:.6f}",
        "white_avg_moves_evaluated": f"{(white_stats['moves_evaluated_total'] / white_stats['moves']) if white_stats['moves'] else 0.0:.2f}",
        "black_avg_moves_evaluated": f"{(black_stats['moves_evaluated_total'] / black_stats['moves']) if black_stats['moves'] else 0.0:.2f}",
    }

    return {
        "game_record": game_record,
        "white_stats": white_stats,
        "black_stats": black_stats,
        "move_fieldnames": move_fieldnames,
        "move_records": move_records,
    }


def write_game_result(result: dict, games_csv: str, moves_csv: str) -> None:
    for move_record in result["move_records"]:
        append_csv_row(moves_csv, result["move_fieldnames"], move_record)
    append_csv_row(games_csv, list(result["game_record"].keys()), result["game_record"])


def simulate_game_worker(task: dict) -> dict:
    return simulate_game(
        base_url=task["base_url"],
        white_version=task["white_version"],
        black_version=task["black_version"],
        opening_fen=task["opening_fen"],
        timeout=task["timeout"],
        max_plies=task["max_plies"],
        transport=task["transport"],
        run_id=task["run_id"],
        game_index=task["game_index"],
    )


def summarize_matchup(run_id: str, matchup: str, results: list[dict], summary_csv: str) -> None:
    games = len(results)
    white_wins = sum(1 for item in results if item["game_record"]["result"] == "1-0")
    black_wins = sum(1 for item in results if item["game_record"]["result"] == "0-1")
    draws = sum(1 for item in results if item["game_record"]["result"] == "1/2-1/2")
    plies_total = sum(item["game_record"]["plies"] for item in results)
    duration_total = sum(float(item["game_record"]["game_duration_seconds"]) for item in results)

    white_version = results[0]["game_record"]["white_version"]
    black_version = results[0]["game_record"]["black_version"]

    white_moves = sum(item["white_stats"]["moves"] for item in results)
    black_moves = sum(item["black_stats"]["moves"] for item in results)
    white_latency_total = sum(item["white_stats"]["latency_total"] for item in results)
    black_latency_total = sum(item["black_stats"]["latency_total"] for item in results)
    white_processing_total = sum(item["white_stats"]["processing_time_total"] for item in results)
    black_processing_total = sum(item["black_stats"]["processing_time_total"] for item in results)
    white_moves_evaluated_total = sum(item["white_stats"]["moves_evaluated_total"] for item in results)
    black_moves_evaluated_total = sum(item["black_stats"]["moves_evaluated_total"] for item in results)
    white_errors = sum(item["white_stats"]["http_errors"] + item["white_stats"]["invalid_moves"] for item in results)
    black_errors = sum(item["black_stats"]["http_errors"] + item["black_stats"]["invalid_moves"] for item in results)

    summary_record = {
        "run_id": run_id,
        "matchup": matchup,
        "games": games,
        "white_version": white_version,
        "black_version": black_version,
        "white_wins": white_wins,
        "black_wins": black_wins,
        "draws": draws,
        "white_score": f"{white_wins + 0.5 * draws:.1f}",
        "black_score": f"{black_wins + 0.5 * draws:.1f}",
        "avg_plies": f"{(plies_total / games) if games else 0.0:.2f}",
        "avg_game_duration_seconds": f"{(duration_total / games) if games else 0.0:.6f}",
        "white_avg_round_trip_seconds": f"{(white_latency_total / white_moves) if white_moves else 0.0:.6f}",
        "black_avg_round_trip_seconds": f"{(black_latency_total / black_moves) if black_moves else 0.0:.6f}",
        "white_avg_processing_time_seconds": f"{(white_processing_total / white_moves) if white_moves else 0.0:.6f}",
        "black_avg_processing_time_seconds": f"{(black_processing_total / black_moves) if black_moves else 0.0:.6f}",
        "white_avg_moves_evaluated": f"{(white_moves_evaluated_total / white_moves) if white_moves else 0.0:.2f}",
        "black_avg_moves_evaluated": f"{(black_moves_evaluated_total / black_moves) if black_moves else 0.0:.2f}",
        "white_errors": white_errors,
        "black_errors": black_errors,
    }

    append_csv_row(summary_csv, list(summary_record.keys()), summary_record)


def run_simulation(
    base_url: str,
    versions: list[str],
    timeout: float,
    games_per_pair: int,
    max_plies: int,
    output_dir: str,
    opening_fen: str,
    openings_file: str | None,
    transport: str,
    workers: int,
) -> int:
    if len(versions) < 2:
        raise ValueError("--versions requires at least two engine versions")
    if games_per_pair < 1:
        raise ValueError("--games-per-pair must be at least 1")
    if max_plies < 1:
        raise ValueError("--max-plies must be at least 1")
    if workers < 1:
        raise ValueError("--workers must be at least 1")
    if transport not in {"direct", "http"}:
        raise ValueError("--simulation-transport must be 'direct' or 'http'")

    ensure_directory(output_dir)
    opening_fens = load_opening_fens(openings_file, opening_fen)
    run_id = timestamp_slug()
    games_csv = os.path.join(output_dir, f"{run_id}_games.csv")
    moves_csv = os.path.join(output_dir, f"{run_id}_moves.csv")
    summary_csv = os.path.join(output_dir, f"{run_id}_summary.csv")
    output_txt = os.path.join(output_dir, f"{run_id}_output.txt")

    all_matchups: list[tuple[str, str]] = []
    for index, white_version in enumerate(versions):
        for black_version in versions[index + 1:]:
            all_matchups.append((white_version, black_version))
            all_matchups.append((black_version, white_version))

    total_games = len(all_matchups) * games_per_pair
    game_counter = 0
    tasks = []
    for white_version, black_version in all_matchups:
        matchup = matchup_slug(white_version, black_version)
        for pairing_game_index in range(games_per_pair):
            game_counter += 1
            opening_index = pairing_game_index % len(opening_fens)
            tasks.append(
                {
                    "base_url": base_url,
                    "white_version": white_version,
                    "black_version": black_version,
                    "opening_fen": opening_fens[opening_index],
                    "timeout": timeout,
                    "max_plies": max_plies,
                    "transport": transport,
                    "run_id": run_id,
                    "game_index": game_counter,
                    "opening_index": opening_index,
                    "opening_count": len(opening_fens),
                    "matchup": matchup,
                }
            )
    results_by_matchup: dict[str, list[dict]] = defaultdict(list)

    with open(output_txt, "w", encoding="utf-8") as output_handle:
        tee_stdout = TeeWriter(sys.stdout, output_handle)
        tee_stderr = TeeWriter(sys.stderr, output_handle)
        with redirect_stdout(tee_stdout), redirect_stderr(tee_stderr):
            print(f"Simulation transport: {transport}", flush=True)
            print(f"Simulation workers: {workers}", flush=True)

            if transport == "direct" and workers > 1:
                mp_context = multiprocessing.get_context("fork")
                with ProcessPoolExecutor(max_workers=workers, mp_context=mp_context) as executor:
                    future_to_task = {
                        executor.submit(simulate_game_worker, task): task
                        for task in tasks
                    }
                    for future in as_completed(future_to_task):
                        task = future_to_task[future]
                        result = future.result()
                        write_game_result(result, games_csv, moves_csv)
                        results_by_matchup[task["matchup"]].append(result)
                        game_record = result["game_record"]
                        print(
                            f"[{task['game_index']}/{total_games}] {task['white_version']} vs {task['black_version']} "
                            f"=> {game_record['result']} ({game_record['termination_reason']}, {game_record['plies']} plies, "
                            f"{game_record['game_duration_seconds']}s, opening {task['opening_index'] + 1}/{task['opening_count']})",
                            flush=True,
                        )
            else:
                for task in tasks:
                    result = simulate_game_worker(task)
                    write_game_result(result, games_csv, moves_csv)
                    results_by_matchup[task["matchup"]].append(result)
                    game_record = result["game_record"]
                    print(
                        f"[{task['game_index']}/{total_games}] {task['white_version']} vs {task['black_version']} "
                        f"=> {game_record['result']} ({game_record['termination_reason']}, {game_record['plies']} plies, "
                        f"{game_record['game_duration_seconds']}s, opening {task['opening_index'] + 1}/{task['opening_count']})",
                        flush=True,
                    )

            for matchup, matchup_results in results_by_matchup.items():
                summarize_matchup(run_id, matchup, matchup_results, summary_csv)
            print(f"Run ID: {run_id}", flush=True)
            print(f"Games CSV: {games_csv}", flush=True)
            print(f"Moves CSV: {moves_csv}", flush=True)
            print(f"Summary CSV: {summary_csv}", flush=True)
            print(f"Output TXT: {output_txt}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Legacy local runner for simulation and HTTP testing paths kept outside the active experiment workflow."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for the local or deployed backend.")
    parser.add_argument("--version", default="v0", help="Bot version to call for single or bench mode.")
    parser.add_argument("--fen", default=DEFAULT_FEN, help="FEN string to send to the backend.")
    parser.add_argument("--timeout", type=float, default=35.0, help="HTTP timeout in seconds for each request.")
    parser.add_argument(
        "--mode",
        choices=("single", "bench", "simulate"),
        default="simulate",
        help="Use 'single' for one request, 'bench' for repeated HTTP requests, or 'simulate' for historical engine matchups.",
    )
    parser.add_argument("--requests", type=int, default=10, help="Number of requests to send in bench mode.")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers in bench mode.")
    parser.add_argument(
        "--versions",
        nargs="+",
        default=["v1", "v1.1", "v1.2"],
        help="Historical engine versions to include in simulate mode.",
    )
    parser.add_argument("--games-per-pair", type=int, default=2, help="Number of games to run for each ordered version pairing.")
    parser.add_argument("--max-plies", type=int, default=200, help="Maximum number of plies before a game is recorded as a draw.")
    parser.add_argument("--output-dir", default="results", help="Directory where simulate mode writes CSV output.")
    parser.add_argument("--openings-file", help="Optional text file of starting FENs for simulate mode.")
    parser.add_argument(
        "--simulation-transport",
        choices=("direct", "http"),
        default="direct",
        help="Use direct in-process engine calls for simulation, or http to exercise the Flask path.",
    )
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes for direct simulate mode.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.requests < 1:
        parser.error("--requests must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    try:
        if args.mode == "single":
            return run_single_request(args.base_url, args.version, args.fen, args.timeout)
        if args.mode == "simulate":
            return run_simulation(
                base_url=args.base_url,
                versions=args.versions,
                timeout=args.timeout,
                games_per_pair=args.games_per_pair,
                max_plies=args.max_plies,
                output_dir=args.output_dir,
                opening_fen=args.fen,
                openings_file=args.openings_file,
                transport=args.simulation_transport,
                workers=args.workers,
            )
        return run_benchmark(
            args.base_url,
            args.version,
            args.fen,
            args.timeout,
            args.requests,
            args.concurrency,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"Failed to reach backend: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

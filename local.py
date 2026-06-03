import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


DEFAULT_BASE_URL = "http://localhost:3000"
DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# These aliases let the local CLI stay convenient while still hitting the
# exact versioned HTTP routes that the deployed frontend uses.
VERSION_TO_PATH = {
    "0": "/chess_v0",
    "v0": "/chess_v0",
    "1": "/chess_v1",
    "v1": "/chess_v1",
    "1.1": "/chess_v1-1",
    "v1.1": "/chess_v1-1",
    "1.2": "/chess_v1-2",
    "v1.2": "/chess_v1-2",
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


def run_single_request(base_url: str, version: str, fen: str, timeout: float) -> int:
    endpoint = resolve_endpoint(version)
    status, body, elapsed = post_move_request(base_url, endpoint, fen, timeout)

    print(f"Endpoint: {endpoint}")
    print(f"HTTP status: {status}")
    print(f"Round-trip time: {elapsed:.3f}s")
    print(json.dumps(body, indent=2, sort_keys=True))

    return 0 if status < 400 else 1


def run_benchmark(base_url: str, version: str, fen: str, timeout: float, requests: int, concurrency: int) -> int:
    endpoint = resolve_endpoint(version)

    # This benchmark intentionally measures the HTTP surface, not just the
    # search function. That keeps local testing aligned with how the frontend
    # will actually call the backend.
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
            except Exception as exc:  # pragma: no cover - defensive CLI error handling
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local HTTP client for testing the chess Flask backend through the same endpoints used in deployment."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for the local or deployed backend.")
    parser.add_argument("--version", default="v1.2", help="Bot version to call, for example v0, v1, v1.1, or v1.2.")
    parser.add_argument("--fen", default=DEFAULT_FEN, help="FEN string to send to the endpoint.")
    parser.add_argument("--timeout", type=float, default=35.0, help="HTTP timeout in seconds for each request.")
    parser.add_argument(
        "--mode",
        choices=("single", "bench"),
        default="single",
        help="Use 'single' for one request or 'bench' for repeated concurrent requests.",
    )
    parser.add_argument("--requests", type=int, default=10, help="Number of requests to send in bench mode.")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent workers in bench mode.")
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

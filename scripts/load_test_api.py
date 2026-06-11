#!/usr/bin/env python3
"""Simple API load test for the graduation credit verification backend.

This script uses only Python standard library modules so it can run without
installing extra packages. It logs in with a demo account, then repeatedly hits
read-only API endpoints that exercise FastAPI, SQLAlchemy ORM, and MySQL.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable


DEFAULT_BACKEND_URL = "https://backend-production-fe197.up.railway.app"
DEFAULT_FRONTEND_URL = "https://frontend-production-1ced.up.railway.app/#/login"
DEFAULT_USERNAME = "111001001"
DEFAULT_PASSWORD = "password123"


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: str
    path: str
    needs_auth: bool = False
    weight: int = 1


@dataclass
class Result:
    endpoint: str
    status: int
    elapsed_ms: float
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class FrontendTarget:
    name: str
    url: str
    weight: int = 1


ENDPOINTS: tuple[Endpoint, ...] = (
    Endpoint("health", "GET", "/", False, 1),
    Endpoint("student_detail", "GET", f"/students/{DEFAULT_USERNAME}", False, 2),
    Endpoint("credit_check_me", "GET", "/credit-check/me", True, 3),
    Endpoint("credit_summary_me", "GET", "/credit-check/me/summary", True, 2),
    Endpoint("records_me", "GET", "/student-course-records/me", True, 3),
    Endpoint("courses", "GET", "/courses/", False, 2),
    Endpoint("course_categories", "GET", "/course-categories/", False, 1),
    Endpoint("course_category_mappings", "GET", "/course-category-mappings/", False, 1),
)


class FrontendAssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): value for name, value in attrs if value}
        if tag in {"script", "img", "iframe"} and "src" in attrs_dict:
            self.urls.append(attrs_dict["src"])
        if tag == "link" and "href" in attrs_dict:
            rel = attrs_dict.get("rel", "")
            if any(item in rel for item in ("stylesheet", "icon", "preload", "modulepreload")):
                self.urls.append(attrs_dict["href"])


print_lock = threading.Lock()


def normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil((pct / 100) * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def request(
    base_url: str,
    method: str,
    path: str,
    token: str | None = None,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, bytes, float]:
    url = base_url + path
    headers = {"User-Agent": "graduation-credit-load-test/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type

    started = time.perf_counter()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            elapsed_ms = (time.perf_counter() - started) * 1000
            return response.status, body, elapsed_ms
    except urllib.error.HTTPError as exc:
        body = exc.read()
        elapsed_ms = (time.perf_counter() - started) * 1000
        return exc.code, body, elapsed_ms


def login(base_url: str, username: str, password: str, timeout: float) -> str:
    form = urllib.parse.urlencode({"username": username, "password": password}).encode()
    status, body, _elapsed = request(
        base_url=base_url,
        method="POST",
        path="/auth/login",
        data=form,
        content_type="application/x-www-form-urlencoded",
        timeout=timeout,
    )
    if status != 200:
        raise RuntimeError(f"login failed: HTTP {status}, body={body[:300]!r}")

    payload = json.loads(body.decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"login response did not include access_token: {payload!r}")
    return token


def run_once(base_url: str, endpoint: Endpoint, token: str, timeout: float) -> Result:
    started_endpoint = endpoint.name
    started = time.perf_counter()
    try:
        status, body, elapsed_ms = request(
            base_url=base_url,
            method=endpoint.method,
            path=endpoint.path,
            token=token if endpoint.needs_auth else None,
            timeout=timeout,
        )
        ok = 200 <= status < 400
        error = "" if ok else body[:200].decode("utf-8", errors="replace")
        return Result(started_endpoint, status, elapsed_ms, ok, error)
    except Exception as exc:  # noqa: BLE001 - keep load test resilient.
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Result(started_endpoint, 0, elapsed_ms, False, repr(exc))


def worker(
    worker_id: int,
    base_url: str,
    username: str,
    password: str,
    duration: float,
    timeout: float,
    think_time: float,
    endpoints: tuple[Endpoint, ...],
    shared_token: str | None,
    login_stagger: float,
) -> list[Result]:
    results: list[Result] = []
    token = shared_token
    if token is None:
        if login_stagger > 0:
            time.sleep(random.uniform(0, login_stagger))
        login_started = time.perf_counter()
        try:
            token = login(base_url, username, password, timeout)
            results.append(Result("auth_login", 200, (time.perf_counter() - login_started) * 1000, True))
        except Exception as exc:  # noqa: BLE001 - login failures are load-test results.
            elapsed_ms = (time.perf_counter() - login_started) * 1000
            results.append(Result("auth_login", 0, elapsed_ms, False, repr(exc)))
            with print_lock:
                print(f"worker {worker_id} login failed")
            return results
    choices: list[Endpoint] = []
    for endpoint in endpoints:
        choices.extend([endpoint] * endpoint.weight)

    end_at = time.monotonic() + duration
    while time.monotonic() < end_at:
        endpoint = random.choice(choices)
        results.append(run_once(base_url, endpoint, token, timeout))
        if think_time > 0:
            time.sleep(think_time)

    with print_lock:
        print(f"worker {worker_id} finished: {len(results)} requests")
    return results


def request_absolute_url(url: str, timeout: float) -> tuple[int, bytes, float]:
    parsed = urllib.parse.urlsplit(url)
    base_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    return request(base_url, "GET", path, timeout=timeout)


def run_frontend_once(target: FrontendTarget, timeout: float) -> Result:
    started = time.perf_counter()
    try:
        status, body, elapsed_ms = request_absolute_url(target.url, timeout)
        ok = 200 <= status < 400
        if target.name == "frontend_page":
            ok = ok and b"root" in body[:5000]
        error = "" if ok else body[:200].decode("utf-8", errors="replace")
        return Result(target.name, status, elapsed_ms, ok, error)
    except Exception as exc:  # noqa: BLE001 - keep load test resilient.
        elapsed_ms = (time.perf_counter() - started) * 1000
        return Result(target.name, 0, elapsed_ms, False, repr(exc))


def frontend_worker(
    worker_id: int,
    duration: float,
    timeout: float,
    think_time: float,
    targets: tuple[FrontendTarget, ...],
) -> list[Result]:
    results: list[Result] = []
    choices: list[FrontendTarget] = []
    for target in targets:
        choices.extend([target] * target.weight)

    end_at = time.monotonic() + duration
    while time.monotonic() < end_at:
        target = random.choice(choices)
        results.append(run_frontend_once(target, timeout))
        if think_time > 0:
            time.sleep(think_time)

    with print_lock:
        print(f"frontend worker {worker_id} finished: {len(results)} requests")
    return results


def check_frontend(frontend_url: str, timeout: float) -> Result:
    base_url, path = split_frontend_url(frontend_url)
    try:
        status, body, elapsed_ms = request(base_url, "GET", path, timeout=timeout)
        ok = status == 200 and b"root" in body[:5000]
        return Result("frontend_login_page", status, elapsed_ms, ok)
    except Exception as exc:  # noqa: BLE001
        return Result("frontend_login_page", 0, 0.0, False, repr(exc))


def split_frontend_url(frontend_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(frontend_url)
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    base_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return normalize_base_url(base_url), path


def discover_frontend_targets(frontend_url: str, timeout: float) -> tuple[FrontendTarget, ...]:
    base_url, path = split_frontend_url(frontend_url)
    page_url = base_url + path
    targets = [FrontendTarget("frontend_page", page_url, 5)]

    try:
        status, body, _elapsed_ms = request(base_url, "GET", path, timeout=timeout)
        if status != 200:
            return tuple(targets)

        parser = FrontendAssetParser()
        parser.feed(body[:500000].decode("utf-8", errors="ignore"))
        seen = {page_url}
        for index, asset_url in enumerate(parser.urls, start=1):
            absolute_url = urllib.parse.urljoin(page_url, asset_url)
            parsed_asset = urllib.parse.urlsplit(absolute_url)
            if parsed_asset.scheme not in {"http", "https"} or absolute_url in seen:
                continue
            seen.add(absolute_url)
            targets.append(FrontendTarget(f"frontend_asset_{index}", absolute_url, 1))
    except Exception:
        return tuple(targets)

    return tuple(targets)


def summarize(
    results: Iterable[Result],
    max_p95_ms: float | None = None,
    max_error_rate: float | None = None,
) -> int:
    all_results = list(results)
    total = len(all_results)
    ok_results = [result for result in all_results if result.ok]
    failed_results = [result for result in all_results if not result.ok]
    latencies = [result.elapsed_ms for result in all_results if result.elapsed_ms > 0]
    error_rate = (len(failed_results) / total) if total else 1.0
    overall_p95 = percentile(latencies, 95)

    print("\n=== Summary ===")
    print(f"total_requests: {total}")
    print(f"success: {len(ok_results)}")
    print(f"failed: {len(failed_results)}")
    print(f"error_rate: {error_rate:.4f}")
    if latencies:
        print(f"avg_ms: {statistics.mean(latencies):.2f}")
        print(f"p50_ms: {percentile(latencies, 50):.2f}")
        print(f"p95_ms: {overall_p95:.2f}")
        print(f"max_ms: {max(latencies):.2f}")

    print("\n=== By endpoint ===")
    for endpoint in sorted({result.endpoint for result in all_results}):
        endpoint_results = [result for result in all_results if result.endpoint == endpoint]
        endpoint_latencies = [result.elapsed_ms for result in endpoint_results if result.elapsed_ms > 0]
        failures = [result for result in endpoint_results if not result.ok]
        avg = statistics.mean(endpoint_latencies) if endpoint_latencies else 0.0
        p95 = percentile(endpoint_latencies, 95)
        print(
            f"{endpoint}: count={len(endpoint_results)} "
            f"failed={len(failures)} avg_ms={avg:.2f} p95_ms={p95:.2f}"
        )

    threshold_failed = False
    if max_p95_ms is not None:
        p95_passed = overall_p95 <= max_p95_ms
        threshold_failed = threshold_failed or not p95_passed
        print(f"\nthreshold_p95_ms: max={max_p95_ms:.2f} actual={overall_p95:.2f} passed={p95_passed}")
    if max_error_rate is not None:
        error_rate_passed = error_rate <= max_error_rate
        threshold_failed = threshold_failed or not error_rate_passed
        print(
            f"threshold_error_rate: max={max_error_rate:.4f} "
            f"actual={error_rate:.4f} passed={error_rate_passed}"
        )

    if failed_results:
        print("\n=== First failures ===")
        for result in failed_results[:10]:
            print(
                f"{result.endpoint}: status={result.status} "
                f"elapsed_ms={result.elapsed_ms:.2f} error={result.error[:200]}"
            )
        return 1

    return 1 if threshold_failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test the deployed frontend and backend.")
    parser.add_argument(
        "--target",
        choices=("backend", "frontend", "both"),
        default="backend",
        help="What to load test. Use frontend to repeatedly request the frontend app.",
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--users", type=int, default=5, help="Concurrent virtual users.")
    parser.add_argument("--duration", type=float, default=30.0, help="Test duration in seconds.")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds.")
    parser.add_argument("--think-time", type=float, default=0.2, help="Delay between requests per user.")
    parser.add_argument(
        "--auth-mode",
        choices=("shared", "per-user"),
        default="shared",
        help=(
            "shared logs in once before the test and reuses the token for API load testing; "
            "per-user makes every virtual user log in and is suitable for login stress testing."
        ),
    )
    parser.add_argument(
        "--login-stagger",
        type=float,
        default=0.0,
        help="Randomly spread per-user login attempts over this many seconds.",
    )
    parser.add_argument("--max-p95-ms", type=float, help="Fail if overall P95 latency is above this value.")
    parser.add_argument("--max-error-rate", type=float, help="Fail if failed request rate is above this value.")
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip the frontend login page availability check.",
    )
    args = parser.parse_args()

    if args.users < 1:
        raise SystemExit("--users must be at least 1")
    if args.duration <= 0:
        raise SystemExit("--duration must be greater than 0")

    backend_url = normalize_base_url(args.backend_url)
    print(f"target: {args.target}")
    print(f"backend_url: {backend_url}")
    print(f"frontend_url: {args.frontend_url}")
    print(f"users: {args.users}")
    print(f"duration_seconds: {args.duration}")
    print(f"auth_mode: {args.auth_mode}")

    all_results: list[Result] = []
    if args.target in {"backend", "both"} and not args.skip_frontend:
        frontend_result = check_frontend(args.frontend_url, args.timeout)
        print(
            f"frontend check: status={frontend_result.status} "
            f"ok={frontend_result.ok} elapsed_ms={frontend_result.elapsed_ms:.2f}"
        )

    if args.target in {"frontend", "both"}:
        frontend_targets = discover_frontend_targets(args.frontend_url, args.timeout)
        print(f"frontend targets discovered: {len(frontend_targets)}")
        with ThreadPoolExecutor(max_workers=args.users) as executor:
            futures = [
                executor.submit(
                    frontend_worker,
                    worker_id,
                    args.duration,
                    args.timeout,
                    args.think_time,
                    frontend_targets,
                )
                for worker_id in range(1, args.users + 1)
            ]
            for future in as_completed(futures):
                all_results.extend(future.result())

    if args.target in {"backend", "both"}:
        print("checking backend login...")
        shared_token = login(backend_url, args.username, args.password, args.timeout)
        print("login ok")
        if args.auth_mode == "per-user":
            shared_token = None

        with ThreadPoolExecutor(max_workers=args.users) as executor:
            futures = [
                executor.submit(
                    worker,
                    worker_id,
                    backend_url,
                    args.username,
                    args.password,
                    args.duration,
                    args.timeout,
                    args.think_time,
                    ENDPOINTS,
                    shared_token,
                    args.login_stagger,
                )
                for worker_id in range(1, args.users + 1)
            ]
            for future in as_completed(futures):
                all_results.extend(future.result())

    return summarize(
        all_results,
        max_p95_ms=args.max_p95_ms,
        max_error_rate=args.max_error_rate,
    )


if __name__ == "__main__":
    sys.exit(main())

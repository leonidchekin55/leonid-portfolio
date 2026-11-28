#!/usr/bin/env python3
"""Read-only availability and API contract checks for published portfolio demos."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

SERVICES = {
    "portfolio": (
        "https://leonid-portfolio.onrender.com",
        ("/", "/en.html", "/atlas-studio-demo.html", "/pulseboard.html", "/pulseboard-ui.js?v=5", "/ai-engineer-tour.html", "/assets/ai-engineer-portfolio-tour.srt", "/assets/ai-engineer-portfolio-tour.mp4"),
    ),
    "pulseboard": (
        "https://portfolio-pulseboard-demo.onrender.com",
        ("/health/live", "/health/ready", "/docs", "/openapi.json"),
    ),
    "knowledge": (
        "https://portfolio-knowledge-demo.onrender.com",
        ("/health/live", "/health/ready", "/docs", "/openapi.json", "/"),
    ),
    "ai_portfolio": (
        "https://leonid-ai-engineer-portfolio.onrender.com",
        ("/05-production/ready", "/sandbox", "/openapi.json"),
    ),
}
REQUIRED = {
    "pulseboard": {"/api/v1/demo/session", "/api/v1/demo/board", "/api/v1/demo/projects", "/api/v1/demo/tasks", "/api/v1/demo/reset"},
    "knowledge": {"/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/documents", "/api/v1/chat"},
}


TRANSIENT_HTTP = frozenset({502, 503, 504})
RETRY_DELAY = 3


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str
    render_routing: str = ""


def fetch(url: str) -> Response:
    request = urllib.request.Request(url, headers={"User-Agent": "portfolio-live-audit/1.0", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return Response(response.status, response.read(2_000_000), response.headers.get_content_type(),
                            response.headers.get("x-render-routing", ""))
    except urllib.error.HTTPError as error:
        with error:
            return Response(error.code, error.read(1000), error.headers.get_content_type(),
                            error.headers.get("x-render-routing", ""))


def is_render_suspended(base: str, response: Response) -> bool:
    host = urlsplit(base).hostname or ""
    return (host.endswith(".onrender.com") and response.status == 503
            and response.render_routing.strip().lower() == "suspend")


def check_payload(name: str, path: str, body: bytes) -> str | None:
    if path == "/05-production/ready":
        ready = json.loads(body)
        if not isinstance(ready, dict) or ready.get("status") != "ready" or ready.get("llm_mode") != "mock":
            return "expected readiness in zero-cost mock mode"
    if path == "/pulseboard-ui.js?v=5":
        if body.count(b"const memory") != 1 or b"window.sessionStorage" not in body:
            return "expected one script instance and tab-scoped tokens"
    if path == "/atlas-studio-demo.html":
        modules = sum(line.lstrip().startswith(b"['") for line in body.splitlines())
        if modules != 15 or b"localhost" in body or b"127.0.0.1" in body:
            return "expected 15 ATLAS modules and no local backend URLs"
    if path == "/openapi.json" and name in REQUIRED:
        spec = json.loads(body)
        routes = spec.get("paths") if isinstance(spec, dict) else None
        if not isinstance(routes, dict):
            return "expected an OpenAPI paths object"
        missing = REQUIRED[name] - routes.keys()
        if missing:
            return "missing OpenAPI demo routes: " + ", ".join(sorted(missing))
    return None


def audit_service(name: str, base: str, paths: tuple[str, ...]) -> list[tuple[str, str]]:
    rows = []
    suspended = False
    for path in paths:
        label = f"{name} {path}"
        if suspended:
            rows.append(("SKIP", f"{label}: host already confirmed suspended"))
            continue
        for attempt in range(2):
            try:
                response = fetch(base + path)
            except (OSError, urllib.error.URLError) as error:
                if attempt == 0:
                    time.sleep(RETRY_DELAY)
                    continue
                rows.append(("FAIL", f"{label}: network error ({type(error).__name__})"))
                break

            if is_render_suspended(base, response):
                suspended = True
                rows.append(("SUSPENDED", f"{label}: Render suspended this service (HTTP 503)"))
                break
            if response.status in TRANSIENT_HTTP and attempt == 0:
                time.sleep(RETRY_DELAY)
                continue
            if response.status != 200:
                rows.append(("FAIL", f"{label}: HTTP {response.status} ({response.content_type})"))
                break

            try:
                problem = check_payload(name, path, response.body)
            except (ValueError, UnicodeError):
                problem = "invalid JSON response"
            if problem:
                rows.append(("FAIL", f"{label}: {problem}"))
            else:
                detail = " after retry" if attempt else ""
                rows.append(("PASS", f"{label}: HTTP 200 ({response.content_type}){detail}"))
            break
    return rows


def main() -> int:
    # Probe independent public hosts concurrently. Report in configuration order for reproducible logs.
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(audit_service, name, base, paths) for name, (base, paths) in SERVICES.items()]
        rows = [row for job in jobs for row in job.result()]
    counts = dict.fromkeys(("PASS", "FAIL", "SUSPENDED", "SKIP"), 0)
    for status, message in rows:
        counts[status] += 1
        print(f"{status} {message}", flush=True)
    print("Summary: " + ", ".join(f"{key}={count}" for key, count in counts.items()), flush=True)
    return int(bool(counts["FAIL"] or counts["SUSPENDED"]))


if __name__ == "__main__":
    raise SystemExit(main())

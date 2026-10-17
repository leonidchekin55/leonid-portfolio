#!/usr/bin/env python3
"""Turn an owner-approved portfolio issue into a reviewable pull request."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_PATH = ROOT / "content" / "portfolio.json"
API = "https://api.github.com"
COMMAND = "/portfolio-update"
ALLOWED_PROJECT_FIELDS = {
    "slug", "title_ru", "title_en", "status_ru", "status_en", "role_ru", "role_en",
    "summary_ru", "summary_en", "tech", "links", "include_in_resume",
}
ALLOWED_RESUME_FIELDS = {"title", "text", "links"}


def validate_project(project: object) -> dict:
    if not isinstance(project, dict):
        raise ValueError("project must be a JSON object")
    if set(project) != ALLOWED_PROJECT_FIELDS:
        missing = sorted(ALLOWED_PROJECT_FIELDS - set(project))
        extra = sorted(set(project) - ALLOWED_PROJECT_FIELDS)
        raise ValueError(f"project fields mismatch (missing: {missing}; extra: {extra})")
    if not isinstance(project["slug"], str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", project["slug"]):
        raise ValueError("slug must contain lowercase letters, numbers, and hyphens")
    limits = {
        "title_ru": 200, "title_en": 200, "status_ru": 200, "status_en": 200,
        "role_ru": 1000, "role_en": 1000, "summary_ru": 4000, "summary_en": 4000, "tech": 400,
    }
    for field, limit in limits.items():
        value = project[field]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{field} must be a single line")
        if any(marker in value.casefold() for marker in ("заполнить", "описать", "fill in", "describe")):
            raise ValueError(f"{field} still contains a template placeholder")
    if not isinstance(project["include_in_resume"], bool):
        raise ValueError("include_in_resume must be true or false")
    links = project["links"]
    if not isinstance(links, list) or not links or len(links) > 12:
        raise ValueError("links must contain between 1 and 12 entries")
    for link in links:
        if not isinstance(link, dict) or set(link) != {"label_ru", "label_en", "url"}:
            raise ValueError("each link must have only label_ru, label_en, and url")
        if any(not isinstance(link[field], str) or not link[field].strip() or len(link[field]) > 120 for field in ("label_ru", "label_en")):
            raise ValueError("link labels must be non-empty strings")
        if not isinstance(link["url"], str) or len(link["url"]) > 2048 or not re.fullmatch(r"https://[^\s]+", link["url"]):
            raise ValueError("portfolio links must use HTTPS")
    return project


def parse_update(issue_body: str) -> dict:
    blocks = re.findall(r"```json\s*\n(.*?)\n```", issue_body, flags=re.DOTALL | re.IGNORECASE)
    if len(blocks) != 1:
        raise ValueError("issue body must contain exactly one ```json block")
    try:
        payload = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in issue body: {exc.msg}") from exc
    if not isinstance(payload, dict) or set(payload) != {"operation", "collection", "project"}:
        raise ValueError("JSON block must contain operation, collection, and project")
    if payload["operation"] not in {"add", "update"}:
        raise ValueError("operation must be add or update")
    if payload["collection"] == "new_projects":
        payload["project"] = validate_project(payload["project"])
    elif payload["collection"] == "resume_projects":
        if payload["operation"] != "update":
            raise ValueError("resume_projects supports updates only")
        payload["project"] = validate_resume_project(payload["project"])
    else:
        raise ValueError("collection must be new_projects or resume_projects")
    return payload


def validate_resume_project(project: object) -> dict:
    if not isinstance(project, dict) or set(project) != ALLOWED_RESUME_FIELDS:
        raise ValueError("resume project must contain only title, text, and links")
    for field, limit in (("title", 250), ("text", 5000)):
        if not isinstance(project[field], str) or not project[field].strip() or len(project[field]) > limit:
            raise ValueError(f"{field} must be a non-empty string of at most {limit} characters")
    links = project["links"]
    if not isinstance(links, list) or len(links) > 12:
        raise ValueError("links must be a list of at most 12 entries")
    for link in links:
        if not isinstance(link, dict) or set(link) != {"label", "url"}:
            raise ValueError("each resume link must have only label and url")
        if not isinstance(link["label"], str) or not link["label"].strip() or len(link["label"]) > 120:
            raise ValueError("resume link label must be a non-empty string")
        if not isinstance(link["url"], str) or len(link["url"]) > 2048 or not re.fullmatch(r"https://[^\s]+", link["url"]):
            raise ValueError("resume links must use HTTPS")
    return project


def apply_update(portfolio: dict, payload: dict) -> None:
    collection = payload["collection"]
    projects = portfolio.setdefault(collection, [])
    record = payload["project"]
    if collection == "resume_projects":
        matches = [index for index, project in enumerate(projects) if project.get("title") == record["title"]]
    else:
        matches = [index for index, project in enumerate(projects) if project.get("slug") == record["slug"]]
    if payload["operation"] == "add":
        if collection != "new_projects":
            raise ValueError("only new_projects entries can be added")
        if matches:
            raise ValueError(f"project slug already exists: {record['slug']}")
        projects.append(record)
        return
    if len(matches) != 1:
        identity = record.get("slug", record.get("title", "unknown"))
        raise ValueError(f"update requires exactly one existing {collection} entry: {identity}")
    projects[matches[0]] = record


def github_api(method: str, path: str, token: str, payload: dict | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} returned {exc.code}: {detail}") from exc


def create_pull_request(event: dict) -> str:
    issue = event.get("issue", {})
    comment = event.get("comment", {})
    if issue.get("pull_request"):
        raise ValueError("pull request comments cannot update portfolio data")
    if comment.get("author_association") != "OWNER" or comment.get("body", "").strip() != COMMAND:
        raise ValueError("only the repository owner can request this operation with /portfolio-update")
    if issue.get("state") != "open" or not isinstance(issue.get("number"), int):
        raise ValueError("source issue must be open")

    payload = parse_update(issue.get("body") or "")
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    issue_number = issue["number"]
    comment_id = comment.get("id")
    if not isinstance(comment_id, int):
        raise ValueError("GitHub event is missing the comment ID")
    open_pulls = github_api("GET", f"/repos/{quote(repository)}/pulls?state=open&per_page=100", token)
    issue_branch_prefix = f"codex/portfolio-update-issue-{issue_number}-"
    for existing in open_pulls:
        if existing.get("head", {}).get("ref", "").startswith(issue_branch_prefix):
            raise ValueError(f"an update pull request is already open: {existing['html_url']}; edit that pull request directly")

    portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    before = json.dumps(portfolio, ensure_ascii=False, sort_keys=True)
    apply_update(portfolio, payload)
    after = json.dumps(portfolio, ensure_ascii=False, sort_keys=True)
    if before == after:
        raise ValueError("portfolio update makes no changes")
    PORTFOLIO_PATH.write_text(json.dumps(portfolio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    branch = f"codex/portfolio-update-issue-{issue_number}-{comment_id}"

    subprocess.run([sys.executable, "scripts/build_portfolio.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], cwd=ROOT, check=True)
    subprocess.run(["npm", "run", "test:html"], cwd=ROOT, check=True)
    subprocess.run(["npm", "run", "test:links"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "checkout", "-b", branch], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "content/portfolio.json", "index.html", "en.html", "downloads/Leonid_Chekin_Resume_Python_AI_FinTech.pdf"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", f"Prepare portfolio update from issue #{issue_number}"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "--set-upstream", "origin", branch], cwd=ROOT, check=True)

    project = payload["project"]
    project_title = project.get("title_en") or project["title"]
    title = f"Review portfolio update from #{issue_number}: {project_title}"
    body = (
        f"Prepared from #{issue_number} after the repository owner requested `/portfolio-update`.\n\n"
        "Please verify the project facts and whether it belongs in the resume. Merging this PR refreshes the site and PDF; "
        "Google Docs sync runs when the configured connection is available.\n\n"
        f"Closes #{issue_number}"
    )
    pr = github_api(
        "POST",
        f"/repos/{quote(repository)}/pulls",
        token,
        {"title": title, "head": branch, "base": "main", "body": body, "draft": True},
    )
    return pr["html_url"]


def main() -> None:
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    event = json.loads(event_path.read_text(encoding="utf-8"))
    print(f"Created portfolio update pull request: {create_pull_request(event)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Portfolio update request failed: {exc}", file=sys.stderr)
        raise

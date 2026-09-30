#!/usr/bin/env python3
"""Create a review issue when a new public GitHub project is detected."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "content" / "github-project-discovery.json"
PORTFOLIO_PATH = ROOT / "content" / "portfolio.json"
API = "https://api.github.com"


def api(method: str, path: str, payload: dict | None = None) -> tuple[object, dict[str, str]]:
    token = os.environ["GITHUB_TOKEN"]
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        API + path,
        data=body,
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
            return json.loads(response.read()), dict(response.headers.items())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} returned {exc.code}: {detail}") from exc


def repository_names_in_portfolio() -> set[str]:
    portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    names: set[str] = set()
    for project in portfolio.get("resume_projects", []):
        for link in project.get("links", []):
            names.update(repository_names_from_url(link.get("url", "")))
    for project in portfolio.get("new_projects", []):
        for link in project.get("links", []):
            names.update(repository_names_from_url(link.get("url", "")))
    return names


def repository_names_from_url(url: str) -> set[str]:
    match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git)?(?:/|$)", url, re.IGNORECASE)
    return {match.group(1).lower()} if match else set()


def list_owned_repositories(owner: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        data, headers = api(
            "GET",
            f"/users/{quote(owner)}/repos?type=owner&sort=created&direction=desc&per_page=100&page={page}",
        )
        if not isinstance(data, list):
            raise RuntimeError("GitHub returned an unexpected repository list")
        items.extend(data)
        if len(data) < 100 or "next" not in headers.get("Link", ""):
            return items
        page += 1


def make_issue(repos: list[dict]) -> tuple[str, str]:
    rows = []
    ids = []
    for repo in repos:
        ids.append(str(repo["id"]))
        description = repo.get("description") or "Описание в GitHub не заполнено."
        language = repo.get("language") or "не указан"
        topics = ", ".join(repo.get("topics", [])) or "не указаны"
        created = repo["created_at"][:10]
        rows.append(
            f"### [{repo['full_name']}]({repo['html_url']})\n"
            f"- Создан: {created}\n- Описание GitHub: {description}\n"
            f"- Основной язык: {language}\n- Темы: {topics}\n"
            "- [ ] Добавить краткое описание проекта на русском и английском\n"
            "- [ ] Указать вашу роль и подтверждаемые результаты\n"
            "- [ ] Решить, включать ли проект в резюме\n"
        )
    title = f"Новые GitHub-проекты для портфолио ({len(repos)})"
    marker = ",".join(ids)
    body = (
        "Автоматическая проверка обнаружила новые публичные репозитории. "
        "Они пока не добавлены на сайт или в резюме, потому что GitHub не сообщает вашу роль, "
        "статус работы и результаты. Заполните пункты ниже, затем добавьте подтверждённые сведения в `content/portfolio.json`.\n\n"
        + "\n".join(rows)
        + "\nШаблон записи находится в [инструкции](../blob/main/docs/AUTOMATIC_UPDATES.md).\n\n"
        + f"<!-- discovered-repository-ids:{marker} -->"
    )
    return title, body


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    owner, current_repo = repository.split("/", 1)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    created_after = datetime.fromisoformat(state["created_after"].replace("Z", "+00:00"))
    seen = {str(item) for item in state.get("seen_repository_ids", [])}
    listed = repository_names_in_portfolio()
    candidates = []
    for repo in list_owned_repositories(owner):
        if repo["name"].lower() == current_repo.lower():
            continue
        if repo.get("fork") or repo.get("archived") or repo.get("is_template") or not repo.get("visibility", "public") == "public":
            continue
        repo_id = str(repo["id"])
        created = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
        if created <= created_after or repo_id in seen:
            continue
        if repo["full_name"].lower() in listed:
            seen.add(repo_id)
            continue
        candidates.append(repo)

    if candidates:
        title, body = make_issue(candidates)
        api("POST", f"/repos/{quote(owner)}/{quote(current_repo)}/issues", {"title": title, "body": body})
        seen.update(str(repo["id"]) for repo in candidates)
        print(f"Created a portfolio review issue for {len(candidates)} new public repositories.")
    else:
        print("No new public repositories need portfolio review.")

    updated_state = {
        "created_after": state["created_after"],
        "seen_repository_ids": sorted(seen, key=int),
    }
    if updated_state != state:
        STATE_PATH.write_text(json.dumps(updated_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"GitHub project discovery failed: {exc}", file=sys.stderr)
        raise

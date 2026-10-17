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


def project_records_by_repository() -> dict[str, dict]:
    portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    records = {}
    for project in portfolio.get("new_projects", []):
        for link in project.get("links", []):
            for name in repository_names_from_url(link.get("url", "")):
                records.setdefault(name, {"collection": "new_projects", "project": project})
    for project in portfolio.get("resume_projects", []):
        for link in project.get("links", []):
            for name in repository_names_from_url(link.get("url", "")):
                records.setdefault(name, {"collection": "resume_projects", "project": project})
    return records


def repository_names_from_url(url: str) -> set[str]:
    match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git)?(?:/|$)", url, re.IGNORECASE)
    return {match.group(1).lower()} if match else set()


def portfolio_template(repo_name: str, project_record: dict | None = None) -> dict:
    if project_record:
        collection = project_record["collection"]
        record = project_record["project"]
        operation = "update"
    else:
        collection = "new_projects"
        owner, name = repo_name.split("/", 1)
        record = {
            "slug": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
            "title_ru": "Заполнить название проекта",
            "title_en": "Fill in the project title",
            "status_ru": "Заполнить статус",
            "status_en": "Fill in the status",
            "role_ru": "Заполнить свою роль по фактам",
            "role_en": "Fill in your role using verified facts",
            "summary_ru": "Описать реализованные функции и ограничения проекта",
            "summary_en": "Describe implemented features and project limitations",
            "tech": "Заполнить подтверждённый стек",
            "links": [{"label_ru": "Исходный код", "label_en": "Source code", "url": f"https://github.com/{owner}/{name}"}],
            "include_in_resume": False,
        }
        operation = "add"
    return {"operation": operation, "collection": collection, "project": record}


def make_issue(repo: dict) -> tuple[str, str]:
    repo_name = repo["full_name"]
    data = {
        "repository": repo_name,
        "created": repo["created_at"][:10],
        "description": repo.get("description") or "Описание в GitHub не заполнено.",
        "language": repo.get("language") or "не указан",
        "topics": ", ".join(repo.get("topics", [])) or "не указаны",
    }
    payload = json.dumps(portfolio_template(repo_name), ensure_ascii=False, indent=2)
    title = f"Новая работа для портфолио: {repo_name}"
    body = (
        "GitHub обнаружил новый публичный репозиторий. Чтобы подготовить обновление, проверьте описание, "
        "свою роль, статус, результаты и включение в резюме. Затем замените пример ниже актуальной JSON-записью.\n\n"
        f"- Репозиторий: https://github.com/{data['repository']}\n"
        f"- Создан: {data['created']}\n- Описание: {data['description']}\n"
        f"- Язык: {data['language']}\n- Темы: {data['topics']}\n\n"
        "После проверки сведений оставьте комментарий `/portfolio-update`. Автоматизация проверит поля и создаст PR; "
        "публикация произойдёт только после просмотра и слияния PR.\n\n"
        "```json\n" + payload + "\n```\n\n"
        f"<!-- portfolio-repository:{repo_name.lower()} -->"
    )
    return title, body


def pushes_since(events: list[dict], previous_push: str) -> list[dict]:
    pushes = [
        event for event in events
        if event.get("type") == "PushEvent" and event.get("created_at", "") > previous_push
    ]
    return sorted(pushes, key=lambda event: event.get("created_at", ""))[-10:]


def make_activity_issue(repo: dict, project_record: dict | None, pushes: list[dict]) -> tuple[str, str]:
    repo_name = repo["full_name"]
    history_url = f"https://github.com/{repo_name}/activity"
    push_rows = []
    for event in pushes:
        payload = event.get("payload", {})
        ref = payload.get("ref", "")
        head = payload.get("head", "")
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", ref):
            continue
        if re.fullmatch(r"[a-f0-9]{7,40}", head, re.IGNORECASE):
            link = f"https://github.com/{repo_name}/commit/{head}"
            push_rows.append(f"- Ветка `{ref.removeprefix('refs/heads/')}`: {link}")
    recent_push_text = "\n".join(push_rows) if push_rows else f"- История активности: {history_url}"
    payload = json.dumps(portfolio_template(repo_name, project_record), ensure_ascii=False, indent=2)
    title = f"Обновление работы для портфолио: {repo_name}"
    body = (
        "Плановая проверка обнаружила новые изменения в публичном репозитории.\n\n"
        f"- Репозиторий: https://github.com/{repo_name}\n- Последнее обновление: {repo['pushed_at']}\n"
        f"Последние обнаруженные отправки:\n{recent_push_text}\n\n"
        "Проверьте, изменились ли функции, статус или подтверждённые результаты проекта. Если карточку нужно обновить, "
        "исправьте JSON ниже и оставьте комментарий `/portfolio-update`. Создастся проверяемый PR; сайт и резюме "
        "обновятся после его слияния. Если изменений для портфолио нет, закройте задачу без команды.\n\n"
        "```json\n" + payload + "\n```\n\n"
        f"<!-- portfolio-repository:{repo_name.lower()} -->"
    )
    return title, body


def has_new_push(repo_id: str, pushed_at: str, previous_pushes: dict[str, str]) -> bool:
    previous = previous_pushes.get(repo_id)
    return previous is not None and previous != pushed_at


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


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    owner, current_repo = repository.split("/", 1)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    original_state = json.dumps(state, sort_keys=True)
    created_after = datetime.fromisoformat(state["created_after"].replace("Z", "+00:00"))
    seen = {str(item) for item in state.get("seen_repository_ids", [])}
    listed = repository_names_in_portfolio()
    all_repositories = list_owned_repositories(owner)
    candidates = []
    for repo in all_repositories:
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
        for repo in candidates:
            title, body = make_issue(repo)
            api("POST", f"/repos/{quote(owner)}/{quote(current_repo)}/issues", {"title": title, "body": body})
        seen.update(str(repo["id"]) for repo in candidates)
        print(f"Created portfolio update issues for {len(candidates)} new public repositories.")
    else:
        print("No new public repositories need portfolio review.")

    activity_state = state.get("seen_repository_pushes", {})
    project_records = project_records_by_repository()
    open_issues, _ = api("GET", f"/repos/{quote(owner)}/{quote(current_repo)}/issues?state=open&per_page=100")
    if not isinstance(open_issues, list):
        raise RuntimeError("GitHub returned an unexpected issue list")
    repositories_with_open_issues = set()
    for issue in open_issues:
        if issue.get("pull_request"):
            continue
        body = issue.get("body") or ""
        repositories_with_open_issues.update(re.findall(r"<!-- portfolio-repository:([a-z0-9_.-]+/[a-z0-9_.-]+) -->", body, re.IGNORECASE))
        repositories_with_open_issues.update(
            f"{owner_name}/{repository_name}".lower()
            for owner_name, repository_name in re.findall(r"https?://github\.com/([^/\s`]+)/([^/\s`/?#]+)", body, re.IGNORECASE)
        )

    public_repositories = [
        repo for repo in all_repositories
        if repo["name"].lower() != current_repo.lower()
        and not repo.get("fork") and not repo.get("archived") and not repo.get("is_template")
        and repo.get("visibility", "public") == "public"
    ]
    known_repository_names = {repo["full_name"].lower() for repo in public_repositories}
    for repo_name in sorted(set(project_records) - known_repository_names):
        repo, _ = api("GET", f"/repos/{quote(repo_name)}")
        if not isinstance(repo, dict):
            raise RuntimeError(f"GitHub returned unexpected metadata for {repo_name}")
        if repo.get("visibility", "public") == "public" and not repo.get("archived") and not repo.get("fork") and not repo.get("is_template"):
            public_repositories.append(repo)
    for repo in public_repositories:
        repo_id = str(repo["id"])
        repo_name = repo["full_name"].lower()
        pushed_at = repo.get("pushed_at") or ""
        previous_push = activity_state.get(repo_id)
        if not pushed_at:
            continue
        if previous_push is None:
            activity_state[repo_id] = pushed_at
            continue
        if not has_new_push(repo_id, pushed_at, activity_state):
            continue
        if repo_name in repositories_with_open_issues:
            print(f"An open portfolio issue already covers {repo_name}; leaving its push checkpoint unchanged.")
            continue
        if repo_name in listed and repo_name not in project_records:
            activity_state[repo_id] = pushed_at
            continue
        events, _ = api("GET", f"/repos/{quote(repo_name)}/events?per_page=100")
        if not isinstance(events, list):
            raise RuntimeError(f"GitHub returned an unexpected event list for {repo_name}")
        pushes = pushes_since(events, previous_push)
        title, body = make_activity_issue(repo, project_records.get(repo_name), pushes)
        api("POST", f"/repos/{quote(owner)}/{quote(current_repo)}/issues", {"title": title, "body": body})
        repositories_with_open_issues.add(repo_name)
        print(f"Created an activity review issue for {repo_name}.")
        activity_state[repo_id] = pushed_at

    updated_state = {
        "created_after": state["created_after"],
        "seen_repository_ids": sorted(seen, key=int),
        "seen_repository_pushes": activity_state,
    }
    if json.dumps(updated_state, sort_keys=True) != original_state:
        STATE_PATH.write_text(json.dumps(updated_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"GitHub project discovery failed: {exc}", file=sys.stderr)
        raise

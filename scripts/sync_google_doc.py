#!/usr/bin/env python3
"""Sync the generated Russian resume into the configured native Google Doc."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "content" / "portfolio.json").read_text(encoding="utf-8"))
DOC_ID = os.environ["GOOGLE_RESUME_DOC_ID"]


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def paragraphs() -> list[dict]:
    resume = DATA["resume"]
    rows = [
        ("title", resume["name"]),
        ("subtitle", resume["title"]),
        ("contact", f'{resume["phone"]} · {resume["email"]} · Telegram: {resume["telegram"]}'),
        ("contact", f'{resume["location"]} · удалённая работа'),
        ("h1", "Профессиональный профиль"),
        ("body", resume["summary"]),
        ("h1", "Ключевые компетенции"),
        *(("bullet", item) for item in resume["competencies"]),
        ("h1", "Опыт"),
    ]
    for item in resume["experience"]:
        rows.extend([("h2", item["title"]), ("body", item["text"])])
    rows.append(("h1_page", "Избранные проекты"))
    projects = list(DATA["resume_projects"])
    projects.extend(
        {
            "title": project["title_ru"],
            "text": f'{project["role_ru"]} {project["summary_ru"]}',
            "links": [{"label": link["label_ru"], "url": link["url"]} for link in project["links"]],
        }
        for project in DATA["new_projects"] if project.get("include_in_resume", True)
    )
    for project in projects:
        rows.extend([("h2", project["title"]), ("body", project["text"])])
        if project.get("links"):
            rows.append(("links", " · ".join(f'{link["label"]}: {link["url"]}' for link in project["links"]), project["links"]))
    rows.extend([
        ("h1", "Образование и дополнительная информация"),
        ("body", f'Образование: {resume["education"]} Английский: {resume["english"]}'),
        ("body", f'Формат: {resume["work_format"]}'),
        ("links", f'Портфолио: {resume["portfolio_url"]} · Хабр Карьера: {resume["habr_url"]}', [
            {"label": "Портфолио", "url": resume["portfolio_url"]},
            {"label": "Хабр Карьера", "url": resume["habr_url"]},
        ]),
    ])
    offset = 1
    result = []
    for row in rows:
        kind, text, *extra = row
        start = offset
        offset += units(text) + 1
        result.append({"kind": kind, "text": text, "start": start, "end": offset, "links": extra[0] if extra else []})
    return result


def main() -> None:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/documents"])
    session = AuthorizedSession(credentials)
    endpoint = f"https://docs.googleapis.com/v1/documents/{quote(DOC_ID, safe='')}"
    response = session.get(endpoint, params={"includeTabsContent": "true"}, timeout=30)
    response.raise_for_status()
    document = response.json()
    tabs = document.get("tabs", [])
    tab = tabs[0] if tabs else None
    if tab:
        tab_id = tab["tabProperties"]["tabId"]
        content = tab["documentTab"]["body"]["content"]
    else:
        tab_id = None
        content = document["body"]["content"]
    end_index = max(item.get("endIndex", 1) for item in content)
    rows = paragraphs()
    text = "".join(row["text"] + "\n" for row in rows)
    length = units(text)
    location = {"index": 1}
    range_base = {"startIndex": 1, "endIndex": 1 + length}
    if tab_id:
        location["tabId"] = tab_id
        range_base["tabId"] = tab_id
    requests = []
    if end_index > 2:
        delete_range = {"startIndex": 1, "endIndex": end_index - 1}
        if tab_id:
            delete_range["tabId"] = tab_id
        requests.append({"deleteContentRange": {"range": delete_range}})
    requests.append({"insertText": {"location": location, "text": text}})
    requests.append({"updateTextStyle": {
        "range": range_base,
        "textStyle": {"weightedFontFamily": {"fontFamily": "Arial"}, "fontSize": {"magnitude": 10.5, "unit": "PT"}},
        "fields": "weightedFontFamily,fontSize",
    }})
    for row in rows:
        start, end = row["start"], row["end"]
        char_end = end - 1
        target_range = {"startIndex": start, "endIndex": end}
        text_range = {"startIndex": start, "endIndex": char_end}
        if tab_id:
            target_range["tabId"] = tab_id
            text_range["tabId"] = tab_id
        kind = row["kind"]
        if kind in ("h1", "h1_page"):
            style = {"namedStyleType": "HEADING_1", "spaceAbove": {"magnitude": 10, "unit": "PT"}, "spaceBelow": {"magnitude": 3, "unit": "PT"}, "keepWithNext": True}
            fields = "namedStyleType,spaceAbove,spaceBelow,keepWithNext"
            if kind == "h1_page":
                style["pageBreakBefore"] = True
                fields += ",pageBreakBefore"
            requests.append({"updateParagraphStyle": {"range": target_range, "paragraphStyle": style, "fields": fields}})
            requests.append({"updateTextStyle": {"range": text_range, "textStyle": {"bold": True, "fontSize": {"magnitude": 15, "unit": "PT"}}, "fields": "bold,fontSize"}})
        elif kind == "h2":
            requests.append({"updateParagraphStyle": {"range": target_range, "paragraphStyle": {"namedStyleType": "HEADING_2", "spaceAbove": {"magnitude": 6, "unit": "PT"}, "spaceBelow": {"magnitude": 2, "unit": "PT"}, "keepWithNext": True}, "fields": "namedStyleType,spaceAbove,spaceBelow,keepWithNext"}})
            requests.append({"updateTextStyle": {"range": text_range, "textStyle": {"bold": True, "fontSize": {"magnitude": 11.5, "unit": "PT"}}, "fields": "bold,fontSize"}})
        elif kind == "title":
            requests.append({"updateTextStyle": {"range": text_range, "textStyle": {"bold": True, "fontSize": {"magnitude": 23, "unit": "PT"}}, "fields": "bold,fontSize"}})
        elif kind == "subtitle":
            requests.append({"updateTextStyle": {"range": text_range, "textStyle": {"fontSize": {"magnitude": 12, "unit": "PT"}, "foregroundColor": {"color": {"rgbColor": {"red": .25, "green": .25, "blue": .25}}}}, "fields": "fontSize,foregroundColor"}})
        elif kind == "contact":
            requests.append({"updateTextStyle": {"range": text_range, "textStyle": {"fontSize": {"magnitude": 9.5, "unit": "PT"}, "foregroundColor": {"color": {"rgbColor": {"red": .25, "green": .25, "blue": .25}}}}, "fields": "fontSize,foregroundColor"}})
        if kind == "contact" and DATA["resume"]["email"] in row["text"]:
            email_start = start + units(row["text"].split(DATA["resume"]["email"], 1)[0])
            email_end = email_start + units(DATA["resume"]["email"])
            email_range = {"startIndex": email_start, "endIndex": email_end}
            if tab_id:
                email_range["tabId"] = tab_id
            requests.append({"updateTextStyle": {"range": email_range, "textStyle": {"link": {"url": f'mailto:{DATA["resume"]["email"]}'}}, "fields": "link"}})
        if kind == "links":
            for link in row["links"]:
                offset = row["text"].find(link["url"])
                link_start = start + units(row["text"][:offset])
                link_range = {"startIndex": link_start, "endIndex": link_start + units(link["url"])}
                if tab_id:
                    link_range["tabId"] = tab_id
                requests.append({"updateTextStyle": {"range": link_range, "textStyle": {"link": {"url": link["url"]}}, "fields": "link"}})
    payload = {"requests": requests, "writeControl": {"requiredRevisionId": document["revisionId"]}}
    response = session.post(endpoint + ":batchUpdate", json=payload, timeout=60)
    response.raise_for_status()
    print("Google Doc synchronized.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Google Doc sync failed: {exc}", file=sys.stderr)
        raise

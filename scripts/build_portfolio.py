#!/usr/bin/env python3
"""Build project additions and the downloadable resume from content/portfolio.json."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "content" / "portfolio.json"
PDF_PATH = ROOT / "downloads" / "Leonid_Chekin_Resume_Python_AI_FinTech.pdf"
RU_HTML = ROOT / "index.html"
EN_HTML = ROOT / "en.html"
START = "<!-- AUTO_PROJECTS_START -->"
END = "<!-- AUTO_PROJECTS_END -->"


def load_data() -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    required = {"title_ru", "title_en", "summary_ru", "summary_en", "role_ru", "role_en", "tech", "links"}
    seen = set()
    for index, project in enumerate(data.get("new_projects", []), start=1):
        missing = required - project.keys()
        if missing:
            raise ValueError(f"new_projects[{index - 1}] is missing: {', '.join(sorted(missing))}")
        slug = project.get("slug", "").strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"new_projects[{index - 1}].slug must use lowercase letters, numbers and hyphens")
        if slug in seen:
            raise ValueError(f"duplicate project slug: {slug}")
        seen.add(slug)
        if not isinstance(project["links"], list):
            raise ValueError(f"new_projects[{index - 1}].links must be a list")
        for link in project["links"]:
            if not link.get("label_ru") or not link.get("label_en") or not re.match(r"^https://", link.get("url", "")):
                raise ValueError(f"new_projects[{index - 1}] has an invalid link (use HTTPS and localized labels)")
    return data


def project_card(project: dict, lang: str, number: int) -> str:
    title = html.escape(project[f"title_{lang}"])
    role = html.escape(project[f"role_{lang}"])
    summary = html.escape(project[f"summary_{lang}"])
    tech = html.escape(project["tech"])
    status = html.escape(project.get(f"status_{lang}", "Personal project" if lang == "en" else "Проект"))
    links = "".join(
        f'<a class="project-outlink" href="{html.escape(link["url"], quote=True)}" target="_blank" rel="noopener">{html.escape(link[f"label_{lang}"])} ↗</a>'
        for link in project["links"]
    )
    return (
        f'<article class="project generated-project" data-project="{html.escape(project["slug"], quote=True)}">'
        f'<div class="project-top"><span>{status}</span><span class="number">N{number:02d}</span></div>'
        f'<h3>{title}</h3><p><strong>{role}</strong> {summary}</p>'
        f'<div class="tech">{tech}</div>{links}</article>'
    )


def update_html(path: Path, data: dict, lang: str) -> None:
    source = path.read_text(encoding="utf-8")
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError(f"expected one generated-project marker pair in {path.name}")
    cards = "\n".join(project_card(item, lang, i) for i, item in enumerate(data["new_projects"], start=1))
    start = source.index(START) + len(START)
    end = source.index(END)
    source = source[:start] + "\n" + cards + "\n" + source[end:]
    path.write_text(source, encoding="utf-8")


def find_font() -> tuple[str, str]:
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            return regular, bold
    raise FileNotFoundError("Install DejaVu Sans or Arial fonts before building the Russian resume PDF")


def link_markup(links: list[dict]) -> str:
    if not links:
        return ""
    return " · ".join(
        f'<link href="{html.escape(item["url"], quote=True)}" color="#0755a0">{html.escape(item["label"])}</link>'
        for item in links
    )


def build_pdf(data: dict) -> None:
    regular, bold = find_font()
    pdfmetrics.registerFont(TTFont("Resume", regular))
    pdfmetrics.registerFont(TTFont("Resume-Bold", bold))
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ResumeTitle", parent=styles["Title"], fontName="Resume-Bold", fontSize=22, leading=26, textColor=colors.HexColor("#172a24"), alignment=TA_LEFT, spaceAfter=3)
    subtitle = ParagraphStyle("ResumeSubtitle", parent=styles["Normal"], fontName="Resume", fontSize=11, leading=14, textColor=colors.HexColor("#44534a"), spaceAfter=2)
    contact = ParagraphStyle("ResumeContact", parent=styles["Normal"], fontName="Resume", fontSize=9, leading=11, textColor=colors.HexColor("#44534a"), spaceAfter=2)
    h1 = ParagraphStyle("ResumeH1", parent=styles["Heading1"], fontName="Resume-Bold", fontSize=14, leading=17, textColor=colors.HexColor("#172a24"), spaceBefore=9, spaceAfter=3, keepWithNext=True)
    h2 = ParagraphStyle("ResumeH2", parent=styles["Heading2"], fontName="Resume-Bold", fontSize=10.5, leading=13, textColor=colors.HexColor("#172a24"), spaceBefore=5, spaceAfter=2, keepWithNext=True)
    body = ParagraphStyle("ResumeBody", parent=styles["BodyText"], fontName="Resume", fontSize=9.2, leading=12, textColor=colors.black, spaceAfter=4, splitLongWords=1)
    story: list = []
    profile = data["resume"]
    story.append(Paragraph(html.escape(profile["name"]), title_style))
    story.append(Paragraph(html.escape(profile["title"]), subtitle))
    story.append(Paragraph(html.escape(f'{profile["phone"]} · {profile["email"]} · Telegram: {profile["telegram"]}'), contact))
    story.append(Paragraph(html.escape(f'{profile["location"]} · удалённая работа'), contact))
    story.append(Paragraph("Профессиональный профиль", h1))
    story.append(Paragraph(html.escape(profile["summary"]), body))
    story.append(Paragraph("Ключевые компетенции", h1))
    for item in profile["competencies"]:
        story.append(Paragraph("• " + html.escape(item), body))
    story.append(Paragraph("Опыт", h1))
    for item in profile["experience"]:
        story.append(KeepTogether([Paragraph(html.escape(item["title"]), h2), Paragraph(html.escape(item["text"]), body)]))
    story.append(PageBreak())
    story.append(Paragraph("Избранные проекты", h1))
    projects = list(data["resume_projects"])
    projects.extend(
        {"title": item["title_ru"], "text": f'{item["role_ru"]} {item["summary_ru"]}', "links": [{"label": link["label_ru"], "url": link["url"]} for link in item["links"]]}
        for item in data["new_projects"] if item.get("include_in_resume", True)
    )
    for item in projects:
        block = [Paragraph(html.escape(item["title"]), h2), Paragraph(html.escape(item["text"]), body)]
        links = link_markup(item.get("links", []))
        if links:
            block.append(Paragraph(links, contact))
        story.append(KeepTogether(block))
    story.append(Paragraph("Образование и дополнительная информация", h1))
    story.append(Paragraph(f'Образование: {html.escape(profile["education"])} Английский: {html.escape(profile["english"])}', body))
    story.append(Paragraph(f'Формат: {html.escape(profile["work_format"])}', body))
    links = link_markup([{"label": "Портфолио", "url": profile["portfolio_url"]}, {"label": "Хабр Карьера", "url": profile["habr_url"]}])
    story.append(Paragraph(links, body))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Resume", 8)
        canvas.setFillColor(colors.HexColor("#68766d"))
        canvas.drawRightString(letter[0] - 54, 32, f'{doc.page}')
        canvas.restoreState()

    document = SimpleDocTemplate(str(PDF_PATH), pagesize=letter, leftMargin=54, rightMargin=54, topMargin=50, bottomMargin=48, title=f'{profile["name"]} — Python Backend Developer | Applied AI', author=profile["name"])
    def deterministic_canvas(*args, **kwargs):
        kwargs["invariant"] = 1
        return canvas.Canvas(*args, **kwargs)

    document.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=deterministic_canvas)


def main() -> None:
    data = load_data()
    update_html(RU_HTML, data, "ru")
    update_html(EN_HTML, data, "en")
    build_pdf(data)
    print(f'Built {len(data["new_projects"])} new project cards and {len(data["resume_projects"])}+ resume highlights.')


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"portfolio build failed: {exc}", file=sys.stderr)
        raise

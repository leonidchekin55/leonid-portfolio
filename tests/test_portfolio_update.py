import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "apply_portfolio_update.py"
SPEC = importlib.util.spec_from_file_location("apply_portfolio_update", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

DISCOVERY_PATH = Path(__file__).resolve().parents[1] / "scripts" / "discover_github_projects.py"
DISCOVERY_SPEC = importlib.util.spec_from_file_location("discover_github_projects", DISCOVERY_PATH)
DISCOVERY = importlib.util.module_from_spec(DISCOVERY_SPEC)
assert DISCOVERY_SPEC.loader is not None
DISCOVERY_SPEC.loader.exec_module(DISCOVERY)


def project_record(slug="arqa-shift-diary"):
    return {
        "slug": slug,
        "title_ru": "Дневник смен водителя",
        "title_en": "Driver Shift Diary",
        "status_ru": "Тестовое задание · локальный прототип",
        "status_en": "Coding assignment · local prototype",
        "role_ru": "Моя роль: разработал API и веб-интерфейс, проверил расчёты и обработку повторов.",
        "role_en": "My role: built the API and web interface, and verified calculations and retry handling.",
        "summary_ru": "FastAPI-приложение для поездок и дневных сводок с проверкой данных и безопасной обработкой повторной отправки.",
        "summary_en": "A FastAPI app for trips and daily summaries with input validation and safe retry handling.",
        "tech": "Python / FastAPI / HTML / CSS / JavaScript / JSON / Pytest",
        "links": [{"label_ru": "Исходный код", "label_en": "Source code", "url": "https://github.com/leonidchekin55/arqa-shift-diary"}],
        "include_in_resume": True,
    }


class PortfolioUpdateTests(unittest.TestCase):
    def test_extracts_update_record_from_issue_body(self):
        record = project_record()
        body = "Подтверждённое описание.\n\n```json\n" + json.dumps({"operation": "add", "collection": "new_projects", "project": record}, ensure_ascii=False) + "\n```"

        self.assertEqual(MODULE.parse_update(body), {"operation": "add", "collection": "new_projects", "project": record})

    def test_discovery_issue_contains_a_valid_new_project_template(self):
        repo = {
            "full_name": "leonidchekin55/example-project",
            "created_at": "2026-10-17T00:00:00Z",
            "description": "Example project",
            "language": "Python",
            "topics": ["api"],
        }

        title, body = DISCOVERY.make_issue(repo)

        self.assertIn("example-project", title)
        with self.assertRaisesRegex(ValueError, "template placeholder"):
            MODULE.parse_update(body)
        self.assertIn("/portfolio-update", body)

    def test_activity_issue_contains_existing_record_and_change_links(self):
        project = project_record()
        repo = {
            "full_name": "leonidchekin55/arqa-shift-diary",
            "default_branch": "main",
            "pushed_at": "2026-10-17T12:00:00Z",
        }

        pushes = [{"type": "PushEvent", "created_at": "2026-10-17T12:00:00Z", "payload": {"ref": "refs/heads/feature/update", "head": "abcdef123456"}}]
        _, body = DISCOVERY.make_activity_issue(repo, {"collection": "new_projects", "project": project}, pushes)

        self.assertEqual(MODULE.parse_update(body), {"operation": "update", "collection": "new_projects", "project": project})
        self.assertIn("/commit/abcdef123456", body)
        self.assertIn("feature/update", body)
        self.assertIn("portfolio-repository:leonidchekin55/arqa-shift-diary", body)

    def test_push_detector_distinguishes_baseline_unchanged_and_new_activity(self):
        baseline = {"123": "2026-10-17T10:00:00Z"}

        self.assertFalse(DISCOVERY.has_new_push("456", "2026-10-17T11:00:00Z", baseline))
        self.assertFalse(DISCOVERY.has_new_push("123", "2026-10-17T10:00:00Z", baseline))
        self.assertTrue(DISCOVERY.has_new_push("123", "2026-10-17T11:00:00Z", baseline))

    def test_unavailable_linked_repository_does_not_stop_discovery(self):
        with patch.object(DISCOVERY, "api", side_effect=RuntimeError("GitHub API GET returned 404: Not Found")):
            self.assertIsNone(DISCOVERY.get_linked_public_repository("leonidchekin55/missing-repo"))

        with patch.object(DISCOVERY, "api", side_effect=RuntimeError("GitHub API GET returned 500: Server error")):
            with self.assertRaisesRegex(RuntimeError, "returned 500"):
                DISCOVERY.get_linked_public_repository("leonidchekin55/flaky-api")

    def test_activity_issue_can_update_a_resume_project(self):
        project = {
            "title": "City Sentinel · мониторинг оборудования",
            "text": "В командном проекте реализовал MQTT-контур.",
            "links": [{"label": "Демо", "url": "https://example.com"}],
        }
        repo = {"full_name": "leonidchekin55/city-sentinel", "default_branch": "main", "pushed_at": "2026-10-17T12:00:00Z"}
        _, body = DISCOVERY.make_activity_issue(repo, {"collection": "resume_projects", "project": project}, [])

        self.assertEqual(MODULE.parse_update(body), {"operation": "update", "collection": "resume_projects", "project": project})

        portfolio = {"resume_projects": [project, {"title": "Other", "text": "Keep me", "links": []}]}
        replacement = {**project, "text": "Updated, verified project summary."}
        MODULE.apply_update(portfolio, {"operation": "update", "collection": "resume_projects", "project": replacement})
        self.assertEqual(portfolio["resume_projects"][0]["text"], "Updated, verified project summary.")
        self.assertEqual(portfolio["resume_projects"][1]["title"], "Other")

    def test_push_event_filter_uses_only_events_after_saved_checkpoint(self):
        events = [
            {"type": "PushEvent", "created_at": "2026-10-17T12:00:00Z", "payload": {"head": "new"}},
            {"type": "WatchEvent", "created_at": "2026-10-17T11:30:00Z", "payload": {}},
            {"type": "PushEvent", "created_at": "2026-10-17T10:00:00Z", "payload": {"head": "old"}},
        ]

        pushes = DISCOVERY.pushes_since(events, "2026-10-17T11:00:00Z")

        self.assertEqual([event["payload"]["head"] for event in pushes], ["new"])

    def test_adds_valid_project_without_changing_other_records(self):
        portfolio = {"new_projects": [{"slug": "existing"}]}

        MODULE.apply_update(portfolio, {"operation": "add", "collection": "new_projects", "project": project_record()})

        self.assertEqual([item["slug"] for item in portfolio["new_projects"]], ["existing", "arqa-shift-diary"])

    def test_updates_only_the_matching_project(self):
        current = project_record()
        portfolio = {"new_projects": [current, project_record("another-project")]}
        replacement = project_record()
        replacement["status_en"] = "Active project · prototype"

        MODULE.apply_update(portfolio, {"operation": "update", "collection": "new_projects", "project": replacement})

        self.assertEqual(portfolio["new_projects"][0]["status_en"], "Active project · prototype")
        self.assertEqual(portfolio["new_projects"][1]["slug"], "another-project")

    def test_rejects_untrusted_or_incomplete_payloads(self):
        with self.assertRaises(ValueError):
            MODULE.parse_update("```json\n{\"operation\":\"add\",\"project\":{}}\n```")

        with self.assertRaises(ValueError):
            MODULE.validate_project({**project_record(), "links": [{"label_ru": "X", "label_en": "X", "url": "javascript:alert(1)"}]})

    def test_rejects_duplicate_add_and_missing_update_targets(self):
        portfolio = {"new_projects": [project_record()]}

        with self.assertRaises(ValueError):
            MODULE.apply_update(portfolio, {"operation": "add", "collection": "new_projects", "project": project_record()})

        with self.assertRaises(ValueError):
            MODULE.apply_update(portfolio, {"operation": "update", "collection": "new_projects", "project": project_record("missing")})

    def test_update_command_requires_owner_association(self):
        event = {
            "issue": {"number": 99, "state": "open", "body": ""},
            "comment": {"author_association": "CONTRIBUTOR", "body": "/portfolio-update"},
        }

        with self.assertRaisesRegex(ValueError, "repository owner"):
            MODULE.create_pull_request(event)

    def test_resume_project_update_creates_a_draft_pull_request(self):
        project = {
            "title": "City Sentinel · мониторинг оборудования",
            "text": "Обновлённое подтверждённое описание проекта.",
            "links": [{"label": "Репозиторий", "url": "https://github.com/leonidchekin55/city-sentinel"}],
        }
        body = "```json\n" + json.dumps(
            {"operation": "update", "collection": "resume_projects", "project": project},
            ensure_ascii=False,
        ) + "\n```"
        event = {
            "issue": {"number": 23, "state": "open", "body": body},
            "comment": {"id": 456, "author_association": "OWNER", "body": "/portfolio-update"},
        }
        portfolio = {"resume_projects": [{**project, "text": "Старое описание."}]}

        with tempfile.TemporaryDirectory() as temp_dir:
            portfolio_path = Path(temp_dir) / "portfolio.json"
            portfolio_path.write_text(json.dumps(portfolio), encoding="utf-8")
            with (
                patch.object(MODULE, "PORTFOLIO_PATH", portfolio_path),
                patch.dict("os.environ", {"GITHUB_REPOSITORY": "leonidchekin55/leonid-portfolio", "GITHUB_TOKEN": "test-token"}),
                patch.object(MODULE, "github_api", side_effect=[[], {"html_url": "https://github.com/leonidchekin55/leonid-portfolio/pull/42"}]) as github_api,
                patch.object(MODULE.subprocess, "run") as run,
            ):
                url = MODULE.create_pull_request(event)
                persisted_portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))

        self.assertEqual(url, "https://github.com/leonidchekin55/leonid-portfolio/pull/42")
        self.assertEqual(persisted_portfolio["resume_projects"][0]["text"], project["text"])
        pull_request_payload = github_api.call_args.args[3]
        self.assertIn(project["title"], pull_request_payload["title"])
        self.assertTrue(pull_request_payload["draft"])
        self.assertEqual(run.call_count, 10)

    def test_repeated_update_does_not_claim_an_existing_pull_request_was_refreshed(self):
        project = project_record()
        body = "```json\n" + json.dumps(
            {"operation": "update", "collection": "new_projects", "project": project},
            ensure_ascii=False,
        ) + "\n```"
        event = {
            "issue": {"number": 23, "state": "open", "body": body},
            "comment": {"id": 456, "author_association": "OWNER", "body": "/portfolio-update"},
        }
        existing = [{
            "head": {"ref": "codex/portfolio-update-issue-23-123"},
            "html_url": "https://github.com/leonidchekin55/leonid-portfolio/pull/42",
        }]

        with (
            patch.dict("os.environ", {"GITHUB_REPOSITORY": "leonidchekin55/leonid-portfolio", "GITHUB_TOKEN": "test-token"}),
            patch.object(MODULE, "github_api", return_value=existing),
        ):
            with self.assertRaisesRegex(ValueError, "edit that pull request directly"):
                MODULE.create_pull_request(event)


if __name__ == "__main__":
    unittest.main()

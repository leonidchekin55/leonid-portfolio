import contextlib
import io
import unittest
from unittest.mock import patch
from urllib.error import URLError

from scripts import audit_live_services as monitor


OK = monitor.Response(200, b"{}", "application/json")
HTTP_503 = monitor.Response(503, b'unavailable', 'text/html')
SUSPENDED = monitor.Response(503, b'suspended', 'text/html', 'suspend')
PULSE = "https://portfolio-pulseboard-demo.onrender.com"


class LiveMonitorTests(unittest.TestCase):
    def test_render_suspension_stays_red_without_extra_requests_and_other_hosts_run(self):
        targets = {"pulseboard": (PULSE, ("/health/live", "/docs")),
                   "portfolio": ("https://example.com", ("/",))}
        def fetch(url):
            return SUSPENDED if url.startswith(PULSE) else OK
        with patch.object(monitor, "SERVICES", targets), patch.object(monitor, "fetch", side_effect=fetch) as req:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(monitor.main(), 1)
        self.assertEqual(req.call_count, 2)
        self.assertIn("SUSPENDED pulseboard /health/live", out.getvalue())
        self.assertIn("SKIP pulseboard /docs", out.getvalue())
        self.assertIn("PASS portfolio /", out.getvalue())
        self.assertIn("Summary: PASS=1, FAIL=0, SUSPENDED=1, SKIP=1", out.getvalue())

    @patch.object(monitor.time, "sleep")
    def test_transient_503_can_recover(self, sleep):
        with patch.object(monitor, "fetch", side_effect=[HTTP_503, OK]) as req:
            rows = monitor.audit_service("pulseboard", PULSE, ("/health/live",))
        self.assertEqual(req.call_count, 2)
        sleep.assert_called_once()
        self.assertEqual(rows[0][0], "PASS")
        self.assertIn("after retry", rows[0][1])

    @patch.object(monitor.time, "sleep")
    def test_persistent_unmarked_503_stays_red_and_does_not_skip(self, _sleep):
        with patch.object(monitor, "fetch", side_effect=[HTTP_503, HTTP_503, OK]) as req:
            rows = monitor.audit_service("pulseboard", PULSE, ("/health/live", "/docs"))
        self.assertEqual(req.call_count, 3)
        self.assertEqual([row[0] for row in rows], ["FAIL", "PASS"])

    @patch.object(monitor.time, "sleep")
    def test_network_error_is_reported_without_leaking_error_details(self, _sleep):
        with patch.object(monitor, "fetch", side_effect=URLError("sensitive internal detail")):
            rows = monitor.audit_service("portfolio", "https://example.com", ("/",))
        self.assertEqual(rows, [("FAIL", "portfolio /: network error (URLError)")])

    def test_invalid_payload_does_not_abort_later_checks(self):
        bad = monitor.Response(200, b'[]', "application/json")
        with patch.object(monitor, "fetch", side_effect=[bad, OK]):
            rows = monitor.audit_service("knowledge", PULSE, ("/openapi.json", "/docs"))
        self.assertEqual([row[0] for row in rows], ["FAIL", "PASS"])

    def test_missing_openapi_routes_stays_a_failure(self):
        response = monitor.Response(200, b'{"paths": {}}', "application/json")
        with patch.object(monitor, "fetch", return_value=response):
            rows = monitor.audit_service("pulseboard", PULSE, ("/openapi.json",))
        self.assertEqual(rows[0][0], "FAIL")
        self.assertIn("missing OpenAPI demo routes", rows[0][1])

    def test_all_success_exits_zero(self):
        targets = {"portfolio": ("https://example.com", ("/",))}
        with patch.object(monitor, "SERVICES", targets), patch.object(monitor, "fetch", return_value=OK):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(monitor.main(), 0)
        self.assertIn("Summary: PASS=1, FAIL=0, SUSPENDED=0, SKIP=0", out.getvalue())

    def test_provider_header_is_not_trusted_on_an_unrelated_domain(self):
        self.assertFalse(monitor.is_render_suspended("https://example.com", SUSPENDED))

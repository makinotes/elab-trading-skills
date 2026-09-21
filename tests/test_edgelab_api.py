"""Offline credential-boundary tests using only invented keys and HTTP responses."""

import contextlib
from email.message import Message
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request
import urllib.response


SCRIPT = Path(__file__).resolve().parents[1] / "elab-research/scripts/edgelab_api.py"
SPEC = importlib.util.spec_from_file_location("edgelab_api", SCRIPT)
API = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(API)
FAKE_TOKEN = "mk_live_" + "SYNTHETIC_NOT_A_REAL_KEY"


class FakeResponse(io.BytesIO):
    def __init__(self, url, body=b'{"items": []}', status=200, headers=None):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = headers or {}

    def getcode(self):
        return self.status

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, body=b'{"items": []}', error=None, status=200, final_url=None):
        self.body, self.error, self.status = body, error, status
        self.final_url = final_url
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return FakeResponse(self.final_url or request.full_url, self.body, self.status)


class FakeRedirectHTTPS(urllib.request.HTTPSHandler):
    """Exercise urllib's real redirect dispatch without opening a socket."""

    handler_order = 100

    def __init__(self, destination, status):
        super().__init__()
        self.destination, self.status = destination, status
        self.requests = []

    def https_open(self, request):
        self.requests.append(request)
        headers = Message()
        headers["Location"] = self.destination
        response = urllib.response.addinfourl(
            io.BytesIO(FAKE_TOKEN.encode()), headers, request.full_url, self.status
        )
        response.msg = "Redirect with " + FAKE_TOKEN
        return response


class EdgeLabAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.token_path = Path(self.temporary.name) / "token"
        self.token_path.write_text(FAKE_TOKEN + "\n", encoding="ascii")
        self.token_path.chmod(0o600)

    def run_cli(self, argv, opener=None, token_path=None):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            status = API.main(argv, token_path=token_path or self.token_path,
                              opener=opener if opener is not None else FakeOpener())
        self.assertNotIn(FAKE_TOKEN, output.getvalue() + error.getvalue())
        return status, output.getvalue(), error.getvalue()

    def test_radars_reads_private_file_and_sends_only_to_fixed_origin(self):
        opener = FakeOpener()
        status, output, error = self.run_cli(["radars"], opener)
        self.assertEqual(status, 0)
        self.assertEqual(error, "")
        self.assertEqual(json.loads(output), {"ok": True, "http_status": 200, "data": {"items": []}})
        request = opener.requests[0]
        self.assertEqual(request.full_url, "https://invest.makinote.cn/api/v1/radars")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + FAKE_TOKEN)
        self.assertEqual(request.get_method(), "GET")
        self.assertNotIn(FAKE_TOKEN, request.full_url)
        self.assertEqual(self.token_path.read_text(), FAKE_TOKEN + "\n")

    def test_signals_encodes_requested_filters_without_changing_origin(self):
        opener = FakeOpener()
        status, _, _ = self.run_cli([
            "signals", "--type", "fear_card", "--since", "2026-01-01",
            "--until", "2026-02-28", "--limit", "10",
        ], opener)
        self.assertEqual(status, 0)
        parsed = urllib.parse.urlsplit(opener.requests[0].full_url)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ("https", "invest.makinote.cn", "/api/v1/signals"))
        self.assertEqual(urllib.parse.parse_qs(parsed.query), {
            "type": ["fear_card"], "since": ["2026-01-01"],
            "until": ["2026-02-28"], "limit": ["10"],
        })
        date_url = API.build_url("signals", "fear_card", date="2024-02-29")
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(date_url).query)["date"],
                         ["2024-02-29"])

    def test_invalid_filters_fail_before_reading_a_token_or_requesting(self):
        examples = [
            ["signals"], ["signals", "--type", "../../other"],
            ["signals", "--type", "x&url=https://example.invalid"],
            ["signals", "--type", "x", "--limit", "0"],
            ["signals", "--type", "x", "--limit", "101"],
            ["signals", "--type", "x", "--limit", FAKE_TOKEN],
            ["signals", "--type", "x", "--date", "2026-02-29"],
            ["signals", "--type", "x", "--date", "20260101"],
            ["signals", "--type", "x", "--date", "2026-01-01", "--since", "2025-01-01"],
            ["signals", "--type", "x", "--since", "2026-02-01", "--until", "2026-01-01"],
            ["radars", "--token", FAKE_TOKEN],
            ["radars", "--url", "https://example.invalid"],
        ]
        for argv in examples:
            with self.subTest(argv=argv), patch.object(API, "read_token") as read:
                opener = FakeOpener()
                status, output, error = self.run_cli(argv, opener)
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertEqual(json.loads(error)["error"]["code"], "invalid_arguments")
                read.assert_not_called()
                self.assertEqual(opener.requests, [])

    def test_token_file_failures_do_not_echo_content_or_path(self):
        missing = Path(self.temporary.name) / "missing"
        status, _, error = self.run_cli(["radars"], token_path=missing)
        self.assertEqual(status, 1)
        self.assertNotIn(str(missing), error)
        for value in (b"", b"wrong-format", (FAKE_TOKEN + "\r\nInjected: value").encode(),
                      b"\xff", b"x" * (API.MAX_TOKEN_BYTES + 1)):
            with self.subTest(value=value[:20]):
                self.token_path.write_bytes(value)
                opener = FakeOpener()
                status, output, error = self.run_cli(["radars"], opener)
                self.assertEqual(status, 1)
                self.assertEqual(json.loads(error)["error"]["code"], "token_invalid")
                self.assertEqual(output, "")
                self.assertEqual(opener.requests, [])

    @unittest.skipUnless(os.name == "posix", "POSIX permissions are unavailable")
    def test_world_readable_credentials_and_symlinks_are_rejected(self):
        self.token_path.chmod(0o644)
        opener = FakeOpener()
        status, _, error = self.run_cli(["radars"], opener)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(error)["error"]["code"], "token_permissions")
        self.assertEqual(opener.requests, [])
        self.token_path.chmod(0o600)
        link = Path(self.temporary.name) / "link"
        link.symlink_to(self.token_path)
        status, _, error = self.run_cli(["radars"], opener, link)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(error)["error"]["code"], "token_unavailable")
        self.assertEqual(opener.requests, [])
        # The lstat check still rejects a direct link without O_NOFOLLOW support.
        with patch.object(API.os, "O_NOFOLLOW", 0):
            status, _, error = self.run_cli(["radars"], opener, link)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(error)["error"]["code"], "token_unavailable")

    def test_all_redirect_statuses_are_rejected_before_a_second_request(self):
        destinations = ("https://example.invalid/collect", "http://example.invalid/collect",
                        API.API_ORIGIN + "/other", "/api/v1/signals")
        for code in (301, 302, 303, 307, 308):
            for destination in destinations:
                with self.subTest(code=code, destination=destination):
                    handler = FakeRedirectHTTPS(destination, code)
                    with patch.dict(os.environ, {"HTTPS_PROXY": "http://example.invalid:3128",
                                                 "https_proxy": "http://example.invalid:3128"}):
                        opener = API.build_opener()
                    opener.add_handler(handler)
                    status, output, error = self.run_cli(["radars"], opener)
                    self.assertEqual(status, 1)
                    self.assertEqual(output, "")
                    self.assertEqual(json.loads(error)["http_status"], code)
                    self.assertEqual(json.loads(error)["error"]["code"], "redirect_blocked")
                    self.assertEqual(len(handler.requests), 1)
                    self.assertEqual(handler.requests[0].host, "invest.makinote.cn")

    def test_unexpected_final_url_is_rejected(self):
        status, _, error = self.run_cli(["radars"], FakeOpener(final_url="https://example.invalid"))
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(error)["error"]["code"], "redirect_blocked")

    def test_http_errors_keep_status_but_drop_untrusted_body_and_message(self):
        codes = {401: "authentication_failed", 403: "access_denied", 429: "rate_limited",
                 503: "not_ready", 500: "server_error", 404: "http_error"}
        for status_code, expected in codes.items():
            with self.subTest(status=status_code):
                body = io.BytesIO(("echo " + FAKE_TOKEN).encode())
                failure = urllib.error.HTTPError(API.API_ORIGIN, status_code, FAKE_TOKEN,
                                                 {"Retry-After": "12"}, body)
                status, output, error = self.run_cli(["radars"], FakeOpener(error=failure))
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                result = json.loads(error)
                self.assertEqual(result["http_status"], status_code)
                self.assertEqual(result["error"]["code"], expected)
                self.assertTrue(body.closed)
                if status_code == 429:
                    self.assertEqual(result["retry_after_seconds"], 12)
        failure = urllib.error.HTTPError(API.API_ORIGIN, 429, "limit", {"Retry-After": FAKE_TOKEN}, None)
        _, _, error = self.run_cli(["radars"], FakeOpener(error=failure))
        self.assertNotIn("retry_after_seconds", json.loads(error))

    def test_successful_json_redacts_reflected_credentials_in_keys_and_values(self):
        body = json.dumps({FAKE_TOKEN: ["Bearer " + FAKE_TOKEN], "price": 123.45}).encode()
        status, output, error = self.run_cli(["radars"], FakeOpener(body=body))
        self.assertEqual(status, 0)
        self.assertEqual(error, "")
        self.assertEqual(json.loads(output)["data"], {"[REDACTED]": ["Bearer [REDACTED]"], "price": 123.45})

    def test_invalid_large_and_nonfinite_responses_fail_without_content(self):
        for body in (("<html>" + FAKE_TOKEN).encode(), b"\xff", b'{"number": NaN}'):
            with self.subTest(body=body):
                status, output, error = self.run_cli(["radars"], FakeOpener(body=body))
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                self.assertEqual(json.loads(error)["error"]["code"], "invalid_response")
        with patch.object(API, "MAX_RESPONSE_BYTES", 16):
            status, _, error = self.run_cli(["radars"], FakeOpener(body=b"x" * 17))
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(error)["error"]["code"], "invalid_response")

    def test_network_and_unexpected_exceptions_never_print_request_details(self):
        for failure, expected in ((urllib.error.URLError(FAKE_TOKEN), "network_error"),
                                  (RuntimeError("Authorization: " + FAKE_TOKEN), "client_error")):
            with self.subTest(expected=expected):
                status, output, error = self.run_cli(["radars"], FakeOpener(error=failure))
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                self.assertEqual(json.loads(error)["error"]["code"], expected)


if __name__ == "__main__":
    unittest.main()

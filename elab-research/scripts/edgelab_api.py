#!/usr/bin/env python3
"""Read EdgeLab market data without exposing its credential to tools or argv."""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request


API_ORIGIN = "https://invest.makinote.cn"
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_TOKEN_BYTES = 4096


class ClientError(Exception):
    """Only fixed, non-sensitive messages may cross the CLI boundary."""

    def __init__(self, code, message, http_status=None, retry_after=None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.retry_after = retry_after

    def as_json(self):
        result = {
            "ok": False,
            "http_status": self.http_status,
            "error": {"code": self.code, "message": str(self)},
        }
        if self.retry_after is not None:
            result["retry_after_seconds"] = self.retry_after
        return result


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse otherwise echoes rejected values, which may be credentials.
        raise ClientError("invalid_arguments", "Invalid arguments; see --help.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Deny even same-origin redirects: only the two documented paths are used.
        return None


def build_opener():
    # Do not route authenticated traffic via unselected environment proxies.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def build_url(endpoint, dataset=None, date=None, since=None, until=None, limit=30):
    if endpoint not in ("radars", "signals"):
        raise ClientError("invalid_arguments", "Only radars and signals are supported.")
    if endpoint == "radars":
        if any(value is not None for value in (dataset, date, since, until)) or limit != 30:
            raise ClientError("invalid_arguments", "radars does not accept filters.")
        return API_ORIGIN + "/api/v1/radars"
    if not isinstance(dataset, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", dataset):
        raise ClientError("invalid_arguments", "signals requires a valid dataset id from radars.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ClientError("invalid_arguments", "limit must be an integer from 1 to 100.")
    for value in (date, since, until):
        if value is None:
            continue
        try:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError
            datetime.date.fromisoformat(value)
        except ValueError:
            raise ClientError("invalid_arguments", "Dates must be valid YYYY-MM-DD values.") from None
    if date is not None and (since is not None or until is not None):
        raise ClientError("invalid_arguments", "Use date OR since/until, not both.")
    if since is not None and until is not None and since > until:
        raise ClientError("invalid_arguments", "since must not be after until.")
    query = {"type": dataset, "limit": limit}
    query.update({key: value for key, value in (("date", date), ("since", since), ("until", until))
                  if value is not None})
    return API_ORIGIN + "/api/v1/signals?" + urllib.parse.urlencode(query)


def read_token(path=None):
    path = Path(path) if path is not None else Path.home() / ".elab" / "token"
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise ClientError("token_unavailable", "The token must be a regular private file.")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(str(path), flags), "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode)
                    or (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino)):
                raise ClientError("token_unavailable", "The token must be a regular private file.")
            if os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.geteuid()):
                raise ClientError("token_permissions", "The token must be owned by the current user with mode 600.")
            raw = handle.read(MAX_TOKEN_BYTES + 1)
    except OSError:
        raise ClientError("token_unavailable", "The private token file is missing or unreadable.") from None
    if len(raw) > MAX_TOKEN_BYTES:
        raise ClientError("token_invalid", "The token file does not contain a valid member key.")
    try:
        token = raw.decode("ascii").rstrip("\r\n")
    except UnicodeDecodeError:
        raise ClientError("token_invalid", "The token file does not contain a valid member key.") from None
    if not re.fullmatch(r"mk_live_[A-Za-z0-9_-]+", token):
        raise ClientError("token_invalid", "The token file does not contain a valid member key.")
    return token


def http_failure(status, headers=None):
    retry_after = None
    value = headers.get("Retry-After", "") if headers is not None else ""
    if status == 429 and re.fullmatch(r"[0-9]{1,6}", value):
        retry_after = int(value)
    if 300 <= status < 400:
        code, message = "redirect_blocked", "The API returned a redirect; no redirect was followed."
    elif status == 401:
        code, message = "authentication_failed", "The member key is invalid or expired."
    elif status == 403:
        code, message = "access_denied", "The API denied access."
    elif status == 429:
        code, message = "rate_limited", "The API rate limit was reached; retry later."
    elif status == 503:
        code, message = "not_ready", "The requested API data or service is not ready."
    elif status >= 500:
        code, message = "server_error", "The API is temporarily unavailable."
    else:
        code, message = "http_error", "The API request failed."
    return ClientError(code, message, status, retry_after)


def redact_token(value, token):
    # A server may reflect a header in otherwise successful JSON, even in a key.
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]")
    if isinstance(value, list):
        return [redact_token(item, token) for item in value]
    if isinstance(value, dict):
        return {redact_token(key, token): redact_token(item, token) for key, item in value.items()}
    return value


def fetch(endpoint, *, dataset=None, date=None, since=None, until=None, limit=30,
          token_path=None, opener=None):
    url = build_url(endpoint, dataset, date, since, until, limit)
    token = read_token(token_path)
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "EdgeLab-Skills-MarketData/1.0",
    }, method="GET")
    transport = opener if opener is not None else build_opener()
    try:
        with transport.open(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.getcode()
            if response.geturl() != url:
                raise ClientError("redirect_blocked", "The response did not come from the requested API URL.")
            if not 200 <= status < 300:
                raise http_failure(status, response.headers)
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        error = http_failure(exc.code, exc.headers)
        exc.close()
        raise error from None
    except (urllib.error.URLError, OSError):
        raise ClientError("network_error", "The API could not be reached securely.") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise ClientError("invalid_response", "The API response exceeds the supported size.", status)
    try:
        payload = json.loads(body.decode("utf-8"))
        sanitized = redact_token(payload, token)
        # Validate that the result can be emitted as strict JSON before returning.
        json.dumps(sanitized, allow_nan=False)
    except (ValueError, RecursionError):
        raise ClientError("invalid_response", "The API did not return supported JSON data.", status) from None
    return {"ok": True, "http_status": status, "data": sanitized}


def main(argv=None, *, token_path=None, opener=None):
    parser = SafeArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="endpoint", required=True, parser_class=SafeArgumentParser)
    commands.add_parser("radars", allow_abbrev=False, help="Discover available dataset ids and dates")
    signals = commands.add_parser("signals", allow_abbrev=False, help="Read one discovered dataset")
    signals.add_argument("--type", dest="dataset", required=True)
    signals.add_argument("--date")
    signals.add_argument("--since")
    signals.add_argument("--until")
    signals.add_argument("--limit", type=int, default=30)
    try:
        args = vars(parser.parse_args(argv))
        result = fetch(**args, token_path=token_path, opener=opener)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except ClientError as exc:
        print(json.dumps(exc.as_json(), ensure_ascii=False), file=sys.stderr)
        return 2 if exc.code == "invalid_arguments" else 1
    except Exception:
        # Never serialize an unexpected exception: it may contain a header or body.
        print(json.dumps({"ok": False, "http_status": None, "error": {
            "code": "client_error", "message": "The API client failed without exposing request details."
        }}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

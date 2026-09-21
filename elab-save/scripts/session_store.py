#!/usr/bin/env python3
"""Append a validated session snapshot using only an explicit state root.

Inputs must be redacted before reaching this tool. The sensitive-data checks cover
recognizable credential/account assignments and private-key markers, not arbitrary hidden secrets.
No semantic truth, source ownership, or resolution decision is inferred here.
Descriptor-relative, no-follow filesystem operations require a POSIX runtime.
The explicit state root's parent must already exist; its ancestors are not made
or modified. Existing ancestor aliases (such as macOS /tmp) are canonicalized.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata
from typing import Any, Dict, Iterator, Optional, TextIO


MAX_INPUT_BYTES = 1024 * 1024
CLASSIFICATIONS = frozenset({"public", "member", "private", "unknown"})
SECTIONS = ("关键判断", "已排除的方向", "待回填假设", "下一步")
FIELDS = frozenset({"title", "source_skill", "next_skill", "data_classification",
                    "sources", "body", "previous_snapshot", "status"})
REQUIRED = frozenset({"title", "source_skill", "data_classification", "sources", "body"})
SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")
SKILL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
ASSIGNMENT = re.compile(
    # Chinese labels can directly follow words such as “测试” or “我的”.
    # Only English labels need a boundary against longer ASCII identifiers.
    r"(?i)(?:(?<![A-Za-z0-9_])(?:password|passwd|pwd|(?:access[_ -]?|refresh[_ -]?)?token|"
    r"api[_ -]?(?:key|token)|auth[_ -]?token|private[_ -]?key|app[_ -]?secret|"
    r"client[_ -]?secret|secret[_ -]?key|secret|cookie|authorization|"
    r"account_id|account_number)|密码|口令|密钥|私钥|账户号|完整账号)"
    r"[\"']?\s*[:=：]\s*([^\r\n]+)"
)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
TOKEN_VALUE = re.compile(r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{30,}|"
                         r"github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,})")
REDACTIONS = frozenset({"[redacted]", "<redacted>", "redacted", "***", "[已脱敏]",
                        "已脱敏", "null", "none", "未提供", "不记录"})


class StoreError(Exception):
    """A safe, constant diagnostic that never includes submitted content."""


def _text(value: Any, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise StoreError("Invalid text field.")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise StoreError("Invalid text encoding.") from None
    if "\x00" in value:
        raise StoreError("Invalid text field.")
    return value


def _reject_credentials(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_credentials(key)
            _reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            _reject_credentials(item)
    elif isinstance(value, str):
        if PRIVATE_KEY.search(value) or TOKEN_VALUE.search(value):
            raise StoreError("Possible credential material rejected; redact before submission.")
        for match in ASSIGNMENT.finditer(value):
            assigned = match.group(1).strip().rstrip(",;}").strip().strip("\"'").strip()
            if assigned.lower().startswith("bearer "):
                assigned = assigned[7:].strip()
            if assigned and assigned.lower() not in REDACTIONS:
                raise StoreError("Possible credential or full account identifier rejected; redact before submission.")


def _unique_object(pairs: Any) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise StoreError("Duplicate JSON field.")
        result[key] = value
    return result


def _invalid_constant(_value: str) -> None:
    raise StoreError("Invalid JSON constant.")


def load_input(path: str, stdin: Optional[TextIO] = None) -> Dict[str, Any]:
    """Read at most one MiB; refuse symlink, directory, device, and FIFO inputs."""
    try:
        if path == "-":
            raw = (stdin if stdin is not None else sys.stdin).read(MAX_INPUT_BYTES + 1)
            if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
                raise StoreError("Input is too large.")
        else:
            if not hasattr(os, "O_NOFOLLOW"):
                raise StoreError("No-follow filesystem operations are unavailable.")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise StoreError("Input must be a regular, non-symlink file.")
                raw_bytes = handle.read(MAX_INPUT_BYTES + 1)
            if len(raw_bytes) > MAX_INPUT_BYTES:
                raise StoreError("Input is too large.")
            raw = raw_bytes.decode("utf-8")
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise StoreError("Unable to read valid JSON from a regular input file or stdin.") from None
    if not isinstance(value, dict):
        raise StoreError("Input must be a JSON object.")
    return value


def _markdown_visible(body: str) -> str:
    """Ignore fenced examples when checking headings and source-reference tags."""
    lines = []
    fence = None
    for line in body.splitlines():
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}\s*", line):
                fence = None
            lines.append("")
        elif opening:
            fence = (opening[1][0], len(opening[1]))
            lines.append("")
        else:
            lines.append(line)
    if fence:
        raise StoreError("Unclosed Markdown code fence.")
    return "\n".join(lines)


def validate_payload(payload: Dict[str, Any], status: str) -> Dict[str, Any]:
    """Validate structure and explicit references, without inferring provenance."""
    if not isinstance(payload, dict) or set(payload) - FIELDS or not REQUIRED <= set(payload):
        raise StoreError("Missing or unknown JSON fields.")
    if status not in ("open", "resolved"):
        raise StoreError("Invalid explicit status.")
    if "status" in payload and payload["status"] != status:
        raise StoreError("Input status conflicts with explicit CLI status.")
    _reject_credentials(payload)
    title = _text(payload["title"], 200)
    if any(unicodedata.category(c).startswith("C") for c in title):
        raise StoreError("Title must not contain control characters.")
    for field in ("source_skill", "next_skill"):
        value = payload.get(field)
        if field == "next_skill" and (value is None or value == ""):
            continue
        if field == "source_skill" and value == "对话":
            continue
        if not isinstance(value, str) or not SKILL_NAME.fullmatch(value):
            raise StoreError("Invalid skill field.")
    classification = payload["data_classification"]
    if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
        raise StoreError("Invalid data classification.")
    sources = payload["sources"]
    if not isinstance(sources, list) or not sources or len(sources) > 1000:
        raise StoreError("Invalid sources list.")
    identifiers = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"id", "classification", "reference"}:
            raise StoreError("Invalid source fields.")
        identifier = source["id"]
        if not isinstance(identifier, str) or not SOURCE_ID.fullmatch(identifier) or identifier in identifiers:
            raise StoreError("Source IDs must be valid and unique.")
        identifiers.add(identifier)
        if not isinstance(source["classification"], str) or source["classification"] not in CLASSIFICATIONS:
            raise StoreError("Invalid source classification.")
        if classification == "public" and source["classification"] != "public":
            raise StoreError("Public snapshots cannot include restricted or unknown sources.")
        _text(source["reference"], 4096)
    body = _text(payload["body"], MAX_INPUT_BYTES)
    visible = _markdown_visible(body)
    headings = list(re.finditer(r"^ {0,3}##[ \t]+([^\n]+?)[ \t]*$", visible, re.M))
    if [m[1] for m in headings] != list(SECTIONS):
        raise StoreError("Body must contain the four required level-two sections in order.")
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(visible)
        if not visible[heading.end():end].strip():
            raise StoreError("Required Markdown sections must not be empty.")
    citations = list(re.finditer(r"\[来源[ \t]+([^\]\r\n]+)\]", visible))
    if visible.count("[来源") != len(citations):
        raise StoreError("Malformed source reference.")
    for citation in citations:
        cited = re.split(r"[\s,，、;；]+", citation[1].strip())
        if any(identifier not in identifiers for identifier in cited):
            raise StoreError("Body references an undeclared source ID.")
    if not any(headings[0].end() <= citation.start() < headings[1].start() for citation in citations):
        raise StoreError("Key judgments must reference at least one declared source.")
    previous = payload.get("previous_snapshot")
    if previous is not None:
        _text(previous, 240)
        if ("/" in previous or "\\" in previous or ".." in previous
                or not re.fullmatch(r"[0-9]{8}-[0-9]{6}-.+\.md", previous)
                or any(unicodedata.category(c).startswith("C") for c in previous)):
            raise StoreError("Previous snapshot must be a same-project snapshot filename.")
    return payload


def safe_title(title: str) -> str:
    name = re.sub(r"[\s/\\:*?\"<>|]+", "-", title).strip(" .-")
    name = re.sub(r"\.{2,}", "-", name) or "记录"
    while len(name.encode("utf-8")) > 180:
        name = name[:-1]
    return name.rstrip(" .-") or "记录"


def _slug(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", value):
        raise StoreError("Invalid project slug.")
    return value


def _directory(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        os.fchmod(fd, 0o700)
    except BaseException:
        os.close(fd)
        raise
    return fd


@contextmanager
def _project_directory(state_root: Path, slug: str) -> Iterator[Any]:
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise StoreError("Descriptor-relative no-follow filesystem operations are unavailable.")
    if ".." in state_root.parts or state_root.name in ("", ".", ".."):
        raise StoreError("Invalid explicit state root.")
    root = state_root.absolute()
    # Existing ancestors belong to the explicit path; never create/change them.
    parent = root.parent.resolve(strict=True)
    descriptors = [os.open(str(parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    try:
        for name in (root.name, "sessions", slug):
            descriptors.append(_directory(descriptors[-1], name))
        yield descriptors[-1], parent / root.name / "sessions" / slug
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def render_snapshot(payload: Dict[str, Any], slug: str, status: str, created: str) -> bytes:
    # JSON escapes also exclude YAML's non-printable Unicode control characters.
    # Decoding the header preserves Unicode titles/references without ambiguity.
    quote = lambda value: json.dumps(value, ensure_ascii=True)
    header = ["---"]
    for field, value in (("title", payload["title"]), ("slug", slug), ("created", created),
                         ("status", status), ("source_skill", payload["source_skill"]),
                         ("next_skill", payload.get("next_skill") or ""),
                         ("data_classification", payload["data_classification"])):
        header.append(field + ": " + quote(value))
    if payload.get("previous_snapshot") is not None:
        header.append("previous_snapshot: " + quote(payload["previous_snapshot"]))
    header.append("sources:" if payload["sources"] else "sources: []")
    for source in payload["sources"]:
        header.extend(["  - id: " + quote(source["id"]),
                       "    classification: " + quote(source["classification"]),
                       "    reference: " + quote(source["reference"])])
    header.extend(["---", "", ""])
    body = payload["body"]
    return ("\n".join(header) + body + ("" if body.endswith("\n") else "\n")).encode("utf-8")


def _write_all(fd: int, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(fd, remaining)
        if written <= 0:
            raise StoreError("Snapshot write did not complete.")
        remaining = remaining[written:]
    os.fsync(fd)


def _readback(directory_fd: int, name: str, identity: Any) -> bytes:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != identity:
            raise StoreError("Snapshot identity changed during readback.")
        return handle.read(MAX_INPUT_BYTES * 2 + 1)


def save_snapshot(payload: Dict[str, Any], state_root: Path, slug: str, status: str) -> Dict[str, str]:
    """Create one immutable snapshot; never infer status from pending body text."""
    validate_payload(payload, status)
    _slug(slug)
    now = datetime.now().astimezone()
    created = now.date().isoformat()
    saved_at = now.isoformat(timespec="seconds")
    content = render_snapshot(payload, slug, status, created)
    digest = hashlib.sha256(content).hexdigest()
    try:
        with _project_directory(Path(state_root), slug) as (directory_fd, folder):
            previous = payload.get("previous_snapshot")
            if previous is not None:
                info = os.stat(previous, dir_fd=directory_fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    raise StoreError("Previous snapshot must be a regular same-project file.")
            stem = now.strftime("%Y%m%d-%H%M%S") + "-" + safe_title(payload["title"])
            for attempt in range(10000):
                name = stem + ("" if attempt == 0 else "-" + str(attempt)) + ".md"
                try:
                    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory_fd)
                    break
                except FileExistsError:
                    continue
            else:
                raise StoreError("No unused snapshot filename is available.")
            identity = None
            try:
                try:
                    info = os.fstat(fd)
                    identity = (info.st_dev, info.st_ino)
                    os.fchmod(fd, 0o600)
                    _write_all(fd, content)
                finally:
                    os.close(fd)
                readback = _readback(directory_fd, name, identity)
                if readback != content or hashlib.sha256(readback).hexdigest() != digest:
                    raise StoreError("Snapshot readback verification failed.")
            except BaseException:
                # Remove only the inode created by this attempt, never an old file.
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if identity is not None and (info.st_dev, info.st_ino) == identity:
                    os.unlink(name, dir_fd=directory_fd)
                raise
            return {"path": str(folder / name), "status": status, "sha256": digest,
                    "title": payload["title"], "created": created, "saved_at": saved_at, "slug": slug}
    except (OSError, UnicodeError):
        raise StoreError("Unable to save snapshot safely; no existing snapshot was overwritten.") from None


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise StoreError("Invalid command line arguments; use --help.")


def main(argv: Optional[Any] = None) -> int:
    parser = _ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("save", help="create a new session snapshot")
    save.add_argument("--state-root", required=True, type=Path)
    save.add_argument("--slug", required=True)
    save.add_argument("--status", required=True, choices=("open", "resolved"))
    save.add_argument("--input", required=True, help="redacted JSON file, or - for stdin")
    try:
        args = parser.parse_args(argv)
        receipt = save_snapshot(load_input(args.input), args.state_root, args.slug, args.status)
        print(json.dumps(receipt, ensure_ascii=False))
        return 0
    except StoreError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

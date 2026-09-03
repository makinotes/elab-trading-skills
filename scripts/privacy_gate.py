#!/usr/bin/env python3
"""Fail closed when private material is staged for the public EdgeLab repo."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BLOCKED_PATH_PARTS = {
    "_data",
    "eval",
    "evaluation",
    "evaluations",
    "feishu_inbox",
    "elab-skills-internal",
}
BLOCKED_PATH_PREFIX = re.compile(
    r"^(?:goldsets?|transcripts?|scores?|rubrics?|prompts?|answers?)(?:[-_.]|$)"
)
BLOCKED_FILENAMES = {
    ".env",
    "my-work.md",
    "selfchat.jsonl",
    "feishu_watermark.json",
}
RULE_FIXTURES = {
    Path("scripts/privacy_gate.py"),
    Path("tests/test_privacy_gate.py"),
}
BLOCKED_CONTENT = re.compile(
    rb"MYSELF_FEISHU_(?:DOC_TOKEN|SELF_CHAT_ID)"
    rb"|(?:^|[^A-Za-z0-9])oc_[A-Za-z0-9_-]{20,}"
    rb"|last_successful_pull"
    rb"|selfchat_last_pull"
    rb"|feishu_inbox"
    rb"|/Users/makino/"
    rb"|/root/cc/",
    flags=re.MULTILINE,
)


def git_paths(staged: bool) -> list[Path]:
    if staged:
        command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]
    else:
        command = ["git", "ls-files", "-co", "--exclude-standard", "-z"]
    raw = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return [Path(item.decode("utf-8")) for item in raw.split(b"\0") if item]


def read_candidate(path: Path, staged: bool) -> bytes:
    if staged:
        result = subprocess.run(
            ["git", "show", f":{path.as_posix()}"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return result.stdout if result.returncode == 0 else b""
    absolute = ROOT / path
    if absolute.is_symlink():
        return str(absolute.readlink()).encode("utf-8")
    if not absolute.is_file():
        return b""
    return absolute.read_bytes()


def path_reason(path: Path) -> str | None:
    lowered = [part.lower() for part in path.parts]
    if any(
        part in BLOCKED_PATH_PARTS or BLOCKED_PATH_PREFIX.match(part)
        for part in lowered
    ):
        return "private-only path"
    if path.name.lower() in BLOCKED_FILENAMES or path.name.lower().startswith(".env."):
        return "credential or personal-data filename"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()

    findings: list[tuple[Path, str]] = []
    for path in sorted(set(git_paths(args.staged))):
        reason = path_reason(path)
        if reason:
            findings.append((path, reason))
            continue
        data = read_candidate(path, args.staged)
        if path not in RULE_FIXTURES and BLOCKED_CONTENT.search(data):
            findings.append((path, "private locator, watermark, or machine path"))
            continue
        text = data.decode("utf-8", errors="ignore")
        if path not in RULE_FIXTURES and all(
            marker in text for marker in ('"message_id"', '"create_time"', '"content"')
        ):
            findings.append((path, "raw chat-export schema"))

    if findings:
        print("PRIVACY_GATE=FAIL")
        for path, reason in findings:
            print(f"- {path.as_posix()}: {reason}")
        return 1

    print(f"PRIVACY_GATE=PASS files={len(set(git_paths(args.staged)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

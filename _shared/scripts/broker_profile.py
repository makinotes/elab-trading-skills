#!/usr/bin/env python3
"""Manage EdgeLab broker preference and report local connector readiness hints.

This file never stores credentials and never calls a broker network endpoint.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = "1.0"
PROVIDERS = ("futu", "longbridge", "ibkr")
DEFAULT_CONFIG = Path.home() / ".elab" / "broker-connectors.json"


class ProfileError(RuntimeError):
    pass


def config_path() -> Path:
    override = os.environ.get("ELAB_BROKER_PROFILE_PATH")
    return Path(override).expanduser() if override else DEFAULT_CONFIG


def empty_profile() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "default_provider": None,
        "updated_at": None,
    }


def load_profile(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        return empty_profile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot read valid JSON profile: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProfileError(f"profile must be a JSON object: {path}")
    provider = raw.get("default_provider")
    if provider is not None and provider not in PROVIDERS:
        raise ProfileError(f"unsupported default_provider in {path}: {provider!r}")
    return {
        "schema_version": SCHEMA_VERSION,
        "default_provider": provider,
        "updated_at": raw.get("updated_at"),
    }


def save_profile(profile: dict[str, Any], path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    safe = {
        "schema_version": SCHEMA_VERSION,
        "default_provider": profile.get("default_provider"),
        "updated_at": profile.get("updated_at"),
    }
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(safe, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def set_default(provider: str) -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ProfileError(f"unsupported provider: {provider}")
    profile = load_profile()
    profile["default_provider"] = provider
    profile["updated_at"] = utc_now()
    save_profile(profile)
    return profile


def clear_default() -> dict[str, Any]:
    profile = empty_profile()
    profile["updated_at"] = utc_now()
    save_profile(profile)
    return profile


def tcp_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def json_has_mcp(path: Path, server_name: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    servers = data.get("mcpServers", {})
    return isinstance(servers, dict) and server_name in servers


def codex_has_mcp(path: Path, server_name: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    pattern = rf"(?m)^\s*\[mcp_servers\.{re.escape(server_name)}\]\s*$"
    return re.search(pattern, text) is not None


def mcp_configured_in(server_name: str, home: Path) -> list[str]:
    found: list[str] = []
    if codex_has_mcp(home / ".codex" / "config.toml", server_name):
        found.append("codex")
    if json_has_mcp(home / ".claude.json", server_name):
        found.append("claude")
    if json_has_mcp(home / ".codebuddy" / "mcp.json", server_name):
        found.append("codebuddy")
    if json_has_mcp(home / ".workbuddy" / "mcp.json", server_name):
        found.append("workbuddy")
    return found


def skill_installed(skill_name: str, home: Path) -> list[str]:
    runtimes = {
        "claude": home / ".claude" / "skills",
        "codex": home / ".codex" / "skills",
        "codebuddy": home / ".codebuddy" / "skills",
        "workbuddy": home / ".workbuddy" / "skills",
    }
    return [
        runtime
        for runtime, root in runtimes.items()
        if (root / skill_name / "SKILL.md").is_file()
    ]


def doctor(provider: str) -> dict[str, Any]:
    home = Path.home()
    selected = PROVIDERS if provider == "all" else (provider,)
    output: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "checked_at": utc_now(),
        "network_auth_verified": False,
        "providers": {},
    }
    if "futu" in selected:
        host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
        try:
            port = int(os.environ.get("FUTU_OPEND_PORT", "11111"))
        except ValueError as exc:
            raise ProfileError("FUTU_OPEND_PORT must be an integer") from exc
        sdk = importlib.util.find_spec("futu") is not None
        skills = skill_installed("futuapi", home)
        opend = tcp_reachable(host, port)
        output["providers"]["futu"] = {
            "sdk_module_installed": sdk,
            "futuapi_skill_installed_in": skills,
            "opend_host": host,
            "opend_port": port,
            "opend_reachable": opend,
            "ready_for_minimal_query": opend and (sdk or bool(skills)),
        }
    if "longbridge" in selected:
        binary = shutil.which("longbridge")
        mcp = mcp_configured_in("longbridge", home)
        output["providers"]["longbridge"] = {
            "cli_path": binary,
            "mcp_configured_in": mcp,
            "ready_for_minimal_query": bool(binary or mcp),
        }
    if "ibkr" in selected:
        mcp = mcp_configured_in("ibkr", home)
        output["providers"]["ibkr"] = {
            "mcp_configured_in": mcp,
            "ready_for_minimal_query": bool(mcp),
        }
    return output


def emit(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if "providers" in data:
        print(f"checked_at: {data['checked_at']}")
        print("network_auth_verified: false")
        for name, status in data["providers"].items():
            print(f"{name}: ready_for_minimal_query={str(status['ready_for_minimal_query']).lower()}")
        return
    print(f"default_provider: {data.get('default_provider') or '(not set)'}")
    print(f"updated_at: {data.get('updated_at') or '(never)'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EdgeLab broker preference and local readiness helper (stores no credentials)."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show", help="Show the saved default provider.")
    show.add_argument("--json", action="store_true")
    set_command = commands.add_parser("set-default", help="Save an explicitly chosen default provider.")
    set_command.add_argument("provider", choices=PROVIDERS)
    set_command.add_argument("--json", action="store_true")
    clear = commands.add_parser("clear-default", help="Clear the saved default provider.")
    clear.add_argument("--json", action="store_true")
    check = commands.add_parser("doctor", help="Check local installation/configuration hints only.")
    check.add_argument("--provider", choices=("all",) + PROVIDERS, default="all")
    check.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "show":
            result = load_profile()
        elif args.command == "set-default":
            result = set_default(args.provider)
        elif args.command == "clear-default":
            result = clear_default()
        else:
            result = doctor(args.provider)
        emit(result, args.json)
        return 0
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

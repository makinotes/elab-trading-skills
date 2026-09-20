#!/usr/bin/env python3
"""Deterministic public tests for the broker connector helper and wiring."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "_shared" / "scripts" / "broker_profile.py"
SPEC = importlib.util.spec_from_file_location("broker_profile", SCRIPT)
assert SPEC and SPEC.loader
BP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BP)


class BrokerProfileTest(unittest.TestCase):
    def test_missing_profile_is_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = BP.load_profile(Path(temporary) / "missing.json")
        self.assertEqual(profile["schema_version"], "1.0")
        self.assertIsNone(profile["default_provider"])

    def test_save_profile_keeps_only_non_secret_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / ".elab" / "broker-connectors.json"
            BP.save_profile(
                {
                    "default_provider": "longbridge",
                    "updated_at": "2026-09-02T00:00:00+00:00",
                    "token": "must-not-be-written",
                    "account_id": "must-not-be-written",
                },
                path,
            )
            stored = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(stored["default_provider"], "longbridge")
        self.assertNotIn("token", stored)
        self.assertNotIn("account_id", stored)
        self.assertEqual(mode, 0o600)

    def test_cli_set_show_and_clear(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            env = os.environ.copy()
            env["ELAB_BROKER_PROFILE_PATH"] = str(path)
            set_result = subprocess.run(
                [str(SCRIPT), "set-default", "ibkr", "--json"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            show_result = subprocess.run(
                [str(SCRIPT), "show", "--json"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            clear_result = subprocess.run(
                [str(SCRIPT), "clear-default", "--json"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
        self.assertEqual(set_result.returncode, 0, set_result.stderr)
        self.assertEqual(json.loads(show_result.stdout)["default_provider"], "ibkr")
        self.assertEqual(clear_result.returncode, 0, clear_result.stderr)
        self.assertIsNone(json.loads(clear_result.stdout)["default_provider"])

    def test_doctor_is_read_only_and_does_not_claim_auth(self):
        result = BP.doctor("all")
        self.assertFalse(result["network_auth_verified"])
        self.assertEqual(set(result["providers"]), set(BP.PROVIDERS))
        for status in result["providers"].values():
            self.assertIn("ready_for_minimal_query", status)

    def test_non_object_mcp_server_map_is_treated_as_unconfigured(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mcp.json"
            for value in (None, [], "invalid"):
                path.write_text(json.dumps({"mcpServers": value}), encoding="utf-8")
                self.assertFalse(BP.json_has_mcp(path, "longbridge"))

    def test_skill_wiring_and_suite_version(self):
        expected = {
            "elab/SKILL.md": "_shared/broker-connectors.md",
            "elab-research/SKILL.md": "_shared/broker-connectors.md",
            "elab-trade/SKILL.md": "_shared/broker-connectors.md",
        }
        for relative, needle in expected.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(needle, text, relative)
        self.assertEqual((ROOT / "_shared" / "SUITE_VERSION").read_text().strip(), "0.6.0")

    def test_installer_copies_connector_to_all_supported_runtimes(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            for runtime in (".claude", ".codex", ".codebuddy", ".workbuddy"):
                stale = home / runtime / "skills" / "elab-removed-from-suite"
                stale.mkdir(parents=True)
                (stale / "SKILL.md").write_text("must be removed\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(home)
            completed = subprocess.run(
                ["bash", str(ROOT / "install.sh")],
                text=True,
                capture_output=True,
                env=env,
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("EdgeLab Skills 0.6.0", completed.stdout)
            for runtime in (".claude", ".codex", ".codebuddy", ".workbuddy"):
                skill_root = home / runtime / "skills"
                self.assertTrue((skill_root / "elab" / "SKILL.md").is_file())
                self.assertTrue((skill_root / "_shared" / "SUITE_VERSION").is_file())
                self.assertEqual(
                    (skill_root / "_shared" / "trading-consistency.md").read_bytes(),
                    (ROOT / "_shared" / "trading-consistency.md").read_bytes(),
                )
                iv_script = skill_root / "elab-research" / "scripts" / "iv_metrics.py"
                self.assertTrue(iv_script.is_file())
                for reference in ("research-methods.md", "external-research.md"):
                    self.assertTrue((skill_root / "elab-research" / "references" / reference).is_file())
                helper = skill_root / "_shared" / "scripts" / "broker_profile.py"
                self.assertTrue(helper.is_file())
                self.assertTrue(os.access(helper, os.X_OK))
                self.assertFalse((skill_root / "elab-removed-from-suite").exists())

    def test_update_rejects_unversioned_target_before_network(self):
        completed = subprocess.run(
            ["bash", str(ROOT / "update.sh"), "--to", "latest"],
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("vX.Y.Z", completed.stdout)

    def test_versioned_update_installs_tag_without_switching_worktree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            # Keep this fixture pinned to the version represented by its tag,
            # independent of the current worktree's suite version.
            (repo / "_shared" / "SUITE_VERSION").write_text("0.4.0\n", encoding="utf-8")
            commands = (
                ["git", "init", "-q"],
                ["git", "config", "user.name", "EdgeLab Test"],
                ["git", "config", "user.email", "test@example.invalid"],
                ["git", "add", "."],
                ["git", "commit", "-qm", "fixture"],
                ["git", "tag", "v0.4.0"],
            )
            for command in commands:
                completed = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            origin = root / "origin.git"
            subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
            subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)
            subprocess.run(["git", "push", "-q", "origin", "refs/tags/v0.4.0"], cwd=repo, check=True)
            # A same-named local tag must not override the published tag.
            (repo / "_shared" / "SUITE_VERSION").write_text("9.9.9\n", encoding="utf-8")
            subprocess.run(["git", "add", "_shared/SUITE_VERSION"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "unpublished local commit"], cwd=repo, check=True)
            subprocess.run(["git", "tag", "-f", "v0.4.0"], cwd=repo, check=True, capture_output=True)
            before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            home = root / "home"
            (home / ".codex").mkdir(parents=True)
            stale = home / ".codex" / "skills" / "elab-newer-only"
            stale.mkdir(parents=True)
            (stale / "SKILL.md").write_text("must be removed\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(home)
            completed = subprocess.run(
                ["bash", str(repo / "update.sh"), "--to", "v0.4.0"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
            )
            after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(before, after)
            self.assertIn("已安装/回退到 EdgeLab Skills 0.4.0", completed.stdout)
            installed = home / ".codex" / "skills"
            self.assertEqual((installed / "_shared" / "SUITE_VERSION").read_text().strip(), "0.4.0")
            self.assertTrue((installed / "elab" / "SKILL.md").is_file())
            self.assertFalse((installed / "elab-newer-only").exists())

    def test_versioned_update_can_rollback_to_legacy_tag_without_version_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            commands = (
                ["git", "init", "-q"],
                ["git", "config", "user.name", "EdgeLab Test"],
                ["git", "config", "user.email", "test@example.invalid"],
                ["git", "add", "."],
                ["git", "commit", "-qm", "fixture"],
            )
            for command in commands:
                completed = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            (repo / "_shared" / "SUITE_VERSION").unlink()
            subprocess.run(["git", "add", "-u"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "legacy fixture"], cwd=repo, check=True)
            subprocess.run(["git", "tag", "v0.3.0"], cwd=repo, check=True)
            origin = root / "origin.git"
            subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
            subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=repo, check=True)
            subprocess.run(["git", "push", "-q", "origin", "refs/tags/v0.3.0"], cwd=repo, check=True)
            home = root / "home"
            (home / ".codex").mkdir(parents=True)
            env = os.environ.copy()
            env["HOME"] = str(home)
            completed = subprocess.run(
                ["bash", str(repo / "update.sh"), "--to", "v0.3.0"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("版本号取自 Git tag", completed.stdout)
            self.assertIn("EdgeLab Skills 0.3.0", completed.stdout)
            installed = home / ".codex" / "skills"
            self.assertTrue((installed / "elab" / "SKILL.md").is_file())
            self.assertFalse((installed / "_shared" / "SUITE_VERSION").exists())

    def test_public_connector_files_do_not_contain_eval_assets(self):
        public_files = [
            ROOT / "_shared" / "broker-connectors.md",
            ROOT / "_shared" / "scripts" / "broker_profile.py",
        ]
        forbidden = ("goldset", "judge prompt", "expected answer", "case_id", "rubric")
        for path in public_files:
            lowered = path.read_text(encoding="utf-8").lower()
            for term in forbidden:
                self.assertNotIn(term, lowered, f"{term} leaked into {path}")


if __name__ == "__main__":
    unittest.main()

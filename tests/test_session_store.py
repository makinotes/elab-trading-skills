"""Public, synthetic tests for append-only session snapshot storage."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "elab-save" / "scripts" / "session_store.py"
SPEC = importlib.util.spec_from_file_location("session_store", SCRIPT)
assert SPEC and SPEC.loader
STORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STORE)


def example():
    return {
        "title": "回款观察 / 待核：练习",
        "source_skill": "elab-save",
        "next_skill": "",
        "data_classification": "private",
        "sources": [{"id": "user-note", "classification": "private",
                     "reference": "用户提供的虚构练习记录"}],
        "body": "## 关键判断\n[来源 user-note] 原判断保持不变。\n\n"
                "## 已排除的方向\n无。\n\n"
                "## 待回填假设\n[待验证] 后续材料仍缺失。\n\n"
                "## 下一步\n本次讨论已经收口，后续研究单独继续。\n",
    }


class SessionStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "含 空格的状态根"

    def tearDown(self):
        self.temporary.cleanup()

    def save(self, payload=None, status="open", slug="research-notes"):
        return STORE.save_snapshot(example() if payload is None else payload,
                                   self.root, slug, status)

    def cli(self, payload=None, *, raw=None, status="open", input_path="-"):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "save", "--state-root", str(self.root),
             "--slug", "research-notes", "--status", status, "--input", str(input_path)],
            input=(json.dumps(example() if payload is None else payload, ensure_ascii=False)
                   if raw is None else raw),
            text=True, capture_output=True, check=False,
        )

    def test_cli_resolved_keeps_pending_body_and_has_verifiable_receipt(self):
        before = datetime.now().astimezone()
        result = self.cli(status="resolved")
        after = datetime.now().astimezone()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        path = Path(receipt["path"])
        saved = path.read_bytes()
        self.assertEqual(receipt["status"], "resolved")
        self.assertIn('status: "resolved"', saved.decode())
        self.assertIn("[待验证] 后续材料仍缺失。", saved.decode())
        self.assertNotIn("body", receipt)
        self.assertNotIn("后续材料", result.stdout)
        self.assertEqual(receipt["sha256"], hashlib.sha256(saved).hexdigest())
        created = datetime.fromisoformat(receipt["saved_at"])
        self.assertEqual(receipt["created"], created.date().isoformat())
        self.assertIn('created: "' + created.date().isoformat() + '"', saved.decode())
        self.assertLessEqual(before.replace(microsecond=0), created)
        self.assertLessEqual(created, after)
        self.assertTrue(path.name.startswith(created.strftime("%Y%m%d-%H%M%S")))
        self.assertIn("回款观察", path.name)
        self.assertNotIn("/", path.name)
        self.assertEqual(path.parent, self.root.resolve() / "sessions" / "research-notes")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        for directory in (self.root, self.root / "sessions", path.parent):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertTrue(saved.decode().endswith(example()["body"]))

    def test_regular_file_input_and_no_environment_change(self):
        input_path = self.base / "中文 输入.json"
        input_path.write_text(json.dumps(example(), ensure_ascii=False), encoding="utf-8")
        environment = os.environ.copy()
        result = self.cli(input_path=input_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.environ, environment)
        self.assertEqual(STORE.load_input(str(input_path)), example())

    def test_explicit_status_conflict_is_rejected_before_creating_state(self):
        payload = example()
        payload["status"] = "open"
        result = self.cli(payload, status="resolved")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.root.exists())
        payload["status"] = "resolved"
        self.assertEqual(self.cli(payload, status="resolved").returncode, 0)

    def test_collision_never_overwrites_even_with_identical_timestamp_and_title(self):
        fixed = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with mock.patch.object(STORE, "datetime") as clock:
            clock.now.return_value = fixed
            first = self.save()
            original = Path(first["path"]).read_bytes()
            second = self.save()
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(Path(first["path"]).read_bytes(), original)
        self.assertTrue(Path(second["path"]).name.endswith("-1.md"))

    def test_slug_and_root_traversal_rejected(self):
        for slug in ("..", "../escape", "a/b", "a\\b", "a.b", "", "/absolute",
                     "中文", "MixedCase", "under_score"):
            with self.subTest(slug=slug), self.assertRaises(STORE.StoreError):
                self.save(slug=slug)
        with self.assertRaises(STORE.StoreError):
            STORE.save_snapshot(example(), self.base / "child" / ".." / "escape", "safe", "open")
        self.assertFalse(self.root.exists())
        self.assertFalse((self.base / "escape").exists())

    def test_root_and_descendant_symlinks_do_not_escape(self):
        outside = self.base / "outside"
        outside.mkdir()
        for level in ("root", "sessions", "slug"):
            root = self.base / ("root-" + level)
            if level == "root":
                root.symlink_to(outside, target_is_directory=True)
            else:
                root.mkdir()
                if level == "sessions":
                    (root / "sessions").symlink_to(outside, target_is_directory=True)
                else:
                    (root / "sessions").mkdir()
                    (root / "sessions" / "safe").symlink_to(outside, target_is_directory=True)
            with self.subTest(level=level), self.assertRaises(STORE.StoreError):
                STORE.save_snapshot(example(), root, "safe", "open")
        self.assertEqual(list(outside.iterdir()), [])

    def test_explicit_ancestor_alias_is_canonicalized_but_not_changed(self):
        actual = self.base / "actual"
        actual.mkdir()
        alias = self.base / "ancestor-link"
        alias.symlink_to(actual, target_is_directory=True)
        receipt = STORE.save_snapshot(example(), alias / "state", "safe", "open")
        self.assertEqual(Path(receipt["path"]).parent, actual.resolve() / "state/sessions/safe")
        self.assertTrue(alias.is_symlink())

    def test_input_symlink_directory_and_fifo_are_rejected(self):
        regular = self.base / "input.json"
        regular.write_text(json.dumps(example()), encoding="utf-8")
        link = self.base / "input-link.json"
        link.symlink_to(regular)
        fifo = self.base / "pipe"
        os.mkfifo(fifo)
        for path in (link, self.base, fifo):
            with self.subTest(path=path), self.assertRaises(STORE.StoreError):
                STORE.load_input(str(path))
        self.assertFalse(self.root.exists())

    def test_malformed_duplicate_non_object_and_nonfinite_json_rejected(self):
        for raw in ("{", "[]", '{"title":"a","title":"b"}', '{"title":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(STORE.StoreError):
                STORE.load_input("-", io.StringIO(raw))
        self.assertFalse(self.root.exists())

    def test_unknown_fields_and_strict_source_types_are_rejected(self):
        bad_sources = [None, {}, [], [None], [{"id": "a"}],
                       [{"id": "a", "classification": "invalid", "reference": "demo"}],
                       [{"id": [], "classification": "public", "reference": "demo"}],
                       [{"id": "a", "classification": "public", "reference": 3}],
                       [{"id": "a", "classification": "public", "reference": "demo", "extra": 1}],
                       [example()["sources"][0], example()["sources"][0]]]
        for sources in bad_sources:
            payload = example()
            payload["sources"] = sources
            with self.subTest(sources=sources), self.assertRaises(STORE.StoreError):
                self.save(payload)
        for field, value in (("title", 1), ("body", []), ("source_skill", None),
                             ("next_skill", False), ("data_classification", [])):
            payload = example()
            payload[field] = value
            with self.subTest(field=field), self.assertRaises(STORE.StoreError):
                self.save(payload)
        payload = example()
        payload["unexpected"] = "not accepted"
        with self.assertRaises(STORE.StoreError):
            self.save(payload)
        self.assertFalse(self.root.exists())

    def test_required_sections_and_declared_source_references(self):
        replacements = [example()["body"].replace("## 下一步", "## 其他"),
                        example()["body"].replace("[来源 user-note]", "[来源 missing]"),
                        example()["body"].replace("[来源 user-note]", "[来源]"),
                        example()["body"].replace("[来源 user-note]", ""),
                        "```markdown\n" + example()["body"] + "```\n",
                        example()["body"] + "```\nunclosed",
                        example()["body"].replace("无。", "")]
        for body in replacements:
            payload = example()
            payload["body"] = body
            with self.subTest(body=body), self.assertRaises(STORE.StoreError):
                self.save(payload)
        self.assertFalse(self.root.exists())

    def test_multiple_source_references_and_optional_next_skill(self):
        payload = example()
        payload.pop("next_skill")
        payload["sources"].append({"id": "public-note", "classification": "public", "reference": "演示"})
        payload["body"] = payload["body"].replace("[来源 user-note]", "[来源 user-note, public-note]")
        self.save(payload)
        payload["next_skill"] = None
        self.save(payload)

    def test_public_cannot_downgrade_any_restricted_source(self):
        for classification in ("member", "private", "unknown"):
            payload = example()
            payload["data_classification"] = "public"
            payload["sources"][0]["classification"] = classification
            with self.subTest(classification=classification), self.assertRaises(STORE.StoreError):
                self.save(payload)
        self.assertFalse(self.root.exists())

    def test_documented_conversation_example_runs_through_cli(self):
        document = (ROOT / "elab-save/references/session-input.md").read_text(encoding="utf-8")
        match = re.search(r"```json\n(.*?)\n```", document, re.S)
        self.assertIsNotNone(match)
        payload = json.loads(match[1])
        self.assertEqual(payload["source_skill"], "对话")
        result = self.cli(payload, status="resolved")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "resolved")

    def test_state_root_parent_must_already_exist(self):
        missing_parent = self.base / "not-created"
        with self.assertRaises(STORE.StoreError):
            STORE.save_snapshot(example(), missing_parent / "state", "safe", "open")
        self.assertFalse(missing_parent.exists())

    def test_previous_snapshot_is_only_a_same_project_regular_filename(self):
        first = self.save()
        payload = example()
        payload["previous_snapshot"] = Path(first["path"]).name
        receipt = self.save(payload, status="resolved")
        self.assertIn('previous_snapshot: "', Path(receipt["path"]).read_text())
        for previous in ("../old.md", first["path"], "20240102-030405-missing.md"):
            payload["previous_snapshot"] = previous
            with self.subTest(previous=previous), self.assertRaises(STORE.StoreError):
                self.save(payload)
        link = Path(first["path"]).parent / "20240102-030405-link.md"
        link.symlink_to(Path(first["path"]))
        payload["previous_snapshot"] = link.name
        with self.assertRaises(STORE.StoreError):
            self.save(payload)

    def test_json_quoted_header_cannot_inject_yaml_fields(self):
        payload = example()
        payload["title"] = '中文标题" : [value] # 注释'
        payload["sources"][0]["reference"] = '引文"\nstatus: resolved\n---\n恶意外层'
        receipt = self.save(payload)
        header = Path(receipt["path"]).read_text().split("---\n", 2)[1]
        self.assertEqual(header.count("status:"), 2)  # one real field, one escaped string
        self.assertEqual(sum(line.startswith("status:") for line in header.splitlines()), 1)
        title_line = next(line for line in header.splitlines() if line.startswith("title:"))
        self.assertEqual(json.loads(title_line.split(": ", 1)[1]), payload["title"])
        reference_line = next(line for line in header.splitlines() if line.startswith("    reference:"))
        self.assertEqual(json.loads(reference_line.split(": ", 1)[1]), payload["sources"][0]["reference"])

    def test_credential_assignments_rejected_without_echo_or_state(self):
        harmless = "synthetic-value-not-a-real-credential"
        snippets = ["pass" + "word = " + harmless,
                    "api_" + "key: " + harmless,
                    "private_" + "key: " + harmless,
                    '"access_' + 'token": "' + harmless + '"',
                    "Authorization" + ": Bearer " + harmless,
                    "密码" + "：" + harmless,
                    "-----BEGIN " + "PRIVATE KEY-----\n" + harmless]
        for snippet in snippets:
            payload = example()
            payload["body"] += "\n" + snippet
            with self.subTest(kind=snippet.split()[0]):
                result = self.cli(payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(harmless, result.stdout + result.stderr)
                self.assertFalse(self.root.exists())
        payload = example()
        payload["sources"][0]["reference"] = "token" + "=" + harmless
        self.assertNotEqual(self.cli(payload).returncode, 0)
        self.assertFalse(self.root.exists())

    def test_redacted_assignment_is_allowed_but_not_a_general_secret_claim(self):
        payload = example()
        payload["body"] += "\npassword" + " = [REDACTED]\n"
        self.save(payload)

    def test_explicit_full_account_identifiers_rejected_without_echo_or_state(self):
        identifier = "synthetic-account-not-a-real-identifier"
        for label in ("account_id", "account_number", "账户号", "完整账号"):
            payload = example()
            payload["body"] += "\n" + label + ": " + identifier
            with self.subTest(label=label):
                result = self.cli(payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(identifier, result.stdout + result.stderr)
                self.assertFalse(self.root.exists())

    def test_account_alias_tail_note_and_redacted_identifier_remain_allowed(self):
        payload = example()
        payload["body"] += "\naccount_alias: 演示账户\n账户尾号：4321\naccount_id: [REDACTED]\n"
        self.save(payload)

    def test_prefixed_chinese_sensitive_assignments_rejected_without_echo_or_state(self):
        harmless = "synthetic-value-not-a-real-credential"
        for label in ("测试口令", "我的密码", "演示密钥", "连接私钥", "我的账户号", "我的完整账号"):
            payload = example()
            payload["body"] += "\n" + label + "：" + harmless
            with self.subTest(label=label):
                result = self.cli(payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(harmless, result.stdout + result.stderr)
                self.assertFalse(self.root.exists())

    def test_prefixed_redactions_and_longer_english_identifiers_remain_allowed(self):
        payload = example()
        payload["body"] += ("\n测试口令：[REDACTED]\n我的密码：[已脱敏]\n我的账户号：不记录\n"
                            "previous_token: 普通展示标签\naccount_id_hint: 仅使用别名\n")
        self.save(payload)

    def test_write_failure_removes_only_new_file_and_retains_old_snapshot(self):
        first = self.save()
        old_path = Path(first["path"])
        original = old_path.read_bytes()

        def fail_after_partial_write(fd, _content):
            os.write(fd, b"partial content")
            raise OSError("synthetic disk failure")

        with mock.patch.object(STORE, "_write_all", side_effect=fail_after_partial_write):
            with self.assertRaises(STORE.StoreError):
                self.save()
        self.assertEqual(old_path.read_bytes(), original)
        self.assertEqual(list(old_path.parent.iterdir()), [old_path])

    def test_readback_failure_removes_only_new_file(self):
        first = self.save()
        old_path = Path(first["path"])
        old_hash = hashlib.sha256(old_path.read_bytes()).hexdigest()
        with mock.patch.object(STORE, "_readback", return_value=b"corrupted"):
            with self.assertRaises(STORE.StoreError):
                self.save()
        self.assertEqual(hashlib.sha256(old_path.read_bytes()).hexdigest(), old_hash)
        self.assertEqual(list(old_path.parent.iterdir()), [old_path])

    def test_collision_with_symlink_does_not_write_its_target(self):
        first = self.save()
        path = Path(first["path"])
        outside = self.base / "keep.txt"
        outside.write_text("unchanged", encoding="utf-8")
        path.unlink()
        path.symlink_to(outside)
        frozen = datetime.fromisoformat(first["saved_at"])
        with mock.patch.object(STORE, "datetime") as clock:
            clock.now.return_value = frozen
            second = self.save()
        self.assertTrue(path.is_symlink())
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(outside.read_text(), "unchanged")

    def test_input_size_limit_and_long_chinese_filename(self):
        with self.assertRaises(STORE.StoreError):
            STORE.load_input("-", io.StringIO("x" * (STORE.MAX_INPUT_BYTES + 1)))
        payload = example()
        payload["title"] = "中文练习" * 45
        receipt = self.save(payload)
        self.assertLess(len(Path(receipt["path"]).name.encode("utf-8")), 255)
        self.assertEqual(receipt["title"], payload["title"])


if __name__ == "__main__":
    unittest.main()

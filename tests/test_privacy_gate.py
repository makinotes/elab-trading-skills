from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_GATE = Path(__file__).resolve().parents[1] / "scripts" / "privacy_gate.py"


class PrivacyGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(SOURCE_GATE, self.root / "scripts" / "privacy_gate.py")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_gate(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "scripts/privacy_gate.py"],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_clean_product_file_passes(self) -> None:
        (self.root / "README.md").write_text("Public product documentation.\n")
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PRIVACY_GATE=PASS", result.stdout)

    def test_private_path_fails_without_echoing_content(self) -> None:
        path = self.root / "_data" / "myself" / "notes.md"
        path.parent.mkdir(parents=True)
        path.write_text("private sentence that must not be printed\n")
        result = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn("_data/myself/notes.md", result.stdout)
        self.assertNotIn("private sentence", result.stdout)

    def test_internal_evaluation_paths_fail(self) -> None:
        for relative in ("eval/run/result.json", "tests/goldset-v1.md"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic fixture\n")
            result = self.run_gate()
            self.assertEqual(result.returncode, 1)
            self.assertIn(relative, result.stdout)
            path.unlink()

    def test_feishu_locator_marker_fails_without_echoing_value(self) -> None:
        secret_value = "REDACTED_TEST_VALUE"
        (self.root / "notes.md").write_text(
            f"MYSELF_FEISHU_DOC_TOKEN={secret_value}\n"
        )
        result = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn("notes.md", result.stdout)
        self.assertNotIn(secret_value, result.stdout)

    def test_policy_fixture_does_not_whitelist_embedded_locator(self) -> None:
        locator = "oc_" + "x" * 24
        path = self.root / "tests" / "test_privacy_gate.py"
        path.parent.mkdir(parents=True)
        path.write_text(f"embedded = {locator}\n")
        result = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn("tests/test_privacy_gate.py", result.stdout)
        self.assertNotIn(locator, result.stdout)

    def test_internal_detail_in_ordinary_document_fails(self) -> None:
        content = "goldset" + " case " + str(42) + " internal acceptance\n"
        (self.root / "notes.md").write_text(content)
        result = self.run_gate()
        self.assertEqual(result.returncode, 1)
        self.assertIn("internal evaluation detail", result.stdout)
        self.assertNotIn(content.strip(), result.stdout)

    def test_boundary_documentation_is_not_an_evaluation_result(self) -> None:
        (self.root / "CONTRIBUTING.md").write_text(
            "Goldset、评分结果和标准答案只保存在私有仓。\n"
        )
        result = self.run_gate()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_credential_patterns_are_blocked_even_in_policy_tests(self) -> None:
        fixtures = ["mk_live_" + "x" * 32, "ghp_" + "x" * 36,
                    "sk-" + "x" * 32, "-----BEGIN " + "PRIVATE KEY-----"]
        for relative in ("config.json", "tests/test_privacy_gate.py"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            for value in fixtures:
                with self.subTest(path=relative, kind=value[:8]):
                    path.write_text(value)
                    result = self.run_gate()
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertNotIn(value, result.stdout)
            path.unlink()

    def test_machine_paths_do_not_require_a_specific_username(self) -> None:
        for prefix in ("/Users/", "/home/"):
            value = prefix + "fictional-owner" + "/private/file.txt"
            (self.root / "notes.md").write_text(value)
            result = self.run_gate()
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertNotIn(value, result.stdout)

    def test_staged_gate_reads_index_not_unstaged_cleanup(self) -> None:
        path = self.root / "notes.md"
        value = "mk_live_" + "x" * 32
        path.write_text(value)
        subprocess.run(["git", "add", "notes.md"], cwd=self.root, check=True)
        path.write_text("Clean worktree, unsafe index.\n")
        result = subprocess.run(["python3", "scripts/privacy_gate.py", "--staged"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("notes.md", result.stdout)
        self.assertNotIn(value, result.stdout)


if __name__ == "__main__":
    unittest.main()

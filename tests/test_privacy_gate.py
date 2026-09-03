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


if __name__ == "__main__":
    unittest.main()

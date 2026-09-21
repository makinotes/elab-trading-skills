"""Guard the README against silent drift.

The suite version was once written into README prose in both Chinese and
English. A patch release bumped SUITE_VERSION and the frontmatter but not the
prose, so both language sections advertised a stale version. Volatile facts
belong in one place; these tests keep them out of the README.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

# "版本：0.6.0" / "suite version: 0.6.0" and similar.
HARDCODED_VERSION = re.compile(
    r"(?:套件版本|当前版本|suite version|current version)[^\n]{0,40}?\d+\.\d+\.\d+",
    re.IGNORECASE,
)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE = re.compile(r'<img[^>]+src="([^"]+)"')


class ReadmeConsistencyTest(unittest.TestCase):
    def setUp(self):
        self.text = README.read_text(encoding="utf-8")

    def test_readme_does_not_hardcode_the_suite_version(self):
        found = HARDCODED_VERSION.findall(self.text)
        self.assertEqual(
            found,
            [],
            "README must not state the suite version; point at the release "
            f"badge or _shared/SUITE_VERSION instead. Found: {found}",
        )

    def test_english_section_and_its_anchor_agree(self):
        self.assertIn("\n## English\n", self.text)
        self.assertIn("(#english)", self.text)

    def test_relative_links_and_images_resolve(self):
        targets = set(MARKDOWN_LINK.findall(self.text)) | set(
            HTML_IMAGE.findall(self.text)
        )
        missing = sorted(
            target
            for target in targets
            if not target.startswith(("http://", "https://", "#", "mailto:"))
            and not (ROOT / target.split("#", 1)[0]).exists()
        )
        self.assertEqual(missing, [], f"README points at missing files: {missing}")

    def test_changelog_latest_release_matches_suite_source(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first_release = re.search(r"^## .*?EdgeLab Skills (\d+\.\d+\.\d+)", text, re.M)
        self.assertIsNotNone(first_release)
        version = (ROOT / "_shared" / "SUITE_VERSION").read_text().strip()
        self.assertEqual(first_release.group(1), version)
        self.assertNotRegex(text, re.compile(r"^## 当前源码版本.*\d+\.\d+\.\d+", re.M))
        self.assertNotIn("| **EdgeLab Skills suite** |", text)


if __name__ == "__main__":
    unittest.main()

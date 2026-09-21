"""Installation transactions use only synthetic suites and temporary homes."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("install_runtime", ROOT / "scripts/install_runtime.py")
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


def make_source(root, extra=False):
    for name in ("elab", "elab-old") if extra else ("elab",):
        unit = root / name
        unit.mkdir(parents=True)
        (unit / "SKILL.md").write_text(f"---\nname: {name}\n---\n# EdgeLab fixture\n")
    shared = root / "_shared"
    shared.mkdir()
    (shared / "credit.md").write_text("# EdgeLab 署名规范（SSOT）\n")
    (shared / "SUITE_VERSION").write_text("1.0.0\n")
    return root


def snapshot(root):
    output = {}
    if not root.exists():
        return output
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            key = path.relative_to(root).as_posix()
            output[key] = ("link", os.readlink(path)) if path.is_symlink() else (
                ("dir",) if path.is_dir() else ("file", path.read_bytes()))
    return output


class InstallSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = make_source(self.root / "source")
        self.home = self.root / "home"
        self.home.mkdir()
        self.dest = self.home / ".codex" / "skills"

    def tearDown(self):
        self.temporary.cleanup()

    def plan(self, dest=None, mode="copy", source=None):
        source = source or self.source
        return INSTALL.plan_install(source, dest or self.dest, mode, "1.0.0", source, [source])

    def install(self, dest=None, mode="copy", source=None):
        INSTALL.apply_plans([self.plan(dest, mode, source)])

    def test_entry_does_not_authorize_foreign_shared_and_other_runtime_is_unchanged(self):
        first = self.home / ".claude" / "skills"
        self.install(first)
        self.dest.mkdir(parents=True)
        shutil.copytree(self.source / "elab", self.dest / "elab")
        (self.dest / "_shared").mkdir()
        (self.dest / "_shared" / "foreign.txt").write_text("keep")
        before = snapshot(self.home)
        with self.assertRaisesRegex(INSTALL.InstallError, "无法确认属于 EdgeLab"):
            plans = [self.plan(first), self.plan(self.dest)]
            INSTALL.apply_plans(plans)
        self.assertEqual(snapshot(self.home), before)

    def test_copy_preserves_mixed_shared_and_third_party_extensions(self):
        self.install()
        (self.dest / "_shared" / "foreign.txt").write_text("keep shared data")
        extension = self.dest / "elab-third-party"
        extension.mkdir()
        (extension / "SKILL.md").write_text("third party")
        (self.source / "_shared" / "credit.md").write_text("# EdgeLab 署名规范（SSOT）\nnew")
        self.install()
        self.assertEqual((self.dest / "_shared" / "foreign.txt").read_text(), "keep shared data")
        self.assertEqual((extension / "SKILL.md").read_text(), "third party")
        self.assertTrue((self.dest / "_shared" / "credit.md").read_text().endswith("new"))
        manifest = json.loads((self.dest / INSTALL.MANIFEST).read_text())
        self.assertNotIn("foreign.txt", manifest["units"]["_shared"]["files"])

    def test_legacy_mixed_shared_adopts_only_known_paths(self):
        shutil.copytree(self.source, self.dest)
        (self.dest / "_shared" / "foreign.txt").write_text("keep")
        self.install()
        self.assertEqual((self.dest / "_shared" / "foreign.txt").read_text(), "keep")

    def test_legacy_marker_does_not_authorize_foreign_same_path_file(self):
        (self.source / "_shared" / "schema.md").write_text("# EdgeLab 共享契约\n")
        shutil.copytree(self.source, self.dest)
        foreign = self.dest / "_shared" / "schema.md"
        foreign.write_text("FOREIGN SCHEMA MUST SURVIVE")
        before = snapshot(self.home)
        with self.assertRaisesRegex(INSTALL.InstallError, "无法确认旧安装文件归属"):
            self.install()
        self.assertEqual(snapshot(self.home), before)

    def test_legacy_release_bytes_can_migrate_without_overwriting_unknowns(self):
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic old release")
        self.git("tag", "v1.0.0")
        self.dest.mkdir(parents=True)
        for name in ("elab", "_shared"):
            shutil.copytree(self.source / name, self.dest / name)
        (self.dest / "_shared" / "foreign.txt").write_text("keep")
        (self.source / "elab" / "SKILL.md").write_text("---\nname: elab\n---\nEdgeLab updated")
        (self.source / "_shared" / "credit.md").write_text("# EdgeLab 署名规范\nupdated")
        self.install()
        self.assertEqual((self.dest / "elab" / "SKILL.md").read_bytes(),
                         (self.source / "elab" / "SKILL.md").read_bytes())
        self.assertEqual((self.dest / "_shared" / "foreign.txt").read_text(), "keep")
        self.assertTrue((self.dest / INSTALL.MANIFEST).is_file())

    def test_link_refuses_to_hide_mixed_shared_content(self):
        self.install()
        (self.dest / "_shared" / "foreign.txt").write_text("keep")
        before = snapshot(self.home)
        with self.assertRaisesRegex(INSTALL.InstallError, "混合目录"):
            self.install(mode="link")
        self.assertEqual(snapshot(self.home), before)

    def test_removes_only_obsolete_owned_files(self):
        source = make_source(self.root / "older-source", extra=True)
        self.install(source=source)
        (self.dest / "elab-old" / "personal.txt").write_text("preserve")
        self.install()
        self.assertFalse((self.dest / "elab-old" / "SKILL.md").exists())
        self.assertEqual((self.dest / "elab-old" / "personal.txt").read_text(), "preserve")

    def test_source_nested_in_replaced_unit_is_rejected(self):
        source = make_source(self.dest / "elab" / "repo")
        (self.dest / "elab" / "SKILL.md").write_text("---\nname: elab\n---\nEdgeLab")
        before = snapshot(self.home)
        with self.assertRaisesRegex(INSTALL.InstallError, "相交"):
            self.install(source=source)
        self.assertEqual(snapshot(self.home), before)

    def test_symlink_parent_cannot_redirect_an_owned_file_write(self):
        (self.source / "_shared" / "scripts").mkdir()
        (self.source / "_shared" / "scripts" / "helper.py").write_text("old")
        self.install()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "helper.py").write_text("keep")
        shutil.rmtree(self.dest / "_shared" / "scripts")
        (self.dest / "_shared" / "scripts").symlink_to(outside)
        with self.assertRaises(INSTALL.InstallError):
            self.install()
        self.assertEqual((outside / "helper.py").read_text(), "keep")

    def test_second_runtime_staging_failure_changes_no_installation(self):
        first = self.home / ".claude" / "skills"
        self.install(first)
        self.install()
        before = snapshot(self.home)
        (self.source / "elab" / "SKILL.md").write_text("---\nname: elab\n---\nEdgeLab new")
        copy = shutil.copy2

        def failing_copy(source, target, *args, **kwargs):
            if str(target).startswith(str(self.dest)):
                raise OSError("synthetic disk full")
            return copy(source, target, *args, **kwargs)

        with mock.patch.object(INSTALL.shutil, "copy2", side_effect=failing_copy):
            with self.assertRaisesRegex(OSError, "disk full"):
                INSTALL.apply_plans([self.plan(first), self.plan()])
        self.assertEqual(snapshot(self.home), before)

    def test_second_runtime_commit_failure_rolls_back_all_targets(self):
        first = self.home / ".claude" / "skills"
        self.install(first)
        self.install()
        before = snapshot(self.home)
        (self.source / "elab" / "SKILL.md").write_text("---\nname: elab\n---\nEdgeLab new")
        replace = os.replace
        failed = False

        def failing_replace(source, target):
            nonlocal failed
            if target == self.dest / "elab" and "fresh" in Path(source).parts and not failed:
                failed = True
                raise OSError("synthetic rename failure")
            return replace(source, target)

        with mock.patch.object(INSTALL.os, "replace", side_effect=failing_replace):
            with self.assertRaisesRegex(OSError, "rename failure"):
                INSTALL.apply_plans([self.plan(first), self.plan()])
        self.assertTrue(failed)
        self.assertEqual(snapshot(self.home), before)

    def test_interrupt_after_backup_rename_preserves_old_installation(self):
        self.install()
        (self.dest / "_shared" / "personal.txt").write_text("must survive")
        before = snapshot(self.home)
        replace = os.replace
        interrupted = False

        def interrupt_after_rename(source, target):
            nonlocal interrupted
            replace(source, target)
            if "backup" in Path(target).parts and not interrupted:
                interrupted = True
                raise KeyboardInterrupt()

        with mock.patch.object(INSTALL.os, "replace", side_effect=interrupt_after_rename):
            with self.assertRaises(KeyboardInterrupt):
                self.install()
        self.assertTrue(interrupted)
        self.assertEqual(snapshot(self.home), before)

    def test_copy_link_copy_and_legacy_rollback(self):
        self.install()
        self.install(mode="link")
        self.assertTrue((self.dest / "elab").is_symlink())
        legacy = make_source(self.root / "legacy")
        (legacy / "_shared" / "SUITE_VERSION").unlink()
        self.install(source=legacy)
        self.assertFalse((self.dest / "elab").is_symlink())
        self.assertFalse((self.dest / "_shared" / "SUITE_VERSION").exists())
        self.assertTrue((self.source / "_shared" / "SUITE_VERSION").exists())

    def test_update_skips_runtime_without_suite_even_with_foreign_shared(self):
        self.install()
        foreign = self.home / ".claude" / "skills" / "_shared"
        foreign.mkdir(parents=True)
        (foreign / "keep.txt").write_text("foreign")
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            status = INSTALL.main(["--source", str(self.source), "--version", "1.0.0", "--update"])
        self.assertEqual(status, 0)
        self.assertFalse((foreign.parent / "elab").exists())
        self.assertEqual((foreign / "keep.txt").read_text(), "foreign")

    def test_manifest_path_traversal_is_rejected(self):
        self.install()
        path = self.dest / INSTALL.MANIFEST
        data = json.loads(path.read_text())
        data["units"]["elab"]["files"].append("../../keep.txt")
        path.write_text(json.dumps(data))
        before = snapshot(self.home)
        with self.assertRaisesRegex(INSTALL.InstallError, "清单无效"):
            self.install()
        self.assertEqual(snapshot(self.home), before)

    def test_finalize_failure_rolls_back_links_and_copies(self):
        self.install(mode="link")
        before = snapshot(self.home)

        def fail():
            raise INSTALL.InstallError("checkout changed")

        with self.assertRaisesRegex(INSTALL.InstallError, "checkout changed"):
            INSTALL.apply_plans([self.plan(mode="copy")], fail)
        self.assertEqual(snapshot(self.home), before)

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.source,
                              env=dict(os.environ, HOME=str(self.home)),
                              text=True, capture_output=True, check=True).stdout.strip()

    def prepare_upstream(self, broken_filter=False):
        for file in ("install.sh", "update.sh"):
            shutil.copy2(ROOT / file, self.source / file)
        (self.source / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts" / "install_runtime.py",
                     self.source / "scripts" / "install_runtime.py")
        (self.source / "CHANGELOG.md").write_text("Synthetic release\n")
        if broken_filter:
            (self.source / ".gitattributes").write_text("elab/z-fail.txt filter=broken\n")
            (self.source / ".gitignore").write_text("elab/private-local.txt\n")
            (self.source / "elab" / "a-good.txt").write_text("OLD GOOD")
            (self.source / "elab" / "z-fail.txt").write_text("OLD LAST")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic initial version")
        old = self.git("rev-parse", "HEAD")
        origin = self.root / "origin.git"
        self.git("init", "--bare", "-q", str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-qu", "origin", "main")
        writer = self.root / "writer"
        self.git("clone", "-q", "--branch", "main", str(origin), str(writer))
        self.git("config", "user.name", "Synthetic Test", cwd=writer)
        self.git("config", "user.email", "test@example.invalid", cwd=writer)
        (writer / "_shared" / "SUITE_VERSION").write_text("1.1.0\n")
        (writer / "elab" / "new.txt").write_text("new release")
        if broken_filter:
            (writer / "elab" / "a-good.txt").write_text("NEW GOOD")
            (writer / "elab" / "z-fail.txt").write_text("NEW LAST")
        update_file = writer / "update.sh"
        update_file.write_text(update_file.read_text().replace("set -euo pipefail",
                               "# " + "synthetic padding " * 800 + "\nset -euo pipefail", 1))
        self.git("add", ".", cwd=writer)
        self.git("commit", "-qm", "synthetic next version", cwd=writer)
        self.git("push", "-q", cwd=writer)
        return old, self.git("rev-parse", "HEAD", cwd=writer)

    def update(self, *args):
        return subprocess.run(["bash", str(self.source / "update.sh"), *args],
                              cwd=self.source, text=True, errors="replace", capture_output=True,
                              env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1"))

    def test_default_update_commits_copy_and_link_installs_then_fast_forwards(self):
        old, new = self.prepare_upstream()
        self.install(mode="link")
        copy_dest = self.home / ".claude" / "skills"
        self.install(copy_dest)
        (copy_dest / "_shared" / "personal.txt").write_text("keep")
        (self.home / ".workbuddy").mkdir()
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(old, new)
        self.assertEqual(self.git("rev-parse", "HEAD"), new)
        self.assertTrue((self.dest / "elab").is_symlink())
        for dest in (self.dest, copy_dest):
            self.assertEqual((dest / "elab" / "new.txt").read_text(), "new release")
        self.assertEqual((copy_dest / "_shared" / "personal.txt").read_text(), "keep")
        self.assertFalse((self.home / ".workbuddy" / "skills").exists())

    def test_update_preflight_failure_preserves_link_source_checkout(self):
        old, _ = self.prepare_upstream()
        self.install(mode="link")
        copy_dest = self.home / ".claude" / "skills"
        self.install(copy_dest)
        shutil.rmtree(copy_dest / "_shared")
        (copy_dest / "_shared").mkdir()
        (copy_dest / "_shared" / "foreign.txt").write_text("keep")
        before = snapshot(self.home)
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), old)
        self.assertEqual(snapshot(self.home), before)
        self.assertFalse((self.dest / "elab" / "new.txt").exists())

    def test_failed_git_filter_restores_checkout_links_and_ignored_files(self):
        old, _ = self.prepare_upstream(broken_filter=True)
        (self.source / "elab" / "private-local.txt").write_text("IGNORED LOCAL DATA")
        self.install(mode="link")
        self.git("config", "filter.broken.clean", "cat")
        # git archive invokes the filter too. Permit its first invocation, then
        # fail when the actual update entry point reaches the checkout phase.
        driver = self.root / "smudge.sh"
        marker = self.root / "filter-called"
        driver.write_text('if [ -e "$1" ]; then exit 1; fi\n: > "$1"\ncat\n')
        self.git("config", "filter.broken.smudge",
                 f"sh {shlex.quote(str(driver))} {shlex.quote(str(marker))}")
        self.git("config", "filter.broken.required", "true")
        before = snapshot(self.home)
        result = self.update()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("已恢复原工作树与安装", result.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), old)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(snapshot(self.home), before)
        self.assertEqual((self.dest / "elab" / "a-good.txt").read_text(), "OLD GOOD")
        self.assertEqual((self.dest / "elab" / "z-fail.txt").read_text(), "OLD LAST")
        self.assertEqual((self.dest / "elab" / "private-local.txt").read_text(), "IGNORED LOCAL DATA")
        recovery = list(self.root.glob(".elab-checkout-backup-*"))
        self.assertEqual(len(recovery), 1)
        self.assertEqual((recovery[0] / "after-failure" / "elab" / "a-good.txt").read_text(), "NEW GOOD")

    def test_tag_rollback_to_legacy_does_not_switch_checkout(self):
        _, new = self.prepare_upstream()
        self.install(mode="link")
        writer = self.root / "writer"
        (writer / "_shared" / "SUITE_VERSION").unlink()
        self.git("add", "-u", cwd=writer)
        self.git("commit", "-qm", "synthetic legacy release", cwd=writer)
        self.git("tag", "v0.3.0", cwd=writer)
        self.git("push", "-q", "origin", "v0.3.0", cwd=writer)
        before = self.git("rev-parse", "HEAD")
        result = self.update("--to", "v0.3.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("版本号取自 Git tag", result.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertFalse((self.dest / "elab").is_symlink())
        self.assertTrue((self.dest / "elab" / "new.txt").is_file())
        self.assertFalse((self.dest / "_shared" / "SUITE_VERSION").exists())


if __name__ == "__main__":
    unittest.main()

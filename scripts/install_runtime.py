#!/usr/bin/env python3
"""Install the suite with an ownership manifest and rollback across runtimes."""

from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


MANIFEST = ".elab-install.json"
PRODUCT = "edgelab-skills"
RUNTIMES = ("claude", "codex", "codebuddy", "workbuddy")
UNIT = re.compile(r"elab(?:-[a-z0-9]+)*\Z")


class InstallError(Exception):
    pass


def present(path):
    return path.exists() or path.is_symlink()


def unit_name(name):
    return name == "_shared" or bool(UNIT.fullmatch(name))


def owned_identity(path, name):
    """Legacy adoption needs evidence in the unit itself, never a sibling."""
    try:
        if name == "_shared":
            markers = (("credit.md", "# EdgeLab 署名规范"),
                       ("schema.md", "# EdgeLab 共享契约"))
            return any((path / file).is_file() and
                       (path / file).read_text(encoding="utf-8").startswith(marker)
                       for file, marker in markers)
        text = (path / "SKILL.md").read_text(encoding="utf-8")
        return (bool(re.search(r"^name:\s*" + re.escape(name) + r"\s*$", text, re.M))
                and "EdgeLab" in text)
    except (OSError, UnicodeError):
        return False


def inventory(path, source=False):
    files, dirs = set(), set()
    if not path.is_dir():
        raise InstallError(f"不是可读取目录：{path}")

    def fail(error):
        raise error

    for root, names, leaves in os.walk(path, followlinks=False, onerror=fail):
        for name in list(names):
            item = Path(root) / name
            relative = item.relative_to(path).as_posix()
            if source and name == "__pycache__":
                names.remove(name)
            elif item.is_symlink():
                names.remove(name)
                files.add(relative)
            else:
                dirs.add(relative)
        for name in leaves:
            if source and (name.endswith(".pyc") or name == ".DS_Store"):
                continue
            files.add((Path(root) / name).relative_to(path).as_posix())
    if source and any((path / name).is_symlink() or not (path / name).is_file()
                      for name in files):
        raise InstallError(f"安装源含软链或特殊文件，拒绝读取外部内容：{path}")
    return {"files": sorted(files), "dirs": sorted(dirs)}


def read_manifest(dest):
    path = dest / MANIFEST
    if not present(path):
        return None
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("manifest is not a regular file")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("product") != PRODUCT or data.get("format") != 1
                or data.get("mode") not in ("copy", "link")
                or not isinstance(data.get("units"), dict)):
            raise ValueError("invalid manifest")
        for name, entry in data["units"].items():
            if not unit_name(name) or not isinstance(entry, dict):
                raise ValueError("invalid unit")
            for key in ("files", "dirs"):
                if not isinstance(entry.get(key), list):
                    raise ValueError("invalid inventory")
                for value in entry[key]:
                    if (not isinstance(value, str) or not value
                            or PurePosixPath(value).is_absolute()
                            or ".." in PurePosixPath(value).parts
                            or PurePosixPath(value).as_posix() != value
                            or value == "."):
                        raise ValueError("invalid inventory path")
        return data
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise InstallError(f"安装清单无效，保留现有文件：{path}") from exc


def installed(dest):
    return present(dest / MANIFEST) or owned_identity(dest / "elab", "elab")


def overlap(left, right):
    return left == right or left in right.parents or right in left.parents


def check_slot(dest, name, protected):
    # Resolve parent aliases, but do not follow the unit link being replaced.
    slot = dest.resolve() / name
    if any(overlap(slot, root.resolve()) for root in protected):
        raise InstallError(f"源目录与安装目标相交，拒绝替换：{slot}")


def safe_parents(root, relative):
    for part in (root / relative).relative_to(root).parents:
        if part == Path("."):
            continue
        path = root / part
        if present(path) and (path.is_symlink() or not path.is_dir()):
            raise InstallError(f"管理文件的父路径不是普通目录：{path}")


@lru_cache(maxsize=1024)
def historical_hashes(repo, relative):
    """Read local release objects only; never fetch or expose their contents."""
    try:
        tags = subprocess.check_output(["git", "tag", "--list", "v*"], cwd=repo,
                                       stderr=subprocess.DEVNULL, text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        return frozenset()
    hashes = set()
    for tag in tags:
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
            continue
        result = subprocess.run(["git", "show", f"{tag}:{relative}"], cwd=repo,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            hashes.add(hashlib.sha256(result.stdout).hexdigest())
    return frozenset(hashes)


def legacy_owned_file(source, target, relative, history_root):
    if target.is_symlink() or not target.is_file():
        return False
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return (digest == hashlib.sha256(source.read_bytes()).hexdigest()
            or digest in historical_hashes(history_root, relative))


def plan_install(source, dest, mode, version, link_root, protected):
    old = read_manifest(dest)
    units = {}
    for path in sorted(source.iterdir()):
        if not unit_name(path.name):
            continue
        if path.is_symlink() or not owned_identity(path, path.name):
            raise InstallError(f"无法确认安装源属于 EdgeLab：{path}")
        units[path.name] = inventory(path, source=True)
    if "elab" not in units or "_shared" not in units:
        raise InstallError("安装源缺少 elab 或 _shared")
    old_units = old["units"] if old else {}
    names = sorted(set(units) | set(old_units))
    adopted = {}
    for name in names:
        check_slot(dest, name, protected)
        target = dest / name
        previous = old_units.get(name)
        if not present(target):
            adopted[name] = previous or {"files": [], "dirs": []}
            continue
        if not target.is_dir():
            raise InstallError(f"无法确认属于 EdgeLab，保留现有文件：{target}")
        # Shared directory ownership is always verified independently.
        if (name == "_shared" or previous is None) and not owned_identity(target, name):
            raise InstallError(f"无法确认属于 EdgeLab，保留现有文件：{target}")
        existing = inventory(target)
        # A directory marker does not establish ownership of its other files.
        # Adopt only bytes known from this source or a locally available release.
        if previous is None:
            previous = {key: sorted(set(existing[key]) & set(units[name][key]))
                        for key in ("files", "dirs")}
            for relative in previous["files"]:
                safe_parents(target, relative)
                if not legacy_owned_file(source / name / relative, target / relative,
                                         f"{name}/{relative}", link_root):
                    raise InstallError(
                        f"无法确认旧安装文件归属，保留原目录；请先备份并人工迁移冲突：{target / relative}"
                    )
        adopted[name] = previous
        desired = units.get(name, {"files": [], "dirs": []})
        for relative in set(previous["files"]) | set(desired["files"]):
            safe_parents(target, relative)
            file = target / relative
            if present(file) and file.is_dir() and not file.is_symlink():
                raise InstallError(f"管理文件已变成目录，保留其内容：{file}")
            if (present(file) and relative in desired["files"]
                    and relative not in previous["files"]):
                raise InstallError(f"新版本文件与未管理文件冲突：{file}")
        for relative in desired["dirs"]:
            directory = target / relative
            if present(directory) and (directory.is_symlink() or not directory.is_dir()):
                raise InstallError(f"新版本目录与现有文件冲突：{directory}")
        if mode == "link" and name in units:
            same_link = target.is_symlink() and target.resolve() == (link_root / name).resolve()
            extra = any(set(existing[key]) - set(previous[key]) for key in ("files", "dirs"))
            if extra and not same_link:
                raise InstallError(f"软链模式不能替换混合目录；请使用 --copy 保留未管理内容：{target}")
    check_slot(dest, MANIFEST, protected)
    return {"dest": dest, "source": source, "mode": mode, "link_root": link_root,
            "names": names, "old": adopted, "units": units,
            "manifest": {"product": PRODUCT, "format": 1, "version": version,
                         "mode": mode, "units": units}}


def stage_plan(plan):
    dest = plan["dest"]
    missing = []
    parent = dest
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    plan["created"] = missing
    dest.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=".elab-stage-", dir=dest))
    plan["scratch"] = scratch
    fresh = scratch / "fresh"
    fresh.mkdir()
    (scratch / "backup").mkdir()
    for name in plan["names"]:
        target, output = dest / name, fresh / name
        desired = plan["units"].get(name)
        if plan["mode"] == "link" and desired is not None:
            output.symlink_to(plan["link_root"] / name, target_is_directory=True)
            continue
        if present(target):
            shutil.copytree(target, output, symlinks=True)
        else:
            output.mkdir()
        for relative in plan["old"][name]["files"]:
            file = output / relative
            if present(file):
                file.unlink()
        for relative in sorted(plan["old"][name]["dirs"], key=lambda p: p.count("/"), reverse=True):
            directory = output / relative
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
        if desired is not None:
            for relative in desired["dirs"]:
                (output / relative).mkdir(parents=True, exist_ok=True)
            for relative in desired["files"]:
                shutil.copy2(plan["source"] / name / relative, output / relative)
        elif not any(output.iterdir()):
            output.rmdir()
    (fresh / MANIFEST).write_text(json.dumps(plan["manifest"], ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")


def cleanup_plans(plans):
    for plan in reversed(plans):
        scratch = plan.get("scratch")
        if scratch and scratch.exists():
            shutil.rmtree(scratch)
        for path in plan.get("created", []):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()


def apply_plans(plans, finalize=None):
    """Stage all targets, journal renames, and retain backups until commit."""
    journal = []
    try:
        for plan in plans:
            stage_plan(plan)
        for plan in plans:
            for name in plan["names"] + [MANIFEST]:
                target = plan["dest"] / name
                backup = plan["scratch"] / "backup" / name
                fresh = plan["scratch"] / "fresh" / name
                # Record intent before rename. An interrupt can arrive after the
                # syscall succeeded but before Python can set a completion flag.
                record = [target, backup, fresh, present(fresh)]
                journal.append(record)
                if present(target):
                    os.replace(target, backup)
                if present(fresh):
                    os.replace(fresh, target)
        if finalize:
            finalize()
    except BaseException:
        failures = []
        for target, backup, fresh, had_new in reversed(journal):
            try:
                if had_new and not present(fresh) and present(target):
                    os.replace(target, fresh)
                if present(backup):
                    os.replace(backup, target)
            except OSError as exc:
                failures.append(f"{backup}: {exc}")
        if failures:
            raise InstallError("回滚未全部完成；旧文件保留在以下备份，请勿删除：\n" + "\n".join(failures))
        cleanup_plans(plans)
        raise
    # The installation has committed. Cleanup failure must not undo a checkout
    # fast-forward; old backups remain available and no installed data is lost.
    try:
        cleanup_plans(plans)
    except OSError as exc:
        print(f"安装完成；临时备份清理失败，保留供检查：{exc}")


def advance_checkout(repo, commit, expected_head):
    """Restore checkout bytes directly if Git's filters fail mid-checkout."""
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo)

    head = git("rev-parse", "HEAD").decode().strip()
    if head != expected_head or git("status", "--porcelain"):
        raise InstallError("更新期间 Git 工作树发生变化，已撤销安装替换。")
    changed_paths = git("diff", "--no-renames", "--name-only", "-z", expected_head, commit).decode().split("\0")
    changed_roots = {Path(name).parts[0] for name in changed_paths if name}
    recovery = Path(tempfile.mkdtemp(prefix=".elab-checkout-backup-", dir=repo.parent))
    original = recovery / "original"
    original.mkdir()
    index = Path(git("rev-parse", "--git-path", "index").decode().strip())
    if not index.is_absolute():
        index = repo / index
    try:
        # Copy the affected top-level entries, including ignored local files.
        # Git may delete ignored files during checkout; tracked blobs alone are
        # insufficient to restore the actual previous working tree.
        for name in changed_roots:
            file = repo / name
            target = original / name
            if file.is_dir() and not file.is_symlink():
                shutil.copytree(file, target, symlinks=True)
            elif present(file):
                shutil.copy2(file, target, follow_symlinks=False)
        shutil.copy2(index, recovery / "index")
    except BaseException:
        shutil.rmtree(recovery)
        raise
    # No Git mutation has happened yet; a concurrent edit must be left in place.
    if (git("rev-parse", "HEAD").decode().strip() != expected_head
            or git("status", "--porcelain")):
        shutil.rmtree(recovery)
        raise InstallError("备份期间 Git 工作树发生变化，停止更新。")
    try:
        subprocess.run(["git", "merge", "--ff-only", commit], cwd=repo, check=True)
    except BaseException as error:
        # Preserve partial checkout files (including possible concurrent edits)
        # outside the repository, before restoring known-good bytes. No reset or
        # checkout is used here: either could re-run the same failing filter.
        current = recovery / "after-failure"
        current.mkdir()
        try:
            for name in sorted(changed_roots):
                live = repo / name
                if present(live):
                    os.replace(live, current / name)
                old = original / name
                if old.is_dir() and not old.is_symlink():
                    shutil.copytree(old, live, symlinks=True)
                elif present(old):
                    shutil.copy2(old, live, follow_symlinks=False)
            after_head = git("rev-parse", "HEAD").decode().strip()
            if after_head not in (expected_head, commit):
                raise InstallError("更新期间出现其它 Git 提交；保留现场供人工恢复。")
            if after_head != expected_head:
                subprocess.run(["git", "update-ref", "HEAD", expected_head, after_head], cwd=repo, check=True)
            shutil.copy2(recovery / "index", index)
        except BaseException as restore_error:
            raise InstallError(f"Git 更新和恢复未全部完成；原文件与失败现场均保留：{recovery}") from restore_error
        raise InstallError(
            f"Git 更新失败，已恢复原工作树与安装；失败现场（含可能的并发修改）保留：{recovery}"
        ) from error
    try:
        shutil.rmtree(recovery)
    except OSError:
        print(f"工作树更新完成；备份清理失败，保留供检查：{recovery}")


def main(argv=None):
    if sys.version_info < (3, 9):
        raise InstallError("安装与更新需要 Python 3.9+")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--link-root", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--mode", choices=("copy", "link", "auto"), default="copy")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--advance-repo", type=Path)
    parser.add_argument("--advance-commit")
    parser.add_argument("--expected-head")
    parser.add_argument("runtimes", nargs="*")
    args = parser.parse_args(argv)
    if any(runtime not in RUNTIMES for runtime in args.runtimes):
        raise InstallError("未知 runtime；支持 claude、codex、codebuddy、workbuddy。")
    source = args.source.resolve()
    link_root = (args.link_root or source).resolve()
    protected = [source, link_root]
    home = Path.home()
    plans = []
    for runtime in dict.fromkeys(args.runtimes or RUNTIMES):
        conf = home / ("." + runtime)
        dest = conf / "skills"
        if args.update:
            if not installed(dest):
                continue
        elif not args.runtimes and not conf.is_dir():
            continue
        if args.list:
            print(f"{runtime}: {dest}")
            continue
        mode = args.mode
        if mode == "auto":
            mode = "link" if (dest / "elab").is_symlink() else "copy"
        plans.append(plan_install(source, dest, mode, args.version, link_root, protected))
    if args.list:
        return 0
    if not plans:
        if args.update:
            raise InstallError("未发现已安装的 EdgeLab 套件；请先运行 install.sh。")
        print("未识别到支持的 runtime。")
        return 0
    destinations = [plan["dest"].resolve() for plan in plans]
    if any(overlap(left, right) for i, left in enumerate(destinations)
           for right in destinations[i + 1:]):
        raise InstallError("多个 runtime 的 skills 目录相交，请使用独立的安装目录。")

    def advance():
        advance_checkout(args.advance_repo, args.advance_commit, args.expected_head)

    apply_plans(plans, advance if args.advance_repo else None)
    for plan in plans:
        print(f"已安装 EdgeLab Trading Skills {args.version} → {plan['dest']}（{plan['mode']}）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (InstallError, OSError, subprocess.CalledProcessError) as exc:
        print(f"安装已停止：{exc}")
        sys.exit(1)

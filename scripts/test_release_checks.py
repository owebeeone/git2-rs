"""Gearu's release check for the git2-rs fork's two packages, which share one tag.

The check refuses before any gate when a manifest still says publish = false, when
the tag's version is not gwz-git2's, when gwz-git2 asks for a different sys version
than the sys manifest carries, or when the vendored libgit2 is not the pinned
commit. Then it runs the gates in order and stops at the first that fails.
Packaging is the exact stage, on the release commit, because `cargo package`
refuses uncommitted files."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import release_checks

PINNED = release_checks.PINNED_LIBGIT2


def repository(
    directory: str,
    version: str = "0.21.0",
    requirement: str = "=0.18.8",
    api_publish: str | None = None,
    sys_publish: str | None = None,
    sys_version: str = "0.18.8+1.9.7",
) -> Path:
    root = Path(directory)
    (root / "libgit2-sys").mkdir()
    api = (
        f'[package]\nname = "gwz-git2"\nversion = "{version}"\n'
        + (f"publish = {api_publish}\n" if api_publish else "")
        + f'\n[dependencies]\nlibgit2-sys = {{ package = "gwz-libgit2-sys", path = "libgit2-sys", version = "{requirement}" }}\n'
    )
    sys = f'[package]\nname = "gwz-libgit2-sys"\nversion = "{sys_version}"\n' + (
        f"publish = {sys_publish}\n" if sys_publish else ""
    )
    (root / "Cargo.toml").write_text(api)
    (root / "libgit2-sys" / "Cargo.toml").write_text(sys)
    return root


class Recorder:
    def __init__(self, failing: int | None = None):
        self.commands: list[list[str]] = []
        self.failing = failing

    def __call__(self, command, *, cwd, check):
        self.commands.append(command)
        code = 3 if len(self.commands) - 1 == self.failing else 0
        return subprocess.CompletedProcess(command, code)


def pinned(_root: Path) -> str:
    return PINNED


def moved(_root: Path) -> str:
    return "0" * 40


class ReleaseCheckTests(unittest.TestCase):
    def refused(self, root: Path, version: str, gitlink=pinned) -> None:
        for exact in (False, True):
            run = Recorder()
            self.assertEqual(release_checks.check(root, version, run, exact=exact, gitlink=gitlink), 1)
            self.assertEqual(run.commands, [])

    def test_a_version_other_than_gwz_git2s_is_refused_in_both_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            self.refused(repository(directory), "0.21.1")

    def test_publish_false_on_either_package_is_refused_in_both_stages(self):
        for api, sys in (("false", None), (None, "false")):
            with tempfile.TemporaryDirectory() as directory:
                self.refused(repository(directory, api_publish=api, sys_publish=sys), "0.21.0")

    def test_a_sys_requirement_that_the_sys_manifest_does_not_meet_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            self.refused(repository(directory, requirement="=0.18.9"), "0.21.0")

    def test_a_vendored_libgit2_other_than_the_pinned_commit_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            self.refused(repository(directory), "0.21.0", gitlink=moved)

    def test_the_candidate_stage_checks_out_libgit2_then_runs_the_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Recorder()
            self.assertEqual(release_checks.check(repository(directory), "0.21.0", run, gitlink=pinned), 0)
        self.assertEqual(run.commands, [
            ["git", "submodule", "update", "--init", "libgit2-sys/libgit2"],
            ["cargo", "test", "--locked"],
        ])

    def test_the_exact_stage_dry_runs_both_packages_together(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Recorder()
            self.assertEqual(
                release_checks.check(repository(directory), "0.21.0", run, exact=True, gitlink=pinned), 0
            )
        self.assertEqual(run.commands, [
            ["git", "submodule", "update", "--init", "libgit2-sys/libgit2"],
            ["cargo", "publish", "--dry-run", "--locked", "-p", "gwz-libgit2-sys", "-p", "gwz-git2"],
        ])

    def test_the_first_failing_gate_ends_the_check_with_its_status(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Recorder(failing=0)
            self.assertEqual(release_checks.check(repository(directory), "0.21.0", run, gitlink=pinned), 3)
        self.assertEqual(len(run.commands), 1)

    def test_the_gitlink_reader_reports_the_commit_the_head_tree_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in (
                ["git", "init", "-q"],
                ["git", "update-index", "--add", "--cacheinfo", f"160000,{PINNED},libgit2-sys/libgit2"],
                ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"],
            ):
                subprocess.run(command, cwd=root, check=True, capture_output=True)
            self.assertEqual(release_checks.read_gitlink(root), PINNED)

    def test_this_repositorys_manifests_are_open_and_agree(self):
        root = Path(__file__).resolve().parents[1]
        version = release_checks.api_version(root)
        self.assertEqual(release_checks.problems(root, version, gitlink=pinned), [])


if __name__ == "__main__":
    unittest.main()

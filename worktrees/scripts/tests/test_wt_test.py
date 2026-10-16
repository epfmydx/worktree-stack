"""Regression tests for disposable snapshots; never contacts Docker or a network."""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "wt-test"
LOADER = importlib.machinery.SourceFileLoader("wt_test_runner", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
wt_test = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(wt_test)


class GitFixture(unittest.TestCase):
    def setUp(self):
        original_run = subprocess.run

        def local_process_only(argv, *args, **kwargs):
            if Path(argv[0]).name == "docker":
                raise AssertionError("Regression tests must mock every Docker subprocess")
            return original_run(argv, *args, **kwargs)

        subprocess_guard = mock.patch.object(wt_test.subprocess, "run", side_effect=local_process_only)
        subprocess_guard.start()
        self.addCleanup(subprocess_guard.stop)
        temporary = tempfile.TemporaryDirectory(prefix="wt-test-regression-")
        self.addCleanup(temporary.cleanup)
        self.stack = Path(temporary.name).resolve()
        self.repository = self.stack / "example" / "backend" / "source"
        self.repository.mkdir(parents=True)
        self.git(self.repository, "init", "-q")
        self.git(self.repository, "config", "user.name", "Snapshot Test")
        self.git(self.repository, "config", "user.email", "snapshot@example.invalid")
        for name, text in {
            ".gitignore": "ignored.txt\nignored-dir/\n",
            "tracked.txt": "committed\n",
            "deleted.txt": "remove me\n",
            "run.sh": "#!/bin/sh\nexit 0\n",
        }.items():
            (self.repository / name).write_text(text)
        (self.repository / "run.sh").chmod(0o644)
        self.git(self.repository, "add", ".")
        self.git(self.repository, "commit", "-qm", "Initial fixture")
        self.worktree = self.stack / "worktrees" / "example" / "feature"
        self.git(self.repository, "worktree", "add", "--detach", str(self.worktree), "HEAD")
        self.archive_path = self.stack / "snapshot.tar"
        self.config = {
            "version": 1,
            "source_repository": "backend/source",
            "container_prefix": "example-app",
            "workdir": "/app",
            "environment": {},
            "host_environment": {
                "GATES_CONTAINER": "{{container}}",
                "TEST_DATABASE": "isolated_{{db_suffix}}",
            },
            "prepare": [],
            "profiles": {
                "full": {
                    "full_gate": True,
                    "steps": [{"scope": "container", "name": "check", "argv": ["true"]}],
                },
            },
            "services": [],
        }

    @staticmethod
    def git(root, *args):
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return result.stdout.decode().strip()

    def snapshot(self):
        return wt_test.snapshot(self.worktree, self.archive_path, wt_test.DEFAULT_EXCLUDES)

    def runner(self):
        args = argparse.Namespace(
            project="example", slug="feature", profile="full", image="test-image",
            output_dir=str(self.stack / "reports"),
        )
        runner = wt_test.Runner(self.stack, args, self.config)
        self.addCleanup(runner.temporary.cleanup)
        return runner


class SnapshotTests(GitFixture):
    def test_captures_working_files_modes_and_deletions_without_ignored_or_secret_files(self):
        (self.worktree / "tracked.txt").write_text("staged\n")
        self.git(self.worktree, "add", "tracked.txt")
        (self.worktree / "tracked.txt").write_text("current working contents\n")
        (self.worktree / "new file.txt").write_text("untracked input\n")
        (self.worktree / "deleted.txt").unlink()
        (self.worktree / "run.sh").chmod(0o755)
        for name in ("ignored.txt", ".env", ".env.testing", ".secrets.local"):
            (self.worktree / name).write_text("do not include\n")
        for directory in ("ignored-dir", "vendor", "node_modules"):
            (self.worktree / directory).mkdir()
            (self.worktree / directory / "generated.txt").write_text("generated\n")

        manifest = self.snapshot()
        expected = {".gitignore", "tracked.txt", "new file.txt", "run.sh"}
        self.assertEqual(set(manifest["files"]), expected)
        self.assertEqual(manifest["head"], self.git(self.worktree, "rev-parse", "HEAD"))
        with tarfile.open(self.archive_path) as archive:
            self.assertEqual(set(archive.getnames()), expected)
            self.assertEqual(archive.extractfile("tracked.txt").read(), b"current working contents\n")
            self.assertEqual(archive.extractfile("new file.txt").read(), b"untracked input\n")
            self.assertEqual(archive.getmember("run.sh").mode, 0o755)
            self.assertEqual(archive.getmember("tracked.txt").mode, 0o644)

    def test_tracked_ignored_files_remain_inputs_but_tracked_env_is_excluded(self):
        (self.worktree / "ignored.txt").write_text("intentionally tracked\n")
        (self.worktree / ".env").write_text("sensitive configuration\n")
        self.git(self.worktree, "add", "-f", "ignored.txt", ".env")
        manifest = self.snapshot()
        self.assertIn("ignored.txt", manifest["files"])
        self.assertNotIn(".env", manifest["files"])

    def test_first_git_filename_preserves_leading_space(self):
        name = " first-tracked-file.txt"
        (self.worktree / name).write_text("leading space belongs to the name\n")
        self.git(self.worktree, "add", "--", name)
        manifest = self.snapshot()
        self.assertIn(name, manifest["files"])
        with tarfile.open(self.archive_path) as archive:
            self.assertEqual(archive.extractfile(name).read(), b"leading space belongs to the name\n")

    def test_internal_relative_symlink_is_preserved(self):
        (self.worktree / "link.txt").symlink_to("tracked.txt")
        manifest = self.snapshot()
        self.assertEqual(manifest["files"]["link.txt"]["target"], "tracked.txt")
        with tarfile.open(self.archive_path) as archive:
            entry = archive.getmember("link.txt")
            self.assertTrue(entry.issym())
            self.assertEqual(entry.linkname, "tracked.txt")

    def test_absolute_symlink_is_refused_even_when_target_is_inside_checkout(self):
        (self.worktree / "link.txt").symlink_to(self.worktree / "tracked.txt")
        with self.assertRaisesRegex(wt_test.Refusal, "Absolute symlink"):
            self.snapshot()

    def test_relative_symlink_escaping_checkout_is_refused(self):
        outside = self.worktree.parent / "outside.txt"
        outside.write_text("outside input\n")
        (self.worktree / "link.txt").symlink_to("../outside.txt")
        with self.assertRaisesRegex(wt_test.Refusal, "escapes snapshot"):
            self.snapshot()

    def test_symlink_cannot_reintroduce_excluded_configuration(self):
        (self.worktree / ".env").write_text("private\n")
        (self.worktree / "configuration.txt").symlink_to(".env")
        with self.assertRaisesRegex(wt_test.Refusal, "excluded data"):
            self.snapshot()

    def test_tracked_path_with_symlink_ancestor_is_refused(self):
        directory = self.worktree / "directory"
        directory.mkdir()
        (directory / "child.txt").write_text("original\n")
        self.git(self.worktree, "add", "directory/child.txt")
        (directory / "child.txt").unlink()
        directory.rmdir()
        replacement = self.worktree / "replacement"
        replacement.mkdir()
        (replacement / "child.txt").write_text("replacement\n")
        directory.symlink_to("replacement", target_is_directory=True)
        with self.assertRaisesRegex(wt_test.Refusal, "Symlink ancestor"):
            self.snapshot()

    def test_submodule_gitlink_is_refused_without_network_or_checkout(self):
        head = self.git(self.worktree, "rev-parse", "HEAD")
        self.git(self.worktree, "update-index", "--add", "--cacheinfo", "160000", head, "module")
        with self.assertRaisesRegex(wt_test.Refusal, "Submodules"):
            self.snapshot()

    def test_snapshot_stays_frozen_after_worktree_changes(self):
        manifest = self.snapshot()
        archive_before = self.archive_path.read_bytes()
        (self.worktree / "tracked.txt").write_text("edited after capture\n")
        (self.worktree / "new.txt").write_text("created after capture\n")
        (self.worktree / "deleted.txt").unlink()
        self.assertEqual(self.archive_path.read_bytes(), archive_before)
        with tarfile.open(self.archive_path) as archive:
            self.assertEqual(archive.extractfile("tracked.txt").read(), b"committed\n")
            self.assertIn("deleted.txt", archive.getnames())
            self.assertNotIn("new.txt", archive.getnames())
        current = wt_test.scan_source(self.worktree, wt_test.DEFAULT_EXCLUDES)
        self.assertNotEqual(current, manifest["files"])

    def test_mutation_during_copy_refuses_and_removes_unstable_archive(self):
        original_scan = wt_test.scan_source

        def edit_after_copy(root, patterns, archive=None):
            entries = original_scan(root, patterns, archive)
            if archive is not None:
                (root / "tracked.txt").write_text("concurrent edit\n")
            return entries

        with mock.patch.object(wt_test, "scan_source", side_effect=edit_after_copy):
            with self.assertRaisesRegex(wt_test.Refusal, "Source changed"):
                self.snapshot()
        self.assertFalse(self.archive_path.exists())

    def test_fingerprint_changes_for_permission_only_edit(self):
        before = self.snapshot()
        (self.worktree / "run.sh").chmod(0o755)
        after = self.snapshot()
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])


class StackRepositoryTests(GitFixture):
    def setUp(self):
        super().setUp()
        self.stack = self.stack / "whole-stack"
        self.stack.mkdir()
        self.git(self.stack, "init", "-q")
        self.git(self.stack, "config", "user.name", "Snapshot Test")
        self.git(self.stack, "config", "user.email", "snapshot@example.invalid")
        self.relative = Path("example/backend/source")
        (self.stack / self.relative).mkdir(parents=True)
        (self.stack / self.relative / "app.txt").write_text("app only\n")
        (self.stack / "outside.txt").write_text("other project, never snapshot\n")
        (self.stack / ".gitignore").write_text("worktrees/\n*.ignored\n")
        self.git(self.stack, "add", ".")
        self.git(self.stack, "commit", "-qm", "Stack fixture")
        self.checkout = self.stack / "worktrees" / "feature"
        self.git(self.stack, "worktree", "add", "--detach", str(self.checkout), "HEAD")
        self.worktree = self.checkout / self.relative
        self.config.update(repository_scope="stack", source_repository=".", source_subdirectory=str(self.relative))

    def test_registered_stack_worktree_resolves_to_app_subdirectory(self):
        self.assertEqual(wt_test.resolve_worktree(self.stack, "example", "feature", self.config), self.worktree)

    def test_snapshot_includes_only_selected_subtree_with_relative_paths(self):
        (self.worktree / "app.txt").write_text("dirty app\n")
        (self.worktree / "new.txt").write_text("new app input\n")
        (self.worktree / "file.ignored").write_text("ignored by parent repo\n")
        (self.checkout / "outside.txt").write_text("dirty other project\n")
        (self.checkout / "new-outside.txt").write_text("untracked other project\n")
        # An unrelated gitlink must not cause this app's snapshot to fail.
        head = self.git(self.checkout, "rev-parse", "HEAD")
        self.git(self.checkout, "update-index", "--add", "--cacheinfo", "160000", head, "other-module")
        manifest = self.snapshot()
        self.assertEqual(set(manifest["files"]), {"app.txt", "new.txt"})
        with tarfile.open(self.archive_path) as archive:
            self.assertEqual(archive.extractfile("app.txt").read(), b"dirty app\n")
            self.assertEqual(set(archive.getnames()), {"app.txt", "new.txt"})

    def test_snapshot_rejects_symlink_into_other_stack_project(self):
        (self.worktree / "link.txt").symlink_to("../../../outside.txt")
        with self.assertRaisesRegex(wt_test.Refusal, "escapes snapshot"):
            self.snapshot()

    def test_source_subdirectory_cannot_escape_worktree(self):
        self.config["source_subdirectory"] = "../example"
        with self.assertRaisesRegex(wt_test.Refusal, "relative snapshot path"):
            wt_test.resolve_worktree(self.stack, "example", "feature", self.config)

    def test_source_subdirectory_symlink_is_refused(self):
        (self.checkout / "alias").symlink_to(self.relative, target_is_directory=True)
        self.config["source_subdirectory"] = "alias"
        with self.assertRaisesRegex(wt_test.Refusal, "must not contain symlinks"):
            wt_test.resolve_worktree(self.stack, "example", "feature", self.config)

    def test_nested_repository_is_refused(self):
        self.git(self.worktree, "init", "-q")
        with self.assertRaisesRegex(wt_test.Refusal, "nested repository"):
            wt_test.resolve_worktree(self.stack, "example", "feature", self.config)


class OwnershipAndEnvironmentTests(GitFixture):
    def test_accepts_registered_worktree_of_configured_repository(self):
        self.assertEqual(
            wt_test.resolve_worktree(self.stack, "example", "feature", self.config),
            self.worktree,
        )

    def test_refuses_git_repository_in_expected_path_with_wrong_owner(self):
        self.git(self.repository, "worktree", "remove", str(self.worktree))
        self.worktree.mkdir()
        self.git(self.worktree, "init", "-q")
        with self.assertRaisesRegex(wt_test.Refusal, "another repository"):
            wt_test.resolve_worktree(self.stack, "example", "feature", self.config)

    def test_runner_does_not_inherit_host_database_or_gate_overrides(self):
        hostile = {
            "DB_HOST": "development-db", "DB_DATABASE": "interactive_database",
            "DB_PASSWORD": "host-only-value", "MYSQL_TEST_DATABASE": "main",
            "TEST_DATABASE": "host_database", "GATES_CONTAINER": "interactive-app",
            "GATES_SKIP_TESTS": "1", "GATES_TEST_MYSQL": "0", "APP_ENV": "production",
        }
        with mock.patch.dict(os.environ, hostile):
            runner = self.runner()
        self.assertEqual(runner.env["GATES_CONTAINER"], runner.container)
        self.assertEqual(runner.env["TEST_DATABASE"], "isolated_" + runner.variables["db_suffix"])
        for name in hostile.keys() - {"GATES_CONTAINER", "TEST_DATABASE"}:
            self.assertNotIn(name, runner.env)
        for name in hostile:
            self.assertNotIn(name, runner.base_env)

    def test_mount_image_donor_uses_exact_source_and_preserves_immutable_id(self):
        self.config["image_donor"] = "mount"
        runner = self.runner()
        donor = {"Name": "/custom-stack-example-feature-api", "Image": "sha256:runtime",
                 "Mounts": [{"Type": "bind", "Source": str(self.worktree), "Destination": "/app"}]}
        other = {"Mounts": [{"Type": "bind", "Source": str(self.repository), "Destination": "/app"}]}
        image = {"Id": "sha256:runtime", "Architecture": "arm64", "Config": {}}
        runner.args.image = None
        with mock.patch.object(wt_test, "output", return_value="unrelated\nselected"), \
                mock.patch.object(runner, "docker_json", side_effect=[other, donor, image]):
            self.assertEqual(runner.image(), "sha256:runtime")
        self.assertEqual(runner.result["image_donor"], "custom-stack-example-feature-api")

    def test_ambiguous_mount_donor_is_refused(self):
        self.config["image_donor"] = "mount"
        runner = self.runner()
        runner.args.image = None
        donor = {"Mounts": [{"Type": "bind", "Source": str(self.worktree), "Destination": "/app"}]}
        with mock.patch.object(wt_test, "output", return_value="one\ntwo"), \
                mock.patch.object(runner, "docker_json", return_value=donor):
            with self.assertRaisesRegex(wt_test.Refusal, "Expected one running image donor"):
                runner.image()


class CleanupTests(GitFixture):
    def test_foreign_run_label_blocks_stop_and_removal(self):
        runner = self.runner()
        runner.resources = [("volume", "owned-source"), ("container", "other-service")]
        foreign = {"Config": {"Labels": {wt_test.RUN_LABEL: "another-run"}}, "State": {"Running": True}}
        with mock.patch.object(runner, "resource_exists", return_value=True), \
                mock.patch.object(runner, "docker_json", return_value=foreign), \
                mock.patch.object(wt_test, "output") as command, \
                mock.patch.object(wt_test.subprocess, "run") as process:
            runner.cleanup()
        command.assert_not_called()
        process.assert_not_called()
        self.assertTrue(any("Ownership label mismatch" in error for error in runner.result["cleanup_errors"]))

    def test_volume_remaining_after_successful_remove_is_reported(self):
        runner = self.runner()
        runner.resources = [("volume", "owned-source")]
        owned = {"Labels": {wt_test.RUN_LABEL: runner.run_id}}
        with mock.patch.object(runner, "resource_exists", return_value=True), \
                mock.patch.object(runner, "docker_json", return_value=owned), \
                mock.patch.object(wt_test, "output") as command, \
                mock.patch.object(wt_test.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            runner.cleanup()
        command.assert_called_once_with(["docker", "volume", "rm", "owned-source"], env=runner.base_env)
        self.assertTrue(any("Resource remains" in error for error in runner.result["cleanup_errors"]))

    def test_report_copy_failure_after_failed_checks_retains_owned_evidence(self):
        runner = self.runner()
        runner.resources = [("volume", runner.volume), ("container", runner.container)]
        runner.result["snapshot_verified"] = True
        owned = {"Config": {"Labels": {wt_test.RUN_LABEL: runner.run_id}},
                 "State": {"Running": False}}
        with mock.patch.object(runner, "resource_exists", return_value=True), \
                mock.patch.object(runner, "docker_json", return_value=owned), \
                mock.patch.object(wt_test, "output") as removal, \
                mock.patch.object(wt_test.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            runner.cleanup()
        removal.assert_not_called()
        self.assertTrue(any("retained for recovery" in error for error in runner.result["cleanup_errors"]))

    def test_interrupted_create_is_remembered_and_owned_resource_is_cleaned(self):
        runner = self.runner()
        argv = ["docker", "network", "create", *runner.labels(), runner.network]
        with mock.patch.object(runner, "resource_exists", return_value=False), \
                mock.patch.object(runner, "command", side_effect=wt_test.Interrupted(wt_test.signal.SIGINT)):
            with self.assertRaises(wt_test.Interrupted):
                runner.create_resource("network", runner.network, argv, "create test network")
        self.assertIn(("network", runner.network), runner.resources)
        recorded = json.loads((runner.report / "result.json").read_text())
        self.assertIn({"kind": "network", "name": runner.network}, recorded["resources"])
        owned = {"Labels": {wt_test.RUN_LABEL: runner.run_id}}
        with mock.patch.object(runner, "resource_exists", side_effect=[True, False]), \
                mock.patch.object(runner, "docker_json", return_value=owned), \
                mock.patch.object(wt_test, "output") as command, \
                mock.patch.object(wt_test.subprocess, "run") as process:
            runner.cleanup()
        command.assert_called_once_with(["docker", "network", "rm", runner.network], env=runner.base_env)
        process.assert_not_called()
        self.assertEqual(runner.result["cleanup_errors"], [])

    def test_interrupted_create_with_confirmed_absent_resource_needs_no_removal(self):
        runner = self.runner()
        argv = ["docker", "volume", "create", *runner.labels(), runner.volume]
        with mock.patch.object(runner, "resource_exists", return_value=False), \
                mock.patch.object(runner, "command", side_effect=wt_test.Interrupted(wt_test.signal.SIGINT)):
            with self.assertRaises(wt_test.Interrupted):
                runner.create_resource("volume", runner.volume, argv, "create source volume")
        self.assertIn(("volume", runner.volume), runner.resources)
        with mock.patch.object(runner, "resource_exists", return_value=False), \
                mock.patch.object(runner, "docker_json") as inspect, \
                mock.patch.object(wt_test, "output") as command, \
                mock.patch.object(wt_test.subprocess, "run") as process:
            runner.cleanup()
        inspect.assert_not_called()
        command.assert_not_called()
        process.assert_not_called()
        self.assertEqual(runner.result["cleanup_errors"], [])

    def test_existing_resource_is_not_claimed_or_created(self):
        runner = self.runner()
        with mock.patch.object(runner, "resource_exists", return_value=True), \
                mock.patch.object(runner, "command") as command:
            with self.assertRaisesRegex(wt_test.Refusal, "already exists"):
                runner.create_resource("volume", runner.volume, ["docker", "volume", "create"], "create volume")
        command.assert_not_called()
        self.assertEqual(runner.resources, [])
        self.assertEqual(runner.result["resources"], [])

    def test_resource_inventory_requires_exact_name_and_includes_stopped_containers(self):
        runner = self.runner()
        with mock.patch.object(wt_test, "output", return_value=runner.container + "-other\n") as inventory:
            self.assertFalse(runner.resource_exists("container", runner.container))
        self.assertIn("--all", inventory.call_args.args[0])
        with mock.patch.object(wt_test, "output", return_value=runner.container + "\n"):
            self.assertTrue(runner.resource_exists("container", runner.container))

    def test_failed_inventory_cannot_establish_that_resource_is_absent(self):
        runner = self.runner()
        with mock.patch.object(wt_test, "output", side_effect=wt_test.Refusal("daemon unavailable")):
            with self.assertRaisesRegex(wt_test.Refusal, "daemon unavailable"):
                runner.resource_exists("volume", runner.volume)

    def test_process_exiting_between_poll_and_stop_does_not_break_cleanup(self):
        runner = self.runner()
        runner.child = mock.Mock()
        runner.child.poll.return_value = None
        with mock.patch.object(wt_test.os, "killpg", side_effect=ProcessLookupError):
            runner.terminate_child()

    def test_successful_checks_with_incomplete_cleanup_exit_nonzero_and_report_failure(self):
        adapter = self.stack / "example" / "wt-test.json"
        adapter.write_text(json.dumps(self.config))

        def passed(runner):
            runner.result["checks_passed"] = True

        def incomplete_cleanup(runner):
            runner.result["cleanup_errors"].append("owned source volume could not be removed")
            runner.temporary.cleanup()

        with mock.patch.object(wt_test, "__file__", str(self.stack / "worktrees" / "scripts" / "wt-test")), \
                mock.patch.object(wt_test.Runner, "run", passed), \
                mock.patch.object(wt_test.Runner, "cleanup", incomplete_cleanup), \
                mock.patch.object(wt_test.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = wt_test.main(["example", "feature", "--output-dir", str(self.stack / "reports")])
        result = json.loads((self.stack / "reports" / "result.json").read_text())
        self.assertNotEqual(code, 0)
        self.assertEqual(result["exit_code"], code)
        self.assertTrue(result["checks_passed"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["full_gate_passed"])
        self.assertTrue(result["cleanup_errors"])


if __name__ == "__main__":
    unittest.main()

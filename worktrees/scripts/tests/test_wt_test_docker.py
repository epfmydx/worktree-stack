"""Opt-in Docker acceptance tests using only an explicitly supplied local image.

Run with WT_TEST_DOCKER_IMAGE=<local-app-image> python3 -m unittest discover
-s worktrees/scripts/tests -p test_wt_test_docker.py -v. The image needs GNU tar,
sh and sleep, and must not declare volumes. No pulls or application services run.
Diagnostic files remain in the printed temporary directory, including on failure.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "wt-test"
RUN_LABEL = "io.github.epfmydx.worktree-stack.ci.run"
FIXTURE_LABEL = "io.github.epfmydx.worktree-stack.ci.docker-fixture"
IMAGE = os.environ.get("WT_TEST_DOCKER_IMAGE")


def docker(*args, check=True):
    return subprocess.run(["docker", *args], text=True, capture_output=True, check=check, timeout=60)


def inventory(kind, label):
    args = [kind, "ls"] + (["--all"] if kind == "container" else [])
    field = "Names" if kind == "container" else "Name"
    return docker(*args, "--filter", "label=" + label, "--format", "{{." + field + "}}").stdout.splitlines()


@unittest.skipUnless(IMAGE, "Set WT_TEST_DOCKER_IMAGE to opt into live Docker tests")
class DockerSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="wt-test-docker-regression-")).resolve()
        cls.fixture_id = secrets.token_hex(8)
        cls.fixture_container = "wt-test-fixture-" + cls.fixture_id
        cls.image = None
        cls.addClassCleanup(cls.cleanup_fixture)
        print("\nwt-test Docker regression reports: " + str(cls.root), flush=True)
        base = json.loads(docker("image", "inspect", IMAGE).stdout)[0]
        if base.get("Config", {}).get("Volumes"):
            raise RuntimeError("The supplied test image declares implicit volumes")
        cls.sentinel = ".image-only-" + cls.fixture_id
        sentinel_file = cls.root / cls.sentinel
        sentinel_file.write_text("This must never be copied into a source volume.\n")
        # Keep the sentinel image local and isolate fixture construction from networks.
        docker("create", "--name", cls.fixture_container, "--network", "none", "--user", "0:0",
               "--label", FIXTURE_LABEL + "=" + cls.fixture_id,
               "--entrypoint", "sleep", base["Id"], "infinity")
        docker("start", cls.fixture_container)
        docker("exec", cls.fixture_container, "sh", "-ec", "mkdir -p /var/www/html")
        docker("cp", str(sentinel_file), cls.fixture_container + ":/var/www/html/" + cls.sentinel)
        docker("stop", "--time", "5", cls.fixture_container)
        # The copied volume must work with the non-root user common in dev images.
        cls.image = docker("commit", "--change", "USER 65534:65534", cls.fixture_container).stdout.strip()
        docker("container", "rm", cls.fixture_container)

    @classmethod
    def cleanup_fixture(cls):
        errors = []
        try:
            names = inventory("container", FIXTURE_LABEL + "=" + cls.fixture_id)
            if cls.fixture_container in names:
                docker("container", "rm", "--force", cls.fixture_container)
        except Exception as error:
            errors.append(str(error))
        if cls.image:
            try:
                image = json.loads(docker("image", "inspect", cls.image).stdout)[0]
                if image.get("Config", {}).get("Labels", {}).get(FIXTURE_LABEL) != cls.fixture_id:
                    raise RuntimeError("Refused fixture image cleanup: ownership label differs")
                docker("image", "rm", cls.image)
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError("Fixture cleanup incomplete: " + "; ".join(errors))

    def setUp(self):
        self.case = self.root / self._testMethodName
        self.stack = self.case / "stack"
        scripts = self.stack / "worktrees" / "scripts"
        scripts.mkdir(parents=True)
        self.runner = scripts / "wt-test"
        shutil.copy2(SCRIPT, self.runner)
        source = self.stack / "fixture" / "backend" / "source"
        source.mkdir(parents=True)
        whole_stack = self._testMethodName.endswith("stack_subtree")
        self.repo = self.stack if whole_stack else source
        self.processes = []
        self.reports = []
        self.addCleanup(self.cleanup_runs)
        self.git(self.repo, "init", "-q")
        self.git(self.repo, "config", "user.name", "Disposable Docker Test")
        self.git(self.repo, "config", "user.email", "docker-test@example.invalid")
        for name, content in {
            ".gitignore": "ignored.txt\n", "tracked.txt": "original\n",
            "deleted.txt": "remove\n", "executable.sh": "#!/bin/sh\nexit 0\n",
        }.items():
            (source / name).write_text(content)
        if whole_stack:
            (self.stack / ".gitignore").write_text("worktrees/\n")
            (self.stack / "other-project.txt").write_text("Must never enter app snapshot\n")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-qm", "Fixture baseline")
        checkout = self.stack / "worktrees" / "feature" if whole_stack else self.stack / "worktrees" / "fixture" / "feature"
        self.git(self.repo, "worktree", "add", "--detach", str(checkout), "HEAD")
        self.source = checkout / "fixture" / "backend" / "source" if whole_stack else checkout
        (self.source / "tracked.txt").write_text("dirty\n")
        (self.source / "untracked.txt").write_text("untracked\n")
        (self.source / "deleted.txt").unlink()
        (self.source / "ignored.txt").write_text("ignored\n")
        (self.source / ".env").write_text("excluded fixture configuration\n")
        (self.source / "link.txt").symlink_to("tracked.txt")
        if hasattr(os, "lchmod"):
            try:
                os.lchmod(self.source / "link.txt", 0o755)
            except NotImplementedError:
                pass
        (self.source / "executable.sh").chmod(0o755)
        success = (
            'test "$(cat tracked.txt)" = dirty; '
            'test "$(cat untracked.txt)" = untracked; '
            'test -L link.txt; test "$(readlink link.txt)" = tracked.txt; '
            'test -x executable.sh; test ! -e deleted.txt; '
            'test ! -e ignored.txt; test ! -e .env; '
            'test ! -e ' + self.sentinel + '; '
            "printf 'snapshot-ok\\n' > /tmp/wt-test-reports/fixture.txt"
        )
        wait = (
            "printf 'waiting\\n'; printf 'started\\n' > /tmp/wt-test-reports/fixture.txt; "
            "count=0; while [ ! -f /tmp/wt-test-reports/release ]; do "
            "count=$((count + 1)); test \"$count\" -lt 120; sleep 1; done; "
        )
        profile = lambda name, command: {
            "full_gate": False, "reports": ["fixture.txt"],
            "steps": [{"scope": "container", "name": name, "argv": ["sh", "-ec", command]}],
        }
        adapter = {
            "version": 1, "source_repository": "backend/source",
            "container_prefix": "wt-test-fixture-app", "workdir": "/var/www/html",
            "environment": {}, "host_environment": {}, "services": [],
            "prepare": [{"scope": "container", "name": "prepare reports", "argv": [
                "sh", "-ec", "mkdir -p /tmp/wt-test-reports",
            ]}],
            "profiles": {
                "success": profile("verify snapshot", success),
                "failure": profile("intentional failure", "printf 'failed\\n' > /tmp/wt-test-reports/fixture.txt; exit 23"),
                "waiting": profile("wait for release", wait + success),
            },
        }
        if whole_stack:
            adapter.update(repository_scope="stack", source_repository=".", source_subdirectory="fixture/backend/source")
        (self.stack / "fixture" / "wt-test.json").write_text(json.dumps(adapter))

    @staticmethod
    def git(root, *args):
        return subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True,
                              check=True, timeout=30).stdout.strip()

    def start(self, profile, name):
        report = self.case / (name + "-reports")
        self.reports.append(report)
        log = (self.case / (name + "-controller.log")).open("wb")
        process = subprocess.Popen(
            [sys.executable, str(self.runner), "fixture", "feature", "--image", self.image,
             "--profile", profile, "--output-dir", str(report)],
            stdout=log, stderr=subprocess.STDOUT,
        )
        self.processes.append((process, log))
        return process, report

    def finish(self, process, report):
        code = process.wait(timeout=60)
        self.assertTrue((report / "result.json").is_file(), "No result; inspect " + str(self.case))
        result = json.loads((report / "result.json").read_text())
        self.assertEqual(result["exit_code"], code)
        self.assertEqual(result["cleanup_errors"], [])
        for kind in ("container", "volume", "network"):
            self.assertEqual(inventory(kind, RUN_LABEL + "=" + result["run_id"]), [],
                             "Leaked " + kind + "; inspect " + str(report))
        return code, result

    def wait_until_blocked(self, process, report):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            logs = list(report.glob("*-wait-for-release.log"))
            if logs and b"waiting" in logs[0].read_bytes():
                return json.loads((report / "result.json").read_text())
            if process.poll() is not None:
                self.fail("Runner exited before the waiting step; inspect " + str(self.case))
            time.sleep(0.1)
        self.fail("Runner did not reach waiting step; inspect " + str(self.case))

    def cleanup_runs(self):
        errors = []
        for process, log in self.processes:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
            finally:
                log.close()
        for report in self.reports:
            if not (report / "result.json").exists():
                continue
            result = json.loads((report / "result.json").read_text())
            for kind in ("container", "volume", "network"):
                owned = {item["name"] for item in result["resources"] if item["kind"] == kind}
                try:
                    for name in inventory(kind, RUN_LABEL + "=" + result["run_id"]):
                        if name not in owned:
                            raise RuntimeError("Unexpected run-owned resource requires manual review: " + name)
                        docker(kind, "rm", *(["--force"] if kind == "container" else []), name)
                except Exception as error:
                    errors.append(str(error))
        if errors:
            raise RuntimeError("Run cleanup incomplete: " + "; ".join(errors))

    def test_success_preserves_working_snapshot_reports_and_excludes_image_sentinel(self):
        process, report = self.start("success", "success")
        code, result = self.finish(process, report)
        self.assertEqual(code, 0, "Inspect " + str(self.case))
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["snapshot_verified"])
        self.assertTrue(result["current_source_matches"])
        self.assertEqual(result["runtime_user"], "65534:65534")
        self.assertEqual((report / "junit" / "fixture.txt").read_text(), "snapshot-ok\n")
        manifest = json.loads((report / "input-manifest.json").read_text())
        self.assertEqual(manifest["files"]["link.txt"]["mode"], 0o777)
        self.assertEqual(manifest["files"]["link.txt"]["target"], "tracked.txt")
        self.assertNotIn(self.sentinel, manifest["files"])
        self.assertEqual((self.source / "tracked.txt").read_text(), "dirty\n")
        self.assertTrue((self.source / "link.txt").is_symlink())

    def test_failing_step_returns_nonzero_with_reports_and_cleanup(self):
        process, report = self.start("failure", "failure")
        code, result = self.finish(process, report)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["full_gate_passed"])
        self.assertEqual(result["steps"][-1]["exit_code"], 23)
        self.assertEqual((report / "junit" / "fixture.txt").read_text(), "failed\n")

    def test_success_bounds_snapshot_to_stack_subtree(self):
        process, report = self.start("success", "stack")
        code, result = self.finish(process, report)
        self.assertEqual(code, 0, "Inspect " + str(self.case))
        self.assertTrue(result["snapshot_verified"])
        manifest = json.loads((report / "input-manifest.json").read_text())
        self.assertEqual(set(manifest["files"]), {".gitignore", "tracked.txt", "untracked.txt", "executable.sh", "link.txt"})
        self.assertNotIn("other-project.txt", manifest["files"])

    def test_sigterm_cancels_work_and_cleans_resources(self):
        process, report = self.start("waiting", "cancel")
        self.wait_until_blocked(process, report)
        process.send_signal(signal.SIGTERM)
        code, result = self.finish(process, report)
        self.assertEqual(code, 128 + signal.SIGTERM)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["full_gate_passed"])
        self.assertEqual((report / "junit" / "fixture.txt").read_text(), "started\n")

    def test_simultaneous_runs_use_distinct_resources_and_the_same_snapshot(self):
        first, first_report = self.start("waiting", "first")
        second, second_report = self.start("waiting", "second")
        first_state = self.wait_until_blocked(first, first_report)
        second_state = self.wait_until_blocked(second, second_report)
        self.assertIsNone(first.poll())
        self.assertIsNone(second.poll())
        self.assertNotEqual(first_state["run_id"], second_state["run_id"])
        self.assertEqual(first_state["fingerprint"], second_state["fingerprint"])
        first_names = {item["name"] for item in first_state["resources"]}
        second_names = {item["name"] for item in second_state["resources"]}
        self.assertTrue(first_names.isdisjoint(second_names))
        for state in (first_state, second_state):
            containers = inventory("container", RUN_LABEL + "=" + state["run_id"])
            expected = [item["name"] for item in state["resources"] if item["kind"] == "container"]
            self.assertEqual(containers, expected)
            self.assertEqual(len(containers), 1)
            docker("exec", containers[0], "sh", "-ec", "touch /tmp/wt-test-reports/release")
        self.assertEqual(self.finish(first, first_report)[0], 0)
        self.assertEqual(self.finish(second, second_report)[0], 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Daemon-free checks for initialization, namespace rendering, and CoreDNS patching."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("configure_dns", ROOT / "k8s/configure-dns.py")
kube = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kube)


class InfrastructureTests(unittest.TestCase):
    def test_coredns_preserves_existing_plugins_and_updates_only_own_block(self):
        original = '.:53 {\n    errors\n    forward . /etc/resolv.conf\n    reload\n}\n'
        first = kube.patch_corefile(original, 'worktree.test', 'first')
        both = kube.patch_corefile(first, 'other.test', 'second')
        changed = kube.patch_corefile(both, 'new.test', 'first')
        self.assertIn('    forward . /etc/resolv.conf\n    reload\n', changed)
        self.assertIn('other\\.test', changed)
        self.assertIn('new\\.test', changed)
        self.assertNotIn('worktree\\.test', changed)
        self.assertEqual(changed, kube.patch_corefile(changed, 'new.test', 'first'))
        with self.assertRaises(ValueError):
            kube.patch_corefile('custom:53 {\n}\n', 'worktree.test', 'first')

    def test_init_is_private_idempotent_and_does_not_need_docker(self):
        with tempfile.TemporaryDirectory(prefix='worktree-stack-init-') as tmp:
            root = Path(tmp)
            for relative in ('.env.example', 'scripts/init.py', 'scripts/stack.sh', 'gateway/scripts/gen-certs.sh', 'database/postgres17/scripts/gen-postgres-certs.sh'):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            result = subprocess.run(['python3', str(root / 'scripts/init.py')], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            before = (root / '.env').read_bytes()
            self.assertEqual((root / '.env').stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b'MYSQL_ROOT_PASSWORD=\n', before)
            cert = (root / 'gateway/certs/fullchain.pem').read_bytes()
            key = (root / 'gateway/certs/privkey.pem').read_bytes()
            result = subprocess.run(['python3', str(root / 'scripts/init.py')], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(before, (root / '.env').read_bytes())
            self.assertEqual(cert, (root / 'gateway/certs/fullchain.pem').read_bytes())
            self.assertEqual(key, (root / 'gateway/certs/privkey.pem').read_bytes())
            self.assertEqual((root / 'gateway/certs/privkey.pem').stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(shutil.which('docker'), 'Docker CLI needed for Compose rendering only')
    def test_compose_namespaces_loopback_and_worktree_ownership(self):
        with tempfile.TemporaryDirectory(prefix='worktree-stack-config-') as tmp:
            values = {}
            for line in (ROOT / '.env.example').read_text().splitlines():
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    values[key] = value
            values.update(STACK_NAME='test-stack', HOST_CONTAINERS_PATH=str(ROOT), MYSQL_ROOT_PASSWORD='synthetic-test', POSTGRES_PASSWORD='synthetic-test', REDIS_PASSWORD='synthetic-test', DASHBOARD_PASSWORD='synthetic-test')
            envfile = Path(tmp) / '.env'
            envfile.write_text(''.join(f'{key}={shlex.quote(value)}\n' for key, value in values.items()))
            environment = {key: value for key, value in os.environ.items() if key not in values}
            environment.update(CONTAINER='test-stack-example-branch', WT_HOST='example-branch', SLUG='branch', DB_NAME='sample_wt_branch', WORKTREE_PATH=str(Path(tmp) / 'worktree'))
            for project in ('dnsmasq', 'gateway', 'database', 'redis', 'dashboard', 'sample-laravel', 'sample-fastapi'):
                command = ['docker', 'compose', '--env-file', str(envfile), '-f', str(ROOT / project / 'docker-compose.yml')]
                result = subprocess.run(command + ['config', '--format', 'json'], env=environment, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, f'{project}: {result.stderr}')
                config = json.loads(result.stdout)
                self.assertEqual(config['name'], f'test-stack-{project}')
                for network in config.get('networks', {}).values():
                    self.assertTrue(network['name'].startswith('test-stack-'))
                for service in config['services'].values():
                    for port in service.get('ports', []):
                        self.assertEqual(port['host_ip'], '127.0.0.1')
                if project.startswith('sample-'):
                    result = subprocess.run(command + ['-f', str(ROOT / project / 'docker-compose.worktree.yml'), 'config', '--format', 'json'], env=environment, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    worktree = json.loads(result.stdout)
                    for service in worktree['services'].values():
                        labels = service['labels']
                        self.assertEqual(labels['io.github.epfmydx.worktree-stack.stack'], 'test-stack')
                        self.assertEqual(labels['io.github.epfmydx.worktree-stack.project'], project)
                        self.assertEqual(labels['io.github.epfmydx.worktree-stack.slug'], 'branch')
                        aliases = service['networks']['main-net']['aliases']
                        self.assertFalse(any(alias.startswith(project) for alias in aliases), aliases)


if __name__ == '__main__':
    unittest.main()

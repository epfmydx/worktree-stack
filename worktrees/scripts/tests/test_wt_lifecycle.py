"""Lifecycle and database guard regressions; no real Docker or database calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
LABEL = 'io.github.epfmydx.worktree-stack'
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, pathlib, re, sys
args = sys.argv[1:]
state_path = pathlib.Path(os.environ['FAKE_STATE'])
state = json.loads(state_path.read_text())
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
if args[:2] == ['container', 'ls']:
    if os.environ.get('FAIL_INVENTORY'): sys.exit(7)
    rows = state.items()
    for i, arg in enumerate(args):
        if arg == '--filter':
            key, value = args[i+1][6:].split('=', 1)
            rows = [(name, row) for name, row in rows if row['labels'].get(key) == value]
    for name, row in rows:
        if '--all' in args or row.get('running', True): print(name)
elif args[0] == 'inspect':
    name = args[-1]
    row = state[name]
    template = args[args.index('--format') + 1]
    template = re.sub(r'{{index \.Config.Labels "([^"]+)"}}', lambda m: row['labels'].get(m[1], ''), template)
    template = template.replace('{{.State.Running}}', str(row.get('running', True)).lower())
    print(template)
elif args[0] == 'compose':
    project = args[args.index('-p') + 1]
    if args[-1] == 'down':
        if os.environ.get('FAIL_DOWN'): sys.exit(23)
        if not os.environ.get('RETAIN_CONTAINER'):
            state = {n:r for n,r in state.items() if r['labels'].get('com.docker.compose.project') != project}
    elif 'up' in args:
        p = 'io.github.epfmydx.worktree-stack'
        state['runtime'] = {'running': True, 'labels': {
            p+'.managed':'true', p+'.stack':os.environ['STACK_NAME'], p+'.project':os.environ['PROJECT'],
            p+'.slug':os.environ['SLUG'], 'com.docker.compose.project':project}}
    state_path.write_text(json.dumps(state))
elif args[0] == 'exec':
    if os.environ.get('FAIL_DROP') and '/scripts/drop-db.sh' in args: sys.exit(17)
else:
    raise RuntimeError('Unexpected fake Docker call: ' + repr(args))
'''
FAKE_DATABASE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
is_dump = name in ('mysqldump', 'pg_dump')
with open(os.environ['DB_LOG'], 'a') as log:
    log.write(json.dumps({'command': name, 'argv':args, 'stdin': '' if is_dump else sys.stdin.read()}) + '\n')
if is_dump:
    print('fixture dump')
    if os.environ.get('FAIL_DUMP'): sys.exit(9)
elif os.environ.get('FAIL_RESTORE'):
    if (name == 'mysql' and '-e' not in args) or (name == 'psql' and args[args.index('-d') + 1].endswith('_seed')):
        sys.exit(12)
'''

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wt-lifecycle-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'stack'
        scripts = self.root / 'worktrees' / 'scripts'
        scripts.mkdir(parents=True)
        for name in ('wt-common.sh', 'wt-spin', 'wt-down', 'wt-seed', 'wt-prune'):
            shutil.copy2(ROOT / 'worktrees' / 'scripts' / name, scripts / name)
        self.scripts = scripts
        project = self.root / 'sample'
        (project / 'source').mkdir(parents=True)
        (project / 'source' / 'tracked.txt').write_text('fixture\n')
        (project / 'wt-config.sh').write_text('PREFIX=sample\nSOURCE_PATH_REL=source\nMAIN_DB=sample\nDB_HOST=mysql\nDB_USERNAME=root\n')
        for name in ('docker-compose.yml', 'docker-compose.worktree.yml'):
            (project / name).write_text('services: {}\n')
        (self.root / '.env').write_text('STACK_NAME=fixture\nDEV_DOMAIN=worktree.test\nGATEWAY_HTTPS_PORT=8443\n')
        self.git(self.root, 'init', '-q')
        self.git(self.root, 'config', 'user.name', 'Lifecycle Fixture')
        self.git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.root, 'add', '.')
        self.git(self.root, 'commit', '-qm', 'Fixture')
        self.worktree = self.root / 'worktrees' / 'topic'
        self.git(self.root, 'worktree', 'add', '--detach', str(self.worktree), 'HEAD')
        binaries = Path(self.tmp.name) / 'bin'
        binaries.mkdir()
        (binaries / 'docker').write_text(FAKE_DOCKER)
        (binaries / 'docker').chmod(0o755)
        self.state_path = Path(self.tmp.name) / 'state.json'
        self.log = Path(self.tmp.name) / 'calls.jsonl'
        self.state = {'database': self.database('fixture'), 'other-database': self.database('unrelated')}
        self.save()
        self.env = os.environ | {'PATH': str(binaries) + os.pathsep + os.environ['PATH'],
                                'FAKE_STATE':str(self.state_path), 'FAKE_LOG':str(self.log)}

    @staticmethod
    def git(root, *args):
        return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True)

    @staticmethod
    def database(stack):
        return {'running':True, 'labels':{'com.docker.compose.project':stack+'-database', 'com.docker.compose.service':'mysql'}}

    def runtime(self, slug='topic', running=True):
        return {'running':running, 'labels':{LABEL+'.managed':'true', LABEL+'.stack':'fixture',
                LABEL+'.project':'sample', LABEL+'.slug':slug, 'com.docker.compose.project':'fixture-sample-'+slug}}

    def save(self):
        self.state_path.write_text(json.dumps(self.state))

    def run_script(self, name, *args, **extra):
        return subprocess.run([str(self.scripts / name), *args], env=self.env | extra, text=True, capture_output=True, timeout=15)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_rejects_project_and_slug_traversal_before_docker(self):
        for project, slug in (('../sample', 'topic'), ('sample', '../topic'), ('sample', 'topic_bad')):
            result = self.run_script('wt-spin', project, slug)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_rejects_foreign_git_repository(self):
        self.git(self.root, 'worktree', 'remove', str(self.worktree))
        self.worktree.mkdir()
        self.git(self.worktree, 'init', '-q')
        result = self.run_script('wt-spin', 'sample', 'topic')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('another repository', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_spin_scopes_database_and_preserves_existing_clone_on_respin(self):
        result = self.run_script('wt-spin', 'sample', 'topic')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('https://sample-topic.worktree.test:8443', result.stdout)
        self.assertEqual(self.run_script('wt-spin', 'sample', 'topic').returncode, 0)
        clones = [c for c in self.calls() if len(c) > 2 and c[2] == '/scripts/clone-db.sh']
        self.assertEqual(clones, [['exec','database','/scripts/clone-db.sh','sample_seed','sample_wt_topic','root']])

    def test_ambiguous_database_refused_before_clone(self):
        self.state['duplicate'] = self.database('fixture'); self.save()
        result = self.run_script('wt-spin', 'sample', 'topic')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('found 2', result.stderr)
        self.assertFalse(any(c[0] == 'exec' for c in self.calls()))

    def test_down_refuses_unowned_matching_compose_project(self):
        self.state['runtime'] = self.runtime()
        del self.state['runtime']['labels'][LABEL+'.managed']; self.save()
        result = self.run_script('wt-down', 'sample', 'topic')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in ('compose','exec') for c in self.calls()))

    def test_failed_down_keeps_database_and_reports_failure(self):
        self.state['runtime'] = self.runtime(); self.save()
        result = self.run_script('wt-down', 'sample', 'topic', FAIL_DOWN='1')
        self.assertEqual(result.returncode, 23)
        self.assertFalse(any('/scripts/drop-db.sh' in c for c in self.calls()))

    def test_remaining_container_prevents_database_drop(self):
        self.state['runtime'] = self.runtime(); self.save()
        result = self.run_script('wt-down', 'sample', 'topic', RETAIN_CONTAINER='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('database retained', result.stderr)
        self.assertFalse(any('/scripts/drop-db.sh' in c for c in self.calls()))

    def test_down_drops_exact_clone_without_deleting_source_or_volumes(self):
        self.state['runtime'] = self.runtime(); self.save()
        result = self.run_script('wt-down', 'sample', 'topic')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.worktree / 'sample' / 'source' / 'tracked.txt').exists())
        self.assertNotIn('--force', result.stdout)
        self.assertIn(['exec','database','/scripts/drop-db.sh','sample_wt_topic'], self.calls())
        compose = [c for c in self.calls() if c[0] == 'compose'][0]
        self.assertNotIn('-v', compose)

    def test_database_drop_failure_is_not_reported_as_success(self):
        result = self.run_script('wt-down', 'sample', 'topic', FAIL_DROP='1')
        self.assertEqual(result.returncode, 17)
        self.assertNotIn('removed;', result.stdout)

    def test_prune_handles_stopped_orphan_once_and_skips_ci_and_other_stack(self):
        self.state['orphan'] = self.runtime('gone', False)
        self.state['second-service'] = self.runtime('gone', False)
        self.state['ci'] = self.runtime('ci-fixture')
        self.state['ci']['labels'][LABEL+'.ci'] = 'true'
        self.state['foreign'] = self.runtime('foreign')
        self.state['foreign']['labels'][LABEL+'.stack'] = 'other'
        self.save()
        result = self.run_script('wt-prune')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('removed 1 orphan environment', result.stdout)
        remaining = json.loads(self.state_path.read_text())
        self.assertIn('ci', remaining)
        self.assertIn('foreign', remaining)
        self.assertNotIn('orphan', remaining)

    def test_inventory_failure_refuses_mutations(self):
        result = self.run_script('wt-down', 'sample', 'topic', FAIL_INVENTORY='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in ('compose','exec') for c in self.calls()))

    def test_seed_selects_exact_stack_database(self):
        result = self.run_script('wt-seed', 'sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['exec','database','/scripts/seed-from.sh','sample','sample_seed','root'], self.calls())

class DatabaseHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='wt-database-')
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log = self.directory / 'calls.jsonl'
        binaries = self.directory / 'bin'; binaries.mkdir()
        for command in ('mysql','mysqldump','psql','pg_dump'):
            path = binaries / command; path.write_text(FAKE_DATABASE); path.chmod(0o755)
        self.env = os.environ | {'PATH':str(binaries)+os.pathsep+os.environ['PATH'], 'DB_LOG':str(self.log),
                                'TMPDIR':str(self.directory), 'MYSQL_ROOT_PASSWORD':'fixture-only',
                                'POSTGRES_PASSWORD':'fixture-only', 'POSTGRES_USER':'custom_admin'}

    def helper(self, engine, script, *args, **extra):
        return subprocess.run([str(ROOT/'database'/'scripts'/engine/script), *args], env=self.env | extra,
                              input='', text=True, capture_output=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_sql_identifier_and_target_guards(self):
        for engine in ('mysql','postgres'):
            for script, args in [('drop-db.sh',('main',)), ('drop-db.sh',('main_wt_x;DROP',)),
                                 ('seed-from.sh',('main','other_seed')), ('clone-db.sh',('main_seed','other_wt_x'))]:
                with self.subTest(engine=engine, script=script, args=args):
                    self.assertNotEqual(self.helper(engine, script, *args).returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_failed_dump_preserves_old_seed_and_cleans_temporary_file(self):
        for engine in ('mysql','postgres'):
            with self.subTest(engine=engine):
                self.log.unlink(missing_ok=True)
                result = self.helper(engine,'seed-from.sh','main','main_seed', FAIL_DUMP='1')
                self.assertEqual(result.returncode, 9)
                self.assertEqual(len(self.calls()), 1)
                self.assertEqual(list(self.directory.glob('worktree-stack-dump.*')), [])

    def test_failed_mysql_clone_dump_creates_no_database(self):
        result = self.helper('mysql','clone-db.sh','main_seed','main_wt_feature', FAIL_DUMP='1')
        self.assertEqual(result.returncode, 9)
        self.assertEqual([c['command'] for c in self.calls()], ['mysqldump'])

    def test_seed_dump_precedes_drop_and_restore(self):
        for engine in ('mysql','postgres'):
            with self.subTest(engine=engine):
                self.log.unlink(missing_ok=True)
                result = self.helper(engine,'seed-from.sh','main','main_seed','owner')
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                self.assertEqual(calls[0]['command'], 'mysqldump' if engine == 'mysql' else 'pg_dump')
                self.assertIn('DROP DATABASE', ' '.join(calls[1]['argv']) + calls[1]['stdin'])
                self.assertEqual(calls[2]['stdin'], 'fixture dump\n')
                self.assertEqual(list(self.directory.glob('worktree-stack-dump.*')), [])

    def test_restore_failure_propagates_and_cleans_temporary_file(self):
        for engine in ('mysql','postgres'):
            with self.subTest(engine=engine):
                result = self.helper(engine,'seed-from.sh','main','main_seed', FAIL_RESTORE='1')
                self.assertEqual(result.returncode, 12)
                self.assertEqual(list(self.directory.glob('worktree-stack-dump.*')), [])

    def test_postgres_uses_configured_administrator(self):
        result = self.helper('postgres','clone-db.sh','main_seed','main_wt_feature','owner')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('custom_admin', self.calls()[0]['argv'])

if __name__ == '__main__':
    unittest.main()

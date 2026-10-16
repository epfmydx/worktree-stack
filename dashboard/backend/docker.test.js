import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { test, after } from 'node:test';

const root = await mkdtemp(path.join(os.tmpdir(), 'worktree-dashboard-'));
process.env.HOST_CONTAINERS_PATH = root;
const { getBaseComposeArgs, listProjects, runAction } = await import('./docker.js');
after(() => rm(root, { recursive: true, force: true }));

test('Compose uses root environment and identical host/container checkout paths', async () => {
  await mkdir(path.join(root, 'demo'));
  await writeFile(path.join(root, 'demo', '.env'), 'DEMO=1\n');
  assert.deepEqual(await getBaseComposeArgs('demo'), [
    'compose', '--env-file', path.join(root, '.env'),
    '-f', path.join(root, 'demo', 'docker-compose.yml'),
    '--project-directory', path.join(root, 'demo'),
    '--env-file', path.join(root, 'demo', '.env'),
  ]);
});

test('reject traversal and unsupported actions before spawning Docker', async () => {
  await assert.rejects(getBaseComposeArgs('../outside'), /Invalid project name/);
  await assert.rejects(runAction('demo', 'build;echo'), /Invalid action/);
});

test('project status includes stopped services and reports a partially running stack', async () => {
  const bin = path.join(root, 'bin');
  const calls = path.join(root, 'docker-args.txt');
  await mkdir(bin);
  await mkdir(path.join(root, 'mixed'));
  await writeFile(path.join(root, 'mixed', 'docker-compose.yml'), 'services: {}\n');
  await writeFile(path.join(bin, 'docker'), `#!/bin/sh
printf '%s\\n' "$@" > '${calls.replace(/'/g, "'\\''")}'
printf '%s\\n' '{"Service":"web","State":"running","Status":"Up 2 minutes"}'
for arg in "$@"; do
  if [ "$arg" = '--all' ]; then
    printf '%s\\n' '{"Service":"worker","State":"exited","Status":"Exited (1) 1 minute ago"}'
  fi
done
`, { mode: 0o755 });

  const originalPath = process.env.PATH;
  process.env.PATH = `${bin}${path.delimiter}${originalPath || ''}`;
  try {
    assert.deepEqual(await listProjects(), [{
      name: 'mixed',
      status: 'partial',
      services: [
        { name: 'web', state: 'running', status: 'Up 2 minutes' },
        { name: 'worker', state: 'exited', status: 'Exited (1) 1 minute ago' },
      ],
    }]);
    const args = (await readFile(calls, 'utf8')).trimEnd().split('\n');
    assert.deepEqual(args.slice(-4), ['ps', '--all', '--format', 'json']);
  } finally {
    if (originalPath === undefined) delete process.env.PATH;
    else process.env.PATH = originalPath;
  }
});

import { execFile, spawn } from 'node:child_process';
import { readdir, access } from 'node:fs/promises';
import path from 'node:path';

// Mount the checkout at the same absolute path inside the dashboard. Compose
// reads build contexts here and sends those same bind paths to the host daemon.
const CONTAINERS_PATH = process.env.HOST_CONTAINERS_PATH || '/containers';
const HOST_CONTAINERS_PATH = CONTAINERS_PATH;
const SKIP_DIRS = new Set(['base-images', 'dashboard']);

function validateProjectName(name) {
  if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
    throw new Error('Invalid project name');
  }
  return name;
}

function getComposePath(name) {
  validateProjectName(name);
  return path.join(CONTAINERS_PATH, name, 'docker-compose.yml');
}

export async function getBaseComposeArgs(name) {
  validateProjectName(name);
  const hostDir = path.join(HOST_CONTAINERS_PATH, name);
  const args = ['compose', '--env-file', path.join(CONTAINERS_PATH, '.env'),
    '-f', getComposePath(name), '--project-directory', hostDir];
  const envFile = path.join(CONTAINERS_PATH, name, '.env');
  try {
    await access(envFile);
    args.push('--env-file', envFile);
  } catch {}
  return args;
}

export async function listProjects() {
  const entries = await readdir(CONTAINERS_PATH, { withFileTypes: true });
  const projects = [];

  for (const entry of entries) {
    if (!entry.isDirectory() || SKIP_DIRS.has(entry.name)) continue;

    const composePath = path.join(CONTAINERS_PATH, entry.name, 'docker-compose.yml');
    try {
      await access(composePath);
    } catch {
      continue;
    }

    const status = await getProjectStatus(entry.name);
    projects.push({ name: entry.name, ...status });
  }

  return projects.sort((a, b) => a.name.localeCompare(b.name));
}

async function getProjectStatus(name) {
  const baseArgs = await getBaseComposeArgs(name);
  return new Promise((resolve) => {
    execFile('docker', [...baseArgs, 'ps', '--all', '--format', 'json'], (err, stdout) => {
      if (err) {
        return resolve({ status: 'error', services: [], error: 'Compose status failed' });
      }
      if (!stdout.trim()) {
        return resolve({ status: 'stopped', services: [] });
      }

      try {
        const services = stdout.trim().split('\n').map(line => {
          const s = JSON.parse(line);
          return { name: s.Service, state: s.State, status: s.Status };
        });

        const running = services.filter(s => s.state === 'running').length;
        let status = 'stopped';
        if (running === services.length && running > 0) status = 'running';
        else if (running > 0) status = 'partial';

        resolve({ status, services });
      } catch {
        resolve({ status: 'error', services: [], error: 'Invalid Compose status output' });
      }
    });
  });
}

const ALLOWED_ACTIONS = {
  up: ['up', '-d'],
  down: ['down'],
  restart: ['restart'],
};

export async function runAction(name, action) {
  const actionArgs = ALLOWED_ACTIONS[action];
  if (!actionArgs) throw new Error('Invalid action');

  const baseArgs = await getBaseComposeArgs(name);
  return new Promise((resolve, reject) => {
    execFile('docker', [...baseArgs, ...actionArgs],
      { maxBuffer: 10 * 1024 * 1024, timeout: 300000 },
      (err, stdout, stderr) => {
        if (err) return reject(new Error(stderr || err.message));
        resolve(stdout + stderr);
      });
  });
}

export async function streamLogs(name, service) {
  validateProjectName(name);
  const baseArgs = await getBaseComposeArgs(name);
  const args = [...baseArgs, 'logs', '--follow', '--tail', '100'];
  if (service) {
    validateProjectName(service);
    args.push(service);
  }
  return spawn('docker', args);
}

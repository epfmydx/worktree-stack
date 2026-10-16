import express from 'express';
import cookieParser from 'cookie-parser';
import { WebSocketServer } from 'ws';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { parse as parseCookies } from 'cookie';
import { generateToken, requireAuth, verifyToken } from './auth.js';
import { listProjects, runAction, streamLogs } from './docker.js';

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ server, path: '/api/logs' });

const PORT = process.env.PORT || 80;
const __dirname = path.dirname(fileURLToPath(import.meta.url));

app.use(express.json());
app.use(cookieParser());

// --- Auth Routes ---

app.post('/api/auth/login', (req, res) => {
  const { password } = req.body;
  if (!password || password !== process.env.DASHBOARD_PASSWORD) {
    return res.status(401).json({ error: 'Wrong password' });
  }

  const token = generateToken(password);
  res.cookie('dashboard_auth', token, {
    httpOnly: true,
    secure: true,
    sameSite: 'strict',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });
  res.json({ ok: true });
});

app.post('/api/auth/logout', (req, res) => {
  res.clearCookie('dashboard_auth');
  res.json({ ok: true });
});

app.get('/api/auth/check', requireAuth, (req, res) => {
  res.json({ ok: true });
});

// --- Project Routes ---

app.get('/api/projects', requireAuth, async (req, res) => {
  try {
    const projects = await listProjects();
    res.json(projects);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/projects/:name/:action', requireAuth, async (req, res) => {
  const { name, action } = req.params;
  if (!['up', 'down', 'restart'].includes(action)) {
    return res.status(400).json({ error: 'Invalid action' });
  }

  try {
    const output = await runAction(name, action);
    res.json({ ok: true, output });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// --- WebSocket Logs ---

wss.on('connection', async (ws, req) => {
  const cookies = parseCookies(req.headers.cookie || '');
  const token = cookies.dashboard_auth;
  if (!token) {
    ws.close(1008, 'Not authenticated');
    return;
  }

  try {
    if (!verifyToken(token)) {
      ws.close(1008, 'Invalid token');
      return;
    }
  } catch {
    ws.close(1008, 'Invalid token');
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host}`);
  const project = url.searchParams.get('project');
  if (!project) {
    ws.close(1008, 'Missing project parameter');
    return;
  }
  const service = url.searchParams.get('service') || undefined;

  let logProcess;
  try {
    logProcess = await streamLogs(project, service);
  } catch (err) {
    ws.close(1008, err.message);
    return;
  }

  logProcess.stdout.on('data', (data) => {
    if (ws.readyState === ws.OPEN) ws.send(data.toString());
  });

  logProcess.stderr.on('data', (data) => {
    if (ws.readyState === ws.OPEN) ws.send(data.toString());
  });

  logProcess.on('close', () => {
    if (ws.readyState === ws.OPEN) ws.close(1000, 'Log stream ended');
  });

  ws.on('close', () => {
    logProcess.kill();
  });
});

// --- Static Files ---

app.use(express.static(path.join(__dirname, 'public')));
app.get('/{*path}', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

server.listen(PORT, () => {
  console.log(`Dashboard running on port ${PORT}`);
});

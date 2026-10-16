(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const loginView = byId('login-view');
  const dashboardView = byId('dashboard-view');
  const passwordInput = byId('password-input');
  const loginButton = byId('login-btn');
  const logoutButton = byId('logout-btn');
  const projectsElement = byId('projects');
  const refreshButton = byId('refresh-btn');
  const logs = new Map();
  const pendingActions = new Map();
  let authenticated = false;
  let interval = null;
  let projects = [];
  let loaded = false;
  let loadSequence = 0;
  let projectRequest = null;
  let messageKind = '';

  const api = (method, path, body) => fetch(path, {
    method, credentials: 'same-origin',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function message(text, kind = '') {
    byId('workspace-message').textContent = text;
    byId('workspace-message').hidden = !text;
    messageKind = kind;
  }

  function showView(signedIn) {
    authenticated = signedIn;
    loginView.hidden = signedIn;
    dashboardView.hidden = !signedIn;
    logoutButton.hidden = !signedIn;
    clearInterval(interval);
    if (signedIn) {
      loadProjects();
      interval = setInterval(loadProjects, 10000);
    } else {
      loadSequence++;
      projectRequest = null;
      for (const name of logs.keys()) closeLogs(name);
      projects = [];
      loaded = false;
      passwordInput.focus();
    }
  }

  async function checkAuth() {
    try {
      const response = await api('GET', '/api/auth/check');
      showView(response.ok);
      if (!response.ok && response.status !== 401) {
        byId('login-error').textContent = 'The dashboard is unavailable. Try again shortly.';
      }
    } catch {
      showView(false);
      byId('login-error').textContent = 'Cannot reach the dashboard. Check the connection and try again.';
    }
  }

  byId('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (loginButton.disabled || !passwordInput.value) return;
    loginButton.disabled = true;
    loginButton.firstElementChild.textContent = 'Signing in…';
    byId('login-error').textContent = '';
    passwordInput.removeAttribute('aria-invalid');
    try {
      const response = await api('POST', '/api/auth/login', { password: passwordInput.value });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Unable to sign in. Try again.');
      }
      passwordInput.value = '';
      showView(true);
      byId('workspace').focus();
    } catch (error) {
      byId('login-error').textContent = error.message === 'Failed to fetch'
        ? 'Cannot reach the dashboard. Try again.' : error.message;
      passwordInput.setAttribute('aria-invalid', 'true');
      passwordInput.focus();
    } finally {
      loginButton.disabled = false;
      loginButton.firstElementChild.textContent = 'Sign in';
    }
  });

  logoutButton.addEventListener('click', async () => {
    logoutButton.disabled = true;
    try {
      const response = await api('POST', '/api/auth/logout');
      if (!response.ok) throw new Error();
      showView(false);
      byId('login-error').textContent = '';
    } catch {
      message('Could not sign out. Check the connection and try again.', 'action');
    } finally {
      logoutButton.disabled = false;
    }
  });
  refreshButton.addEventListener('click', loadProjects);

  function projectState(project) {
    if (project.status === 'error') return { key: 'error', label: 'Unavailable', symbol: '!' };
    const services = project.services || [];
    const running = services.filter(service => service.state === 'running').length;
    if (services.length) {
      if (running === services.length) return { key: 'running', label: 'Running', symbol: '●' };
      if (running) return { key: 'partial', label: 'Partial', symbol: '◐' };
      return { key: 'stopped', label: 'Stopped', symbol: '○' };
    }
    if (project.status === 'running') return { key: 'running', label: 'Running', symbol: '●' };
    if (project.status === 'stopped') return { key: 'stopped', label: 'Stopped', symbol: '○' };
    return { key: 'unknown', label: 'Unknown', symbol: '?' };
  }

  function loadProjects() {
    if (!authenticated) return Promise.resolve();
    if (projectRequest) return projectRequest;
    const request = fetchProjects();
    projectRequest = request;
    request.finally(() => { if (projectRequest === request) projectRequest = null; });
    return request;
  }

  async function fetchProjects() {
    const sequence = ++loadSequence;
    refreshButton.setAttribute('aria-busy', 'true');
    byId('refresh-state').textContent = 'Updating…';
    try {
      const response = await api('GET', '/api/projects');
      if (sequence !== loadSequence || !authenticated) return;
      if (response.status === 401) {
        byId('login-error').textContent = 'Your session ended. Sign in again.';
        showView(false);
        return;
      }
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (!Array.isArray(data)) throw new Error();
      if (sequence !== loadSequence || !authenticated) return;
      projects = data;
      loaded = true;
      if (messageKind === 'load') message('');
      renderProjects();
      byId('refresh-state').textContent = 'Updated just now · every 10s';
    } catch {
      if (sequence !== loadSequence || !authenticated) return;
      message(loaded ? 'Could not refresh projects. Showing the last available status.'
        : 'Could not load projects. Check the Docker connection, then refresh.', 'load');
      byId('refresh-state').textContent = 'Refresh failed';
      if (!loaded) {
        projectsElement.replaceChildren(element('p', 'empty-state', 'Project status is unavailable.'));
        byId('workspace-summary').textContent = 'Connection unavailable';
      }
    } finally {
      if (sequence === loadSequence) refreshButton.removeAttribute('aria-busy');
    }
  }

  function renderProjects() {
    const focusKey = document.activeElement?.dataset.focusKey;
    const scrollPositions = new Map();
    projectsElement.querySelectorAll('.log-output').forEach(node => {
      scrollPositions.set(node.id, { top: node.scrollTop, atEnd: node.scrollHeight - node.clientHeight - node.scrollTop < 30 });
    });
    const names = new Set(projects.map(project => project.name));
    for (const name of logs.keys()) if (!names.has(name)) closeLogs(name);
    projectsElement.replaceChildren();
    byId('project-count').textContent = String(projects.length).padStart(2, '0');
    const running = projects.filter(project => projectState(project).key === 'running').length;
    byId('workspace-summary').textContent = `${running} of ${projects.length} projects running`;
    if (!projects.length) {
      projectsElement.append(element('p', 'empty-state', 'No projects found. Add a project with a docker-compose.yml file to this checkout.'));
    }
    projects.forEach((project, index) => {
      const name = project.name;
      const state = projectState(project);
      const services = project.services || [];
      const activeServices = services.filter(service => service.state === 'running').length;
      const row = element('article', 'project-row');
      row.dataset.project = name;
      row.setAttribute('aria-label', name);
      const main = element('div', 'project-main');
      const number = element('span', 'project-number', String(index + 1).padStart(2, '0'));
      number.setAttribute('aria-hidden', 'true');
      const identity = element('div', 'project-identity');
      identity.append(element('span', 'project-name', name));
      const detail = project.error || (services.length
        ? `${activeServices} / ${services.length} services running · ${services.map(service => service.name).join(', ')}`
        : state.key === 'stopped' ? 'No active services' : 'Service details unavailable');
      identity.append(element('span', 'project-detail', detail));
      const status = element('span', `project-status status-${state.key}`);
      const symbol = element('span', 'status-symbol', state.symbol);
      symbol.setAttribute('aria-hidden', 'true');
      status.append(symbol, document.createTextNode(state.label));
      const actions = element('div', 'project-actions');
      const pending = pendingActions.get(name);
      [['Start', 'up'], ['Stop', 'down'], ['Restart', 'restart']].forEach(([label, action]) => {
        const button = element('button', '', pending === action ? `${label}…` : label);
        button.dataset.focusKey = `${name}:${action}`;
        button.setAttribute('aria-label', `${label} ${name}`);
        button.disabled = !!pending || ['error', 'unknown'].includes(state.key)
          || (action !== 'up' && state.key === 'stopped');
        button.addEventListener('click', () => projectAction(name, action));
        actions.append(button);
      });
      const logsButton = element('button', `logs-button${logs.has(name) ? ' btn-logs-active' : ''}`, 'Logs');
      logsButton.dataset.focusKey = `${name}:logs`;
      logsButton.setAttribute('aria-label', `Logs for ${name}`);
      logsButton.setAttribute('aria-expanded', String(logs.has(name)));
      logsButton.setAttribute('aria-controls', `logs-${name}`);
      logsButton.addEventListener('click', () => {
        if (logs.has(name)) closeLogs(name); else connectLogs(name, null);
        renderProjects();
      });
      actions.append(logsButton);
      main.append(number, identity, status, actions);
      row.append(main, logPanel(project));
      projectsElement.append(row);
    });
    projectsElement.querySelectorAll('.log-output').forEach(node => {
      const position = scrollPositions.get(node.id);
      node.scrollTop = !position || position.atEnd ? node.scrollHeight : position.top;
    });
    if (focusKey) {
      const control = Array.from(projectsElement.querySelectorAll('[data-focus-key]')).find(node => node.dataset.focusKey === focusKey);
      if (control && !control.disabled) control.focus({ preventScroll: true });
      else if (control) control.closest('.project-row').querySelector('.logs-button').focus({ preventScroll: true });
    }
  }

  async function projectAction(name, action) {
    if (pendingActions.has(name)) return;
    pendingActions.set(name, action);
    message('');
    renderProjects();
    try {
      const response = await api('POST', `/api/projects/${encodeURIComponent(name)}/${action}`);
      if (response.status === 401) { showView(false); return; }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'The operation failed.');
      }
      if (projectRequest) await projectRequest;
      await loadProjects();
    } catch (error) {
      message(`${name}: ${error.message === 'Failed to fetch' ? 'Connection lost. Refresh to check the result before retrying.' : error.message}`, 'action');
    } finally {
      pendingActions.delete(name);
      if (authenticated) renderProjects();
    }
  }

  function logPanel(project) {
    const entry = logs.get(project.name);
    const panel = element('section', `log-panel${entry ? ' open' : ''}`);
    panel.id = `logs-${project.name}`;
    panel.setAttribute('aria-label', `Logs for ${project.name}`);
    if (!entry) return panel;
    const toolbar = element('div', 'log-toolbar');
    const title = element('p', 'log-title', entry.state);
    title.id = `log-state-${project.name}`;
    toolbar.append(title);
    if ((project.services || []).length > 1) {
      const tabs = element('div', 'log-tabs');
      tabs.setAttribute('aria-label', 'Filter logs by service');
      [[null, 'All services'], ...project.services.map(service => [service.name, service.name])].forEach(([service, label]) => {
        const button = element('button', entry.filter === service ? 'active' : '', label);
        button.dataset.focusKey = `${project.name}:filter:${service || 'all'}`;
        button.setAttribute('aria-pressed', String(entry.filter === service));
        button.addEventListener('click', () => { connectLogs(project.name, service); renderProjects(); });
        tabs.append(button);
      });
      toolbar.append(tabs);
    }
    const output = element('pre', 'log-output', entry.buffer.join('') || 'Waiting for log output…');
    output.id = `log-output-${project.name}`;
    output.tabIndex = 0;
    output.dataset.focusKey = `${project.name}:output`;
    output.setAttribute('aria-label', `${project.name} log output`);
    panel.append(toolbar, output);
    return panel;
  }

  function connectLogs(name, filter) {
    closeLogs(name);
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${location.host}/api/logs?project=${encodeURIComponent(name)}${filter ? `&service=${encodeURIComponent(filter)}` : ''}`;
    const socket = new WebSocket(url);
    const entry = { socket, filter, buffer: [], state: 'Connecting to logs…' };
    logs.set(name, entry);
    const updateState = text => {
      if (logs.get(name) !== entry) return;
      entry.state = text;
      const title = byId(`log-state-${name}`);
      if (title) title.textContent = text;
    };
    socket.onopen = () => updateState('Live logs');
    socket.onmessage = event => {
      if (logs.get(name) !== entry) return;
      entry.buffer.push(event.data);
      if (entry.buffer.length > 5000) entry.buffer = entry.buffer.slice(-3000);
      const output = byId(`log-output-${name}`);
      if (output) {
        const atEnd = output.scrollHeight - output.clientHeight - output.scrollTop < 30;
        output.textContent = entry.buffer.join('');
        if (atEnd) output.scrollTop = output.scrollHeight;
      }
    };
    socket.onerror = () => updateState('Log connection failed. Close and reopen to retry.');
    socket.onclose = () => {
      if (!entry.state.startsWith('Log connection failed')) updateState('Log stream ended. Close and reopen to reconnect.');
    };
  }

  function closeLogs(name) {
    const entry = logs.get(name);
    logs.delete(name);
    if (entry) entry.socket.close();
  }

  checkAuth();
})();

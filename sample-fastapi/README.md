# FastAPI + React sample

A small Todos application with an async Python API, PostgreSQL and a React/Vite
frontend. A per-project Caddy routes `/api/*` to the API and other paths to Vite;
the shared gateway terminates HTTPS.

From the repository root, follow [setup](../docs/operations/setup.md), then:

```sh
make sample-setup p=sample-fastapi
```

Default URL: `https://sample-fastapi.worktree.test:8443`. Containers install
dependencies and run API migrations before starting. Watch startup logs if the
page is not ready yet. Vite uses the configured gateway port for WebSockets.

[Worktree instructions](../docs/operations/worktrees.md) explain branch runtimes.
[CI instructions](../docs/operations/ci.md) describe the isolated PostgreSQL suite.
The backend adapter does not test the browser or frontend build.

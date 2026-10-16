# Worktree Stack

A local Docker development stack for working on several projects and branches at
once. Edit source with your normal editor or coding agent, run each Git worktree
in its own environment, and run CI checks from a disposable source volume inside
Docker.

This is the workflow I use for my own projects, extracted into a configurable
starting point for other developers and teams.

## What's included

| Component | Purpose |
| --- | --- |
| Shared infrastructure | HTTPS gateway, container DNS, MySQL, PostgreSQL and Redis. |
| Laravel sample | A small MySQL-backed Todos app using a shared PHP image. |
| FastAPI + React sample | A PostgreSQL-backed API and Vite frontend behind Caddy. |
| Worktree commands | Start a branch runtime, clone a development database, and tear down owned resources. |
| Disposable CI | Snapshot current source into a fresh Docker volume, run the project's checks, export reports, and clean up. |
| Optional dashboard | Start, stop and inspect this checkout's Compose projects. |
| Optional Kubernetes DNS | Connect Docker Desktop pods to the local gateway. |

The dashboard has access to the Docker socket. Enable it only on a machine where
you trust the checkout and its users. This stack is for local development.

## Get started

Requirements: Git, Python 3.9+, Bash, Make, OpenSSL and Docker with Compose
**2.24.4 or newer**. The host DNS helper is for macOS with Homebrew dnsmasq.
Linux can use the Compose stack with separately configured host DNS; Windows
support has not been verified.

```sh
git clone https://github.com/epfmydx/worktree-stack.git
cd worktree-stack
make init
# Review .env: stack name, domain, ports and local paths.
make networks
make base
make infra
make sample-setup p=sample-laravel
make sample-setup p=sample-fastapi
```

The defaults use `worktree.test`, a separate Docker network, and loopback ports
8080/8443. Certificates and random local passwords are generated on your machine.
Follow [setup](docs/operations/setup.md) to configure DNS and trust your own
certificate, then open the sample URLs on port 8443.

## Work on a branch

The included examples live in this repository. A worktree contains the whole
checkout; each sample mounts only its own source directory.

```sh
./worktrees/scripts/wt-seed sample-laravel
git worktree add worktrees/feature -b feature
./worktrees/scripts/wt-spin sample-laravel feature
./worktrees/scripts/wt-test sample-laravel feature
./worktrees/scripts/wt-down sample-laravel feature
# Inspect and commit your changes before removing a source worktree.
git worktree remove worktrees/feature
```

`wt-test` freezes tracked working files and nonignored untracked files, including
uncommitted changes. Dependencies are installed inside Linux; host `vendor`,
`node_modules`, `.env` files and Git metadata are excluded. Each run has its own
source volume, network and any test database declared by the adapter.

Editing stays on your host. CI uses Docker's filesystem. There is no bidirectional
source sync to maintain.

## Guides

- [Setup, ports and certificates](docs/operations/setup.md)
- [Worktree lifecycle and database seeds](docs/operations/worktrees.md)
- [Disposable CI and project adapters](docs/operations/ci.md)
- [Architecture and trust boundaries](docs/architecture/overview.md)
- [Kubernetes DNS](k8s/README.md)
- [Validation and current limits](docs/validation.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE). Included third-party material is identified in [NOTICE.md](NOTICE.md).

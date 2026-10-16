# Contributing

Keep examples small and synthetic. Private application configuration, production
routing, runtime data, generated certificates and credentials do not belong in
this repository. Use `.env.example` to document configuration; generate real local
values with `make init`.

## Checks

Initialize ignored local configuration and certificates once before checking a
fresh checkout. `make init` preserves existing settings and does not change host
DNS, trust or running containers.

```sh
make init
python3 -m unittest discover -s worktrees/scripts/tests -p 'test_*.py' -v
node --check dashboard/backend/public/app.js
node --test dashboard/backend/docker.test.js
python3 scripts/test_infrastructure.py -v
make config
```

The unit suite skips live Docker acceptance unless an image is explicitly chosen.
To run that suite with a local Linux image containing GNU tar, coreutils and a
shell, with no declared image volumes:

```sh
WT_TEST_DOCKER_IMAGE=ubuntu:24.04 python3 -m unittest discover \
  -s worktrees/scripts/tests -p test_wt_test_docker.py -v
```

Pull or build the image separately. The test runner never silently pulls an image.
Tests create isolated fixtures and clean up their owned resources. They do not
validate the whole interactive stack; see [validation](docs/validation.md).

## Dependency changes

Keep the sample lockfiles committed. Use `npm ci` for locked frontend installs;
run `npm run build` in each changed sample frontend. The FastAPI frontend needs
Node `^20.19.0 || >=22.12.0`; refresh an older cached `node:22-alpine` image before
using it. The Laravel sample is validated with the default PHP 8.4 image.

Before release, audit all three npm lockfiles (`dashboard/backend`,
`sample-fastapi/source/frontend`, `sample-laravel/backend/source`) with
`npm audit --package-lock-only`. In the Laravel PHP runtime, run
`composer validate --strict`, `composer check-platform-reqs --lock` and
`composer audit --locked`, then rerun its disposable CI profile after PHP updates.
For Python, use an isolated Python 3.12 environment with `pip-audit` installed and
run `pip-audit --disable-pip --no-deps -r requirements-ci.txt` from the backend
directory. That command audits the complete pinned CI list; re-resolve and rerun
the PostgreSQL suite if those pins change. Record the checked versions and limits
in [validation](docs/validation.md). These audits are separate from the toolkit
workflow and do not scan container OS packages.

## Documentation

Update the guide that explains the changed behavior. Command setup belongs in
`docs/operations/`, boundaries in `docs/architecture/`, and tested/untested scope
in `docs/validation.md`. Keep the README brief and use repository-relative links.
Check examples against the implemented commands. Record actual checks separately
from intended behavior; a rendered Compose file is not a running application.

## Release

Use a clean checkout. Run the applicable checks, inspect the staged file list and
review generated/ignored files before publication. Never publish local reports,
source archives, `.env`, database state or private keys. Publish only with the
maintainer's explicit authorization and verify the remote commit after pushing.

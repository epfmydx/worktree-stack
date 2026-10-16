# Validation and limits

Worktree Stack is a local development toolkit. Its automated checks cover
snapshot isolation, resource ownership, infrastructure configuration and the
included sample applications. Use this page to understand what a passing check
establishes for your environment.

## Run the checks

[Contributing](../CONTRIBUTING.md#checks) lists the toolkit commands and the
opt-in Docker acceptance suite. [Disposable CI](operations/ci.md) explains how
to run the sample application profiles and inspect their reports.

The [Toolkit checks workflow](../.github/workflows/checks.yml) runs the Python
and Node toolkit tests, JavaScript syntax checks, infrastructure/configuration
checks and Docker acceptance on Ubuntu. Sample application suites, frontend
builds and dependency audits are separate checks. See
[GitHub Actions](https://github.com/epfmydx/worktree-stack/actions) for the result
of a particular commit.

## Local validation

Local checks recorded on 2026-10-16 used macOS with Docker Desktop. PHP checks
used the repository's PHP 8.4 image; both frontend builds used Node 22.23.2.
The FastAPI backend uses Python 3.12.

| Scope | Coverage and result |
| --- | --- |
| Toolkit | 51 Python regressions passed: 33 for CI snapshots and 18 for interactive lifecycle/database helpers. |
| Docker acceptance | 5 isolated tests passed, covering a non-root runtime, source boundaries, failures, cancellation and concurrent cleanup. |
| Infrastructure | 3 tests passed for generated config/certificates, Compose namespace/aliases/ports and CoreDNS configuration preservation. These tests do not modify host DNS or a live cluster. |
| Dashboard backend | JavaScript syntax checks and 3 command-construction tests passed. |
| Laravel sample CI | Full profile: 5 tests / 16 assertions. Smoke: 1 test / 2 assertions. Uses isolated SQLite. |
| FastAPI sample CI | Full profile: 5 tests including disposable PostgreSQL CRUD. Smoke: 4 health/schema tests. |
| Sample frontends | Clean locked npm installs and both production builds passed; the React build includes TypeScript checks. |
| FastAPI dev server | Loopback HTTP/module responses, allowed/rejected hosts and an HMR update passed on Node 24.15.0. This check does not exercise the HTTPS gateway. |

Sample CI reports verified matching source snapshots and cleanup without errors.
A profile marked `full` covers that adapter's declared suite; it does not include
all possible browser, integration or deployment checks.

### Dependency audits

At the recorded date, npm lockfile audits reported zero findings for the
dashboard and both sample frontends. Composer validation, locked platform
requirements and the advisory audit passed on PHP 8.4.24, with no advisories or
abandoned packages. A Python 3.12 `pip-audit` scan of all 35 pinned CI packages
reported zero findings.

These audits include development dependencies. They do not scan container OS
packages or establish that unknown vulnerabilities are absent. Follow the
[dependency checks](../CONTRIBUTING.md#dependency-changes) when updating locks or
constraints. Image tags and dependency constraints do not guarantee bit-for-bit
reproducibility.

## Support boundaries

- The complete interactive stack and branch runtimes need end-to-end acceptance
  against your chosen images, dependency versions, gateway and host configuration.
  The local checks above do not establish that integration for the current locks.
- Dashboard browser coverage uses synthetic API responses. Real Docker actions,
  authentication/session expiry and gateway behavior require integration checks.
- Laravel's disposable CI profile uses SQLite and does not establish MySQL parity.
  The FastAPI backend profile does not build or test the React frontend.
- Host DNS and system trust commands require deliberate local setup. They were
  inspected but not executed as part of validation.
- Kubernetes support has static patch tests; no live cluster acceptance is claimed.
- Remote Linux VM workflows, Windows and production deployment are unverified.
- Seed replacement is not atomic on restore failure. Resolve the reported error
  and refresh the seed before creating new clones; see [worktrees](operations/worktrees.md).

Keep validation records tied to the source and configuration actually checked.
A passing frozen snapshot does not validate later edits or another installation.

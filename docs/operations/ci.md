# Disposable source-volume CI

Run from the original stack checkout after creating a registered worktree:

```sh
./worktrees/scripts/wt-test sample-laravel feature
./worktrees/scripts/wt-test sample-fastapi feature --profile smoke
```

The samples discover an existing runtime image from exactly one running container
whose source bind mount matches the selected worktree. Run `wt-spin` first, or
choose an existing local image explicitly:

```sh
./worktrees/scripts/wt-test sample-laravel feature \
  --image worktree-stack/php-laravel:8.4 \
  --output-dir /tmp/my-worktree-ci-result
```

The output directory must not exist. The runner never pulls or builds an image
implicitly. Service images must also exist locally; the FastAPI sample needs
`postgres:17.2`. The app image needs a shell, GNU tar, `sleep`, `id` and `chown`;
it must not declare implicit volumes. The runtime image's configured user is
preserved; only the fresh source volume's ownership is initialized as root.

## What a run checks

| Sample | `full` | `smoke` |
| --- | --- | --- |
| Laravel | Included PHPUnit suite using isolated SQLite, including Todos CRUD. | The Todos page response. |
| FastAPI backend | Included pytest suite, including CRUD against a disposable PostgreSQL service. | Health and schema checks. |

`full` means the complete suite declared by that adapter. It does not imply every
possible project gate. These examples do not run security audits, browser tests,
load tests or deployment checks. Laravel CI does not prove MySQL compatibility;
FastAPI CI does not build/test the React frontend. Add the gates your project
requires. Both FastAPI profiles currently prepare PostgreSQL and migrations;
smoke selects fewer tests.

## Input and results

The input includes current tracked contents and nonignored untracked files,
including dirty changes. Deleted files remain absent. Git metadata, `.env*`,
`.secrets*`, host dependencies and adapter-specific generated/runtime paths are
excluded. Symlinks must remain inside the selected source and must not target
excluded content. Submodules need a separate adapter strategy and are refused.

A run records HEAD, a content/mode fingerprint, an archive hash, the adapter hash
and immutable image IDs. The copied source is verified before and after dependency
preparation. A preparation step that rewrites an included source file fails the
run rather than silently changing the tested input.

Default reports are ignored under:

```text
worktrees/test-results/<project>/<slug>/<run-id>/
  input-manifest.json
  result.json
  <number>-<step>.log
  ... exported test reports
```

Read `status`, `checks_passed`, `full_gate_passed`, `current_source_matches` and
`cleanup_errors` in `result.json`. A smoke pass is never a full gate pass. Later
source edits do not invalidate the frozen report, but the report must not be
presented as validation of those later edits.

Each run gets a fresh source volume and private bridge. The FastAPI database uses
tmpfs with random test credentials. No app source bind mount, development network
or host port is attached to the CI runtime. Dependencies are installed inside
Linux; dependency installation still requires network access.

## Adapter contract

Place trusted `wt-test.json` beside a project's Compose file. The two sample
adapters are executable examples:

- [Laravel](../../sample-laravel/wt-test.json)
- [FastAPI](../../sample-fastapi/wt-test.json)

| Field | Meaning |
| --- | --- |
| `version` | `1`. |
| `repository_scope` | `stack` for this repository's samples; omit for a separate application repository. |
| `source_repository` | `.` for stack scope; otherwise path within `<stack>/<project>`, such as `backend/source`. |
| `source_subdirectory` | Required safe path in stack scope; only this subtree is snapshotted. Project scope snapshots its entire application worktree. |
| `image_donor` | `mount` selects exactly one running app with the matching bind mount; otherwise the legacy `<container_prefix>-<slug>` name is used. `--image` overrides discovery. |
| `container_prefix` | Safe lowercase name for the unique CI app container. |
| `workdir` | Absolute runtime source mount / command working directory. |
| `exclude` | Additional source filename patterns. |
| `environment` | Synthetic app environment variables. |
| `host_environment` | Explicit environment additions for host controller steps. |
| `controller_files` | Optional regular files copied from the snapshot for host steps. |
| `services` | Isolated service definitions: `name`, existing local `image`, `environment`, `tmpfs`, `ready`, optional `command`, `ready_environment`, `ready_timeout`. |
| `prepare` | Steps run before source is reverified. |
| `profiles` | Named profiles with `full_gate`, nonempty `steps`, and expected `reports`. |

Steps have a descriptive `name`, `scope` (`container` or `host`) and an `argv`
array. Arguments are passed directly; use `sh -ec` explicitly if shell syntax is
needed. Host steps run in a temporary controller directory, not in the live source.
Reports are exported from `/tmp/wt-test-reports` inside the app container.

Template strings include `{{container}}`, `{{run_id}}`, `{{run_slug}}`,
`{{db_suffix}}`, `{{reports}}`, `{{worktree_slug}}`, `{{test_password}}` and
`{{app_key}}`. Passwords and keys are newly generated for each run. Do not reference
real environment files or external application databases.

For separate repositories, the expected source repository is
`<stack>/<project>/<source_repository>` and its registered worktree is
`<stack>/worktrees/<project>/<slug>`. Stack scope uses
`<stack>/worktrees/<slug>`. Worktrees must share the configured repository's Git
common directory and appear in its worktree registry.

Adapters and host steps are trusted code, not a security sandbox. Review them
before execution. The runner validates structural and ownership invariants; it
cannot decide whether a test command is safe for your external services.

## Cancellation and recovery

SIGINT/SIGTERM stop the host command group and the run's containers before owned
resources are removed. Report export happens before container deletion. If report
retrieval fails after testing starts, stopped resources are retained for recovery
and the command returns failure. Read the printed report path and `cleanup_errors`.

A killed process or unavailable Docker daemon can leave resources. Inspect their
exact run label before deciding to remove them:

```sh
# Replace RUN_ID with the run_id from result.json.
docker container ls -a --filter label=io.github.epfmydx.worktree-stack.ci.run=RUN_ID
docker volume ls --filter label=io.github.epfmydx.worktree-stack.ci.run=RUN_ID
docker network ls --filter label=io.github.epfmydx.worktree-stack.ci.run=RUN_ID
```

Recover reports first if needed. Remove only the exact owned resources listed in
that run's result; do not run a global prune. `wt-down`/`wt-prune` handle interactive
environments and do not clean up CI resources.

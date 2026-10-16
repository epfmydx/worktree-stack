# Worktree environments

The included examples use one Git repository and a whole-repository worktree at
`worktrees/<slug>`. Commands are run from the original checkout. Slugs and project
names must match `[a-z][a-z0-9-]*`.

## Start a branch

First initialize the main sample with [setup](setup.md), then create a seed from
its development database:

```sh
./worktrees/scripts/wt-seed sample-laravel
# Or: ./worktrees/scripts/wt-seed sample-fastapi
```

A seed is a snapshot for development clones. Refreshing it replaces the seed,
not existing worktree databases. The helper validates identifiers and obtains a
complete dump before replacing the seed. Never point these helpers at customer
or production databases.

Seed replacement is not atomic: a restore failure can leave an incomplete seed.
The command reports failure; resolve the cause and rerun it before creating new
clones. An interrupted first startup can leave a clone without a runtime. Use
`wt-down` for that project/slug before retrying; startup refuses to overwrite it.

```sh
git worktree add worktrees/feature -b feature
./worktrees/scripts/wt-spin sample-laravel feature
# To use FastAPI from the same worktree, initialize and seed it too:
make sample-setup p=sample-fastapi
./worktrees/scripts/wt-seed sample-fastapi
./worktrees/scripts/wt-spin sample-fastapi feature
```

The commands verify Git registration/common repository identity, select the exact
stack's database Compose service, and use the project's `wt-config.sh` and
`docker-compose.worktree.yml`. They do not search for an arbitrary MySQL or
PostgreSQL container.

The default Laravel URL is
`https://sample-laravel-feature.worktree.test:8443`. Its database is
`sample_laravel_wt_feature`, cloned from `sample_laravel_seed`. The source stays in
`worktrees/feature/sample-laravel/backend/source`, visible to your editor or agent.

Project hooks may install dependencies and run migrations. Treat those hooks as
trusted project code. For meaningful changes, commit shared stack configuration
before creating a worktree so the branch starts with the intended files.

## Test a branch

```sh
./worktrees/scripts/wt-test sample-laravel feature
./worktrees/scripts/wt-test sample-fastapi feature
```

See [CI](ci.md) for frozen input, image selection, gate scope and reports. CI does
not consume the interactive worktree's database clone.

## Stop and clean up

```sh
./worktrees/scripts/wt-down sample-laravel feature
./worktrees/scripts/wt-down sample-fastapi feature
```

Teardown checks resource ownership, stops the selected runtime and drops that
project's worktree database. Failures are reported. The Git worktree remains.
Inspect and save your changes before removing source:

```sh
git -C worktrees/feature status --short
git worktree remove worktrees/feature
```

If Git refuses because local files remain, inspect them. Use force only after an
explicit decision to discard those files; runtime teardown does not make source
disposable.

`wt-prune` handles stale managed runtimes whose registered source worktree is
gone. It uses ownership labels and excludes CI resources. Prefer normal teardown
while the source and configuration still exist. Run it without arguments from the original checkout:
`./worktrees/scripts/wt-prune`.

## Add a project

Follow the examples' Compose file, worktree override and `wt-config.sh`. Set an
explicit `PREFIX`, optional `MAIN_DB`/`DB_HOST`/`DB_USERNAME`, and source path.
Include the same ownership labels and replace main network aliases in the
worktree override so a branch cannot claim the main app's hostname.

The interactive commands currently use this repository's whole-checkout layout.
The CI runner additionally supports separate application repositories through its
adapter. Do not assume those two layout contracts are interchangeable.

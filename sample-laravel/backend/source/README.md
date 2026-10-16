# Laravel Todos source

This directory contains Worktree Stack's Laravel sample. Apache serves the
application from `public/`, and the stack bind-mounts this source at
`/var/www/html`. The sample provides a Todos page with list, create and delete
actions.

Follow the [sample guide](../../README.md) and the
[stack setup](../../../docs/operations/setup.md) from the repository root.
The [worktree guide](../../../docs/operations/worktrees.md) describes isolated
branch environments, and [disposable CI](../../../docs/operations/ci.md) explains
the SQLite test profiles.

PHP dependencies are locked in `composer.lock`; frontend dependencies are locked
in `package-lock.json`. Use `composer install` and `npm ci` in the PHP runtime.
See [Contributing](../../../CONTRIBUTING.md) for build and dependency checks.

The application skeleton is derived from [Laravel](https://laravel.com/).
Its original [MIT notice](LICENSE) is retained.

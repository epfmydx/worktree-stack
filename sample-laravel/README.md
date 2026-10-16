# Laravel sample

A small Todos application served by Apache/PHP, with a shared MySQL development
service. Source is bind-mounted at `/var/www/html`; no image rebuild is needed
for an ordinary PHP edit.

From the repository root, follow [setup](../docs/operations/setup.md), then:

```sh
make sample-setup p=sample-laravel
```

Default URL: `https://sample-laravel.worktree.test:8443`.

[Worktree instructions](../docs/operations/worktrees.md) explain branch runtimes.
[CI instructions](../docs/operations/ci.md) explain the sample's disposable SQLite
test profile. That profile does not prove MySQL compatibility.

The Laravel skeleton retains its [upstream MIT notice](backend/source/LICENSE).

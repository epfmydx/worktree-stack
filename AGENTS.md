# Working on Worktree Stack

Read the [README](README.md) and affected [guides](docs/README.md). Keep the local
Docker stack and test fixtures isolated from any other stack on the machine.

- Do not run host DNS/trust changes or Kubernetes mutations as routine tests.
- Never use application/customer databases for destructive tests.
- Keep credentials, generated certificates, runtime data and CI reports ignored.
- Preserve source worktrees when stopping runtimes; removal of source is separate.
- Use the validation commands in [Contributing](CONTRIBUTING.md), and distinguish
  unit, Docker fixture and complete-stack evidence.
- Review documentation impact for changed commands, config and ownership rules.

# Setup

Run commands from the repository root. Use Docker with Compose 2.24.4+ and Git,
Python 3.9+, Bash, Make and OpenSSL on the host. The interactive shell helpers
support macOS's Bash 3.2. Docker must have enough memory for the services you run.

## Initialize your checkout

```sh
make init
```

This writes an ignored `.env` with random database/dashboard passwords and the
absolute checkout path. It also generates a local CA, gateway certificate and
PostgreSQL certificate. It does not change system DNS, install trust or start
containers. Repeating it preserves existing configuration and certificates.

Review these settings before starting services:

| Setting | Default / purpose |
| --- | --- |
| `STACK_NAME` | `worktree-stack`; namespaces Compose projects, networks and images. |
| `DEV_DOMAIN` | `worktree.test`; local development domain. |
| `HOST_CONTAINERS_PATH` | Absolute path to this checkout, used by the optional dashboard. |
| `HOST_BIND_IP` | `127.0.0.1`; published ports stay on this host. |
| `GATEWAY_HTTP_PORT`, `GATEWAY_HTTPS_PORT` | `8080`, `8443`. |
| `MYSQL_PORT`, `POSTGRES_PORT`, `REDIS_PORT` | `13306`, `15432`, `16379`. |
| `DEV_SUBNET`, `DNSMASQ_IP`, `GATEWAY_IP` | Private network coordinates; change together if already used. |
| `PHP_VERSION` | `8.4`; the Laravel sample's PHP base image. |

Each installation needs a unique stack name, free host ports and a nonoverlapping
subnet. Changing the stack name after startup creates a different installation;
stop the original services with their original configuration first. Password
changes do not automatically update an already initialized database volume.

`.env` and project hooks are trusted shell configuration. Keep values shell-safe
when editing them. Generated credentials contain only hexadecimal characters.

```sh
make config
make base
make infra
make sample-setup p=sample-laravel
make sample-setup p=sample-fastapi
```

`make infra` creates owned networks and starts DNS, gateway, databases and Redis.
Database state lives in Docker volumes. `sample-setup` creates the relevant sample
database and starts the application. Laravel dependencies/key/migrations are
initialized explicitly; FastAPI installs dependencies and applies migrations on
startup. Read startup logs if a page is not ready yet.

## Resolve local names

On macOS with Homebrew dnsmasq installed:

```sh
brew install dnsmasq
make host-dns
```

This optional command uses sudo to update the domain's resolver/dnsmasq settings
and restart dnsmasq. Review [the script](../../scripts/host-setup.sh) before using
it. Do not run it merely to validate the repository.

On other hosts, configure your resolver or add individual host entries for the
names you use. `/etc/hosts` does not support wildcard entries. Containers can use
the stack's internal service names; Docker-side DNS is available for domain
lookups. See [Kubernetes DNS](../../k8s/README.md) for the optional pod layer.

## Trust your own certificate

Your generated public CA certificate is `gateway/certs/dev-ca.pem`. Its private
key stays local and ignored. On macOS, deliberately trust your own CA with:

```sh
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain gateway/certs/dev-ca.pem
```

Use your host's certificate manager on other systems. Do not share the private
CA key. Remove the CA from the trust store when retiring the installation.
After changing `DEV_DOMAIN`, regenerate certificates and apply the updated
configuration:

```sh
make certs-regen
make up p=gateway
make up p=dnsmasq
```

`make up` recreates containers whose Compose configuration changed. Reapply each
running main sample with `make up p=<project>` so its application URL and allowed
hosts use the new domain. Reapply active branch runtimes with
`./worktrees/scripts/wt-spin <project> <slug>` from the original checkout. Update
host DNS entries/resolvers and any optional Kubernetes DNS configuration to match.
Trust the regenerated CA if its key was replaced.

You can verify HTTPS without changing host DNS or system trust:

```sh
curl --cacert gateway/certs/dev-ca.pem \
  --resolve sample-fastapi.worktree.test:8443:127.0.0.1 \
  https://sample-fastapi.worktree.test:8443/api/health
```

Use the domain and port from your `.env` if changed. With host DNS/trust configured:

- Laravel: `https://sample-laravel.worktree.test:8443`
- FastAPI: `https://sample-fastapi.worktree.test:8443`

## Optional dashboard

```sh
make dashboard
```

Open `https://worktree.test:8443` and use the generated `DASHBOARD_PASSWORD` from
your local `.env`. The dashboard can control Docker through its socket and sees
the checkout at the same absolute path as the host. It operates main Compose
projects; worktrees use the CLI. Enable it only for trusted local use.

The EPFMy DigitalX Services dashboard refreshes project status every 10 seconds.
Running, partial, stopped and unavailable states include text labels. Start also
reconciles an already running project's Compose configuration. Logs stream per project or
service; closing a panel stops that stream. Failed refreshes keep the last known
status with a visible message. Use Refresh after resolving a connection problem.

```sh
make dashboard-down
make down p=sample-laravel
make down p=sample-fastapi
make infra-down
```

These commands stop containers while preserving shared database/Redis volumes.
They do not delete your source, Git worktrees, system resolver or trusted CA.

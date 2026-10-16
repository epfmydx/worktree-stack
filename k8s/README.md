# Optional Docker Desktop Kubernetes DNS

This integration lets pods resolve `*.worktree.test` through `host.docker.internal` and reach the local gateway. It does not install Kubernetes, an ingress controller, or deploy applications. Use the gateway's configured HTTPS port (`8443` by default) in URLs; a DNS rewrite does not change ports. The nginx `k8s-*` route forwards to an ingress controller on host port `30080` if you configure one yourself.

Keep the Kubernetes integration separate from `make init` and `make infra`. Enable Docker Desktop Kubernetes yourself, then select its context explicitly:

```sh
kubectl config use-context docker-desktop
make k8s-coredns-render
```

The preview reads the existing CoreDNS ConfigMap and inserts a marked rewrite into its `.:53` server. It preserves all existing plugins and settings. Inspect the result, then apply deliberately:

```sh
make k8s-coredns APPLY=1
```

Both commands refuse any current context other than `docker-desktop`, and every subsequent cluster command explicitly names that context. Apply saves the original ConfigMap under ignored `artifacts/k8s/` and checks its resource version to avoid overwriting concurrent changes. Repeating the operation updates only this stack's marked block.

Verify with a temporary pod, replacing the domain if you changed `.env`:

```sh
kubectl --context docker-desktop run dns-check --rm -it \
  --image=busybox:1.36 --restart=Never -- nslookup sample-laravel.worktree.test
```

To undo, use `kubectl --context docker-desktop -n kube-system edit configmap coredns` and remove only this stack's `BEGIN worktree-stack` through `END worktree-stack` block. Keep changes made by other tools. After resetting Docker Desktop Kubernetes, preview and apply again if you still need this integration.

The integration has static patch tests. Live Kubernetes behavior must be validated against your Docker Desktop version and configuration.

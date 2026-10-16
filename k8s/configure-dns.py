#!/usr/bin/env python3
"""Preview or explicitly apply a minimal CoreDNS patch in docker-desktop only."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shlex
import subprocess


def patch_corefile(corefile, domain, stack):
    start = f"    # BEGIN worktree-stack {stack}\n"
    end = f"    # END worktree-stack {stack}\n"
    domain_pattern = re.escape(domain)
    block = f"{start}    rewrite name regex (.*)\\.{domain_pattern} host.docker.internal answer auto\n{end}"
    if start in corefile:
        before, rest = corefile.split(start, 1)
        if end not in rest:
            raise ValueError("Incomplete prior worktree-stack marker; review CoreDNS manually")
        return before + block + rest.split(end, 1)[1]
    match = re.search(r"(?m)^\.:53\s*\{\s*\n", corefile)
    if not match:
        raise ValueError("Expected one .:53 CoreDNS server; review this cluster's configuration manually")
    return corefile[:match.end()] + block + corefile[match.end():]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    values = {}
    for line in (root / ".env").read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            parsed = shlex.split(value, comments=True)
            values[key] = parsed[0] if parsed else ""
    domain, stack = values["DEV_DOMAIN"], values["STACK_NAME"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z]+", domain) or not re.fullmatch(r"[a-z][a-z0-9-]*", stack):
        raise SystemExit("Invalid DEV_DOMAIN or STACK_NAME")
    current = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    if current != "docker-desktop":
        raise SystemExit("Refusing: current context must be docker-desktop. Switch explicitly before this optional action.")
    command = ["kubectl", "--context", "docker-desktop", "-n", "kube-system"]
    config = json.loads(subprocess.check_output(command + ["get", "configmap", "coredns", "-o", "json"], text=True))
    old = config["data"]["Corefile"]
    new = patch_corefile(old, domain, stack)
    if not args.apply:
        print(new, end="" if new.endswith("\n") else "\n")
        print("\nPreview only. No cluster changes. Apply with make k8s-coredns APPLY=1.")
        return
    if new == old:
        print("CoreDNS already has this stack's rewrite.")
        return
    directory = root / "artifacts" / "k8s"
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-coredns.json")
    backup.write_text(json.dumps(config, indent=2) + "\n")
    patch = [{"op": "test", "path": "/metadata/resourceVersion", "value": config["metadata"]["resourceVersion"]},
             {"op": "replace", "path": "/data/Corefile", "value": new}]
    subprocess.run(command + ["patch", "configmap", "coredns", "--type=json", "-p", json.dumps(patch)], check=True)
    print(f"Applied minimal DNS rewrite to docker-desktop. Original saved at {backup}")


if __name__ == "__main__":
    main()

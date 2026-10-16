SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help init networks base infra infra-down dashboard dashboard-down host-dns certs-regen config up down build restart logs shell ps sample-setup k8s-coredns k8s-coredns-render

help:
	@echo "make init                 Generate local .env and certificates (no sudo or containers)"
	@echo "make base                 Build the PHP image for this stack"
	@echo "make infra                Start scoped networks, DNS, gateway, databases and Redis"
	@echo "make sample-setup p=sample-laravel|sample-fastapi"
	@echo "make up|down|build|restart|logs|shell p=<project>"
	@echo "make dashboard            Opt in to the dashboard's Docker socket access"
	@echo "make host-dns             Opt in to macOS dnsmasq/resolver configuration (sudo)"
	@echo "make config               Validate all main Compose files without starting services"
	@echo "make infra-down           Stop shared services; preserve their data"
	@echo "make k8s-coredns-render    Preview the optional Docker Desktop DNS patch"
	@echo "make k8s-coredns APPLY=1   Apply that patch to docker-desktop only"

init:
	@python3 scripts/init.py

networks base infra infra-down dashboard dashboard-down certs-regen config ps:
	@./scripts/stack.sh "$@"

up down build restart logs shell sample-setup:
	@./scripts/stack.sh "$@" "$(p)"

host-dns:
	@./scripts/host-setup.sh

k8s-coredns-render:
	@python3 k8s/configure-dns.py

k8s-coredns:
	@test "$(APPLY)" = 1 || { echo 'Preview with make k8s-coredns-render; apply with make k8s-coredns APPLY=1'; exit 1; }
	@python3 k8s/configure-dns.py --apply

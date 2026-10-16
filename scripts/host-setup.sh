#!/usr/bin/env bash
# Explicit opt-in macOS DNS setup. This does not install/trust certificates.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$(uname -s)" = Darwin ]] || { echo 'host-dns supports macOS. Configure local wildcard DNS or hosts entries manually on other systems.' >&2; exit 1; }
[[ -f "$ROOT/.env" ]] || { echo 'Run make init first.' >&2; exit 1; }
. "$ROOT/.env"
[[ "$STACK_NAME" =~ ^[a-z][a-z0-9-]*$ && "$DEV_DOMAIN" =~ ^[a-z0-9][a-z0-9.-]*\.[a-z]+$ ]] || { echo 'Invalid STACK_NAME or DEV_DOMAIN.' >&2; exit 1; }
command -v brew >/dev/null || { echo 'Homebrew is required for this optional step.' >&2; exit 1; }
BREW_PREFIX="$(brew --prefix)"
[[ -x "$BREW_PREFIX/sbin/dnsmasq" || -x "$BREW_PREFIX/bin/dnsmasq" ]] || { echo 'Install dnsmasq first: brew install dnsmasq' >&2; exit 1; }
CONF="$BREW_PREFIX/etc/dnsmasq.conf"
INCLUDE="$BREW_PREFIX/etc/dnsmasq.d/$STACK_NAME.conf"
RESOLVER="/etc/resolver/$DEV_DOMAIN"
if [[ -f "$RESOLVER" ]] && ! grep -qxF 'nameserver 127.0.0.1' "$RESOLVER"; then
  echo "Existing $RESOLVER belongs to another resolver. Review it manually before proceeding." >&2; exit 1
fi
sudo mkdir -p "$BREW_PREFIX/etc/dnsmasq.d" /etc/resolver
printf 'address=/%s/127.0.0.1\n' "$DEV_DOMAIN" | sudo tee "$INCLUDE" >/dev/null
LINE="conf-file=$INCLUDE"
if ! grep -qxF "$LINE" "$CONF" 2>/dev/null; then
  printf '\n%s\n' "$LINE" | sudo tee -a "$CONF" >/dev/null
fi
printf 'nameserver 127.0.0.1\n' | sudo tee "$RESOLVER" >/dev/null
sudo brew services restart dnsmasq
echo "Configured *.$DEV_DOMAIN -> 127.0.0.1. HTTPS uses port $GATEWAY_HTTPS_PORT."
echo "To undo, remove $INCLUDE, its conf-file line in $CONF, and $RESOLVER; restart dnsmasq."

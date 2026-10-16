#!/bin/sh
set -e
: "${DEV_DOMAIN:?DEV_DOMAIN env var required}" "${GATEWAY_IP:?GATEWAY_IP required}"
envsubst '${DEV_DOMAIN} ${GATEWAY_IP}' < /etc/dnsmasq.conf.template > /etc/dnsmasq.conf
exec dnsmasq --keep-in-foreground --log-facility=- --conf-file=/etc/dnsmasq.conf

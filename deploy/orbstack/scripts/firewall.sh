#!/bin/sh
# All app services share this network namespace. There is no host namespace or
# Docker socket access. Install rules before declaring healthy, then drop caps.
set -eu
for firewall in iptables ip6tables; do
  "$firewall" -w -P OUTPUT DROP
  "$firewall" -w -P INPUT DROP
  "$firewall" -w -P FORWARD DROP
  "$firewall" -w -F OUTPUT
  "$firewall" -w -F INPUT
  "$firewall" -w -F FORWARD
  "$firewall" -w -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
  # No external DNS, including Docker's embedded resolver.
  if [ "$firewall" = iptables ]; then
    "$firewall" -w -A OUTPUT -d 127.0.0.11/32 -j REJECT
  fi
  "$firewall" -w -A OUTPUT -p udp --dport 53 -j REJECT
  "$firewall" -w -A OUTPUT -p tcp --dport 53 -j REJECT
  "$firewall" -w -A OUTPUT -o lo -j ACCEPT
  "$firewall" -w -A INPUT -i lo -j ACCEPT
  "$firewall" -w -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
  # New inbound connections only to Caddy. Reply packets are allowed above.
  "$firewall" -w -A INPUT -p tcp --dport 443 -j ACCEPT
done
touch /run/firewall-ready
echo 'Firewall ready: local service traffic and HTTPS replies only; outbound denied.'
# No running process in the stack retains NET_ADMIN after initialization.
exec setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all sh -c 'trap "exit 0" TERM INT; sleep infinity & wait $!'

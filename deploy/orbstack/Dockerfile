# Only the build/download phase uses the internet. Runtime firewall and backup
# helper containers do not download packages or make outbound connections.
FROM alpine:3.23@sha256:21f3e19bafab57a9ff7aa9dd571dac72f868370472c10f450cc0416cc1aca553
RUN apk add --no-cache iptables util-linux age tar curl bind-tools
COPY scripts/firewall.sh /usr/local/bin/firewall.sh
RUN chmod 755 /usr/local/bin/firewall.sh
ENTRYPOINT ["/usr/local/bin/firewall.sh"]

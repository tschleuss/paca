#!/bin/sh
# Copy to ~/.local/bin/start-paca; copy agent.env.example to ~/.config/paca/agent.env.
set -eu
config=${PACA_LOCAL_CONFIG:-"$HOME/.config/paca/agent.env"}
if [ ! -r "$config" ]; then
  echo "Missing Paca credentials file: $config" >&2
  exit 1
fi
set -a
. "$config"
set +a
: "${PACA_API_KEY:?Set PACA_API_KEY}"
: "${PACA_API_URL:?Set PACA_API_URL}"
: "${NODE_EXTRA_CA_CERTS:?Set the public Caddy root certificate path}"
: "${PACA_NODE:?Set absolute Node.js executable path}"
exec "$PACA_NODE" "$HOME/.local/share/paca-mcp/node_modules/@paca-ai/paca-mcp/build/index.js"

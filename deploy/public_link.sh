#!/usr/bin/env bash
# A public https link to the website running on this Mac, through a Cloudflare quick tunnel
# (docs/WEBSITE.md "A public link from this Mac").
#
#   deploy/public_link.sh                  # the full system (Ollama must be running)
#   RAG_OFFLINE=1 deploy/public_link.sh    # the offline demo: recorded answers, no models
#
# It prints a https://<random words>.trycloudflare.com link; Ctrl-C stops the website and
# the link. Each start gives a new link. The website listens on 127.0.0.1 only, so the
# tunnel is the one way in, and the Mac is kept awake while it runs (closing the lid still
# puts it to sleep). Needs: brew install cloudflared.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8501}"
STREAMLIT=".venv/bin/streamlit"

command -v cloudflared >/dev/null || { echo "Install cloudflared: brew install cloudflared" >&2; exit 1; }
[ -x "$STREAMLIT" ] || { echo "No .venv here: see README.md (Quick start)" >&2; exit 1; }
if [ "${RAG_OFFLINE:-}" != "1" ]; then
    curl -sf "${RAG_OLLAMA_URL:-http://localhost:11434}/api/version" >/dev/null \
        || { echo "Ollama is not running: start it with 'ollama serve'" >&2; exit 1; }
fi
if curl -sf "http://127.0.0.1:$PORT/_stcore/health" >/dev/null 2>&1; then
    echo "Port $PORT is in use (another streamlit run?). Stop it, or use PORT=8502." >&2
    exit 1
fi

# Public settings: no maintainer panel, no reloading when a file changes, this machine only.
unset RAG_ADMIN
"$STREAMLIT" run app/streamlit_app.py --server.address 127.0.0.1 --server.port "$PORT" \
    --server.headless true --server.fileWatcherType none --server.runOnSave false &
APP=$!
trap 'kill "$APP" 2>/dev/null || true' EXIT

for _ in $(seq 90); do
    curl -sf "http://127.0.0.1:$PORT/_stcore/health" >/dev/null 2>&1 && break
    kill -0 "$APP" 2>/dev/null || { echo "The website did not start" >&2; exit 1; }
    sleep 1
done

caffeinate -i -w "$APP" &          # no idle sleep while the website runs
echo "Starting the tunnel: the public link is the https://…trycloudflare.com line below."
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"

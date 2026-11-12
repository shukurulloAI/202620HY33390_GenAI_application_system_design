#!/usr/bin/env bash
# A public https link to the website running on this Mac, through a Cloudflare quick tunnel
# (docs/WEBSITE.md "A public link from this Mac").
#
#   deploy/public_link.sh                  # the full system (Ollama must be running)
#   RAG_OFFLINE=1 deploy/public_link.sh    # the offline demo: recorded answers, no models
#
# It prints the https://<random words>.trycloudflare.com link on its own and copies it;
# Ctrl-C stops the website and the link. Each start gives a new link; when Cloudflare gives
# none, it asks again every minute (TUNNEL_TRIES=8 times). The website listens on
# 127.0.0.1 only, so the tunnel is the one way in, and the Mac is kept awake while it runs
# (closing the lid still puts it to sleep). The logs go to .cache/website.log and
# .cache/tunnel.log. Needs: brew install cloudflared.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8501}"
STREAMLIT=".venv/bin/streamlit"
WEBSITE_LOG=".cache/website.log"
TUNNEL_LOG=".cache/tunnel.log"

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
mkdir -p .cache

# Public settings: no maintainer panel, no reloading when a file changes, this machine only.
unset RAG_ADMIN
"$STREAMLIT" run app/streamlit_app.py --server.address 127.0.0.1 --server.port "$PORT" \
    --server.headless true --server.fileWatcherType none --server.runOnSave false \
    >"$WEBSITE_LOG" 2>&1 &
APP=$!
TUNNEL=""
trap 'kill $TUNNEL "$APP" 2>/dev/null || true' EXIT

echo "Starting the website…"
for _ in $(seq 90); do
    curl -sf "http://127.0.0.1:$PORT/_stcore/health" >/dev/null 2>&1 && break
    kill -0 "$APP" 2>/dev/null || { tail -20 "$WEBSITE_LOG" >&2; echo "The website did not start" >&2; exit 1; }
    sleep 1
done
caffeinate -i -w "$APP" &          # no idle sleep while the website runs

# One try: sets LINK, or fails once cloudflared has given up (or found nothing in 60 s).
open_link() {
    cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$TUNNEL_LOG" 2>&1 &
    TUNNEL=$!
    for _ in $(seq 60); do
        LINK=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | grep -v '//api\.' | head -1 || true)
        [ -n "$LINK" ] && return 0
        kill -0 "$TUNNEL" 2>/dev/null || return 1
        sleep 1
    done
    kill "$TUNNEL" 2>/dev/null || true
    return 1
}

# Cloudflare's quick-tunnel service sometimes does not answer for a while ("failed to request
# quick Tunnel"): ask again once a minute for about 10 minutes, with the website kept running.
# Not faster: too many tries in a row get "429 Too Many Requests".
TRIES="${TUNNEL_TRIES:-8}"
LINK=""
for TRY in $(seq "$TRIES"); do
    echo "Opening the public link…"
    open_link && break
    REASON=$(grep -m1 -E 'failed|ERR' "$TUNNEL_LOG" || tail -1 "$TUNNEL_LOG")
    echo "  Cloudflare gave no link (try $TRY of $TRIES): $REASON" >&2
    if [ "$TRY" -lt "$TRIES" ]; then
        echo "  That is Cloudflare's side; asking again in a minute. Ctrl-C stops."
        sleep 60
    fi
done
if [ -z "$LINK" ]; then
    echo "No link after $TRIES tries. Cloudflare's quick tunnels are down for now: try again" >&2
    echo "later (docs/WEBSITE.md, \"A public link from this Mac\"). Log: $TUNNEL_LOG" >&2
    exit 1
fi
printf '%s' "$LINK" | pbcopy 2>/dev/null || true

echo
echo "  Public link (copied):  $LINK"
echo
echo "  A new link can take a minute or two to open everywhere."
echo "  Keep this window open; Ctrl-C stops the website and the link."
echo "  Logs: $WEBSITE_LOG, $TUNNEL_LOG"
wait "$TUNNEL"

#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

cleanup() {
  echo ""
  echo "=== Stopping services ==="
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null
  done
  wait "${PIDS[@]}" 2>/dev/null
  echo "=== All stopped ==="
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "=== Starting all services ==="
cd "$DIR/server_app"
node http_server.js &
PIDS+=($!)
echo "  HTTP :3456"

node ws_server.js &
PIDS+=($!)
echo "  WS+ProtoBuf :3457"

cd "$DIR/heatmap-app"
npx vite --host 0.0.0.0 --port 5173 &
PIDS+=($!)
echo "  Vite :5173"

echo "=== Ready: http://localhost:5173 ==="
wait

#!/bin/bash
trap "echo 'Stopping...'; kill 0; exit" SIGINT SIGTERM
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== Starting all services ==="
cd "$DIR/server_app"
node http_server.js & echo "  HTTP :3456"
node ws_server.js & echo "  WS+ProtoBuf :3457"
cd "$DIR/heatmap-app"
npx vite --host 0.0.0.0 --port 5173 & echo "  Vite :5173"
echo "=== Ready: http://localhost:5173 ==="
wait

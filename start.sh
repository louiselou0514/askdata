#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Starting backend..."
cd "$ROOT/backend"
env $(cat .env | grep -v '^#' | xargs) \
  venv/bin/uvicorn app.main:app \
  --reload \
  --reload-dir "$ROOT/backend/app" \
  --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!

echo "Starting frontend..."
cd "$ROOT/frontend"
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID  |  Frontend PID: $FRONTEND_PID"
echo "Waiting for servers..."
sleep 8

curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health && echo " backend ready"
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 && echo " frontend ready"

echo ""
echo "Open http://localhost:3000"
echo "Logs: tail -f /tmp/backend.log  |  tail -f /tmp/frontend.log"

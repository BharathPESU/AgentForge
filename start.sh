#!/usr/bin/env bash

# AgentForge Startup Script
# Launches both the FastAPI Python Backend and React Vite Frontend concurrently.

set -e

# Navigate to project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Export default environment variables for Frontend Vite server & Python path
export PORT="${PORT:-5173}"
export BASE_PATH="${BASE_PATH:-/}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Determine pnpm command (native pnpm or npx fallback)
if command -v pnpm &> /dev/null; then
    PNPM_CMD="pnpm"
else
    PNPM_CMD="npx --yes pnpm"
fi

# Ensure frontend dependencies are installed
if [ ! -d "$PROJECT_ROOT/Frontend/node_modules" ]; then
    echo "[0/2] Installing Frontend dependencies..."
    (cd "$PROJECT_ROOT/Frontend" && $PNPM_CMD install && $PNPM_CMD approve-builds --all)
fi

echo "=================================================="
echo " Starting AgentForge (Backend + Frontend)"
echo "=================================================="
echo " Backend API:  http://localhost:8000"
echo " Swagger Docs: http://localhost:8000/docs"
echo " React App:    http://localhost:${PORT}"
echo "=================================================="

# Function to clean up background processes on exit (Ctrl+C or SIGTERM)
cleanup() {
    echo ""
    echo "Stopping AgentForge processes..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

trap cleanup EXIT INT TERM

# 1. Start FastAPI Python Backend in background
echo "[1/2] Starting FastAPI backend on port 8000..."
python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait briefly for backend server startup
sleep 2

# 2. Start React Frontend
echo "[2/2] Starting React frontend on port ${PORT}..."
cd "$PROJECT_ROOT/Frontend/artifacts/agentforge-frontend"
$PNPM_CMD dev

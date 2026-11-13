#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR/backend"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please create it first."
    exit 1
fi

source venv/bin/activate
echo "Starting HealthAI FastAPI Gateway on http://localhost:8001..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

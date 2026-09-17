#!/bin/bash
cd "$(dirname "$0")/../.."
if [ -d ".venv" ]; then
    source .venv/bin/activate
    python -m backend.ui.main
elif [ -d "venv" ]; then
    source venv/bin/activate
    python -m backend.ui.main
else
    python3 -m backend.ui.main
fi

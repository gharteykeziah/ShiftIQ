#!/bin/bash
cd "$(dirname "$0")"
if [ -d "venv" ]; then
    source venv/bin/activate
    python main.py
else
    python3 main.py
fi

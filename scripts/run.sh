#!/usr/bin/env bash
set -e
source .venv/bin/activate
MOCK_MODE=1 python -m app.main

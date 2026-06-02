#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code web environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install Python dependencies
cd "$CLAUDE_PROJECT_DIR"
python3.12 -m pip install -e ".[dev]" --quiet --break-system-packages

# Persist PYTHONPATH for the session
echo 'export PYTHONPATH="$CLAUDE_PROJECT_DIR"' >> "$CLAUDE_ENV_FILE"
echo 'export PATH="/usr/bin:$PATH"' >> "$CLAUDE_ENV_FILE"

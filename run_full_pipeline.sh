#!/usr/bin/env bash
# Run from anywhere: ./run_full_pipeline.sh
# Or: bash run_full_pipeline.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -d "$ROOT/.venv" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

if ! command -v ffmpeg &>/dev/null; then
  for p in /opt/miniconda3/bin /opt/homebrew/bin "$HOME/miniconda3/bin"; do
    if [[ -x "$p/ffmpeg" ]]; then
      export PATH="$p:$PATH"
      break
    fi
  done
fi

exec "$PYTHON" run_lecture_pipeline.py "$@"

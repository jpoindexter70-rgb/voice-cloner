#!/usr/bin/env bash
set -euo pipefail
cd /workspace/voice-cloner
export UV_CACHE_DIR=/workspace/voice-cloner/.runtime/uv-cache
export VCR_DATA_DIR=/workspace/voice-cloner/.runtime/studio-data
export HF_HOME=/workspace/voice-cloner/.runtime/huggingface
export NUMBA_CACHE_DIR=/workspace/voice-cloner/.runtime/numba
mkdir -p /workspace/voice-cloner/.runtime
if [ ! -x .runtime/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11 ]; then
  uv python install 3.11 --no-bin --install-dir /workspace/voice-cloner/.runtime/python
fi
if [ ! -x .venv-311/bin/python ]; then
  uv venv .venv-311 --seed --python /workspace/voice-cloner/.runtime/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11
fi
.venv-311/bin/python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv-311/bin/python -m pip install -r requirements-desktop.txt -r requirements-dev.txt
.venv-311/bin/python -m pip check
.venv-311/bin/python -m pytest -q
# Close any studio server before model repair. This command never sends voice recordings.
.venv-311/bin/python -m studio.cli download-models --engine all
.venv-311/bin/python -m studio.cli verify-models --engine all

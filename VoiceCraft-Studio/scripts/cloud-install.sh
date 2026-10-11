#!/usr/bin/env bash
set -euo pipefail
cd /workspace/voice-cloner/Studio-2.0
export UV_CACHE_DIR="$PWD/.runtime/uv-cache"
export PIP_CACHE_DIR="$PWD/.runtime/pip-cache"
export HF_HOME="$PWD/.runtime/huggingface"
export NUMBA_CACHE_DIR="$PWD/.runtime/numba-cache"
mkdir -p .runtime
if [ ! -x .venv-ai/bin/python ]; then
  uv python install 3.11 --no-bin --install-dir "$PWD/.runtime/python"
  uv venv .venv-ai --seed --python "$PWD/.runtime/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11"
fi
.venv-ai/bin/python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
.venv-ai/bin/python -m pip install -r requirements-engine.txt -c requirements-engine-lock.txt
.venv-ai/bin/python -m pip check
.venv-ai/bin/python -m pytest -q
.venv-ai/bin/python -m studio.models download --root "$PWD/.runtime/shared-models" --engine all
.venv-ai/bin/python -m studio.models verify --root "$PWD/.runtime/shared-models" --engine all

.venv-ai/bin/python -m studio.seed_assets download --root "$PWD/.runtime/shared-models"
.venv-ai/bin/python -m studio.seed_assets verify --root "$PWD/.runtime/shared-models"

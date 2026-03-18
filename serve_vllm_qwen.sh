#!/usr/bin/env bash
set -euo pipefail

# Start vLLM server for Qwen3.5. Requires GPU (CUDA/MPS) for reliable operation.
# On Mac CPU-only, vLLM often fails with Qwen3.5. Use Ollama instead: ./serve_ollama_qwen.sh
#
# Usage (from project root, after activating your vLLM Python env):
#   ./serve_vllm_qwen.sh            # port 8010
#   ./serve_vllm_qwen.sh 9000       # custom port
#
# Then set in config/app.env:
#   LLM_BASE_URL=http://localhost:8010/v1
#   LLM_API_KEY=EMPTY
#   LLM_MODEL=Qwen/Qwen3.5-0.8B

PORT="${1:-8010}"
MODEL="${VLLM_MODEL:-Qwen/Qwen3.5-0.8B}"

# Prefer pip-installed vllm (more stable) over repo clone
if command -v vllm &>/dev/null; then
  echo "Using vllm from PATH..."
  exec vllm serve "${MODEL}" \
    --port "${PORT}" \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --language-model-only
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VLLM_DIR="${SCRIPT_DIR}/vllm"

if [ ! -d "${VLLM_DIR}" ]; then
  echo "vLLM not found. Options:"
  echo "  1. pip install vllm   (then run this script again)"
  echo "  2. On Mac without GPU: use Ollama instead: ./serve_ollama_qwen.sh"
  exit 1
fi

cd "${VLLM_DIR}"

echo "Starting vLLM server for model '${MODEL}' on port ${PORT}..."
echo "Note: On Mac CPU, vLLM may fail with Qwen3.5. Use ./serve_ollama_qwen.sh instead."
echo "Press Ctrl+C to stop."

exec vllm serve "${MODEL}" \
  --port "${PORT}" \
  --tensor-parallel-size 1 \
  --max-model-len 8192 \
  --language-model-only

#!/usr/bin/env bash
# Cleanup GradConnectAI: kill processes and optionally remove model caches.
# Usage: ./scripts/cleanup.sh [--weights]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLEAN_WEIGHTS=false
for arg in "$@"; do
  [[ "$arg" == "--weights" ]] && CLEAN_WEIGHTS=true
done

echo "=== Stopping GradConnectAI processes ==="

# Kill uvicorn (backend)
if pgrep -f "uvicorn app.main:app" >/dev/null; then
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  echo "  Stopped uvicorn (backend)"
fi

# Kill vLLM
if pgrep -f "vllm serve" >/dev/null; then
  pkill -f "vllm serve" 2>/dev/null || true
  echo "  Stopped vLLM server"
fi

# Kill processes on common ports
for port in 8009 8010 3000; do
  pid=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    echo "  Stopped process on port $port (PID $pid)"
  fi
done

echo ""
echo "Processes cleared."
echo ""

if [[ "$CLEAN_WEIGHTS" == "true" ]]; then
  echo "=== Removing model caches (--weights) ==="
  
  # Hugging Face / vLLM / sentence-transformers cache
  HF_CACHE="${HOME}/.cache/huggingface"
  if [[ -d "$HF_CACHE" ]]; then
    du -sh "$HF_CACHE" 2>/dev/null || true
    rm -rf "$HF_CACHE"
    echo "  Removed: $HF_CACHE"
  fi

  # Torch / sentence-transformers cache
  TORCH_CACHE="${HOME}/.cache/torch"
  if [[ -d "$TORCH_CACHE" ]]; then
    du -sh "$TORCH_CACHE" 2>/dev/null || true
    rm -rf "$TORCH_CACHE"
    echo "  Removed: $TORCH_CACHE"
  fi

  # Ollama models (optional - ask before removing)
  OLLAMA_MODELS="${HOME}/.ollama/models"
  if [[ -d "$OLLAMA_MODELS" ]]; then
    echo "  Ollama models at $OLLAMA_MODELS (not removed by default)"
    echo "  To remove: rm -rf ~/.ollama/models"
  fi

  echo ""
  echo "Model caches cleared."
  echo "  - Next backend start will re-download sentence-transformers (~90MB)"
  echo "  - vLLM/Ollama models will need to be pulled again"
fi

echo ""
echo "Done."

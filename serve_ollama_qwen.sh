#!/usr/bin/env bash
# Alternative to vLLM: use Ollama for Qwen3.5 on Mac.
# Ollama works reliably on Apple Silicon and Intel Macs.
#
# 1. Install Ollama: brew install ollama
# 2. Run: ollama serve   (or start Ollama app)
# 3. Pull model: ollama pull qwen3.5:0.8b
# 4. Set in backend/.env:
#    LLM_BASE_URL=http://localhost:11434/v1
#    LLM_MODEL=qwen3.5:0.8b
#
# This script just pulls the model if needed. Ollama must be running separately.

set -euo pipefail

echo "Checking Ollama..."
if ! command -v ollama &>/dev/null; then
  echo "Ollama not found. Install with: brew install ollama"
  echo "Then run: ollama serve"
  exit 1
fi

echo "Pulling frob/qwen3.5-instruct:4b (if not already present)..."
ollama pull frob/qwen3.5-instruct:4b

echo ""
echo "Done. Ensure Ollama is running (ollama serve or Ollama app)."
echo "Set in backend/.env:"
echo "  LLM_BASE_URL=http://localhost:11434/v1"
echo "  LLM_MODEL=frob/qwen3.5-instruct:4b"

#!/bin/bash
# Perfil Qwen3-30B-A3B-Q4_K_M para 16 GB VRAM + 32 GB RAM.

set -e

MODELO="$HOME/Proyectos/llama/models/Qwen3-30B-A3B-Q4_K_M.gguf"

# `auto` descarga a GPU tantas capas como quepan y mantiene el resto en
# CPU/RAM. También se puede pasar un número exacto si se quiere reservar VRAM.
NGL="${1:-auto}"
CTX="${2:-8192}"
BATCH="${3:-256}"

LLAMA_SERVER="$HOME/Proyectos/llama/src/llama.cpp/build/bin/llama-server"

if [ ! -f "$MODELO" ]; then
    echo "❌ Modelo no encontrado: $MODELO"
    echo "Uso: ./start_llm_server_qwen30b.sh [capas_gpu] [contexto] [batch]"
    exit 1
fi

if [ ! -x "$LLAMA_SERVER" ]; then
    echo "❌ llama-server no encontrado:"
    echo "$LLAMA_SERVER"
    exit 1
fi

echo "🚀 Iniciando llama.cpp server con offload parcial a RAM..."
echo "   Modelo: $(basename "$MODELO")"
echo "   Capas GPU solicitadas: $NGL (auto = tantas como quepan)"
echo "   Contexto: $CTX"
echo "   Batch: $BATCH"
echo "   URL: http://localhost:8080"
echo ""

# El contexto y el batch son deliberadamente conservadores para dejar RAM
# disponible al sistema y al resto de capas del modelo que no quepan en VRAM.
# No usamos mlock: con un modelo de este tamaño podría bloquear demasiada RAM.
"$LLAMA_SERVER" \
  -m "$MODELO" \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl "$NGL" \
  -c "$CTX" \
  -b "$BATCH" \
  -ub 128 \
  -t 10 \
  -n 2048 \
  --timeout 300 \
  --metrics \
  --perf \
  -ctk q8_0 \
  -ctv q8_0 \
  --jinja

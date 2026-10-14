#!/bin/bash
# Perfil de inicio llama.cpp para Qwen3-14B.

set -e

MODELO="$HOME/Proyectos/llama/models/Qwen3-14B-Q5_K_M.gguf"
NGL="${1:-99}"
CTX="${2:-16384}"

LLAMA_SERVER="$HOME/Proyectos/llama/src/llama.cpp/build/bin/llama-server"

# Verifica que el modelo existe
if [ ! -f "$MODELO" ]; then
    echo "❌ Modelo no encontrado: $MODELO"
    echo "Uso: ./start_llm_server_qwen14b.sh [capas_gpu] [contexto]"
    exit 1
fi


if [ ! -x "$LLAMA_SERVER" ]; then
    echo "❌  llama-server no encontrado:"
    echo "$LLAMA_SERVER"
    exit 1
fi

echo "🚀 Iniciando llama.cpp server..."
echo "   Modelo: $(basename $MODELO)"
echo "   Capas GPU: $NGL"
echo "   Contexto: $CTX"
echo "   URL: http://localhost:8080"
echo ""

# Lanzamiento con optimizaciones para tu hardware
"$LLAMA_SERVER" \
  -m "$MODELO" \
  --host 127.0.0.1 \
  --port 8080 \
  -ngl $NGL \
  -c $CTX \
  -t 10 \
  -n 2048 \
  --timeout 300 \
  --load-mode mlock \
  --metrics \
  --perf \
  -ctk q8_0 \
  -ctv q8_0 \
  --jinja

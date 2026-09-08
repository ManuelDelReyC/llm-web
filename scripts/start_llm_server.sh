#!/bin/bash
# Script Inicio llama.cpp optimizado para HP Elitedesk 600 G4 + GTX 1060 3GB

MODELO="$HOME/Proyectos/llama/models/qwen2.5-coder-7b-instruct-q4_k_m-00001-of-00002.gguf"
NGL="${1:-13}"
CTX="${2:-6144}"

# Verifica que el modelo existe
if [ ! -f "$MODELO" ]; then
    echo "❌ Modelo no encontrado: $MODELO"
    echo "Uso: ./start_llm_server.sh [ruta_modelo] [capas_gpu] [contexto]"
    exit 1
fi

echo "🚀 Iniciando llama.cpp server..."
echo "   Modelo: $(basename $MODELO)"
echo "   Capas GPU: $NGL"
echo "   Contexto: $CTX"
echo "   URL: http://localhost:8080"
echo ""

# Lanzamiento con optimizaciones para tu hardware
~/Proyectos/llama/src/llama.cpp/build/bin/llama-server \
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


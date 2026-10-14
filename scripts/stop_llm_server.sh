PIDS=$(pgrep -f '[l]lama-server')

if [ -n "$PIDS" ]; then
    echo "Deteniendo llama-server: $PIDS"
    kill -15 $PIDS
else
    echo "No se ha encontrado ningún proceso llama-server"
fi

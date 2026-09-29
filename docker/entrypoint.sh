#!/bin/sh
# Prepara el despliegue y comprueba que la aplicacion esta operativa.
# Cualquier fase que falle termina con un codigo distinto de cero
# y un error identificable en la salida de error.
set -eu

DEFAULT_RATES=/app/config/tarifas.json
HEALTH_INTERVAL=60

fail() {
    echo "DEPLOY_FAILED $1: $2" >&2
    exit "$1"
}

prepare_directories() {
    for directory in data logs config; do
        mkdir -p "${TAXIMETER_HOME}/${directory}" \
            || fail 11 "no se pudo crear ${TAXIMETER_HOME}/${directory}"
    done
}

seed_configuration() {
    if [ ! -f "${TAXIMETER_HOME}/config/tarifas.json" ]; then
        cp "${DEFAULT_RATES}" "${TAXIMETER_HOME}/config/tarifas.json" \
            || fail 12 "no se pudo copiar la configuracion de tarifas"
        echo "Configuracion de tarifas inicializada desde la del repositorio."
    else
        echo "Configuracion de tarifas conservada de un despliegue anterior."
    fi
}

run_healthcheck() {
    status=0
    python3 -m taximeter.interfaces.healthcheck || status=$?
    if [ "${status}" -ne 0 ]; then
        fail "${status}" "la comprobacion de operatividad ha fallado (codigo ${status})"
    fi
}

case "${1:-serve}" in
    serve)
        prepare_directories
        seed_configuration
        run_healthcheck
        echo "Despliegue correcto. Usa 'docker compose exec taximetro python3 main.py' para operar."
        while true; do
            sleep "${HEALTH_INTERVAL}"
            run_healthcheck
        done
        ;;
    check)
        prepare_directories
        seed_configuration
        run_healthcheck
        ;;
    *)
        exec "$@"
        ;;
esac

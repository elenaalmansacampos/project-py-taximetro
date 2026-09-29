FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TAXIMETER_HOME=/var/lib/taximetro

# _tkinter viene compilado en la imagen oficial de Python pero las librerias
# de Tcl/Tk no estan presentes, asi que la interfaz grafica no arranca.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libtcl8.6 libtk8.6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Se instala el paquete desde pyproject.toml. Las dependencias base estan
# vacias a proposito: la imagen no necesita nada de la biblioteca estandar.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

COPY main.py ./
COPY config/ ./config/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && groupadd --system taximetro \
    && useradd --system --gid taximetro --home-dir /app --shell /usr/sbin/nologin taximetro \
    && mkdir -p /var/lib/taximetro \
    && chown -R taximetro:taximetro /var/lib/taximetro /app

USER taximetro

VOLUME ["/var/lib/taximetro"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["python3", "-m", "taximeter.interfaces.healthcheck", "--json"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["serve"]

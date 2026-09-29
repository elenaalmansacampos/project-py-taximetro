DEPLOY_TIMEOUT ?= 180
COMPOSE ?= docker compose

.PHONY: help deploy check down down-volumes shell cli test clean images

help:
	@echo "Despliegue del taximetro con un unico comando:"
	@echo ""
	@echo "  make deploy   construye la imagen, levanta el servicio y espera a que este sano"
	@echo "  make check    ejecuta solo la comprobacion de operatividad"
	@echo "  make test     ejecuta la suite de tests en local"
	@echo "  make cli      abre una sesion interactiva de la CLI en el contenedor"
	@echo "  make down     detiene el servicio conservando los datos"
	@echo "  make down-volumes  detiene el servicio y BORRA los datos persistentes"
	@echo ""

deploy:
	@echo "Construyendo la imagen y levantando el servicio..."
	@if $(COMPOSE) up -d --build --wait --wait-timeout $(DEPLOY_TIMEOUT); then \
		echo "Taximetro desplegado y operativo."; \
	else \
		echo ""; \
		echo "ERROR: el despliegue ha fallado. Ultimas lineas del contenedor:"; \
		$(COMPOSE) logs --no-color --tail 40 taximetro; \
		exit 1; \
	fi

check:
	$(COMPOSE) run --rm taximetro check

cli:
	$(COMPOSE) run --rm taximetro python3 main.py

shell:
	$(COMPOSE) run --rm taximetro /bin/sh

test:
	python3 -W error::ResourceWarning -m unittest

down:
	$(COMPOSE) down

down-volumes:
	$(COMPOSE) down --volumes

images:
	$(COMPOSE) images

clean:
	$(COMPOSE) down --volumes --rmi local

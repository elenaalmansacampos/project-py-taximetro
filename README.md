# TaxiTech Solutions - Sistema de Taximetro Digital

Prototipo en Python para calcular el importe de carreras de taxi en tiempo real.

Tarifas por defecto:

- Taxi parado o velocidad menor de 20 km/h: `0.02 EUR/segundo`
- Taxi en movimiento: `0.05 EUR/segundo`

## Funcionalidades

- CLI para iniciar, cambiar estado, finalizar y encadenar carreras.
- Calculo continuo por tramos segun el estado del taxi.
- Historico persistente en `data/historial_carreras.csv`.
- Logs tecnicos en `logs/taximetro.log`.
- Tarifas configurables en `config/tarifas.json`.
- Tests automatizados con `unittest`.
- Acceso protegido con contraseña hasheada mediante PBKDF2.
- Interfaz grafica Tkinter con botones grandes.

## Requisitos

- Python 3.10 o superior.
- No necesita librerias externas.

## Uso CLI

```bash
python3 main.py
```

En la primera ejecucion el programa pedira crear una contraseña.

Comandos disponibles:

- `inicio` o `i`: iniciar carrera.
- `parado` o `p`: cambiar a taxi parado.
- `marcha` o `m`: cambiar a taxi en movimiento.
- `ver` o `v`: ver estado, tiempo e importe actual.
- `fin` o `f`: finalizar carrera y guardar el historico.
- `historial` o `h`: mostrar carreras guardadas.
- `salir` o `s`: cerrar el programa.

## Uso GUI

```bash
python3 main.py --gui
```

## Cambiar tarifas

Las tarifas se cargan al iniciar el programa, tanto en la CLI como en la interfaz grafica. Los cambios se aplican en la siguiente ejecucion; no se recargan durante una carrera.

Edita `config/tarifas.json`:

```json
{
  "stopped_rate_per_second": 0.02,
  "moving_rate_per_second": 0.05
}
```

Si el fichero falta, tiene un JSON mal formado, le falta una clave o contiene una tarifa no numerica o negativa, el programa no inicia y muestra un error de configuracion identificable.

## Despliegue

El despliegue es un contenedor Docker. El destino, los prerrequisitos y el
procedimiento completo estan en
[docs/prod-04-despliegue.md](docs/prod-04-despliegue.md).

Prerrequisito: un runtime de contenedores, Docker Desktop o Colima.

```bash
colima start --cpu 2 --memory 4 --disk 20
```

Un unico comando construye la imagen, levanta el servicio y espera a que la
comprobacion de operatividad confirme que la aplicacion esta lista:

```bash
make deploy
```

Para usar el taximetro:

```bash
make cli
```

El historial, la contrasena, las tarifas y los logs viven en un volumen de
Docker montado en `/var/lib/taximetro` y sobreviven a `make down` +
`make deploy`. Solo `make down-volumes` los borra.

La comprobacion automatica no abre ventana y se puede ejecutar por separado:

```bash
make check
```

## Tests

```bash
python3 -m unittest
```

## Estructura

```text
.
├── config/tarifas.json
├── docker/entrypoint.sh
├── docs/
│   ├── github-project-tasks.md
│   └── prod-04-despliegue.md
├── main.py
├── requirements.txt
├── taximeter/
│   ├── auth.py
│   ├── cli.py
│   ├── config.py
│   ├── gui.py
│   ├── healthcheck.py
│   ├── history.py
│   ├── logging_config.py
│   ├── paths.py
│   └── taximeter.py
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_deploy_security.py
│   ├── test_healthcheck.py
│   ├── test_history.py
│   ├── test_history_interfaces.py
│   ├── test_logging.py
│   ├── test_paths.py
│   └── test_taximeter.py
├── Dockerfile
├── Makefile
└── docker-compose.yml
```

## Historias cubiertas

| ID | Estado |
| --- | --- |
| US-01 | Implementada |
| US-02 | Implementada |
| US-03 | Implementada |
| US-04 | Implementada |
| US-05 | Implementada |
| US-06 | Implementada |
| US-07 | Implementada |
| US-08 | Implementada |
| US-09 | Implementada |
| PROD-04 | Implementada |

Fase 4 documentada: el despliegue reproducible con un comando esta en PROD-04. La
API REST (PROD-02) y el panel web (PROD-03) siguen developing en sus respectivas
ramas.

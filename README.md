# TaxiTech Solutions - Sistema de Taximetro Digital

Prototipo en Python para calcular el importe de carreras de taxi en tiempo real.

Tarifas por defecto:

- Taxi parado o velocidad menor de 20 km/h: `0.02 EUR/segundo`
- Taxi en movimiento: `0.05 EUR/segundo`

## Funcionalidades

- CLI para iniciar, cambiar estado, finalizar y encadenar carreras.
- Calculo continuo por tramos segun el estado del taxi.
- Historico persistente en SQLite `data/taximetro.db` y CSV heredado `data/historial_carreras.csv`.
- API REST de solo lectura para consultar el historial desde otros sistemas.
- Logs tecnicos en `logs/taximetro.log`.
- Tarifas configurables en `config/tarifas.json`.
- Tests automatizados con `unittest`.
- Acceso protegido con contraseña hasheada mediante PBKDF2, almacenada en `data/credentials.json` con permisos `600`.
- Interfaz grafica Tkinter con botones grandes.

## Requisitos

- Python 3.10 o superior.
- No necesita librerias externas.

## Uso CLI

```bash
python3 main.py
```

En la primera ejecucion el programa pedira crear una contraseña. La contraseña
nunca se guarda en texto plano: se almacena su hash PBKDF2-HMAC-SHA256 con un
salt aleatorio, y el archivo de credenciales se crea con permisos `600`. Si el
archivo llega a estar dañado, la aplicacion lo detecta y ofrece restablecer la
contraseña en lugar de quedar bloqueada en la pantalla de acceso.

Comandos disponibles:

- `inicio` o `i`: iniciar carrera.
- `parado` o `p`: cambiar a taxi parado.
- `marcha` o `m`: cambiar a taxi en movimiento.
- `ver` o `v`: ver estado, tiempo e importe actual.
- `fin` o `f`: finalizar carrera y guardar el historico.
- `historial` o `h`: mostrar carreras guardadas.
- `salir` o `s`: cerrar el programa.

## Migrar historial a SQLite

La migracion documentada en `docs/prod-01-migracion-historial.md` se ejecuta desde la raiz del proyecto:

```bash
python3 main.py --migrate-history
```

El informe muestra las filas importadas, las ya existentes y las rechazadas con su linea y motivo. La migracion es idempotente y conserva `data/historial_carreras.csv` sin modificarlo. La CLI y la GUI consultan las carreras desde `data/taximetro.db`; no borres el CSV hasta verificar el informe y consultar la informacion importada.

## API REST del historial

Consulta el historial mediante HTTP. La API es de **solo lectura** y escucha en
`127.0.0.1:8000` por defecto:

```bash
python3 main.py --api
```

```bash
curl http://127.0.0.1:8000/api/v1/trips
```

El unico endpoint es `GET /api/v1/trips`, que devuelve una coleccion JSON con
`date`, `duration_seconds` y `amount` de cada carrera, o una lista vacia si no
hay carreras. Los recursos inexistentes devuelven `404` y los metodos distintos
de `GET` devuelven `405`. Se puede cambiar la direccion y el puerto con
`--api-host` y `--api-port`.

La documentacion completa, con ejemplos de respuestas y errores, esta en
`docs/prod-02-api-rest.md`. La API no requiere contrasena: antes de exponerla
fuera del vehiculo hay que revisar los riesgos pendientes de ese documento.

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

## Tests

```bash
python3 -m unittest
```

## Estructura

```text
.
├── config/tarifas.json
├── docs/github-project-tasks.md
├── docs/prod-01-migracion-historial.md
├── docs/prod-02-api-rest.md
├── main.py
├── taximeter/
│   ├── api.py
│   ├── auth.py
│   ├── cli.py
│   ├── config.py
│   ├── database.py
│   ├── gui.py
│   ├── history.py
│   ├── logging_config.py
│   ├── migration.py
│   └── taximeter.py
└── tests/
    ├── test_api.py
    ├── test_auth.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_database.py
    ├── test_gui.py
    ├── test_history.py
    ├── test_history_interfaces.py
    ├── test_logging.py
    ├── test_migration.py
    └── test_taximeter.py
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
| PROD-01 | Implementada |
| PROD-02 | Implementada |

La evolucion pendiente de la fase 4 incluye panel web y despliegue; el historial
ya tiene una base de datos local consultable y una API REST de solo lectura.

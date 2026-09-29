# 🚕 TaxiTech Solutions · Taxímetro Digital

<p align="center">
  <em>Prototipo en Python para calcular el importe de carreras de taxi en tiempo real</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/gui-customtkinter-1F6FEB?style=flat-square" alt="GUI con customtkinter">
  <img src="https://img.shields.io/badge/tests-62%20OK-4C1?style=flat-square" alt="62 tests OK">
  <img src="https://img.shields.io/badge/historias-9%2F9-6f42c1?style=flat-square" alt="9 de 9 historias">
  <img src="https://img.shields.io/badge/fase-3%20Arquitectura%20y%20UX-orange?style=flat-square" alt="Fase 3">
</p>

---

## 💰 Tarifas por defecto

- CLI para iniciar, cambiar estado, finalizar y encadenar carreras.
- Calculo continuo por tramos segun el estado del taxi.
- Historico persistente en SQLite `data/taximetro.db` y CSV heredado `data/historial_carreras.csv`.
- API REST de solo lectura para consultar el historial desde otros sistemas.
- Panel web del historial para revisarlo desde el navegador.
- Logs tecnicos en `logs/taximetro.log`.
- Tarifas configurables en `config/tarifas.json`.
- Tests automatizados con `unittest`.
- Acceso protegido con contraseña hasheada mediante PBKDF2, almacenada en `data/credentials.json` con permisos `600`.
- Interfaz grafica Tkinter con botones grandes.

---

## ✨ Funcionalidades

- 🖥️ **CLI interactiva** — iniciar, cambiar estado, finalizar y encadenar carreras.
- 📊 **Cálculo continuo** por tramos según el estado del taxi.
- 🔐 **Acceso protegido con contraseña** — PBKDF2-HMAC-SHA256 con 600.000 iteraciones y salt aleatorio por credencial; nunca se guarda en claro.
- 🖼️ **Interfaz gráfica moderna** (customtkinter) con tema oscuro elegante, botones grandes de colores y píldora de estado que cambia según la carrera.
- 📁 **Histórico persistente** en `data/historial_carreras.csv`.
- ⚙️ **Tarifas configurables** en `config/tarifas.json`.
- 📝 **Logs técnicos** en `logs/taximetro.log`.
- ✅ **62 tests automatizados** con `unittest`.

---

## 🚀 Uso rápido

### CLI

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

## Panel web del historial

El mismo servicio publica el historial como pagina web en la raiz:

```text
Panel web del historial: http://127.0.0.1:8000/
```

Basta con abrir `http://127.0.0.1:8000/` en el navegador. Cada carrera aparece
con fecha, duracion e importe en formato legible, y el panel avisa
claramente cuando no hay carreras. El HTML se genera en el servidor, sin
JavaScript ni recursos externos.

El historial se lee de la base en cada peticion, asi que al terminar una carrera
y recargar la pagina aparece el registro nuevo sin reiniciar el servicio. Es de
solo lectura: crear, editar, buscar, filtrar y exportar quedan fuera de alcance.

La documentacion completa esta en `docs/prod-03-panel-web.md`. El panel tampoco
requiere contrasena, con el mismo aviso que la API.

## Uso GUI

```bash
pip install -r requirements.txt   # primera vez
python3 main.py --gui
```

La primera ejecución solicita crear y confirmar una contraseña; en las siguientes, la GUI requiere autenticarse antes de mostrar el taxímetro. Si la contraseña es incorrecta muestra un error y permite reintentar (se puede confirmar con la tecla <kbd>Enter</kbd>).

Interfaz con **tema oscuro elegante**: tarjetas redondeadas, importe grande de lectura inmediata y una **píldora de estado** que cambia de gris (sin carrera) a ámbar (parado) y verde (en movimiento). Los botones `Iniciar` (verde), `Parado` (ámbar), `Marcha` (cian), `Finalizar` (rojo) e `Historial` (gris) se actualizan cada 500 ms.

---

## ⌨️ Comandos CLI

| Comando | Alias | Descripción |
| :--- | :---: | :--- |
| `inicio` | `i` | Iniciar carrera |
| `parado` | `p` | Cambiar a taxi parado |
| `marcha` | `m` | Cambiar a taxi en movimiento |
| `ver` | `v` | Ver estado, tiempo e importe actual |
| `fin` | `f` | Finalizar carrera y guardar en el histórico |
| `historial` | `h` | Mostrar carreras guardadas |
| `salir` | `s` | Cerrar el programa |

---

## ⚙️ Cambiar tarifas

Las tarifas se cargan al iniciar el programa (CLI y GUI). Los cambios se aplican en la siguiente ejecución; no se recargan durante una carrera.

```json
{
  "stopped_rate_per_second": 0.02,
  "moving_rate_per_second": 0.05
}
```

Si el fichero falta, tiene un JSON mal formado, le falta una clave o contiene una tarifa no numérica o negativa, el programa **no inicia** y muestra un error de configuración identificable.

---

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

> **62 tests OK** — cubren dominio, configuración, autenticación, histórico, logging y las dos interfaces (CLI y GUI).

---

## 🏗️ Arquitectura

Separación en tres capas: **presentación** (CLI/GUI), **dominio** puro sin E/S y **infraestructura** (ficheros y logs).

```mermaid
flowchart TD
    M["main.py"] --> CLI["🖥️ cli.py"]
    M --> GUI["🖼️ gui.py"]

    CLI --> AUTH["🔐 auth.py"]
    GUI --> AUTH
    CLI --> TAX["⚙️ taximeter.py (dominio puro)"]
    GUI --> TAX

    TAX --> CFG["📄 config.py"]
    TAX --> HIS["📁 history.py"]
    CLI --> LOG["📝 logging_config.py"]

    AUTH --> CRED[("data/credentials.json<br/>salt + hash")]
    HIS --> CSV[("data/historial_carreras.csv")]
    CFG --> JSON[("config/tarifas.json")]
    LOG --> LOGF[("logs/taximetro.log")]

    style TAX fill:#ffd54f,stroke:#f57f17,color:#000
    style AUTH fill:#ef9a9a,stroke:#c62828,color:#000
    style CFG fill:#a5d6a7,stroke:#2e7d32,color:#000
    style HIS fill:#90caf9,stroke:#1565c0,color:#000
    style LOG fill:#ce93d8,stroke:#6a1b9a,color:#000
```

**Claves de diseño:**

- 🧠 `Taximeter` es **código de dominio puro**: no hace E/S y recibe las tarifas y un **reloj inyectado**, lo que permite simular carreras de 30 s en microsegundos durante los tests.
- 🔌 **Sin acoplamiento a ficheros**: cada componente recibe su ruta por parámetro con un valor por defecto.
- 🔁 **CLI y GUI comparten el mismo dominio**: ambas usan `Taximeter`, `TripHistory` y `PasswordAuth`.
- 🛡️ **Validación exhaustiva** de la configuración: tipos, valores no negativos, números finitos y JSON mal formado.

---

## 📂 Estructura

```bash
.
├── config/tarifas.json
├── docker/entrypoint.sh
├── docs/
│   ├── github-project-tasks.md
│   └── prod-04-despliegue.md
├── main.py
├── requirements.txt
├── taximeter/
│   ├── api.py
│   ├── auth.py
│   ├── cli.py
│   ├── config.py
│   ├── database.py
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

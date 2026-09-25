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

La primera ejecucion solicita crear y confirmar una contraseña; en las siguientes, la GUI requiere autenticarse antes de mostrar el taximetro.

La pantalla ofrece los botones `Iniciar`, `Parado`, `Marcha`, `Finalizar` e `Historial` con tipografia 18 y altura de tres filas. Muestra estado, tiempo e importe, y se actualiza automaticamente cada 500 ms.

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
├── main.py
├── taximeter/
│   ├── auth.py
│   ├── cli.py
│   ├── config.py
│   ├── gui.py
│   ├── history.py
│   ├── logging_config.py
│   └── taximeter.py
└── tests/
    ├── test_auth.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_gui.py
    ├── test_history.py
    ├── test_history_interfaces.py
    ├── test_logging.py
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

La fase 4 queda documentada como evolucion futura porque requiere API, base de datos y despliegue.

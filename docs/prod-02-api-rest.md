# PROD-02: Exponer API REST

## Estado

Implementada. La API se construye con `http.server` de la biblioteca estandar
(`ThreadingHTTPServer`), sin anadir dependencias externas, para no romper la
promesa del proyecto de funcionar solo con Python 3.10 o superior.

## Objetivo

Permitir que un cliente externo consulte el historial de carreras y lo integre
con otros sistemas, sin exponer el control de carreras.

## Como iniciar el servicio

Desde la raiz del proyecto:

```bash
python3 main.py --api
```

El servicio escucha en `http://127.0.0.1:8000` por defecto y muestra por
consola la URL exacta del endpoint. Se detiene con `Ctrl+C`.

La direccion y el puerto son configurables:

```bash
python3 main.py --api --api-host 0.0.0.0 --api-port 9000
```

`--api-host` y `--api-port` solo son validos junto a `--api`; si se pasan sin
el, la aplicacion termina con codigo de salida 2. `--api` es excluyente con
`--gui` y `--migrate-history`.

La API lee de `data/taximetro.db`, la misma base que consultan la CLI y la GUI.
Si la base aun no existe, se crea vacia; conviene ejecutar antes
`python3 main.py --migrate-history` para importar el historico en CSV.

## Endpoint

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| `GET` | `/api/v1/trips` | Devuelve todas las carreras registradas |

La version va en la ruta (`v1`) para poder evolucionar el contrato sin romper a
los clientes existentes. Cada carrera se serializa con exactamente tres
campos: `date`, `duration_seconds` y `amount`. No se exponen identificadores
internos de la base de datos.

El servicio solo admite `GET`. Cualquier otro metodo devuelve `405` con la
cabecera `Allow: GET`. La query string se ignora: no hay filtros ni paginacion.

## Ejemplos

### Consulta correcta

```bash
curl -i http://127.0.0.1:8000/api/v1/trips
```

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 155

[
  {
    "date": "2026-09-25T13:17:38",
    "duration_seconds": 1303.91,
    "amount": 64.75
  },
  {
    "date": "2026-09-25T14:35:10",
    "duration_seconds": 47.58,
    "amount": 2.18
  }
]
```

Las carreras se ordenan por fecha y, a igualdad de fecha, por orden de
insercion.

### Sin carreras: coleccion vacia, no un error

Si la base no tiene carreras, la respuesta es un exito con una lista vacia:

```bash
curl -i http://127.0.0.1:8000/api/v1/trips
```

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: 2

[]
```

### Errores del cliente

Recurso inexistente:

```bash
curl -i http://127.0.0.1:8000/api/v1/conductores
```

```http
HTTP/1.1 404 Not Found
Content-Type: application/json; charset=utf-8

{"error": "not_found", "message": "Recurso no encontrado. El historial se consulta en /api/v1/trips."}
```

Metodo no permitido:

```bash
curl -i -X POST http://127.0.0.1:8000/api/v1/trips
```

```http
HTTP/1.1 405 Method Not Allowed
Allow: GET
Content-Type: application/json; charset=utf-8

{"error": "method_not_allowed", "message": "Solo se admite GET sobre /api/v1/trips. La API es de solo lectura."}
```

Todos los errores usan la misma forma, con un codigo estable para consumir
desde el cliente y un mensaje legible:

```json
{
  "error": "not_found",
  "message": "..."
}
```

### Error interno

Si la base de datos no se puede consultar, el cliente recibe un `500` generico
y el detalle real solo queda en el log del servidor:

```http
HTTP/1.1 500 Internal Server Error
Content-Type: application/json; charset=utf-8

{"error": "internal_error", "message": "No se pudo consultar el historial."}
```

La respuesta no incluye rutas del sistema, excepciones ni mensajes del
gestor de base de datos. El detalle se registra en `logs/taximetro.log` con el
evento `api_trips_error`.

## Codigos de estado

| Codigo | Cuando ocurre |
| --- | --- |
| `200` | Consulta correcta, incluso con lista vacia |
| `404` | La ruta no es `/api/v1/trips` |
| `405` | El metodo no es `GET` |
| `500` | Fallo interno al leer el historial |

## Decisiones

- **Motor HTTP:** `ThreadingHTTPServer` de la biblioteca estandar. No se anade
  Flask ni FastAPI para conservar la ejecucion sin dependencias externas.
- **Solo lectura:** el unico endpoint devuelve datos. No existe forma de crear,
  modificar o borrar carreras por HTTP, tal y como fija el alcance.
- **Escucha en loopback por defecto:** `127.0.0.1`. Exponer el historial en la
  red es una decision consciente, por eso hay que pasar `--api-host` a mano.
- **Sin autenticacion:** ver Riesgos pendientes.
- **Rutas exactas:** `/api/v1/trips/` con barra final devuelve `404`. Se evita
  accepting dos rutas para el mismo recurso.

## Riesgos pendientes

- **La API no requiere contrasena.** La CLI y la GUI protegen el acceso con la
  contraseña del taximetro, pero la API es de consulta y no valida credenciales.
  El alcance de PROD-02 no lo pedia, asi que no se ha implementado, pero deja el
  historial accesible a cualquiera que alcance el puerto. Antes de exponerla
  fuera del equipo del vehiculo hay que decidir entre autenticacion, tokens de
  solo lectura o una red de confianza.
- **Datos sin cifrar en transito.** Al usar HTTP simple, el contenido viaja en
  claro. Es aceptable en `localhost`; no lo es en una red compartida.
- **Sin limite de peticiones.** No hay rate limiting ni limites de tamano de
  respuesta. El historial es pequeño, pero conviene revisarlo si la API se
  consulta desde sistemas automaticos.

## Fuera de alcance

Control de carreras mediante API, escritura de datos, CORS, WebSockets,
filtros y paginacion.

## Verificacion

```bash
python3 -m unittest
```

`tests/test_api.py` levanta un servidor HTTP real en un puerto efimero y
comprueba la respuesta correcta, la coleccion vacia, los `404` y `405` de cada
metodo no admitido, la ausencia de escritura y el `500` sin filtrar detalles
internos.

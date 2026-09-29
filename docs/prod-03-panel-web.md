# PROD-03: Crear panel web de historial

## Estado

Implementada. El panel se sirve desde el mismo proceso que la API, generado en
el servidor con HTML y CSS propios: sin JavaScript, sin CDN y sin dependencias
externas, para que tambien funcione en una tableta sin salida a internet.

## Objetivo

Permitir que un responsable de turno revise las carreras desde el navegador, sin
depender de la CLI ni de la aplicacion de escritorio.

## Como abrir el panel

Se levanta junto con la API. Desde la raiz del proyecto:

```bash
python3 main.py --api
```

Al arrancar, el servicio imprime las dos URLs disponibles:

```text
Panel web del historial: http://127.0.0.1:8000/
API REST del historial: http://127.0.0.1:8000/api/v1/trips
El servicio es de solo lectura. Pulsa Ctrl+C para detenerlo.
```

El panel se abre en `http://127.0.0.1:8000/`. Con `--api-host` y `--api-port`
se cambia la direccion y el puerto.

El panel lee de `data/taximetro.db`, el repositorio de persistencia vigente, el
mismo que consultan la CLI y la GUI. Si la base esta vacia porque el historico
sigue en CSV, ejecuta antes `python3 main.py --migrate-history`.

## Rutas

| Metodo | Ruta | Respuesta |
| --- | --- | --- |
| `GET` | `/` | Panel web del historial en HTML |
| `GET` | `/api/v1/trips` | Mismos datos en JSON (ver `docs/prod-02-api-rest.md`) |

Cualquier otra ruta devuelve `404`. Cualquier metodo distinto de `GET` devuelve
`405` con la cabecera `Allow: GET`: el panel es de solo lectura.

## Listado de carreras

Cada carrera se muestra en una fila con fecha, duracion e importe. El servidor
traduce los datos a un formato legible: la fecha como `dd/mm/aaaa hh:mm`, la
duracion en horas, minutos y segundos, y el importe con dos decimales y la
moneda.

```html
<table><caption>Carreras registradas, de la mas reciente a la mas antigua.</caption>
<thead><tr><th scope="col">Fecha</th><th scope="col">Duración</th>
<th scope="col">Importe</th></tr></thead><tbody>
<tr><td class="date">25/09/2026 13:17</td><td class="duration">21 min 44 s</td><td class="amount">64.75 EUR</td></tr>
<tr><td class="date">25/09/2026 14:35</td><td class="duration">48 s</td><td class="amount">2.18 EUR</td></tr>
</tbody></table>
```

Las carreras se ordenan de la mas reciente a la mas antigua, con la misma
consulta que usa la API, de modo que el panel y el JSON nunca se contradicen.

Los importes usan el punto decimal para ser coherentes con la salida de la CLI
(`64.75 EUR`) y con los datos que devuelve la API.

## Estado vacio

Si todavia no hay carreras, el panel lo dice de forma explicita y no pinta una
tabla vacia que pueda confundirse con un fallo de carga:

```html
<h1>Historial de carreras</h1>
<section class="notice"><p>Todavia no hay carreras registradas.</p></section>
```

La respuesta es un `200`: no hay carreras es un estado normal, no un error. En
cuanto se registra una carrera y se recarga la pagina, el aviso desaparece.

## El panel refleja las carreras nuevas sin reiniciar

El historial se lee de la base de datos **en cada peticion**, no se carga en
memoria al arrancar el servicio. El flujo previsto es:

1. Con el servicio en marcha, se termina una carrera desde la CLI o la GUI.
2. La carrera se guarda en `data/taximetro.db`.
3. Se recarga el navegador.
4. La nueva carrera aparece en la tabla, sin reiniciar el servicio a mano.

El vaciado de cache no es necesario porque el servicio no guarda el historial en
memoria; por eso el panel no tiene boton de recargar ni temporizadores de
actualizacion. Si se quisiera ver un cambio sin recargar la pagina, haria falta
WebSockets, que quedan fuera de alcance.

## Error al obtener el historial

Si la base de datos no se puede consultar, el panel lo comunica sin mostrar
informacion sensible. La respuesta es un `500` y la pagina explica el problema:

```html
<h1>No se pudo consultar el historial</h1>
<section class="notice error">
<h2>No se pudo consultar el historial</h2>
<p>No se pudo obtener el historial de carreras. Comprueba que el servicio sigue
en marcha y vuelve a recargar la pagina.</p>
</section>
```

La pagina no incluye rutas del sistema, excepciones ni mensajes del gestor de
base de datos. El detalle real se registra en `logs/taximetro.log` con el evento
`panel_render_error`. El servicio sigue disponible: en la siguiente peticion que
funcione, el panel vuelve a mostrar la tabla.

## Decisiones

- **Ubicacion del codigo:** el renderizado del panel vive en
  `src/taximeter/interfaces/web/panel.py` y lo sirve
  `src/taximeter/interfaces/api.py` en la misma ruta `/`. Las filas del listado
  son `HistoryEntry` de `src/taximeter/application/ports.py`.
- **HTML generado en el servidor:** el navegador no ejecuta JavaScript. Asi el
  panel funciona sin permisos especiales, funciona offline y el HTML que llega
  al navegador ya contiene los datos reales, sin la posibilidad de que un fallo
  de red se muestre como un historial vacio.
- **Sin recursos externos:** ni scripts, ni hojas de estilo por CDN, ni fuentes
  remotas. El CSS va incrustado en la pagina.
- **Escapado de los datos:** todos los valores del historial se escapan antes de
  inyectarlos en el HTML, de modo que un dato raro en la base no puede inyectar
  marcado.
- **Sin totales ni graficos:** se muestra exactamente lo que pide el alcance,
  una fila por carrera. Un resumen del turno se puede anadir en el futuro.
- **Estetica basica y sin responsive:** el diseno se centra en la legibilidad
  (tipografia de sistema, contraste alto, amounts tabulares) y declara soporte
  de tema claro y oscuro. No se trabajo el diseno movil, que queda fuera de
  alcance.

## Riesgos pendientes

- **El panel no requiere contrasena.** Igual que la API, el servicio no valida
  credenciales: cualquiera que alcance el puerto ve el historial. Los riesgos
  estan detallados en `docs/prod-02-api-rest.md`. El panel no debe publicarse en
  internet tal cual.
- **Sin cache de aplicacion:** es intencionado, pero implica una consulta a la
  base por cada recarga. Con el volumen del prototipo es irrelevante.

## Fuera de alcance

Crear, editar o eliminar carreras, busqueda, filtros, exportacion y diseno
movil especifico.

## Verificacion

```bash
python3 -m unittest
```

`tests/test_panel.py` levanta un servidor HTTP real y comprueba el listado con
los formatos legibles, el estado vacio sin datos inventados, la recarga que
refleja una carrera nueva sin reiniciar el servicio, el mensaje de error sin
informacion sensible, el escapado de valores con marcado y que el panel nunca
escribe en el historial.

# PROD-04 - Preparar despliegue con un comando

## Objetivo

Poner en marcha el taximetro con un unico comando, de forma reproducible, sin
pasos manuales despues del despliegue, y con una comprobacion automatica que
confirme que la aplicacion esta operativa.

## Destino del despliegue

Contenedor Docker. La imagen se construye desde el `Dockerfile` de la raiz y se
levanta con `docker-compose.yml`.

El taximetro es una aplicacion de escritorio, no un servicio web: no expone
ningun puerto ni escucha peticiones. Por eso el contenedor desplegado no publica
un endpoint, sino que **prepara y verifica el entorno de ejecucion** y lo deja
disponible. El taximetro se opera entrando en el contenedor:

```bash
make cli
```

El contenedor permanece en ejecucion y se autocomprueba cada 60 segundos, de
modo que si algo se rompe despues del despliegue el servicio pasa a
`unhealthy` en lugar de fallar en silencio.

## Componentes desplegados

| Componente | Estado | Como se comprueba |
|---|---|---|
| CLI (`main.py`) | Desplegada | Se ejecuta con `make cli` |
| Interfaz grafica (`--gui`) | Incluida en la imagen | `import tkinter` y version de Tcl/Tk |
| Comprobacion de operatividad | Sin pantalla | `python3 -m taximeter.healthcheck` |

La comprobacion automatica **nunca abre una ventana**: importa `tkinter` y lee su
version, pero no instancia `Tk()`. Eso permite validar la GUI en un contenedor
sin display.

Para usar la GUI hacen falta librerias de Tcl/Tk en la imagen. La imagen oficial
`python:3.12-slim` compila `_tkinter` pero **no** incluye las librerias
compartidas, asi que sin `libtcl8.6` y `libtk8.6` la GUI no arranca. El
`Dockerfile` las instala. Para ver la GUI hace falta ademas un display, lo que
supone tunneling X11 hacia el host:

```bash
docker compose run --rm \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -e DISPLAY=host.docker.internal:0 \
  taximetro python3 main.py --gui
```

Esto requiere XQuartz en macOS. No es la via recomendada para un taximetro real,
que se despliega directamente sobre la tablet.

## Prerrequisitos

- Un runtime de contenedores: Docker Desktop, o Colima en macOS.

```bash
colima start --cpu 2 --memory 4 --disk 20
```

- El binario `docker` con el plugin de Compose.
- Nada mas. No hace falta Python, ni librerias, ni permisos de administrador en
  el host: todo ocurre dentro de la imagen.

## Comando unico

```bash
make deploy
```

Ese unico comando construye la imagen, levanta el contenedor, espera a que la
comprobacion de operatividad pase y solo entonces devuelve el control. Si algo
falla, muestra las ultimas lineas del contenedor y termina con codigo distinto
de cero.

Desde una copia limpia del repositorio, sin imagen previa, el comando construye
la imagen, instala las dependencias declaradas en `requirements.txt`, prepara
los directorios persistentes y deja el servicio disponible y verificado.

## Comandos disponibles

| Comando | Que hace |
|---|---|
| `make deploy` | Construye, levanta y espera a que este sano |
| `make check` | Ejecuta solo la comprobacion de operatividad |
| `make cli` | Abre una sesion interactiva de la CLI en el contenedor |
| `make shell` | Abre una shell en el contenedor |
| `make test` | Ejecuta la suite de tests en local |
| `make down` | Detiene el servicio **conservando** los datos |
| `make down-volumes` | Detiene el servicio y **borra** los datos |
| `make help` | Lista los comandos |

## Datos persistentes

Los datos no viven en la imagen ni en el codigo. Viven en un volumen de Docker
montado en `/var/lib/taximetro`:

```
/var/lib/taximetro/config/tarifas.json          tarifas
/var/lib/taximetro/data/historial_carreras.csv   historial de carreras
/var/lib/taximetro/data/credentials.json         hash de la contrasena
/var/lib/taximetro/logs/taximetro.log            registro de operacion
```

La variable `TAXIMETER_HOME` es la que resuelve todas esas rutas. Un
`make down` seguido de `make deploy` conserva historial, contrasena, tarifas
editadas y logs. Solo `make down-volumes` los borra, y hay que pedirlo
explicitamente.

Fuera de Docker, la misma variable permite separar los datos del codigo:

```bash
TAXIMETER_HOME=var python3 -m taximeter.healthcheck
```

En el despliegue, la primera vez se copia `config/tarifas.json` del repositorio
al volumen. Si ya existe, **se conserva**: las tarifas editadas por el usuario
sobreviven a un redeploy. Si el fichero desaparece, el despliegue lo vuelve a
inicializar con los valores del repositorio en vez de dejar la aplicacion sin
configurar.

## Comprobacion de operatividad

`python3 -m taximeter.healthcheck` valida, sin abrir ventana y sin pedir
contrasena:

1. version de Python (3.10 o superior)
2. `tkinter` importable
3. directorios persistentes creables
4. tarifas presentes y validas
5. historial escribible
6. historial legible
7. logs escribibles
8. credenciales sanas y no legibles por otros usuarios
9. calculadora correcta, con un recorrido de 120 s y un resultado esperado

La comprobacion se ejecuta tres veces: al arrancar el contenedor, cada 60
segundos mientras vive, y cada 30 segundos como `HEALTHCHECK` de Docker.

El calculo del punto 9 usa un reloj inyectado, no el reloj real, porque un
recorrido instantaneo daria `0.00 EUR` y la comprobacion fallaria siempre.

## Fallos y codigos de salida

Si alguna fase falla, el comando termina con codigo distinto de cero y un error
identificable. El `entrypoint` imprime `DEPLOY_FAILED <codigo>: <motivo>`.

| Codigo | Comprobacion | Ejemplo de causa |
|---|---|---|
| 0 | Todo correcto | |
| 1 | Fallo inesperado | Excepcion no prevista |
| 10 | Version de Python | Python anterior a 3.10 |
| 11 | Directorios persistentes | Volumen montado en solo lectura |
| 12 | Tarifas ausentes | Sin `config/tarifas.json` |
| 13 | Tarifas invalidas | JSON roto, clave ausente, tarifa negativa |
| 14 | Historial escribible | `data/` no escribible |
| 15 | Historial legible | CSV corrupto |
| 16 | Logs escribibles | `logs/` no escribible |
| 17 | Credenciales | Legibles por otros, incompletas o corruptas |
| 18 | Calculadora | La carrera de prueba no cuadra |
| 19 | tkinter | Sin `_tkinter` en la imagen |

## Credenciales y secretos

- Ninguna credencial vive en el repositorio, en la imagen ni en el comando de
  despliegue. `data/` y `logs/` estan ignorados por git y excluidos por
  `.dockerignore`.
- La contrasena se crea en el primer uso interactivo, no durante el despliegue.
- `PasswordAuth.create_password()` escribe el fichero con permisos `600` y lo
  renombra de forma atomica, de modo que nunca queda legible para otros usuarios
  ni a medio escribir. El despliegue verifica esos permisos y **falla** si no
  son correctos.
- Solo se almacenan sal, hash e iteraciones. Nunca la contrasena.

## Verificacion realizada

Todo lo anterior se ha comprobado ejecutandolo, no solo escrito:

- Build limpio sin imagen previa ni volumen, y build con `--no-cache`.
- `make deploy` desde una copia limpia del repositorio en un directorio aparte.
- Persistencia de historial, contrasena y tarifas editadas tras `down` + `deploy`.
- Aislamiento: dos copias del repo conviven con volumenes independientes.
- Los siete modos de fallo reproducidos, cada uno con su codigo y su mensaje.
- `make deploy` devuelve codigo distinto de cero y vuelca los logs cuando el
  contenedor no llega a estar sano.
- Ausencia de credenciales en la imagen y en el indice de git.
- Suite de 79 tests, incluidos los permisos de `credentials.json` con `umask 000`.

## Limitaciones conocidas

- El despliegue es para un unico host, sin alta disponibilidad ni copias de
  seguridad automaticas. Conviene respaldar el volumen a mano.
- El contenedor no sirve por red. Si en el futuro se quiere consultar el
  historial desde otro dispositivo, hace falta el servicio web de PROD-02.
- La GUI dentro del contenedor es solo para pruebas: requiere tunneling X11.

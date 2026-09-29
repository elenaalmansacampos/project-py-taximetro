# PROD-01: Migracion del historial a base de datos

## Estado

Decision tomada antes de la implementacion: el historial operativo se migra a
SQLite 3 usando el modulo `sqlite3` de la biblioteca estandar de Python. No se
anaden dependencias externas.

## Objetivo

Conservar las carreras existentes en `data/historial_carreras.csv` dentro de
`data/taximetro.db` para que la CLI y la GUI consulten el historial desde una
base consultable por los siguientes componentes del sistema.

## Esquema

La base se inicializa de forma idempotente con el siguiente esquema:

```sql
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_local TEXT NOT NULL,
    duration_seconds REAL NOT NULL CHECK (duration_seconds >= 0),
    amount REAL NOT NULL CHECK (amount >= 0),
    record_key TEXT UNIQUE,
    source TEXT NOT NULL DEFAULT 'app',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trips_date_local
    ON trips (date_local);
```

`record_key` es la huella de deduplicacion de los registros importados del CSV.
Se calcula como SHA-256 de la fecha normalizada, la duracion y el importe
canonicalizados. La base aplica la restriccion `UNIQUE`, por lo que repetir la
migracion no inserta una carrera duplicada. Los registros creados por la
aplicacion dejan `record_key` a `NULL` porque cada carrera nueva es un evento
distinto.

## Decisiones

- **Motor:** SQLite 3. Es local, transaccional, forma parte de la biblioteca
  estandar y no requiere un servidor para el prototipo.
- **Clave de deduplicacion:** `sha256(fecha ISO-8601 normalizada | duracion
  canonica | importe canonico)`. El CSV no tiene identificador de carrera, por
  lo que la combinacion de sus tres campos es la identidad disponible.
- **Fechas:** se conserva el texto de fecha valido del CSV. Se interpreta como
  hora local, sin convertir zona horaria, porque asi lo genera actualmente
  `TripHistory` (`datetime.now().isoformat()`).
- **CSV:** `data/historial_carreras.csv` pasa a ser fuente de migracion y copia
  de seguridad. La migracion no lo borra ni lo modifica. Las nuevas carreras se
  guardan solo en SQLite.
- **Registros invalidos:** se informa cada linea rechazada con su numero y
  motivo. No se descartan silenciosamente.

## Procedimiento

1. Conservar una copia de seguridad del CSV antes de la primera ejecucion.
2. Desde la raiz del proyecto ejecutar:

   ```bash
   python3 main.py --migrate-history
   ```

3. Revisar el informe. Debe indicar cuantos registros se importaron, cuantos
   ya existian, cuantos se rechazaron y si la verificacion fue correcta.
4. Consultar la base con la aplicacion:

   ```bash
   python3 main.py
   python3 main.py --gui
   ```

5. No eliminar el CSV hasta que la informacion importada se haya consultado y
   verificado en la base.

## Verificacion

La migracion se considera verificada cuando todas las filas validas del CSV
tienen una fila equivalente en `trips` (misma fecha, duracion e importe) y no
quedan registros validos pendientes. El informe muestra el resultado y las
lineas rechazadas. Un informe con rechazos termina con codigo de salida 1 para
que el operador pueda corregirlos; las filas validas siguen importadas.

Consulta SQL de comprobacion:

```sql
SELECT date_local, duration_seconds, amount
FROM trips
ORDER BY date_local, id;
```

## Repeticion y recuperacion

La operacion usa una transaccion por registro y la restriccion `UNIQUE` sobre
`record_key`. Ejecutarla de nuevo solo informa de duplicados; no crea carreras
repetidas. Para deshacer una migracion basta con conservar o eliminar la base
`data/taximetro.db` y volver a ejecutar el procedimiento sobre el CSV, que no
se modifica.

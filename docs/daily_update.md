# ActualizaciÃ³n diaria (PROOF + LION + cachÃ©)

Flujo cada dÃ­a, tras subir el Excel `DD-MM-YYYY.xlsx` a la carpeta `sap/daily` de `CO_VISION_DATA_ROOT`:

```
python scripts/daily_update.py
```

Pasos (en orden; si uno falla no se publica la seÃ±al y la app sigue con los datos anteriores):

1. Incorpora a PROOF los Excel pendientes (`folder_sync`, con copia en `proof/sync_backups`).
2. Procesa el snapshot mÃ¡s reciente con LION (precalentamiento).
3. Lee el histÃ³rico PROOF y calcula las finalizaciones. Cada Excel se procesa una sola vez; los resultados se guardan en `vision/cache`, asÃ­ que el dÃ­a nuevo solo procesa su Excel.
4. Escribe `vision/cache/refresh_signal.json` con un token nuevo.

La app (`development_app.py`) lee ese token en cada ejecuciÃ³n. Si cambiÃ³, vacÃ­a `st.cache_data`, `st.cache_resource` y las cachÃ©s de sesiÃ³n (`_vision_*`) y recarga. No hay endpoint de red: la seÃ±al es un archivo.

## ProgramaciÃ³n

Ejecutar el comando justo despuÃ©s de que el Excel estÃ© disponible (por ejemplo, 08:00), en la misma mÃ¡quina/volumen que ve la app:

- Windows: Programador de tareas con `python scripts/daily_update.py`.
- Azure (App Service/contenedor): un WebJob o tarea programada que ejecute el mismo comando sobre el mismo almacenamiento que `CO_VISION_DATA_ROOT`.

## Lectura automÃ¡tica de la carpeta

```
python scripts/daily_update.py --watch
```

Vigila `sap/daily` cada 30 s. Cuando aparece o cambia un `.xlsx` (se ignoran los temporales `~$`) y la carpeta permanece estable 60 s, ejecuta la actualizaciÃ³n completa y publica la seÃ±al. Si falla, reintenta mÃ¡s tarde sin publicar. Debe ejecutarse como proceso permanente (servicio, WebJob continuo o tarea al inicio) junto a la app. En Azure Files, la detecciÃ³n por sondeo evita depender de eventos del sistema de archivos.

`scripts/prewarm.py` solo calienta la cachÃ© de finalizaciones, sin sincronizar ni avisar.

## Despliegue desde GitHub

La app de Azure se actualiza desde `main`; el cÃ³digo de esta funciÃ³n llega con el merge de su PR. La configuraciÃ³n de Azure (almacenamiento, tarea programada, variables) no forma parte del repositorio y debe hacerse en el entorno.


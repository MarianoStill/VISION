# Actualización diaria (PROOF + LION + caché)

Flujo cada día, tras subir el Excel `DD-MM-YYYY.xlsx` a la carpeta `sap/daily` de `CO_VISION_DATA_ROOT`:

```
python scripts/daily_update.py
```

Pasos (en orden; si uno falla no se publica la señal y la app sigue con los datos anteriores):

1. Incorpora a PROOF los Excel pendientes (`folder_sync`, con copia en `proof/sync_backups`).
2. Procesa el snapshot más reciente con LION (precalentamiento).
3. Lee el histórico PROOF y calcula las finalizaciones. Cada Excel se procesa una sola vez; los resultados se guardan en `vision/cache`, así que el día nuevo solo procesa su Excel.
4. Escribe `vision/cache/refresh_signal.json` con un token nuevo.

La app (`development_app.py`) lee ese token en cada ejecución. Si cambió, vacía `st.cache_data`, `st.cache_resource` y las cachés de sesión (`_vision_*`) y recarga. No hay endpoint de red: la señal es un archivo.

## Programación

Ejecutar el comando justo después de que el Excel esté disponible (por ejemplo, 08:00), en la misma máquina/volumen que ve la app:

- Windows: Programador de tareas con `python scripts/daily_update.py`.
- Azure (App Service/contenedor): un WebJob o tarea programada que ejecute el mismo comando sobre el mismo almacenamiento que `CO_VISION_DATA_ROOT`.

`scripts/prewarm.py` solo calienta la caché de finalizaciones, sin sincronizar ni avisar.

## Despliegue desde GitHub

La app de Azure se actualiza desde `main`; el código de esta función llega con el merge de su PR. La configuración de Azure (almacenamiento, tarea programada, variables) no forma parte del repositorio y debe hacerse en el entorno.

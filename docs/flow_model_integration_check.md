# Comprobación acotada de integración: Engine y `flow_model`

## Alcance y seguridad

Revisión de la ruta de PROOF desde `app.py` hasta las vistas del dashboard. No se ejecutó `app.py`, Streamlit, el `Engine` recibido, ningún módulo de filtro ni la suite original de PROOF. No se abrieron `config.json`, bases existentes, ficheros SAP ni datos operativos. No se modificaron las fuentes recibidas.

Antes de importar, se revisaron los módulos relevantes. `app.py` importa Streamlit y crea un `Engine` sobre `datos\historico_real.sqlite` o `datos\operativo.sqlite`; importar/ejecutar esa ruta podría crear directorios/base y lanzar UI. `dashboard.py` también importa Streamlit. `dashboard_filters_flow.py` importa el modelo y módulos de UI/filtros; su dashboard puede crear/escribir el directorio `cache_filtros` y JSON derivado, además de leer blobs Excel guardados. Por esas razones no se importaron ni ejecutaron.

`flow_model.py` en sí solo importa biblioteca estándar. Sus cinco casos de caracterización independientes siguen pasando con fixtures sintéticos, pero no constituyen integración con el `Engine`.

## Recorrido identificado estáticamente

1. `app.py` crea `Engine(dbp, cfg)`. En Resultados pide `observations()`, `matrix()`, `events()` e `instances()`. En Dashboard llama `dashboard.render_dashboard(e, cfg, ...)`.
2. `dashboard.py` tiene un wrapper de `render_dashboard` que importa `dashboard_filters_flow.render_dashboard`. Su dashboard obtiene observaciones, eventos e instancias del engine, y crea un `FilteredEngine` para filtrar documentos.
3. `dashboard_filters_flow.py` importa `project` y `aggregate` desde `flow_model.py`, pero en el archivo recibido no invoca ninguna de esas funciones. Si se elige “Demoras”, llama al dashboard original. Si se elige “Evolución y flujo”, su función `render_flow` delega en `inventory_chart.render_inventory`.
4. `inventory_chart.py` no usa `flow_model`. Consulta las fechas de observación con SQL y calcula las filas mediante `chart_rows(engine.instances(), dates, cfg['sources'], ...)`; esa función implementa una proyección de inventario distinta.

**Resultado:** no existe un recorrido ejecutable desde la entrada `app.py` hasta `flow_model.project`, `flow_model.aggregate` o `flow_model.bucket` en las fuentes recibidas. Hay un import de `project`/`aggregate`, pero es código no llamado por la cadena observada. No se inventó una conexión para la prueba.

### Compatibilidad estructural posible, no probada en ejecución

- El `Engine` define `events()` como una lista de payloads JSON derivados, y `instances()` como una lista de filas por instancia con campos calculados como `elapsed` y `consumption`.
- `flow_model.project(events, instances, dates, rules)` consume listas de eventos/instancias, fechas de observación y reglas. `Engine.observations()` y la configuración del dashboard podrían proporcionar fechas y reglas.
- Esta correspondencia es una lectura de estructuras y firmas, no evidencia de que un consumidor real transforme y pase esos valores a `flow_model`. En particular, no se encontró ese ensamblado en `app.py`, `dashboard.py`, `dashboard_filters_flow.py` ni `inventory_chart.py`.

## Pruebas y dependencias

No se añadió una prueba de integración artificial: el recorrido no existe. Una llamada manual Engine→`flow_model` probaría un enlace nuevo, no el comportamiento de la aplicación actual.

El `Engine` importa `classification_engine`, que importa `openpyxl`. El `.venv` actual de CO-VISION no tiene `openpyxl`; pytest 9.1.1 sí está instalado. Como no hay recorrido de aplicación que ejercitar, no se instaló `openpyxl` en otro entorno ni se creó un puente de prueba que el código no utiliza.

Se ejecutó `scripts\check.py` con `CO_VISION_PROOF_SOURCE_DIR` apuntando a la carpeta recibida:

- **Aprobadas:** 12 (cinco pruebas de caracterización aislada de `flow_model.py`, una prueba de import técnico de PROOF, una de LION, una de VISION y cuatro de carga integrada del scaffold).
- **Fallidas:** 0.
- **Omitidas:** 0.

La prueba técnica general no inicia la aplicación empresarial recibida, no importa su `Engine` ni valida integración con `flow_model`. Las cinco caracterizaciones comprueban solo el comportamiento autónomo descrito en `docs/flow_model_characterization.md`.

## Archivos examinados y SHA-256

Hashes de la copia recibida; calculados localmente en modo lectura:

| Archivo | SHA-256 |
| --- | --- |
| `PROOF\app.py` | `B3738A072AE4C6097D2A4244CA554ECF3AF19DDD30579F68D95881722D628C75` |
| `PROOF\proof.py` | `2A77FCEC37B90B6EF182BD0BB1F9C1A753F719644BC84F6DD9AEC1457AF5FD98` |
| `PROOF\classification_engine.py` | `D6F308C835E8921F46EAF020C2908B78EF1340C72600F0969D39D2B9A0A6282C` |
| `PROOF\dashboard.py` | `A1F36388ABC947653D0DFCB8B44DF75BC0AE108440BC1E12BC6E1DCC4EF99490` |
| `PROOF\dashboard_filters_flow.py` | `EBA6E3486B2E04CBD0253D3D9A57A9BAF9AAA01D6AD7AD9AC00D863E96477B6E` |
| `PROOF\inventory_chart.py` | `74FC04B32D95C31411C4F2E5A495315655F0C98EFAC5C3109FCD74724724BA8F` |
| `PROOF\flow_model.py` | `051C20587A95D8E79A616AE19A6ADA2FE426B32F0BF83EE999A6CDCE418CA9C9` |
| `PROOF\test_flow.py` | `BD86EB8519A33203667013E14290C3C1B138F627A00144E54E9E073BFB560AF6` |

No se leyó ni se hasheó `config.json`, base de datos ni libro Excel.

## Límites y criterio de migración

- **Compatibilidad técnica:** el scaffold CO-VISION pasa sus pruebas; no se ejecutó el Engine recibido con dependencias de aplicación.
- **Equivalencia con la copia:** se caracterizaron cinco casos aislados de `flow_model`; no se comprobó su integración con el Engine ni la UI.
- **Validación empresarial:** no realizada. Las definiciones de cohortes parciales, entradas/movimientos, pendientes terminales y períodos observados requieren aprobación de negocio.
- La coincidencia de LION con Azure no afecta esta comprobación y continúa pendiente por separado.

**Recomendación:** no migrar todavía como cambio de comportamiento preservado. `flow_model.py` es un candidato autocontenido para una futura extracción, pero actualmente no participa en el dashboard de la copia recibida; migrarlo tal cual incorporaría o activaría lógica que no está en el recorrido actual. Primero debe decidirse si CO-VISION adoptará esas proyecciones de cohorte/flujo y sus definiciones, y si reemplazarán o complementarán el inventario que calcula `inventory_chart.py`. Si se aprueba esa función, la migración requerirá entonces una integración intencional con las salidas del Engine y una prueba dedicada, claramente separada de equivalencia del código y aprobación empresarial.

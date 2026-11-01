# Línea base de procedencia de fuentes: LION y PROOF

## Alcance

Revisión estática de las carpetas de recepción. No se iniciaron las aplicaciones ni se ejecutaron pruebas, instaladores o dependencias. No se modificaron fuentes originales. Las rutas de imports descritas abajo son los recorridos observables desde los candidatos de entrada; no prueban qué copia/version se usa en el equipo o en un despliegue.

## Identificado en el código

### LION

**Candidato a punto de entrada para el uso en Azure:** `azure_entry.py`, porque el usuario confirma que utiliza LION desde el navegador en Azure y el paquete recibido incluye documentación y un script de arranque que seleccionan ese archivo. Esto identifica la ruta prevista en el paquete, no demuestra que sea la ruta desplegada.

`DESPLIEGUE_AZURE.md` recomienda `bash startup_lion.sh` como Startup Command. El `startup_lion.sh` recibido cambia al directorio del script y ejecuta `python -m streamlit run azure_entry.py` en `0.0.0.0:8000`, con opciones de servidor explícitas. `azure_entry.py` comprueba identidad/publicación y termina llamando a `app.py` mediante `runpy`. Por tanto, `app.py` es el punto de entrada de la interfaz dentro de esa cadena; también podría arrancarse directamente, pero eso no corresponde al arranque Azure descrito en los documentos recibidos.

**Evidencia de Azure recibida del usuario:** una captura de App Service → Configuración de la pila muestra Python 3.12 y el campo Comando de inicio con `bash startup_lion.sh`. El comando coincide con `DESPLIEGUE_AZURE.md` y con el script de arranque recibido. Esta evidencia confirma esos dos valores de configuración en Azure, no que los archivos ejecutados allí sean idénticos a la carpeta recibida.

El runtime observado en Azure es Python 3.12; el entorno técnico de CO-VISION usa CPython 3.14.10. La compatibilidad de las fuentes LION/PROOF con 3.14.10, y la compatibilidad de la versión desplegada de LION con la copia recibida, siguen sin comprobarse.

**Evidencia de despliegue recibida del usuario:** la captura de Azure Deployment Center indica que el despliegue fue enviado desde `ms-azuretools-vscode`, muestra “Created via a push deployment”, la ruta `/tmp/zipdeploy/extracted`, una compilación Oryx y CI/CD no configurado. El portal muestra identificadores con apariencia de hash, incluida una línea “Preparing deployment for commit id”; se registran como texto mostrado por el portal, no como un commit Git verificado. No se aportó una referencia Git autenticada ni un paquete cuyo contenido pueda compararse.

**Capacidad de comparación comprobada en esta sesión:** no está disponible Azure CLI ni el módulo `Az.Websites` de PowerShell. Por ello no hay herramienta Azure con la que consultar o descargar, en modo lectura, los archivos activos de App Service. Tampoco se ha verificado autorización de lectura para el contenido desplegado; la captura del historial de despliegue no concede ni demuestra ese permiso. No se accedió a Azure ni se intentó modificar, reiniciar o redesplegar LION.

Para una comparación de contenido segura se propone calcular SHA-256 localmente sobre una lista cerrada de fuentes y, usando un canal de lectura autorizado, obtener los mismos archivos de la raíz desplegada de App Service y calcular allí sus hashes. Comparar al menos `startup_lion.sh`, `azure_entry.py`, `app.py`, `logic/lion_v03.py`, `lion_sap_engine.py`, `lion_v05_ui.py` y `lion_cloud_store.py`. No descargar el árbol completo ni incluir `.env`, configuración con valores secretos, archivos XLSX, datos, históricos o bases. Comparar hashes no requiere ejecutar la aplicación. La comparación queda pendiente hasta disponer de acceso de lectura aprobado a esos archivos desplegados o de hashes suministrados desde una fuente de despliegue autenticada.

**Recorrido de imports desde la cadena propuesta:**

- `app.py` importa `logic/lion_v03.py`, `lion_v05_ui.py` y `lion_busqueda_ui.py`; carga además `lion_cloud_store` dinámicamente para obtener la BASE.
- `logic/lion_v03.py` delega `load_model` en `lion_sap_engine.py` y delega `search` en `services/search.py`.
- `lion_busqueda_ui.py` vuelve a usar `logic/lion_v03.py` y `lion_v05_ui.py`.
- `azure_entry.py` importa `lion_cloud_auth.py` y `lion_cloud_store.py`; durante una publicación importa también `logic/lion_v03.py`.
- El recorrido de carga del modelo llega así a `lion_sap_engine.py`, que contiene clasificación y cálculo de urgencia. La interfaz no importa PROOF.

El paquete incluye `DESPLIEGUE_AZURE.md`, `startup_lion.sh` y `.streamlit/config.toml`. También incluye `azure_entry.py.antes_diagnostico`, una copia alternativa que no es el destino del script recibido. La captura del App Service confirma el runtime y Startup Command configurados; la captura de Deployment Center identifica el tipo de despliegue y muestra un identificador con formato de hash, pero no aporta un commit Git verificado ni el contenido desplegado. Por ello no acredita que el código en Azure coincida con esta copia.

**Variantes no presentes en el recorrido directo anterior:** `lion_ocho_etapas.py`, `lion_urgencias.py` y los módulos alternativos bajo `logic/` (`status_logic.py`, `data_loader.py`, `view_logic.py`) no aparecen en los imports estáticos trazados desde `app.py`. También hay instaladores/parches que reescriben archivos, no son módulos de ejecución de la aplicación. Esto solo indica que no entran en el recorrido importado observado; no demuestra que sean obsoletos o que nunca se arranquen por separado.

**Correspondencia de pruebas encontrada:**

- `test_sap_cuartiles.py` importa `lion_sap_engine` y prueba sus predicados de diez etapas, fechas/semanas/urgencia, reparto de colores, carga completa, identidad/detalles, validación y ciertos casos de errores. También prueba `instalar_sap_cuartiles.py` contra una instalación temporal sintética. No es una prueba integral de la interfaz `app.py`.
- `tests/test_cloud.py` importa `lion_cloud_store`, `lion_cloud_auth` y un instalador; cubre validación/publicación, autenticación y comportamiento del instalador. No prueba el arranque real en Azure.
- Los ficheros contienen datos de prueba sintéticos; las pruebas no se ejecutaron en esta revisión.

### PROOF

**Punto de entrada identificado en el lanzador que el usuario dice utilizar:** `INICIAR.bat`. El archivo recibido con ese nombre cambia a su propia carpeta. Si ya existe `.venv`, ejecuta `.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false`; si no existe, intenta crear el entorno e instalar `requirements.txt` antes de lanzar el mismo `app.py`. No se ejecutó ninguna de esas ramas.

**Recorrido de imports observado:**

- `app.py` importa `proof.py`, `dashboard.py` y `load_management.py`.
- `proof.py` importa `classification_engine.py`; `load_management.py` también consume funciones de `proof.py`.
- `dashboard.py` importa `completion_metrics.py`.
- En `proof.py`, `Engine` ingiere observaciones, guarda/reconstruye los eventos y expone proyecciones como observaciones, eventos, instancias y matriz.

**Variantes no presentes en el recorrido directo anterior:** `app_antes_objetivos_20261023_011807_622168.py` es un archivo alternativo fechado y no es importado por `app.py`; los scripts `patch_*`, `migrar_*`, `instalar_*` y BAT de actualización son herramientas de modificación, no imports de la entrada actual. `flow_model.py` no se importa directamente desde `app.py`; los tests y componentes de dashboard/filtros que lo usan constituyen otro recorrido que debe considerarse si se selecciona esa funcionalidad. La presencia de una variante no prueba que esté retirada o que no sea el archivo que el usuario inicia manualmente.

**Correspondencia de pruebas encontrada:**

- `test_queries.py` importa `classification_engine.classify_snapshot`; su prueba determinista corresponde a ese clasificador.
- `test_dashboard.py` importa `dashboard.timing_band`; comprueba umbrales de ese helper.
- `test_completion_metrics.py` importa `completion_metrics.calculate_completion_metrics`.
- `test_flow.py` importa `flow_model.project`, `aggregate` y `bucket`, además de helpers de filtros e instalador. Sus casos de proyección construyen eventos e instancias sintéticos directamente; no los obtiene de un `Engine` real.
- `test_load_management.py` comprueba sintácticamente parches y marcadores de gestión, no ejecuta el flujo completo de ingestión.
- `test_ui.py` usa Streamlit `AppTest` con `dashboard_filters_flow`, no con la ruta de `app.py` identificada arriba.
- `test_proof.py` declara pruebas para la API de ingestión/reconstrucción, pero presenta una discrepancia de API con el `proof.py` recibido, detallada a continuación. Ninguna de estas pruebas se ejecutó.

## Discrepancia entre `proof.py` y `test_proof.py`

### Diferencias de API identificadas

| `test_proof.py` espera | `proof.py` recibido expone |
| --- | --- |
| `from proof import ... read_source ...` | La función disponible para leer pertenencias es `read_memberships(raw, cfg)`; `read_source` no aparece. |
| `Engine.preview(raw, name, fecha, allow_identical=...)` que devuelve candidatos/advertencias | No existe `preview`; existen `add_observation(raw, name, observed_date)` y `add_batch(items)`. |
| `Engine.commit(preview, instancias_a_cerrar, fail_after_events=...)` | No existe `commit`. `add_batch` procesa e incorpora en una transacción; la API de cierre esperada por el test no coincide con ella. |
| `Engine.latest()` | No existe `latest`; se exponen `observations()`, `events()`, `instances()`, `matrix()` y `current_version()`. |
| `Engine.progress()` | No existe `progress`; `dashboard.py` importa `calculate_completion_metrics` desde otro módulo. |
| Configuración de prueba con `stages` | El motor actual lee `cfg['sources']` y `cfg['calendar']`; `app.py` presenta y guarda `sources`. |
| Preview con `candidates`, errores de preview, `ProofError` y simulación de fallo al confirmar | El motor actual no expone ese objeto preview/confirmación ni esos argumentos/resultados. |

La discrepancia afecta tanto a imports como a constructores, nombres, argumentos y formas de resultado. En consecuencia, no se puede tratar `test_proof.py` como evidencia de que el contrato actual de `Engine` está probado. La suite no fue ejecutada; la incompatibilidad es estática y sería necesario confirmar la generación/fuente asociada a esa prueba antes de decidir si es una prueba histórica o si falta una implementación.

### Comportamiento que queda sin comprobar

`test_proof.py` expresa expectativas sobre apertura/cierre, reapertura, múltiples etapas, observaciones repetidas/incompletas, idempotencia, transacciones/rollback, simulación histórica, consumo de objetivos, calendario, identidad, exportación, backup, previews obsoletos y aislamiento de bases. Dada la API incompatible, esas expectativas no comprueban el comportamiento del `proof.py` recibido.

El código actual sí define otras rutas (`add_observation`, `add_batch`, `rebuild`, `preview_rebuild`, `apply_rules`, `_derive`, `instances` y `matrix`), pero esta revisión no ejecutó pruebas que validen su correspondencia, sus límites o la persistencia frente a bases reales.

### Relación con `flow_model.py`

La discrepancia no rompe una dependencia directa: `flow_model.py` es un módulo separado que recibe eventos, instancias, fechas y reglas como argumentos. `test_flow.py` lo importa directamente y sí contiene casos para `project`, `aggregate` y `bucket`.

Sin embargo, esos casos fabrican sus eventos e instancias, por lo que no comprueban que la salida del `Engine` actual tenga la misma forma o semántica que espera `flow_model.py`. La discrepancia de `test_proof.py` tampoco valida el motor que produce esos datos. Una extracción/migración de `flow_model.py` requeriría conservar esas pruebas y añadir una comprobación de integración basada en la API y las estructuras actuales, después de confirmar qué revisión se usa. No se cambió ni adaptó ninguna prueba.

## Identificado en el código frente a confirmado por el usuario

| Tema | Identificado en el código recibido | Confirmado por el usuario |
| --- | --- | --- |
| LION | La cadena documentada en la copia es `bash startup_lion.sh` → Streamlit sobre `azure_entry.py` → `app.py`. | El usuario confirma que utiliza LION desde el navegador en Azure. Las capturas muestran Python 3.12, `bash startup_lion.sh`, un push desde `ms-azuretools-vscode`, “Created via a push deployment”, `/tmp/zipdeploy/extracted`, compilación Oryx y CI/CD no configurado. Los identificadores del portal no se verificaron contra Git; la identidad del código desplegado respecto a esta copia sigue pendiente. |
| PROOF | El archivo recibido `INICIAR.bat` ejecuta Streamlit sobre `app.py`. | El usuario confirma que abre localmente un archivo/acceso llamado `INICIAR`. No se ejecutó ni se comparó con una copia local diferente de las fuentes recibidas. |
| Pruebas | Se identificaron imports y objetivos aparentes de las pruebas indicadas. | No se han ejecutado en esta revisión; no son una aceptación funcional del usuario. |

## Confirmación pendiente

El historial indica un push desde VS Code, pero no identifica un commit Git comprobado ni el contenido del paquete desplegado. La sesión actual no tiene Azure CLI ni el módulo `Az.Websites` de PowerShell, y no se verificó permiso para leer los archivos activos. La coincidencia de la copia recibida con Azure sigue pendiente.

Sobre la copia recibida se puede avanzar con revisión estática, preparar caracterización y pruebas con datos deterministas autorizados, y documentar límites de integración, etiquetando los resultados como pertenecientes a esa copia. No se debe migrar `flow_model.py` todavía ni presentar la copia como réplica confirmada de producción. La compatibilidad de LION con Python 3.14.10 tampoco queda demostrada por la configuración Azure de Python 3.12.

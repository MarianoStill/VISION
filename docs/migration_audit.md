# Auditoría de migración: LION y PROOF

## Alcance y método

Inspección estática, sin ejecutar las aplicaciones, sus pruebas, scripts de instalación o dependencias. No se modificó ningún archivo de `../CO-VISION-inputs/LION` ni de `../CO-VISION-inputs/PROOF`, y no se copiaron implementaciones ni datos al producto.

Se leyeron los puntos de entrada, módulos de clasificación e histórico, manifiestos de dependencias y documentación de ejecución seleccionados. No se abrieron `.env`, datos SAP, bases SQLite, cachés ni archivos con nombres/extensiones que sugieren credenciales o material sensible. En PROOF se identificaron 17 nombres/extensiones de archivo potencialmente sensibles; no se determinó si contienen secretos. Por tanto, esta inspección no certifica que los proyectos estén libres de credenciales. La configuración local de LION contiene una ruta de OneDrive específica de un usuario; no se reproduce aquí.

## Hechos comprobados en el código

### LION

- La entrada de interfaz local es `app.py` (Streamlit). Carga `logic/lion_v03.py`, cuyo `load_model` delega en `lion_sap_engine.py`. `azure_entry.py` es otra entrada: valida identidad y publicación y luego ejecuta `app.py`.
- `lion_sap_engine.py` contiene predicados de clasificación para diez etapas SAP y arma el estado actual de las filas. `logic/lion_v03.py` y `lion_v05_ui.py` representan diez etapas en la ruta actual observada. También existe `lion_ocho_etapas.py`, una presentación de ocho etapas, y otros archivos de versiones/instaladores; no deben tratarse como una sola versión coherente sin fijar qué revisión se desea migrar.
- En la ruta actual, `compute_urgency` calcula una fecha estimada desde la fecha de precio y semanas según el modelo, y obtiene la urgencia como días entre la fecha de referencia y la estimación. `assign_colors` reparte globalmente las urgencias positivas en cuatro grupos; trata valores negativos, cero, entregados y desconocidos por separado.
- Hay otras funciones de urgencia (`lion_urgencias.py`, `lion_v05_ui.py`) con umbrales fijos y un snapshot JSON. Su relación con la ruta activa no está acreditada por los imports de `app.py` revisados. Sus resultados no son equivalentes, por definición, al reparto por cuartiles.
- La publicación de BASE conserva versiones XLSX bajo `LION_STORAGE_DIR` y actualiza un puntero `actual.json`; existe un campo `previous`. Eso conserva archivos, pero el código revisado no reconstruye eventos históricos de etapa a partir de esas versiones.
- `lion_machine_accordion/vision_contract.py` declara un protocolo para comentarios y prioridad de VISION. La búsqueda estática solo encontró su definición/exportación en ese paquete, no una implementación conectada al flujo de `app.py`.
- `config.json` guarda `excel_path` con una ruta local de usuario. `app.py` muestra un campo de ruta, pero la ruta de carga usada después procede de `lion_cloud_store.get_base_path()`, que exige `LION_STORAGE_DIR`. Hay una diferencia entre configuración visible/local y almacenamiento efectivo.
- `lion_cloud_auth.py` requiere el contexto de Azure App Service y variables de tenant/admin. `LION_TEST_MODE` concede acceso de prueba y su comentario/documentación depende de restricciones externas de red; no debe heredarse como configuración de producción.

### PROOF

- `INICIAR.bat` crea/usa `.venv`, instala `requirements.txt` y ejecuta Streamlit con `app.py`. El fallback de intérprete apunta a una ruta Windows Store específica de un perfil y a Python 3.12.
- `app.py` crea/usa `datos/historico_real.sqlite` o `datos/operativo.sqlite` y carga `config.json`.
- `classification_engine.py` contiene predicados de clasificación directa para diez etapas y categorías residuales. `proof.py` usa esa clasificación si el XLSX contiene una hoja `Data` o `Base`; en la ruta alternativa lee pertenencias de hojas configuradas.
- `proof.py` almacena observaciones, contenido XLSX original (`raw`), registros, resúmenes y versiones de reglas en SQLite. `_derive` reconstruye eventos de apertura/cierre a partir de observaciones ordenadas; `_write_derived` reemplaza los eventos derivados. `rebuild` y `apply_rules` actualizan la proyección histórica. La interfaz escribe también los cambios de configuración en `config.json`.
- `flow_model.py` calcula proyecciones de cohortes y flujo de lectura sobre eventos/instancias ya construidos; no consulta SAP ni escribe la base en las funciones revisadas.
- La carpeta recibida es una copia completa y contiene un `.venv` de aproximadamente 366 MB, datos/cachés de aproximadamente 355 MB, una carpeta de históricos SAP de aproximadamente 34 MB, copias anteriores, scripts auxiliares y ejemplos sintéticos. No se inspeccionó el contenido de esas bases, hojas ni cachés y no deben copiarse al repositorio.
- Hay una discrepancia estática entre `proof.py` y `test_proof.py`: la prueba importa APIs como `read_source`, `Engine.preview`, `commit`, `latest` y `progress`, mientras que el `proof.py` inspeccionado expone `read_memberships`, `add_observation`, `add_batch`, `observations`, `events`, `instances` y `matrix`. Además, `config_pruebas.json` tiene una forma distinta de la configuración activa. No se ejecutó la suite para determinar qué archivos/versiones son los vigentes.

## Dependencias y Python

| Proyecto | Dependencias declaradas encontradas | Python declarado/documentado |
| --- | --- | --- |
| LION | `requirements.txt` y `requirements.lion-cloud.txt`: Streamlit `>=1.53,<2`, pandas `>=2.2,<3`, openpyxl `>=3.1.5,<4`, filelock `>=3.16,<4`, defusedxml `>=0.7.1,<1`; no son un lock con versiones exactas | `LEEME.txt` indica Python 3.12; el manifiesto no declara `requires-python` |
| PROOF | `requirements.txt`: Streamlit `==1.53.1`, openpyxl `==3.1.5`, tzdata `>=2024.1`; no se encontró lock fuente independiente de `.venv` | No se encontró una declaración de compatibilidad Python en el manifiesto; `INICIAR.bat` usa una ruta de fallback específica a Python 3.12 |

Leer los manifiestos no demuestra compatibilidad con Python 3.14. No se probaron instalaciones, importaciones ni aplicaciones de las fuentes recibidas. PROOF incluye un entorno virtual ajeno a CO-VISION; no se reutilizó.

## Relación y discrepancia de propiedad

- La ruta activa de LION inspeccionada no importa PROOF; la ruta activa de PROOF tampoco importa LION. Son aplicaciones y procesos de datos independientes.
- Ambos contienen reglas directas para diez estados/etapas sobre columnas SAP. PROOF añade categorías residuales y un modo alternativo basado en hojas de pertenencia. Hay diferencias de nombres, forma de agrupar registros/identidad y contexto de entrada; por tanto, la coincidencia parcial de predicates no prueba que sean reglas idénticas ni autoriza a escoger un propietario.
- Las identidades actuales tampoco son uniformes: PROOF registra eventos por documento de ventas; LION agrupa por pedido y serie cuando está presente y, si falta, usa una identidad de fila del XLSX. No se debe introducir una clave sustitutiva para ocultar esta diferencia.
- El contrato de VISION encontrado en LION es una declaración de tipos/protocolo, no evidencia de una integración operativa con PROOF ni de almacenamiento implementado.
- La propiedad empresarial de clasificación debe resolverse con los responsables y las reglas aprobadas. Esta auditoría no cambia el propietario.

## Riesgos de migración observados

- Las carpetas de entrada contienen artefactos de desarrollo, históricos, cachés y datos junto al código. No copiar el árbol completo a Git: preparar una selección de fuente revisada y excluir datos, `.venv`, bytecode, copias fechadas y artefactos de instalación.
- Los nombres de 17 archivos/extensiones en PROOF merecen revisión de custodia antes de cualquier transferencia adicional; su contenido no fue abierto ni se sabe si son credenciales.
- Hay rutas locales de usuario, una ruta fija de intérprete y dependencias Azure/almacenamiento en LION. Sustituirlas por configuración externa solo cuando se defina el entorno; no trasladar valores locales ni secretos.
- Hay variantes históricas de módulos y pruebas aparentemente de otra generación. Antes de migrar, identificar la revisión de producción/uso aprobada y relacionarla con sus pruebas y configuración.
- Las instrucciones existentes piden ejecutar instaladores y scripts que modifican archivos o bases. No ejecutar esos pasos como parte de la migración sin revisar sus efectos y respaldos.

## Propuesta de primera migración pequeña — no ejecutada

Empezar por el módulo **PROOF**, con una extracción exacta y de solo lectura de `flow_model.py` al paquete CO-VISION, dejando intactos el motor de clasificación, la ingestión, las bases, las reglas de LION y todos los archivos originales. Este código consume eventos/instancias ya construidos y es una unidad acotada que tiene pruebas de caracterización visibles en `test_flow.py`; su colocación en PROOF mantiene el foco en proyección histórica sin decidir quién es dueño de la clasificación SAP.

Antes de moverlo, seleccionar de la generación vigente solo las pruebas aplicables, aislar sus dependencias y crear casos deterministas autorizados. Validar equivalencia comparando todas las salidas de `project`, `aggregate` y `bucket` entre la implementación origen y la extraída, incluyendo cohortes iniciales, reaperturas, cierres terminales y periodos sin observaciones. No usar datos SAP reales para la prueba; no afirmar equivalencia hasta ejecutar esa comparación. Si no se puede identificar la generación vigente o validar la semántica de las pruebas, detener esa migración.

## Pendiente de resolver antes de migrar

1. Confirmar qué revisiones de LION y PROOF son las vigentes y qué archivos de respaldo/instalador son históricos.
2. Obtener aprobación del propietario actual de las reglas de clasificación y resolver las diferencias entre los predicados/configuraciones de ambas aplicaciones.
3. Revisar las versiones autorizadas de dependencias, Python objetivo y mecanismos de ejecución en entornos limpios, después de aprobar y sanear la selección de fuente.
4. Aprobar los contratos y el tratamiento de identidad progresiva antes de conectar los módulos.
5. Confirmar custodia y retirar cualquier dato operativo, secreto o artefacto ajeno antes de importar código al repositorio.

Esta auditoría es estática. No valida que las aplicaciones funcionen, que las reglas sean correctas ni que las dependencias sean compatibles con Python 3.14.

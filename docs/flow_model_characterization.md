# Caracterización estática y aislada de `flow_model.py`

## Alcance y seguridad

Se examinó `flow_model.py`, sus imports directos y los casos de `test_flow.py` en la fuente recibida bajo `../CO-VISION-inputs/PROOF`. No se ejecutaron Streamlit, `app.py`, `proof.py`, instaladores, módulos de filtro, ni la suite original completa. No se abrieron bases de datos, hojas SAP u otros datos operativos.

`flow_model.py` importa únicamente `datetime`, `collections` y `statistics` de la biblioteca estándar. A nivel de módulo define funciones; no abre archivos, conecta bases de datos, inicia servicios ni importa Streamlit/PROOF. Sus funciones reciben eventos, instancias, fechas y reglas como argumentos y realizan proyecciones en memoria. La ruta aislada de prueba importa ese archivo directamente por ruta configurable, evitando el `sys.path` de la copia y cualquier módulo auxiliar.

El cargador de la prueba desactiva temporalmente la escritura de bytecode durante esa importación; por diseño no solicita una base/cache ni carga otros módulos de PROOF. La primera ejecución, antes de añadir esa protección, generó `PROOF\__pycache__\flow_model.cpython-314.pyc`; se eliminó ese artefacto exacto. Los archivos fuente recibidos conservaron sus hashes.

`test_flow.py` completo no es seguro/adecuado como unidad de aislamiento: importa `instalar_flujo_filtros` y `dashboard_filters_flow`, además de SQLite y openpyxl. No se importó ese test. Se reutilizaron literalmente en intención y expectativas sus cinco casos que ejercitan solo `project`, `aggregate` y `bucket`; los helpers y sus entradas se recrearon como **fixtures sintéticos de prueba**, no aprobados como datos, reglas o criterios empresariales. Los otros dos tests de `test_flow.py` cubren instaladores/filtros y quedan fuera de esta prueba de caracterización.

## Archivos examinados y hashes SHA-256

Hashes calculados sobre los archivos recibidos, sin modificar:

| Archivo | SHA-256 |
| --- | --- |
| `PROOF\flow_model.py` | `051C20587A95D8E79A616AE19A6ADA2FE426B32F0BF83EE999A6CDCE418CA9C9` |
| `PROOF\test_flow.py` | `BD86EB8519A33203667013E14290C3C1B138F627A00144E54E9E073BFB560AF6` |

## Referencia configurable y aislamiento

La prueba añadida es `tests\regression\test_flow_model_characterization.py`. Obtiene la carpeta recibida mediante `CO_VISION_PROOF_SOURCE_DIR`; no contiene una ruta personal fija. Si la variable no está configurada, pytest marca esos casos como omitidos. La prueba carga únicamente el `flow_model.py` de esa carpeta. No copia la implementación al repositorio.

Dependencias directas del módulo bajo prueba: solo biblioteca estándar. Dependencia del runner: pytest 9.1.1, ya instalada en `.venv`; no se instaló ni modificó dependencia alguna. El intérprete utilizado fue el Python del `.venv` de CO-VISION, CPython 3.14.10 x64. Esto caracteriza el comportamiento en ese intérprete, no demuestra compatibilidad de producción con Python 3.12 ni corrige/atribuye fallos a ninguna versión.

## Casos ejecutados y resultados

| Caso reutilizado de `test_flow.py` | Resultado observado |
| --- | --- |
| Etapa avanzada presente en la línea base: cohorte entra en la próxima apertura | Pasó |
| Etapa 1 en la línea base: inicio parcial, sin entrada nueva; agrega una salida sin duración completa | Pasó |
| Etapa avanzada sin nueva apertura: excluida y sin fecha de entrada de cohorte | Pasó |
| Reapertura: cuenta movimientos separados de documentos únicos y pendiente al cierre | Pasó |
| Etapa terminal: no mantiene pendientes ni genera días sin observación; bucket semanal | Pasó |

Resultado real del comando dirigido, tras activar la protección contra bytecode: `5 passed in 0.11s`, sin cambios a las expectativas. La prueba parametrizada depende de `CO_VISION_PROOF_SOURCE_DIR`; no crea una copia ni instala nada.

También se ejecutó `scripts\check.py` con la variable de ruta no configurada: `7 passed, 5 skipped`; los cinco skips corresponden a los casos externos configurables. Se cargaron los entry points técnicos del scaffold. Este resultado no es validación empresarial.

## Comportamiento observado, posibles errores y criterios pendientes

- **Observado:** el código recibido se comporta como expresan esos cinco casos concretos con los fixtures sintéticos usados. Esto no afirma que sus semánticas sean correctas para el negocio.
- **Posibles errores:** aún no evaluados como defectos. Un fallo puede revelar discrepancia con el test de caracterización, incompatibilidad en el entorno o un caso defectuoso; requiere investigar y no se considerará automáticamente error empresarial.
- **Pendiente de confirmar:** interpretación de cohortes parciales, “entrada” frente a movimientos/documentos únicos, conteo de pendientes terminales, calendario/granularidad y tratamiento de observaciones faltantes. Los tests reflejan expectativas técnicas existentes, no aprobación de esas reglas.

## Límites y valoración de migración

Esta prueba no integra `flow_model.py` con la API actual de `proof.py`, no verifica la procedencia de los eventos/instancias, no usa datos reales y no prueba la interfaz ni la suite completa. La discrepancia entre `proof.py` y `test_proof.py` permanece sin cambios.

La caracterización puede dar evidencia de comportamiento local de la proyección y es un paso previo útil, pero no basta por sí sola para aprobar una migración: falta confirmar los criterios empresariales y probar el contrato de entrada con la versión de `Engine` que se confirme como vigente. Por ahora no se migra el componente.

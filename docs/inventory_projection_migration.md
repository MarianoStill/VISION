# Migración acotada: proyección de inventario PROOF

## Decisión de alcance

Se preserva primero el comportamiento que utiliza actualmente la copia recibida de PROOF: `inventory_chart.chart_rows`. `flow_model.py` no se activa ni migra en esta fase; sus pruebas de caracterización se conservan. Sus cohortes y métricas quedan como mejora futura pendiente de definición empresarial.

## Procedencia y llamadas

Fuente examinada: `../CO-VISION-inputs/PROOF/inventory_chart.py`, SHA-256:

`74FC04B32D95C31411C4F2E5A495315655F0C98EFAC5C3109FCD74724724BA8F`

La cadena recibida es `app.py` → `dashboard.render_dashboard` → `dashboard_filters_flow.render_dashboard` → `render_flow` → `inventory_chart.render_inventory`. En la vista de evolución, `render_inventory` obtiene las fechas de `engine.db`, obtiene las instancias por `engine.instances()` y llama `chart_rows(instances, dates, cfg['sources'], grain, start, end)`. Esta migración no ejecuta esa cadena ni toca SQLite/Streamlit.

El componente mínimo aislable son `period_key` y `chart_rows`. Dependen únicamente de `datetime.date`, `datetime.timedelta` y `collections.defaultdict`; no dependen de Streamlit, Altair, Engine, archivos ni almacenamiento. `render_inventory`, `PALETTE` y el resto del render quedan fuera.

## Implementación incorporada

El componente se encuentra en `modules/proof/src/proof/inventory_projection.py`, con las mismas funciones y comportamiento observables de la fuente. No añade métricas, no corrige supuestos errores y no altera los criterios de selección. No está conectado a VISION ni a la interfaz empresarial; es una extracción importable para caracterización futura.

El servicio interno público es `proof.project_inventory(instances, dates, rules, grain, start, end)`. Reenvía los argumentos a `inventory_projection.chart_rows` y devuelve el mismo par `(rows, stages)`; no contiene una copia del cálculo.

### Contrato técnico observado (no definitivo)

- `instances`: secuencia de mappings con los campos consultados por la proyección, como `machine`, `stage`, `opening_date` y opcionalmente `closure_date`.
- `dates`: secuencia de fechas ISO `YYYY-MM-DD`; se filtran inclusivamente por `start` y `end`, se deduplican y ordenan.
- `rules`: secuencia de mappings con `id`, `name`, `kind` y opcionalmente `terminal`.
- `grain`: `"Día"`, `"Semana"` o `"Mes"`; cualquier otro valor conserva el fallback actual al agrupamiento diario.
- `start`, `end`: límites de fecha ISO comparados como cadenas.
- Retorno: `(rows, stages)`. Cada fila contiene `Periodo`, `Etapa`, `Expedientes pendientes` y `Fecha observada`. `stages` contiene los mappings de regla que sobreviven al filtro actual, ordenados por ID numérico.
- Sin fechas devuelve cero filas y las etapas filtradas; con todos los argumentos vacíos devuelve `([], [])`.

Esto describe el uso observado de la proyección, no define contratos definitivos de máquina, SAP, identidad ni reglas empresariales.

Ejemplo técnico con **datos sintéticos únicamente**:

```python
from proof import project_inventory

synthetic_instances = [
    {"machine": "SYNTH-1", "stage": "1", "opening_date": "2026-01-02"}
]
synthetic_dates = ["2026-01-02"]
synthetic_rules = [
    {"id": "1", "name": "Etapa sintética", "kind": "standard", "terminal": False}
]

rows, stages = project_inventory(
    synthetic_instances,
    synthetic_dates,
    synthetic_rules,
    "Día",
    "2026-01-01",
    "2026-01-31",
)
```

## Fixtures sintéticos y comportamiento caracterizado

`tests/proof/test_inventory_projection.py` usa únicamente fixtures sintéticos en memoria, expresamente no aprobados como datos SAP ni reglas de negocio. Cubren:

- períodos por día, semana, mes y granularidad no reconocida (fallback actual a día);
- inclusión exclusiva de reglas estándar no terminales con IDs del 1 al 9 y orden numérico;
- fechas únicas y ordenadas, recorte inclusivo del rango, y una fila por etapa y período observado;
- conteo por documento único en la última observación del período, incluyendo reglas actuales de cierre (`closure_date > fecha observada`) y la omisión de documentos cerrados;
- etapa sin pendientes, filtros por tipo/terminal y etapa 10.

No se interpretan esos fixtures como aceptación empresarial.

## Comparación original/migrado

Las pruebas esenciales del servicio no dependen de `CO-VISION-inputs`. Las comparaciones contra `inventory_chart.py` original y la caracterización de `flow_model.py` viven separadas bajo `tests/regression`. Las comparaciones importan módulos originales revisados estáticamente sin iniciar Streamlit, leer/escribir archivos o conectar almacenamiento. Comparan salidas sobre los mismos fixtures sintéticos; no instalan ni copian código original al producto.

Los tests opcionales no contienen una ruta personal fija: si `CO_VISION_PROOF_SOURCE_DIR` no se configura, pytest los omite con motivo explícito. Las pruebas propias del producto siguen ejecutándose sin fuentes externas.

## Entorno y resultados

- Intérprete: CPython 3.14.10 x64, `.venv` existente de CO-VISION.
- Runner: pytest 9.1.1, ya instalado.
- Dependencias nuevas: ninguna. El componente usa solo biblioteca estándar.
- Instalar o probar el Engine de PROOF: no necesario para aislar `chart_rows`; no se instaló `openpyxl` y no se importó el Engine.
- Pruebas esenciales `tests/proof` con `CO_VISION_PROOF_SOURCE_DIR` retirada: 10 aprobadas, 0 fallidas, 0 omitidas.
- Regresiones `tests/regression` con la carpeta recibida configurada: 10 aprobadas, 0 fallidas, 0 omitidas.
- Comprobación general sin fuentes externas: 16 aprobadas y 10 omitidas explícitamente (5 caracterizaciones de `flow_model.py` y 5 comparaciones con `inventory_chart.py`); 0 fallidas. PROOF, LION y VISION cargaron correctamente.
- Comprobación general con la fuente PROOF configurada: 26 aprobadas, 0 fallidas, 0 omitidas; PROOF, LION y VISION cargaron correctamente.
- La fuente recibida conserva el SHA-256 registrado arriba. No se modificó ni se copió al producto.

### Resultados por tipo de validación

| Tipo | Resultado |
| --- | --- |
| Caracterización y API pública con fixtures sintéticos, sin fuentes externas | 10 aprobadas, 0 fallidas, 0 omitidas |
| Regresión de `flow_model.py` y equivalencia original/migrado | 10 aprobadas con fuente configurada; 10 omitidas explícitamente sin ella |
| Comprobación técnica general | 26 aprobadas con fuente configurada; 16 aprobadas y 10 omitidas sin ella |
| Validación empresarial | No realizada |

## Distinciones y límites

- **Compatibilidad técnica:** el componente aislado se importa y ejecuta en CO-VISION con CPython 3.14.10; esto no demuestra compatibilidad completa del Engine PROOF ni del runtime Python 3.12 de Azure LION.
- **Equivalencia con la fuente recibida:** se comprueba salida idéntica para las entradas sintéticas y granularidades cubiertas; no implica equivalencia para todo dato/entrada posible.
- **Validación empresarial:** no realizada. No se aprueba el límite de IDs 1–9, el concepto de documento único, el instante de corte, el tratamiento de fechas ausentes ni el cierre estricto `>`; se conservan porque forman parte del código actual.
- No valida todo PROOF, la interfaz, bases existentes, datos SAP, coincidencia de LION con Azure ni una integración con VISION.

## Siguiente paso

El componente puede consumirse desde otro módulo mediante `from proof import project_inventory`. Queda pendiente decidir cuándo mostrarlo en una pantalla de desarrollo; no se añadió interfaz ni conexión VISION.

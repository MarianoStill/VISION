# Migración acotada: detección de estado entregado de LION

## Procedencia y aislamiento

La función recibida se encuentra en `../CO-VISION-inputs/LION/lion_sap_engine.py`, línea 157. SHA-256 del archivo examinado:

`705CB8DDC67EF9843721E2C8B7A2347898F1F7BBC5465D573D35983410B54DBE`

Su implementación exacta es:

```python
def is_delivered(status):
    return "Entregadas" in str(status).split(" | ")
```

La función solo depende de `str` y `list.__contains__`, integrados en Python. La inspección estática de nivel módulo encontró imports, constantes y definiciones de funciones; no llamadas ejecutables para iniciar Streamlit, leer almacenamiento o acceder a red. El módulo completo importa pandas y openpyxl, por lo que no se importa ni se ejecuta. La prueba de regresión analiza el archivo y compila únicamente el nodo AST de `is_delivered`, sin ejecutar `assign_colors` ni código de nivel módulo. La coincidencia de esta copia con Azure continúa pendiente y no forma parte de esta comprobación.

## API incorporada

- Implementación aislada: `lion.delivery.is_delivered(status)`.
- Servicio público: `lion.is_delivered(status)`, que delega en la implementación interna.
- Adaptador de VISION: `vision.lion_adapter.is_delivered(status)`, que delega únicamente en el servicio público de LION.

No se añadió normalización. El comportamiento observado distingue mayúsculas y espacios: solo un segmento idéntico a `"Entregadas"` después de dividir por el delimitador exacto `" | "` devuelve `True`. El argumento se convierte con `str`, por lo que, por ejemplo, `None` devuelve `False`. Estas son observaciones del código, no una definición empresarial aprobada.

## Pruebas

Los casos de producto son valores de estado sintéticos y están en `tests/lion/test_delivery.py`; verifican la función y delegación del servicio. `tests/vision/test_lion_adapter.py` verifica que el adaptador pasa el argumento y devuelve intacto el resultado del servicio. No requieren `CO-VISION-inputs`.

La comparación opcional está en `tests/regression/test_lion_delivery_source_equivalence.py` y usa `CO_VISION_LION_SOURCE_DIR`. Ejecuta solo la definición AST aislada del archivo recibido y compara la función pública con exactamente las mismas entradas sintéticas. Si la variable no está configurada, estas pruebas se omiten con un motivo explícito.

Resultados con CPython 3.14.10 y pytest 9.1.1:

| Modo | Aprobadas | Fallidas | Omitidas |
| --- | ---: | ---: | ---: |
| Producto autocontenido y comprobación general, sin rutas externas | 29 | 0 | 19 |
| Comprobación general con `CO_VISION_PROOF_SOURCE_DIR` y `CO_VISION_LION_SOURCE_DIR` configuradas | 48 | 0 | 0 |

Las 19 omisiones del modo autocontenido son cinco caracterizaciones de `flow_model.py`, cinco comparaciones PROOF y nueve comparaciones LION; todas requieren las copias externas. Las pruebas focalizadas del incremento LION, sin fuentes externas, dieron 11 aprobadas y 9 comparaciones omitidas. Con la copia LION configurada, las nueve comparaciones original/migrado pasaron. `scripts/check.py` ejecutó además los puntos de entrada técnicos de PROOF, LION y la carga integrada de VISION en ambos modos.

## Alcance y límites

Este incremento migra solo el predicado de estado usado por `assign_colors`; no migra ni ejecuta `assign_colors`, el cálculo de urgencia, la carga SAP, Streamlit, Azure ni almacenamiento. La equivalencia cubre las entradas sintéticas enumeradas, no todas las entradas posibles. No constituye validación empresarial, compatibilidad de la aplicación completa con Python 3.14, ni evidencia de que la copia coincida con producción.

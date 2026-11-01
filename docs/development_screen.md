# Pantalla de desarrollo de VISION

`apps/vision/src/vision/development_app.py` ofrece navegación en español con el
perfil **Comercial** y las vistas Inicio, Mis clientes e Informes:

- **Mis clientes** es la vista inicial y mantiene ocultos los controles técnicos.
  Antes de mostrar la cartera, el comercial se selecciona entre los valores
  presentes en `Sales Representive Name`; LION aplica el filtro de ámbito. La
  selección de cliente se deriva de los resultados filtrados y también se aplica
  mediante el servicio público de LION. El buscador global delega en su búsqueda.
- La situación actual y los conteos de máquinas por etapa proceden de
  `vision.lion_adapter`. PROOF se muestra por separado desde la última
  observación disponible; sus conteos se identifican como expedientes por
  Documento de ventas y no como máquinas físicas. El histórico de la ficha solo
  se vincula cuando el pedido es único en el modelo LION completo.
- La ficha presenta primero el estado y la urgencia LION; los identificadores,
  seguimiento, histórico PROOF, prioridad comercial y comentarios aparecen bajo
  demanda. La prioridad comercial y la persistencia de comentarios están
  pendientes; no se deriva prioridad de la urgencia operacional.
- **Administración / Datos** separa del flujo comercial la selección DEMO/DEV,
  estado de las fuentes y herramientas técnicas. En cada arranque/rerun, VISION
  descubre el snapshot SAP diario más reciente y lo procesa por el servicio
  público de LION; el resultado se almacena en caché por ruta, tamaño, fecha de
  modificación y fecha de referencia. La urgencia LION usa la fecha actual del
  sistema.
- El snapshot seleccionado también se registra en la base externa de PROOF
  mediante su servicio público de ingesta. La búsqueda por huella del servicio
  evita repetir una observación ya almacenada; una colisión de fecha con distinto
  contenido se informa como error, sin sobrescribir ni borrar observaciones.
  PROOF no rellena días históricos ausentes.
- La carga manual y la vista DEMO permanecen como herramientas administrativas;
  no son necesarias para el flujo Comercial normal. DEMO usa datos sintéticos
  claramente etiquetados y no representa evidencia, historia ni resultados
  operacionales.

La historia PROOF no se inventa a partir de una observación; si no hay una
referencia disponible, el usuario ve un estado no disponible.

Los perfiles y permisos organizativos no están definidos y no hay autenticación.
Esta pantalla es un prototipo técnico para revisión, no una aplicación de
producción.

## Inicio local

Desde la raíz del repositorio:

### Windows (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m streamlit run apps\vision\src\vision\development_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
```

### Linux y GitHub cloud

```bash
.venv/bin/python -m streamlit run apps/vision/src/vision/development_app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
```

Abre `http://127.0.0.1:8503` en el mismo entorno local y detén Streamlit con
`Ctrl+C`. No cambies la dirección a `0.0.0.0` ni expongas el puerto.

## Fuentes externas

Por defecto, VISION busca los archivos fuera del repositorio en
`%USERPROFILE%\CO-VISION-data\` (Windows) o `~/CO-VISION-data/` (Linux):

- `sap/daily/`: snapshots SAP diarios `.xlsx`. No se requiere un nombre fijo.
- `proof/proof.db`: base SQLite existente y escribible que recibe nuevas
  observaciones mediante el servicio público de PROOF.

Se ignoran archivos que no sean XLSX, archivos temporales de Excel (`~$...`) y
libros ilegibles o sin hoja `Data`/`Base`. Los nombres con fecha
`YYYY-MM-DD`, `YYYYMMDD` o `DD-MM-YYYY` determinan la fecha de observación y,
cuando todos los candidatos tienen una fecha reconocible, el orden más reciente.
Si algún nombre no tiene una fecha válida, el orden de selección usa la fecha de
modificación del archivo; para un nombre sin fecha válida, esa misma fecha local
de modificación se registra como observación. Si dos candidatos más recientes
empatan en los metadatos de orden, la fuente se considera ambigua y no se elige
ninguna automáticamente.

Se puede configurar otra ubicación sin editar código:

- `CO_VISION_DATA_ROOT`: directorio externo raíz de los datos.
- `CO_VISION_PROOF_DB`: ruta explícita a la base PROOF escribible; prevalece
  sobre `proof/proof.db` bajo la raíz.
- `CO_VISION_PROOF_REFERENCE_DB`: se conserva únicamente para las herramientas
  manuales heredadas de Administración / Datos; la ingesta diaria automática no
  escribe en una base etiquetada como referencia de solo lectura.

El XLSX debe incluir una hoja `Data` o `Base` y las columnas recibidas por LION:
`Documento de ventas`, `Número de serie`, `Denomin.posición`, `Material`,
`Nombre del solicitante`, `Solicitud de pedido`, `Documento compras`,
`La entrada de mercancías está abierta`, `PP DLV Status`, `Entrega`,
`Doc.facturación`, `Status de usuario`, `Internal Note Line`,
`Fecha de entrega` y `Fecha de precio`.

Los archivos se leen localmente y permanecen fuera de Git. No agregues al
repositorio hojas de cálculo, bases SQLite ni archivos `-wal` o `-shm`.

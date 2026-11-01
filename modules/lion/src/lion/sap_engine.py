"""Clasificación SAP directa y urgencia global por máquina. Sin acceso de red."""
from pathlib import Path
from datetime import datetime, date
from numbers import Real
from io import BytesIO
from zoneinfo import ZoneInfo
import hashlib
import math
import zipfile
import unicodedata
import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

VERSION = "sap-cuartiles-1"
ORDER = "Documento de ventas"
SERIAL = "Número de serie"
DESC = "Denomin.posición"
STEPS = ("Liberar pedido", "Compra máquina", "Compra accesorios", "En fabricación", "Fabricado", "Taller", "Planning", "Para entregar", "Arcese", "Entregadas")
REQUIRED = (ORDER, SERIAL, DESC, "Material", "Nombre del solicitante", "Solicitud de pedido", "Documento compras", "La entrada de mercancías está abierta", "PP DLV Status", "Entrega", "Doc.facturación", "Status de usuario", "Internal Note Line", "Fecha de entrega", "Fecha de precio")
WEEKS = (("RX", 9), ("FM-X", 13), ("MX-X", 20), ("EXH", 10), ("EXV", 9), ("RCE", 12), ("RCD", 12), ("ECH", 8))
COLORS = ("#F44336", "#FF9800", "#FFCA28", "#20B26B")
GREY = "#AAB4C3"
BLUE = "#2F80ED"
GREEN = "#20B26B"
OUTPUT = ["ID", "Pedido", "Máquina", "Número de serie", "Cliente", "Estado", "Material", "Documento de compras", "Fecha de entrega (Excel)", "Comercial", "Oficina de ventas", "Evidencia", "Aviso", "Relaciones ambiguas", "Filas de origen", "Fecha estimada de entrega", "Urgencia", "Color urgencia", "Fecha de referencia de urgencia"]


def norm(value):
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, Real) and not isinstance(value, bool) and float(value).is_integer():
        value = int(value)
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def blank(value):
    return value is None or pd.isna(value) or str(value).strip() == ""


def choose_sheet(book):
    # Solo se aceptan nombres explícitos o un único libro de una hoja.
    names = list(book.sheetnames)
    for preferred in ("Data", "Base"):
        hits = [s for s in names if norm(s) == norm(preferred)]
        if len(hits) == 1:
            return hits[0]
    if len(names) == 1:
        return names[0]
    raise ValueError("No se identifica la hoja SAP: utiliza Data o Base.")


def validate_upload(content):
    if not content or len(content) > 30 * 1024 * 1024:
        raise ValueError("El XLSX debe tener contenido y ocupar como máximo 30 MB.")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 10000 or sum(i.file_size for i in entries) > 300 * 1024 * 1024:
                raise ValueError("El libro supera el límite de tamaño descomprimido.")
            if any(i.flag_bits & 1 for i in entries):
                raise ValueError("No se admiten libros cifrados.")
            if any("vbaproject" in i.filename.casefold() for i in entries):
                raise ValueError("No se admiten macros.")
        book = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            name = choose_sheet(book)
            sheet = book[name]
            header = [str(v).strip() if v is not None else "" for v in next(sheet.values, ())]
            missing = [c for c in REQUIRED if c not in header]
            repeated = [c for c in REQUIRED if header.count(c) > 1]
            if missing:
                raise ValueError("Faltan columnas SAP: " + ", ".join(missing))
            if repeated:
                raise ValueError("Columnas esenciales duplicadas: " + ", ".join(repeated))
            if next(sheet.iter_rows(min_row=2, values_only=True), None) is None:
                raise ValueError("La hoja SAP no contiene registros.")
        finally:
            book.close()
    except (zipfile.BadZipFile, KeyError, StopIteration) as exc:
        raise ValueError("El archivo no es un XLSX válido.") from exc


def parse_date(value, epoch, field):
    if blank(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        result = pd.Timestamp(value)
    elif isinstance(value, Real) and not isinstance(value, bool):
        converted = from_excel(float(value), epoch=epoch)
        if not isinstance(converted, (datetime, date)):
            raise ValueError("Valor sin fecha válida en " + field)
        result = pd.Timestamp(converted)
    elif isinstance(value, str):
        result = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y"):
            try:
                result = pd.Timestamp(datetime.strptime(value.strip(), fmt))
                break
            except ValueError:
                pass
        if result is None:
            raise ValueError("Fecha no interpretable en " + field + ": " + value)
    else:
        raise ValueError("Formato de fecha no admitido en " + field)
    if result.tzinfo is not None:
        raise ValueError("No se admiten fechas SAP con zona horaria en " + field)
    return result.normalize()


def classify(frame):
    def empty(column):
        return frame[column].map(blank)
    material = frame["Material"].astype(str).str.strip().str.upper().str.startswith(("SM", "SP"))
    req, po = ~empty("Solicitud de pedido"), ~empty("Documento compras")
    delivery, invoice = ~empty("Entrega"), ~empty("Doc.facturación")
    serial, note = ~empty(SERIAL), ~empty("Internal Note Line")
    gr, pp, user = frame["La entrada de mercancías está abierta"], frame["PP DLV Status"], frame["Status de usuario"]
    pending = ~delivery & ~invoice
    return {
        "Liberar pedido": material & ~req & ~po & user.eq("ZCRE") & pending,
        "Compra máquina": material & req & ~po & user.eq("ZREL") & pending,
        "Compra accesorios": material & req & po & pending,
        "En fabricación": material & gr.eq("Y") & pp.eq("N") & pending & ~serial,
        "Fabricado": material & gr.eq("Y") & pp.eq("N") & pending & serial,
        "Taller": material & gr.eq("N") & pp.eq("N") & pending,
        # Se conserva la segunda rama original, sin añadir restricciones nuevas.
        "Planning": material & ((gr.eq("Y") & pp.eq("Y") & ~req & pending) | (gr.eq("N") & pp.eq("Y") & note)),
        "Para entregar": material & gr.eq("N") & pp.eq("Y") & ~req & pending & ~note,
        "Arcese": material & delivery & ~invoice,
        "Entregadas": material & delivery & invoice,
    }


def compute_urgency(frame, reference_date, epoch):
    reference = pd.Timestamp(reference_date).normalize()
    weeks = []
    estimates = []
    urgency = []
    for model, price_date in zip(frame[DESC], frame["Fecha de precio"]):
        text = str(model).upper()
        count = next((n for code, n in WEEKS if code in text), 11)
        start = parse_date(price_date, epoch, "Fecha de precio")
        estimate = (
            start + pd.Timedelta((count + 2) * 7, unit="D")
            if start is not None
            else None
        )
        weeks.append(count)
        estimates.append(estimate if estimate is not None else pd.NaT)
        urgency.append((reference - estimate).days if estimate is not None else None)
    frame = frame.copy()
    frame["Weeks"] = weeks
    frame["Por días"] = [(w + 2) * 7 for w in weeks]
    frame["Estimado"] = estimates
    frame["Hoy"] = reference
    frame["Urgencia"] = pd.Series(urgency, index=frame.index, dtype=object)
    return frame


def is_delivered(status):
    return "Entregadas" in str(status).split(" | ")


def assign_colors(model):
    if model["ID"].isna().any() or model["ID"].duplicated().any():
        raise ValueError("No se pueden repartir urgencias con identificadores duplicados.")
    result = model.copy()
    result["Color urgencia"] = GREY
    positives = []
    for index, row in result.iterrows():
        if is_delivered(row["Estado"]):
            result.at[index, "Color urgencia"] = GREEN
            continue
        value = row["Urgencia"]
        if blank(value):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        if number < 0:
            result.at[index, "Color urgencia"] = BLUE
        elif number == 0:
            result.at[index, "Color urgencia"] = GREEN
        else:
            positives.append((index, number, str(row["ID"])))
    positives.sort(key=lambda item: (-item[1], item[2]))
    # Los restos se asignan a los primeros grupos. Tamaños difieren como máximo en uno.
    size, remainder = divmod(len(positives), 4)
    offset = 0
    for group, color in enumerate(COLORS):
        count = size + (1 if group < remainder else 0)
        for index, _, _ in positives[offset:offset + count]:
            result.at[index, "Color urgencia"] = color
        offset += count
    return result


def load_model(path, source="Base", reference_date=None):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError("No se encuentra el archivo Excel: " + str(path))
    before = path.stat()
    # Una copia en memoria evita lecturas mezcladas si el fichero cambia en disco.
    content = path.read_bytes()
    if path.stat().st_size != before.st_size or len(content) != before.st_size:
        raise ValueError("El Excel cambió durante la lectura. Actualiza de nuevo.")
    validate_upload(content)
    with pd.ExcelFile(BytesIO(content), engine="openpyxl") as book:
        epoch = book.book.epoch
        source = choose_sheet(book.book)
        frame = pd.read_excel(book, sheet_name=source, dtype=object, keep_default_na=False)
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any():
        raise ValueError("Columnas ambiguas tras normalizar los encabezados.")
    for reserved in ("Fila Excel", "_id", "_active_stages"):
        if reserved in frame:
            raise ValueError("Columna reservada en el origen: " + reserved)
    frame.insert(0, "Fila Excel", range(2, len(frame) + 2))
    frame = frame.loc[frame["Material"].map(norm).str.startswith(("sm", "sp"))].copy()
    if frame.empty:
        raise ValueError("El archivo no contiene máquinas SM/SP.")
    # publish escribe el candidato y lo renombra: conserva mtime de esa carga.
    # No se usa el reloj en cada búsqueda ni el nombre del fichero SAP.
    reference = pd.Timestamp(reference_date).date() if reference_date is not None else datetime.fromtimestamp(before.st_mtime, ZoneInfo("Europe/Madrid")).date()
    frame = compute_urgency(frame, reference, epoch)
    masks = classify(frame)
    orders = frame[ORDER].map(norm)
    serials = frame[SERIAL].map(norm)
    frame["_id"] = ["serie:" + order + ":" + serial if serial else "fila:" + str(line)
                    for order, serial, line in zip(orders, serials, frame["Fila Excel"])]
    frame["_active_stages"] = [[stage for stage, active in zip(STEPS, flags) if bool(active)]
                               for flags in zip(*(masks[stage].tolist() for stage in STEPS))]
    rows, details, issues = [], {}, []
    for entity, group in frame.groupby("_id", sort=False):
        def join(field):
            if field not in group:
                return ""
            return " | ".join(dict.fromkeys(str(v).strip() for v in group[field] if norm(v)))
        found = {s for states in group["_active_stages"] for s in states}
        active = [s for s in STEPS if s in found]
        status = " | ".join(active) if active else "Paradero desconocido"
        notes = []
        if not active:
            notes.append("Sin coincidencia en categorías")
        if len(active) > 1:
            notes.append("Etapas simultáneas en proceso: " + ", ".join(active))
        if not norm(group.iloc[0][ORDER]):
            notes.append("Pedido sin informar; revisar identidad")
        values = list(dict.fromkeys(int(v) for v in group["Urgencia"] if not blank(v)))
        has_missing = any(blank(v) for v in group["Urgencia"])
        urgency = values[0] if len(values) == 1 and not has_missing else None
        if len(values) > 1 or has_missing:
            notes.append("Urgencia ausente o contradictoria en las filas de la máquina")
        if len({norm(v) for v in group["Material"]}) > 1 or len({norm(v) for v in group[DESC]}) > 1:
            notes.append("La identidad agrupa materiales o modelos distintos; revisar")
        dates = [parse_date(v, epoch, "Fecha de entrega") for v in group["Fecha de entrega"]]
        dates = [v for v in dates if v is not None]
        estimate = (max(dates) + pd.Timedelta(days=14)).strftime("%d/%m/%Y") if dates else ""
        evidence = [stage + " · fila " + str(line)
                    for line, stages in zip(group["Fila Excel"], group["_active_stages"]) for stage in stages]
        row = {"ID": entity, "Pedido": join(ORDER), "Máquina": join(DESC), "Número de serie": join(SERIAL), "Cliente": join("Nombre del solicitante"), "Estado": status, "Material": join("Material"), "Documento de compras": join("Documento compras"), "Fecha de entrega (Excel)": join("Fecha de entrega"), "Fecha estimada de entrega": estimate, "Comercial": join("Sales Representive Name"), "Oficina de ventas": join("Descripción de oficina de ventas"), "Evidencia": "; ".join(dict.fromkeys(evidence)), "Aviso": "; ".join(notes), "Relaciones ambiguas": "", "Filas de origen": join("Fila Excel"), "Urgencia": urgency, "Fecha de referencia de urgencia": reference.isoformat()}
        rows.append(row)
        details[entity] = group.drop(columns=["_id", "_active_stages"])
        if notes and (not active or len(values) > 1 or has_missing or any("revisar" in n.casefold() for n in notes)):
            issues.append({"Origen": "SAP · filas " + join("Fila Excel"), "Pedido": join(ORDER), "Motivo": "; ".join(notes)})
    model = pd.DataFrame(rows)
    model = assign_colors(model).reindex(columns=OUTPUT)
    model.attrs.update(lion_engine=VERSION, urgency_reference=reference.isoformat(), source_sha256=hashlib.sha256(content).hexdigest())
    return model, details, pd.DataFrame(issues, columns=["Origen", "Pedido", "Motivo"]), before.st_mtime, source


def process_workbook(content, reference_date, source="Base"):
    if reference_date is None:
        raise ValueError("Se requiere una fecha de observación explícita.")
    # El resultado es una cache derivada, no una fuente de reglas alternativa.
    # JSON tipado comprimido; no se deserializa pickle ni código de terceros.
    from .prepared_store import cache_identity, load_prepared, save_prepared
    identity = None
    try:
        identity = cache_identity(content, reference_date, source, __file__)
        prepared = load_prepared(identity)
        if prepared is not None:
            return prepared
    except (OSError, ValueError, TypeError):
        pass
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix="co-vision-lion-") as temporary_directory:
        path = Path(temporary_directory) / "upload.xlsx"
        path.write_bytes(content)
        result = load_model(path, source=source, reference_date=reference_date)
    if identity is not None:
        save_prepared(identity, result)
    return result

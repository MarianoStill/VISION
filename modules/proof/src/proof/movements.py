"""Movimientos observados PROOF: aperturas A y cierres C por fecha y etapa.

No cambia eventos, observaciones, reglas ni la base de datos.
La unidad es Documento de ventas, no máquina física.
"""
from datetime import date, timedelta


def _day(value):
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return None


def _derive_missing_events(history):
    """Reutilizar el motor PROOF sobre observaciones en memoria; no escribir SQLite."""
    import json
    from types import SimpleNamespace
    from .engine import Engine
    sources = history.get("sources", [])
    observations = history.get("observations", [])
    if not sources or not observations:
        return None
    known = {str(source.get("id")) for source in sources}
    rows = []
    for position, observation in enumerate(observations):
        if "memberships" not in observation or not _day(observation.get("observed_date")):
            return None
        records = observation["memberships"]
        if any(str(record.get("stage")) not in known or not record.get("machine") for record in records):
            return None
        rows.append(dict(id=str(position), observed_date=_day(observation["observed_date"]),
                         records_json=json.dumps(records)))
    # El servicio read_history ya ordena por fecha y secuencia. El orden estable
    # conserva observaciones del mismo día sin inventar una hora de transición.
    rows.sort(key=lambda row: row["observed_date"])
    proxy = SimpleNamespace(observations=lambda: rows)
    config = dict(sources=sources, calendar=history.get("calendar", {}))
    return Engine._derive(proxy, config)["events"]


def movement_index(history):
    """Indexar una vez los eventos existentes; sin recorrer el SAP ni consultar SQLite."""
    observations = history.get("observations", [])
    dates = sorted({d for d in (_day(o.get("observed_date")) for o in observations) if d})
    # Las fechas públicas se contrastan con observaciones, no se fabrican días sin archivo.
    if not dates:
        dates = sorted({d for d in (_day(v) for v in history.get("dates", [])) if d})
    first = dates[0] if dates else None
    previous = {day: dates[i-1] if i else None for i, day in enumerate(dates)}
    events = history.get("events", [])
    index = {}
    ignored = 0
    for event in events:
        day = _day(event.get("observed_date"))
        kind = str(event.get("type", "")).strip()
        stage = str(event.get("stage") or "").strip()
        document = str(event.get("machine") or "").strip()
        if day not in previous or kind not in ("A", "C") or not stage or not document:
            ignored += 1
            continue
        index.setdefault((day, stage, kind), set()).add(document)
    # Si hay pertenencias pero ningún evento, no asumir que la reconstrucción existe.
    covered_dates = {key[0] for key in index}
    from collections import Counter
    event_counts = Counter(_day(event.get("observed_date")) for event in events)
    for observation in observations:
        day = _day(observation.get("observed_date"))
        summary = observation.get("summary", {})
        if "Aperturas" in summary and "Cierres" in summary:
            expected = int(summary["Aperturas"]) + int(summary["Cierres"])
            actual = event_counts[day]
            if expected == actual:
                covered_dates.add(day)
            else:
                covered_dates.discard(day)
    rebuilt_dates = set()
    missing_dates = set(dates) - covered_dates
    if missing_dates:
        derived = _derive_missing_events(history)
        if derived is not None:
            for event in derived:
                day = _day(event.get("observed_date"))
                if day in missing_dates:
                    key = (day, str(event["stage"]), str(event["type"]))
                    index.setdefault(key, set()).add(str(event["machine"]))
            rebuilt_dates = missing_dates
            covered_dates.update(missing_dates)
    has_memberships = any(o.get("memberships") for o in observations)
    derived_available = bool(rebuilt_dates) or ("events" in history and (bool(events) or not has_memberships))
    return dict(dates=dates, first_date=first, previous=previous, events=index, covered_dates=covered_dates, rebuilt_dates=rebuilt_dates,
                derived_available=derived_available, ignored_events=ignored,
                sources=list(history.get("sources", [])))


def stage_movement_counts(history, stage_ids, observed_date, *, index=None):
    """Pedidos distintos con A/C observados ese día. Primera observación = inventario inicial."""
    day = _day(observed_date)
    stages = {str(value).strip() for value in stage_ids if str(value).strip()}
    prepared = movement_index(history) if index is None else index
    result = dict(date=day, unit="pedidos", entered=None, exited=None,
                  entered_documents=[], exited_documents=[], status="unavailable",
                  previous_observation=None, interval_days=None, first_observation=False,
                  terminal_stages=[], warnings=[])
    if not day or not stages:
        result["warnings"].append("Fecha o etapas no disponibles.")
        return result
    if day not in prepared["previous"]:
        result["status"] = "missing_observation"
        result["warnings"].append("No hay observación PROOF para esa fecha; no equivale a cero movimientos.")
        return result
    if not prepared["derived_available"] or (day not in prepared["covered_dates"] and history.get("observations")):
        result["status"] = "events_unavailable"
        result["warnings"].append("Hay observaciones sin eventos derivados disponibles; revisar la reconstrucción PROOF por separado.")
        return result
    if day in prepared.get("rebuilt_dates", set()):
        result["warnings"].append("A/C derivados en memoria por el motor PROOF a partir de observaciones guardadas; sin modificar la base.")
    previous = prepared["previous"][day]
    result["previous_observation"] = previous
    if previous is None:
        result["status"] = "initial_inventory"
        result["first_observation"] = True
        result["warnings"].append("Primera observación: las aperturas son inventario inicial, no entradas nuevas.")
        return result
    result["interval_days"] = (date.fromisoformat(day)-date.fromisoformat(previous)).days
    entries, exits = set(), set()
    for stage in stages:
        entries.update(prepared["events"].get((day, stage, "A"), set()))
        exits.update(prepared["events"].get((day, stage, "C"), set()))
    result.update(entered=len(entries), exited=len(exits), entered_documents=sorted(entries),
                  exited_documents=sorted(exits), status="observed")
    if result["interval_days"] != 1:
        result["warnings"].append("Los movimientos se observaron entre " + previous + " y " + day + "; no se conoce el día exacto del cambio.")
    result["terminal_stages"] = [str(s["id"]) for s in prepared["sources"]
                                 if str(s.get("id")) in stages and s.get("terminal")]
    if result["terminal_stages"]:
        result["warnings"].append("La etapa terminal genera A y C al registrarse: su cierre no significa que abandone Entregadas.")
    if prepared["ignored_events"]:
        result["warnings"].append(str(prepared["ignored_events"]) + " eventos con campos no válidos no se han contado.")
    return result


def daily_stage_movements(history, stage_ids, today, *, index=None):
    """Entradas observadas hoy y cierres observados ayer, sin filtrar por inventario actual."""
    day = _day(today)
    if day is None:
        raise ValueError("Fecha de referencia no válida.")
    prepared = movement_index(history) if index is None else index
    yesterday = (date.fromisoformat(day)-timedelta(days=1)).isoformat()
    return dict(unit="pedidos", today=stage_movement_counts(history, stage_ids, day, index=prepared),
                yesterday=stage_movement_counts(history, stage_ids, yesterday, index=prepared))

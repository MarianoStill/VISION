from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from io import BytesIO
import statistics

import openpyxl
from openpyxl.utils.datetime import from_excel

from .engine import workdays


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _as_date(value, epoch):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            converted = from_excel(value, epoch)
            return converted.date() if isinstance(converted, datetime) else converted
        except (TypeError, ValueError, OverflowError):
            return None
    text = str(value).strip().split(" ")[0]
    for date_format in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def _base_dates(raw):
    workbook = openpyxl.load_workbook(
        BytesIO(raw), data_only=True, read_only=True
    )
    try:
        sheet_name = next(
            (name for name in ("Data", "Base") if name in workbook.sheetnames),
            None,
        )
        if sheet_name is None:
            return {}
        rows = workbook[sheet_name].iter_rows(values_only=True)
        headers = [_text(value) for value in next(rows, ())]
        if "Documento de ventas" not in headers or "Fecha de precio" not in headers:
            return {}
        document_index = headers.index("Documento de ventas")
        price_date_index = headers.index("Fecha de precio")
        result = defaultdict(set)
        for row in rows:
            if max(document_index, price_date_index) >= len(row):
                continue
            document = _text(row[document_index])
            price_date = _as_date(row[price_date_index], workbook.epoch)
            if document and price_date:
                result[document].add(price_date)
        return result
    finally:
        workbook.close()


def calculate_completion_metrics(engine, config, documents=None):
    """Return completion counts and durations using the received PROOF conventions."""
    completion_dates = {}
    terminal_stages = {"9"}
    events = engine.events()
    if documents is not None:
        selected = {str(document) for document in documents}
        events = [
            event
            for event in events
            if str(event.get("machine")) in selected
        ]
    for event in events:
        if str(event.get("stage")) not in terminal_stages or event.get("type") != "C":
            continue
        document = _text(event.get("machine"))
        observed = event.get("observed_date") or event.get("closure_date")
        if document and observed:
            observed_date = date.fromisoformat(str(observed)[:10])
            completion_dates[document] = min(
                completion_dates.get(document, observed_date), observed_date
            )

    dates_by_document = defaultdict(set)
    observations_with_source = 0
    observations_without_source = 0
    observations = engine.observations()
    for observation in observations:
        raw = observation.get("raw")
        if not raw:
            observations_without_source += 1
            continue
        observations_with_source += 1
        try:
            for document, values in _base_dates(bytes(raw)).items():
                dates_by_document[document].update(values)
        except (OSError, ValueError, KeyError, TypeError):
            observations_without_source += 1

    observation_dates = sorted(
        date.fromisoformat(str(observation["observed_date"])[:10])
        for observation in observations
        if observation.get("observed_date")
    )
    baseline_date = observation_dates[0] if observation_dates else None
    baseline_completed_count = sum(
        completion_date == baseline_date
        for completion_date in completion_dates.values()
        if baseline_date is not None
    )
    registered_completion_dates = {
        document: completion_date
        for document, completion_date in completion_dates.items()
        if baseline_date is None or completion_date > baseline_date
    }
    rows = []
    ambiguous = 0
    invalid = 0
    calendar = config.get(
        "calendar", {"weekdays": [0, 1, 2, 3, 4], "holidays": []}
    )
    for document, completion_date in sorted(registered_completion_dates.items()):
        candidates = sorted(dates_by_document.get(document, set()))
        if not candidates:
            continue
        if len(candidates) > 1:
            ambiguous += 1
        start_date = candidates[0]
        if start_date > completion_date:
            invalid += 1
            continue
        elapsed = workdays(
            start_date.isoformat(), completion_date.isoformat(), calendar
        )
        rows.append(
            {
                "Documento de ventas": document,
                "Fecha de precio": start_date.strftime("%d/%m/%Y"),
                "Fecha final observada": completion_date.strftime("%d/%m/%Y"),
                "Días laborables totales": elapsed,
                "Fechas de precio distintas": len(candidates),
            }
        )
    values = [row["Días laborables totales"] for row in rows]
    return {
        "completed_count": len(completion_dates),
        "baseline_date": baseline_date.strftime("%d/%m/%Y") if baseline_date else None,
        "baseline_completed_count": baseline_completed_count,
        "registered_completed_count": len(registered_completion_dates),
        "calculable_count": len(rows),
        "coverage_pct": (
            round(100 * len(rows) / len(registered_completion_dates), 1)
            if registered_completion_dates
            else None
        ),
        "average_days": round(sum(values) / len(values), 1) if values else None,
        "median_days": round(statistics.median(values), 1) if values else None,
        "min_days": min(values) if values else None,
        "max_days": max(values) if values else None,
        "ambiguous_price_dates": ambiguous,
        "invalid_date_ranges": invalid,
        "observations_with_source": observations_with_source,
        "observations_without_source": observations_without_source,
        "rows": sorted(
            rows,
            key=lambda row: row["Días laborables totales"],
            reverse=True,
        ),
    }

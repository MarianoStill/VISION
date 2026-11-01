from covision import BASE_TECHNICAL_STATUS

from . import delivery
from .progress import stage_progress as _stage_progress


def availability() -> str:
    return BASE_TECHNICAL_STATUS


def is_delivered(status):
    """Expose the current LION delivered-status check."""
    return delivery.is_delivered(status)


def process_workbook(content, reference_date, source="Base"):
    """Process uploaded XLSX bytes using the received LION engine."""
    from .sap_engine import process_workbook as run_processing

    return run_processing(content, reference_date, source)


def search_machines(model, query, mode="Todo", exact=False):
    """Filter processed LION results using the received search behavior."""
    from .search import search

    return search(model, query, mode, exact)


def filter_machines(model, details, global_query="", filters=None, exact=False):
    """Apply LION's received global, business-field, and chassis filters."""
    from .search import filter_machines as apply_filters

    return apply_filters(model, details, global_query, filters, exact)


def stage_progress(status):
    """Expose LION's received stage labels and timeline progression."""
    return _stage_progress(status)


__all__ = [
    "availability",
    "filter_machines",
    "is_delivered",
    "process_workbook",
    "search_machines",
    "stage_progress",
]

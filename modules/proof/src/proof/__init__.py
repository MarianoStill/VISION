from covision import BASE_TECHNICAL_STATUS

from . import inventory_projection
from .dashboard import operational_summary
from .movements import movement_index, stage_movement_counts, daily_stage_movements
from .errors import ProofError
from .service import (
    calculate_completion_metrics,
    filter_history,
    filter_history_documents,
    history_for_sales_document,
    read_history,
    read_search_index,
)

def availability() -> str:
    return BASE_TECHNICAL_STATUS


def project_inventory(instances, dates, rules, grain, start, end):
    """Return inventory rows and selected stages using the current projection behavior."""
    return inventory_projection.chart_rows(instances, dates, rules, grain, start, end)


def classify_snapshot(content, config=None):
    from .service import classify_snapshot as classify

    return classify(content, config)


def default_dev_database_path():
    from .service import default_dev_database_path as get_path

    return get_path()


def find_reference_observation(database_path, content):
    from .service import find_reference_observation as find

    return find(database_path, content)


def register_snapshot(
    content,
    source_name,
    observed_date,
    database_path=None,
    *,
    reference_database_path=None,
    config=None,
):
    from .service import register_snapshot as register

    return register(
        content,
        source_name,
        observed_date,
        database_path,
        reference_database_path=reference_database_path,
        config=config,
    )


__all__ = [
    "movement_index",
    "stage_movement_counts",
    "daily_stage_movements",
    "ProofError",
    "availability",
    "classify_snapshot",
    "operational_summary",
    "calculate_completion_metrics",
    "filter_history",
    "filter_history_documents",
    "history_for_sales_document",
    "default_dev_database_path",
    "find_reference_observation",
    "project_inventory",
    "read_history",
    "read_search_index",
    "register_snapshot",
]

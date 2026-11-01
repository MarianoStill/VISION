import lion

from vision import lion_adapter
from vision.lion_adapter import is_delivered


def test_vision_adapter_delegates_to_public_lion_service(monkeypatch):
    received = []
    expected_result = object()

    def public_service(status):
        received.append(status)
        return expected_result

    monkeypatch.setattr(lion, "is_delivered", public_service)
    synthetic_status = "Planning | Entregadas"

    assert is_delivered(synthetic_status) is expected_result
    assert received == [synthetic_status]


def test_vision_adapter_delegates_workbook_processing_to_lion(monkeypatch):
    expected_result = object()
    received = []

    def public_service(content, reference_date):
        received.append((content, reference_date))
        return expected_result

    monkeypatch.setattr(lion, "process_workbook", public_service)
    synthetic_content = b"synthetic-workbook"

    assert lion_adapter.process_workbook(synthetic_content, "2026-10-26") is expected_result
    assert received == [(synthetic_content, "2026-10-26")]


def test_vision_adapter_delegates_search_to_lion(monkeypatch):
    expected_result = object()
    received = []

    def public_service(model, query, mode, exact):
        received.append((model, query, mode, exact))
        return expected_result

    monkeypatch.setattr(lion, "search_machines", public_service)
    synthetic_model = object()

    assert (
        lion_adapter.search_machines(synthetic_model, "synthetic", "Todo", True)
        is expected_result
    )
    assert received == [(synthetic_model, "synthetic", "Todo", True)]


def test_vision_adapter_delegates_field_filters_to_public_lion_service(monkeypatch):
    expected_result = object()
    received = []

    def public_service(model, details, global_query, filters, exact):
        received.append((model, details, global_query, filters, exact))
        return expected_result

    monkeypatch.setattr(lion, "filter_machines", public_service)
    synthetic_model = object()
    synthetic_details = object()
    filters = {"Pedido": "synthetic-order"}

    assert (
        lion_adapter.filter_machines(
            synthetic_model, synthetic_details, "synthetic", filters, True
        )
        is expected_result
    )
    assert received == [
        (synthetic_model, synthetic_details, "synthetic", filters, True)
    ]


def test_vision_adapter_delegates_stage_progress_to_public_lion_service(monkeypatch):
    expected_result = {"timeline": ["synthetic"]}
    received = []

    def public_service(status):
        received.append(status)
        return expected_result

    monkeypatch.setattr(lion, "stage_progress", public_service)
    synthetic_status = "Synthetic stage"

    assert lion_adapter.stage_progress(synthetic_status) is expected_result
    assert received == [synthetic_status]

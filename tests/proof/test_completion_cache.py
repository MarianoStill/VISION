from io import BytesIO

import openpyxl
import pytest

from proof import completion


def _workbook():
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Data"
    sheet.append(["Documento de ventas", "Fecha de precio"])
    sheet.append(["A1", "01/10/2026"])
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _isolated_cache():
    completion._MEMORY_CACHE.clear()
    yield
    completion._MEMORY_CACHE.clear()
    completion.set_base_dates_cache_dir(None)


def test_base_dates_parsed_once_in_memory(monkeypatch):
    calls = []
    original = completion._parse_base_dates
    monkeypatch.setattr(
        completion, "_parse_base_dates", lambda raw: calls.append(1) or original(raw)
    )
    raw = _workbook()
    first = completion._base_dates(raw)
    second = completion._base_dates(raw)
    assert first == second and len(calls) == 1


def test_base_dates_reused_from_disk_after_memory_reset(tmp_path, monkeypatch):
    completion.set_base_dates_cache_dir(tmp_path)
    raw = _workbook()
    expected = completion._base_dates(raw)
    completion._MEMORY_CACHE.clear()
    monkeypatch.setattr(
        completion, "_parse_base_dates",
        lambda raw: pytest.fail("no debería volver a leer el Excel"),
    )
    assert completion._base_dates(raw) == expected

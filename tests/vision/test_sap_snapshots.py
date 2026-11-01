from datetime import datetime
from pathlib import Path
import os

import openpyxl

from vision.sap_snapshots import (
    AmbiguousSnapshotError,
    discover_daily_snapshots,
)


def _write_workbook(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    workbook.active.title = "Data"
    workbook.active.append(["Documento de ventas"])
    workbook.active.append(["SYNTHETIC-ORDER"])
    workbook.save(path)
    workbook.close()


def _set_modified(path: Path, year, month, day, hour=12):
    timestamp = datetime(year, month, day, hour).timestamp()
    os.utime(path, (timestamp, timestamp))


def test_daily_candidates_are_ordered_by_filename_date_before_lion_validation(
    tmp_path,
):
    folder = tmp_path / "sap" / "daily"
    dated_old = folder / "snapshot_2026-10-25.xlsx"
    dated_new = folder / "snapshot_2026-10-27.xlsx"
    invalid_newer = folder / "snapshot_2026-10-29.xlsx"
    _write_workbook(dated_old)
    _write_workbook(dated_new)
    invalid_newer.parent.mkdir(parents=True, exist_ok=True)
    invalid_newer.write_bytes(b"not an xlsx")
    _set_modified(dated_old, 2026, 10, 28)
    _set_modified(dated_new, 2026, 10, 26)

    snapshots = discover_daily_snapshots(folder)

    assert snapshots[0].path == invalid_newer.resolve()
    assert snapshots[0].observation_date == "2026-10-29"
    assert snapshots[0].date_from_filename
    assert [item.path for item in snapshots] == [
        invalid_newer.resolve(),
        dated_new.resolve(),
        dated_old.resolve(),
    ]


def test_multiple_snapshots_are_sorted_newest_first(tmp_path):
    folder = tmp_path / "daily"
    for day in (25, 26, 27):
        _write_workbook(folder / f"snapshot_2026-10-{day}.xlsx")

    snapshots = discover_daily_snapshots(folder)

    assert [item.observation_date for item in snapshots] == [
        "2026-10-27",
        "2026-10-26",
        "2026-10-25",
    ]


def test_temporary_excel_and_non_xlsx_files_are_ignored(tmp_path):
    folder = tmp_path / "daily"
    _write_workbook(folder / "snapshot_2026-10-26.xlsx")
    _write_workbook(folder / "~$snapshot_2026-10-28.xlsx")
    (folder / "snapshot_2026-10-29.csv").write_text("synthetic", encoding="utf-8")

    snapshots = discover_daily_snapshots(folder)

    assert [item.path.name for item in snapshots] == ["snapshot_2026-10-26.xlsx"]


def test_invalid_filename_date_uses_modification_date_safely(tmp_path):
    folder = tmp_path / "daily"
    path = folder / "snapshot_2026-99-99.xlsx"
    _write_workbook(path)
    _set_modified(path, 2026, 10, 24)

    snapshots = discover_daily_snapshots(folder)

    assert len(snapshots) == 1
    assert snapshots[0].observation_date == "2026-10-24"
    assert not snapshots[0].date_from_filename


def test_missing_folder_or_no_candidate_files_returns_no_candidates(tmp_path):
    assert discover_daily_snapshots(tmp_path / "missing") == []

    folder = tmp_path / "daily"
    folder.mkdir()
    (folder / "notes.txt").write_text("synthetic", encoding="utf-8")
    (folder / "~$temporary.xlsx").write_bytes(b"temporary")

    assert discover_daily_snapshots(folder) == []


def test_equal_latest_snapshot_rank_is_reported_as_ambiguous(tmp_path):
    folder = tmp_path / "daily"
    first = folder / "first_2026-10-27.xlsx"
    second = folder / "second_2026-10-27.xlsx"
    _write_workbook(first)
    _write_workbook(second)
    _set_modified(first, 2026, 10, 27)
    _set_modified(second, 2026, 10, 27)

    try:
        discover_daily_snapshots(folder)
    except AmbiguousSnapshotError:
        pass
    else:
        raise AssertionError("Expected equally recent snapshots to be rejected")

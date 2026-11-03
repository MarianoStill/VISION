import json

import pytest

from vision import daily_update


def test_signal_roundtrip_and_token_changes(tmp_path):
    assert daily_update.read_token(tmp_path) is None
    first = daily_update.write_signal(tmp_path, {"added": 1})
    assert daily_update.read_token(tmp_path) == first
    second = daily_update.write_signal(tmp_path, {"added": 0})
    assert second != first
    stored = json.loads(daily_update.signal_path(tmp_path).read_text(encoding="utf-8"))
    assert stored["added"] == 0 and stored["token"] == second


def test_corrupt_signal_is_ignored(tmp_path):
    path = daily_update.signal_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{no json", encoding="utf-8")
    assert daily_update.read_token(tmp_path) is None


def test_fingerprint_changes_with_new_excel_and_ignores_temp(tmp_path):
    empty = daily_update.folder_fingerprint(tmp_path)
    (tmp_path / "~$04-11-2026.xlsx").write_bytes(b"x")
    assert daily_update.folder_fingerprint(tmp_path) == empty
    (tmp_path / "04-11-2026.xlsx").write_bytes(b"abc")
    assert daily_update.folder_fingerprint(tmp_path) != empty


def test_watch_updates_once_after_folder_settles(tmp_path, monkeypatch):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "04-11-2026.xlsx").write_bytes(b"abc")
    sources = {"root": tmp_path, "sap_daily_dir": daily}
    calls = []
    monkeypatch.setattr(
        daily_update, "run_daily_update",
        lambda s: calls.append(1) or {"added": 1, "snapshot": "x"},
    )
    ticks = iter(range(50))
    daily_update.watch_folder(sources, interval=0, settle=0, log=lambda m: None,
                              stop=lambda: next(ticks) >= 6)
    assert len(calls) == 1


def test_missing_proof_database_does_not_publish_signal(tmp_path):
    sources = {"root": tmp_path, "proof_db": tmp_path / "proof.db",
               "sap_daily_dir": tmp_path / "daily"}
    with pytest.raises(FileNotFoundError):
        daily_update.run_daily_update(sources)
    assert daily_update.read_token(tmp_path) is None

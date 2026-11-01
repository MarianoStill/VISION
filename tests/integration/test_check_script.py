from pathlib import Path

import pytest

from scripts import check
from scripts.check import (
    interpreter_path,
    minimum_python_version,
    project_interpreter,
    unsupported_python_message,
)


@pytest.mark.parametrize(
    ("platform", "relative_path"),
    [
        ("win32", Path(".venv") / "Scripts" / "python.exe"),
        ("linux", Path(".venv") / "bin" / "python"),
    ],
)
def test_interpreter_path_is_platform_specific(
    tmp_path: Path, platform: str, relative_path: Path
) -> None:
    assert interpreter_path(tmp_path, platform) == tmp_path / relative_path


def test_project_interpreter_reports_missing_environment(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="virtual environment not found"):
        project_interpreter(tmp_path, "linux")


def test_project_interpreter_reports_missing_interpreter(tmp_path: Path) -> None:
    (tmp_path / ".venv" / "bin").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="interpreter not found"):
        project_interpreter(tmp_path, "linux")


def test_python_requirement_is_read_from_project_configuration() -> None:
    assert minimum_python_version(Path(__file__).resolve().parents[2]) == (3, 13)


def test_unsupported_python_version_is_actionable() -> None:
    message = unsupported_python_message((3, 12), (3, 13))

    assert message is not None
    assert "Python 3.13 or newer is required" in message


def test_supported_python_version_has_no_error() -> None:
    assert unsupported_python_message((3, 14), (3, 13)) is None


def test_missing_dependencies_report_install_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check.importlib.util, "find_spec", lambda _: None)

    assert check.main() == 2
    error = capsys.readouterr().err
    assert "Required development dependencies are unavailable" in error
    assert '.[test,vision,lion,proof]' in error

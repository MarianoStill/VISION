from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re


_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)"),
)


class AmbiguousSnapshotError(ValueError):
    """Raised when equally recent SAP snapshots cannot be distinguished."""


class SnapshotDiscoveryError(ValueError):
    """Raised when the configured SAP snapshot folder cannot be scanned."""


@dataclass(frozen=True)
class SapSnapshot:
    path: Path
    observation_date: str
    date_from_filename: bool
    modified_ns: int
    size: int


def _filename_date(filename: str) -> date | None:
    dates = set()
    for pattern_index, pattern in enumerate(_DATE_PATTERNS):
        for match in pattern.finditer(filename):
            year_first = pattern_index < 2
            year, month, day = (
                (int(match[1]), int(match[2]), int(match[3]))
                if year_first
                else (int(match[3]), int(match[2]), int(match[1]))
            )
            try:
                dates.add(date(year, month, day))
            except ValueError:
                continue
    return next(iter(dates)) if len(dates) == 1 else None


def discover_daily_snapshots(directory: str | Path) -> list[SapSnapshot]:
    folder = Path(directory).expanduser()
    try:
        entries = list(folder.iterdir())
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise SnapshotDiscoveryError(
            "No se pudo consultar la carpeta de snapshots SAP."
        ) from exc

    candidates = []
    for path in entries:
        if (
            not path.is_file()
            or path.name.startswith("~$")
            or path.suffix.casefold() != ".xlsx"
        ):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        filename_date = _filename_date(path.stem)
        observed_date = filename_date or datetime.fromtimestamp(stat.st_mtime).date()
        candidates.append(
            SapSnapshot(
                path=path.resolve(),
                observation_date=observed_date.isoformat(),
                date_from_filename=filename_date is not None,
                modified_ns=stat.st_mtime_ns,
                size=stat.st_size,
            )
        )

    if not candidates:
        return []

    use_filename_dates = all(item.date_from_filename for item in candidates)
    if use_filename_dates:
        candidates.sort(
            key=lambda item: (
                item.observation_date,
                item.modified_ns,
                item.path.name.casefold(),
            ),
            reverse=True,
        )
        same_rank = lambda left, right: (
            left.observation_date,
            left.modified_ns,
        ) == (right.observation_date, right.modified_ns)
    else:
        candidates.sort(
            key=lambda item: (
                item.modified_ns,
                item.path.name.casefold(),
            ),
            reverse=True,
        )
        same_rank = lambda left, right: left.modified_ns == right.modified_ns

    if len(candidates) > 1 and same_rank(candidates[0], candidates[1]):
        raise AmbiguousSnapshotError(
            "Hay varios XLSX SAP con la misma fecha y metadatos de modificación."
        )
    return candidates

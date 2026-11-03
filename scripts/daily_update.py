"""Actualización diaria de VISION: PROOF + LION + cachés + señal de refresco.

Programar tras subir el Excel del día (p. ej. 08:00). Respeta CO_VISION_DATA_ROOT.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT / "apps" / "vision" / "src", ROOT / "modules" / "proof" / "src",
               ROOT / "modules" / "lion" / "src", ROOT / "shared" / "src"):
    if source.exists():
        sys.path.insert(0, str(source))


def main() -> int:
    from vision.daily_update import run_daily_update

    try:
        report = run_daily_update()
    except Exception as exc:
        print(f"Actualización diaria fallida: {type(exc).__name__}: {exc}")
        return 1
    print(f"Actualización lista: {report['added']} observaciones añadidas a PROOF, "
          f"snapshot {report['snapshot']}, {report['calculable']} finalizaciones calculables "
          f"en {report['finished'] - report['started']:.1f} s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

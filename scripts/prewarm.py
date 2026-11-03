"""Precalienta la caché diaria de VISION (programar tras actualizar los Excel, p. ej. 08:00).

Uso: python scripts/prewarm.py   (respeta CO_VISION_DATA_ROOT)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT / "apps" / "vision" / "src", ROOT / "modules" / "proof" / "src",
               ROOT / "modules" / "lion" / "src", ROOT / "shared" / "src"):
    if source.exists():
        sys.path.insert(0, str(source))


def main() -> int:
    import proof
    from vision.data_sources import resolve_external_sources

    sources = resolve_external_sources()
    database = Path(sources["proof_db"])
    if not database.exists():
        print("No se encontró la base PROOF configurada.")
        return 1
    proof.set_base_dates_cache_dir(sources["root"] / "vision" / "cache")
    started = time.time()
    metrics = proof.calculate_completion_metrics(str(database))
    print(f"Caché de finalizaciones lista: {metrics['calculable_count']} calculables "
          f"en {time.time() - started:.1f} s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

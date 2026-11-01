"""Cachés de navegación: sin cálculos LION/PROOF ni datos en Git."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile


def session_value(state, key, signature, loader):
    previous = state.get(key)
    if previous is not None and previous[0] == signature:
        return previous[1]
    value = loader()
    state[key] = (signature, value)
    return value


def catalog_signature(candidates, reference_date):
    return [reference_date, [[str(c.path), c.modified_ns, c.size,
                             c.observation_date] for c in candidates]]


def read_catalog(path, signature):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if value.get("version") != 1 or value.get("signature") != signature:
            return None
        for field in ("commercials", "delegations", "stages"):
            if not isinstance(value.get(field), list) or not all(
                isinstance(item, str) for item in value[field]
            ):
                return None
        return value
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def write_catalog(path, signature, commercials, delegations, stages):
    path = Path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(version=1, signature=signature,
                       commercials=list(commercials), delegations=list(delegations),
                       stages=list(stages))
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(temporary, path)
        return True
    except (OSError, ValueError, TypeError):
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

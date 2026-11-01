from __future__ import annotations

import sqlite3
from pathlib import Path

import proof


def ingest_proof_snapshot(
    database_path: str | Path,
    content: bytes,
    source_name: str,
    observed_date: str,
) -> dict:
    existing = proof.find_reference_observation(database_path, content)
    if existing is not None:
        return {"status": "already_present", **existing}

    try:
        return proof.register_snapshot(
            content,
            source_name,
            observed_date,
            database_path=database_path,
        )
    except (proof.ProofError, sqlite3.IntegrityError):
        existing = proof.find_reference_observation(database_path, content)
        if existing is not None:
            return {"status": "already_present", **existing}
        raise

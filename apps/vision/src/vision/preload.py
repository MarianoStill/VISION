"""Precarga finita compartida por proceso. Sin llamadas Streamlit en el worker.

Los resultados publicados no se modifican. La interfaz recibe una copia por sesión.
La ingestión se solicita explícitamente después de Entrar; nunca en la portada.
"""
from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from time import perf_counter


@dataclass(frozen=True)
class SnapshotRef:
    path: Path
    modified_ns: int
    size: int
    observation_date: str


def database_signature(database_path):
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        return None
    stat = path.stat()
    wal = Path(str(path) + "-wal")
    try:
        wal_stat = wal.stat()
    except FileNotFoundError:
        wal_stat = None
    return (str(path), stat.st_mtime_ns, stat.st_size,
            wal_stat.st_mtime_ns if wal_stat else None,
            wal_stat.st_size if wal_stat else None)


class SourceChangedError(ValueError):
    pass


class LoadJob:
    def __init__(self, key, specs, reference_date, root, proof_path, stages, catalog):
        self.key = key
        self.specs = tuple(specs)
        self.reference_date = reference_date
        self.root = Path(root)
        self.proof_path = Path(proof_path)
        self.stages = tuple(stages)
        self.catalog = deepcopy(catalog)
        self.phase = "queued"
        self.message = "Preparación en cola…"
        self.started = perf_counter()
        self.timings = {}
        self.error = None
        self.result = None
        self.revision = 0
        self.future = None
        self.lock = RLock()

    def status(self):
        with self.lock:
            return dict(phase=self.phase, message=self.message,
                        elapsed=perf_counter()-self.started,
                        catalog=deepcopy(self.catalog), error=self.error,
                        timings=dict(self.timings), revision=self.revision,
                        ingested=bool(self.result and self.result.get("ingested")))

    def copy_result(self):
        with self.lock:
            if self.phase != "ready" or self.result is None:
                raise RuntimeError("La preparación todavía no está lista.")
            # Los objetos de pandas y PROOF no se comparten para mutación entre usuarios.
            return deepcopy(self.result)


class PreloadCoordinator:
    def __init__(self, max_ready=3):
        # Un único worker evita procesamientos y escrituras concurrentes propios.
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vision-preload")
        self._jobs = OrderedDict()
        self._lock = RLock()
        self._database_lock = RLock()
        self.max_ready = max_ready

    @staticmethod
    def key_for(specs, reference_date, root, proof_path):
        return (tuple(tuple(s) for s in specs), str(reference_date),
                str(Path(root).expanduser().resolve()),
                str(Path(proof_path).expanduser().resolve()))

    def request(self, specs, reference_date, root, proof_path, stages, catalog=None):
        key = self.key_for(specs, reference_date, root, proof_path)
        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                # No descartar trabajos activos para arrancar otros iguales.
                if sum(j.phase not in ("ready", "error") for j in self._jobs.values()) >= 4:
                    raise RuntimeError("La preparación está ocupada. Vuelve a intentarlo.")
                job = LoadJob(key, specs, reference_date, root, proof_path, stages, catalog)
                self._jobs[key] = job
                job.future = self._pool.submit(self._prepare, job, None)
            else:
                with job.lock:
                    if job.phase == "ready" and job.result is not None:
                        current = database_signature(proof_path)
                        if current != job.result.get("history_signature"):
                            reuse = job.result
                            job.phase = "queued"
                            job.message = "El histórico cambió; actualizando la lectura…"
                            job.error = None
                            job.started = perf_counter()
                            job.future = self._pool.submit(self._prepare, job, reuse)
            self._jobs.move_to_end(key)
            self._prune(key)
            return job

    def _prune(self, keep):
        ready = [k for k,j in self._jobs.items()
                 if k != keep and j.phase in ("ready", "error")
                 and j.future is not None and j.future.done()]
        while len(self._jobs) > self.max_ready and ready:
            del self._jobs[ready.pop(0)]

    def retry(self, job):
        with self._lock, job.lock:
            if job.phase == "error" and (job.future is None or job.future.done()):
                job.error = None
                job.phase = "queued"
                job.message = "Reintentando la preparación…"
                job.started = perf_counter()
                job.future = self._pool.submit(self._prepare, job, None)

    def enter(self, job):
        with self._lock, job.lock:
            if job.phase == "ready" and job.result is not None and not job.result["ingested"]:
                job.phase = "finalizing"
                job.message = "Conciliando los Excel de la carpeta con PROOF…"
                job.future = self._pool.submit(self._finalize, job, job.result)
            return job

    @staticmethod
    def _phase(job, phase, message):
        with job.lock:
            job.phase, job.message = phase, message

    @staticmethod
    def _time(job, label, started):
        with job.lock:
            job.timings[label] = round(perf_counter()-started, 3)

    @staticmethod
    def _catalog(job, value):
        with job.lock:
            job.catalog = deepcopy(value)

    def _read_history(self, path):
        import proof
        with self._database_lock:
            before = database_signature(path)
            if before is None:
                return None, None, "FileNotFoundError"
            history = proof.read_history(str(path))
            after = database_signature(path)
            if before != after:
                raise SourceChangedError("El histórico cambió durante la lectura.")
            return history, after, None

    def _prepare(self, job, reuse):
        try:
            from vision import lion_adapter
            from vision.commercial_workspace import commercial_options, delegation_options
            from vision.navigation_cache import write_catalog
            candidates = [SnapshotRef(Path(s[0]), s[1], s[2], s[3]) for s in job.specs]
            signature = [job.reference_date, [[str(c.path), c.modified_ns, c.size,
                                              c.observation_date] for c in candidates]]
            if not candidates:
                raise FileNotFoundError("No hay snapshots SAP disponibles.")
            # El catálogo externo existente permite seleccionar sin recorrer el XLSX.
            # Si no existe, una lectura ligera se hace en el worker, nunca en la UI.
            if job.catalog is None:
                self._phase(job, "access", "Preparando comerciales, delegaciones y etapas…")
                started = perf_counter()
                try:
                    from vision.access_options import read_access_options
                    names, offices = read_access_options(candidates[0].path)
                    catalog = dict(commercials=names, delegations=offices, stages=list(job.stages))
                    self._catalog(job, catalog)
                    write_catalog(job.root/"vision"/"access_catalog.json", signature,
                                  names, offices, job.stages)
                except Exception:
                    # El catálogo ligero no es autoridad: se reconstruye desde LION.
                    pass
                self._time(job, "Opciones de acceso", started)
            if reuse is not None:
                selected = reuse["selected_snapshot"]
                output, content = reuse["automatic_lion_output"], reuse["snapshot_content"]
                sap_error = reuse.get("sap_error")
            else:
                selected = output = content = None
                sap_error = None
                self._phase(job, "lion", "Preparando las máquinas con LION…")
                started = perf_counter()
                for candidate in candidates:
                    try:
                        before = candidate.path.stat()
                        if (before.st_mtime_ns, before.st_size) != (candidate.modified_ns, candidate.size):
                            raise SourceChangedError("El archivo SAP cambió antes de la carga.")
                        read_started = perf_counter()
                        raw = candidate.path.read_bytes()
                        after = candidate.path.stat()
                        if ((after.st_mtime_ns, after.st_size) != (candidate.modified_ns, candidate.size)
                                or len(raw) != candidate.size):
                            raise SourceChangedError("El archivo SAP cambió durante la carga.")
                        self._time(job, "Lectura del archivo SAP", read_started)
                        process_started = perf_counter()
                        output = lion_adapter.process_workbook(raw, reference_date=job.reference_date)
                        self._time(job, "Procesamiento LION", process_started)
                        content, selected = raw, candidate
                        break
                    except SourceChangedError:
                        raise
                    except Exception as exc:
                        sap_error = type(exc).__name__
                self._time(job, "Lectura SAP y procesamiento LION", started)
                if selected is None:
                    raise ValueError("Ningún snapshot pudo procesarse: " + str(sap_error))
            self._phase(job, "catalog", "Confirmando las opciones con los datos LION…")
            started = perf_counter()
            model, details = output[:2]
            catalog = dict(commercials=commercial_options(model, details),
                           delegations=delegation_options(model), stages=list(job.stages))
            self._catalog(job, catalog)
            write_catalog(job.root/"vision"/"access_catalog.json", signature,
                          catalog["commercials"], catalog["delegations"], job.stages)
            self._time(job, "Catálogo confirmado por LION", started)
            self._phase(job, "history", "Consultando el histórico PROOF…")
            started = perf_counter()
            try:
                history, history_sig, proof_error = self._read_history(job.proof_path)
            except Exception as exc:
                history, history_sig, proof_error = None, database_signature(job.proof_path), type(exc).__name__
            self._time(job, "Lectura del histórico PROOF", started)
            result = dict(selected_snapshot=selected, automatic_lion_output=output,
                          snapshot_content=content, sap_error=sap_error,
                          automatic_history=history, history_signature=history_sig,
                          proof_error=proof_error, proof_snapshot_status=None,
                          catalog=catalog, ingested=False)
            with job.lock:
                job.result = result
                job.revision += 1
                job.phase, job.message = "ready", "Datos preparados para entrar."
        except Exception as exc:
            with job.lock:
                job.error = type(exc).__name__
                job.phase, job.message = "error", "No se pudo completar la preparación."

    def _finalize(self, job, prepared):
        # Solo se llama después de Entrar. Se mantiene el servicio idempotente existente.
        result = dict(prepared)
        started = perf_counter()
        try:
            with self._database_lock:
                if database_signature(job.proof_path) is None:
                    raise FileNotFoundError("No se encontró la base PROOF configurada.")
                from vision.folder_sync import synchronize_folder
                selected = result["selected_snapshot"]
                response = synchronize_folder(
                    job.proof_path, selected.path.parent,
                    job.root / "proof" / "sync_backups",
                )
                result["folder_sync"] = response
                if response["status"] == "blocked":
                    raise ValueError(response["message"])
                result["proof_snapshot_status"] = (
                    "CARPETA CONCILIADA" if response["added"] == 0
                    else str(response["added"]) + " OBSERVACIONES INCORPORADAS"
                )
                self._time(job, "Conciliación de carpeta e ingestión PROOF", started)
                current = database_signature(job.proof_path)
                if current != result["history_signature"] or result["automatic_history"] is None:
                    self._phase(job, "finalizing", "Actualizando el histórico tras comprobar el snapshot…")
                    read_started = perf_counter()
                    history, history_sig, error = self._read_history(job.proof_path)
                    result.update(automatic_history=history, history_signature=history_sig, proof_error=error)
                    self._time(job, "Relectura PROOF tras ingestión", read_started)
                else:
                    result["proof_error"] = None
        except Exception as exc:
            result["proof_error"] = type(exc).__name__
            result["proof_snapshot_status"] = "ERROR"
            # No presentar un histórico anterior como actual tras una escritura fallida.
            if database_signature(job.proof_path) != result["history_signature"]:
                result["automatic_history"] = None
                result["history_signature"] = database_signature(job.proof_path)
            self._time(job, "Conciliación de carpeta e ingestión PROOF", started)
        result["ingested"] = True
        with job.lock:
            job.result = result
            job.revision += 1
            job.phase, job.message = "ready", "Tu espacio de trabajo está preparado."

    def close(self):
        self._pool.shutdown(wait=True, cancel_futures=False)

"""
Job store: in-memory access backed by SQLite persistence.

Jobs, results, and pose data survive process restarts once init_persistence()
runs (called from app lifespan). Bounded by max_jobs and job_ttl_hours —
oldest/expired entries are evicted on every create and at restore.
Upgradeable to Redis by replacing this module.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.schemas.models import JobResponse, JobStatus, MoleculeResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    job_id TEXT NOT NULL,
    mol_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (job_id, mol_id)
);
CREATE TABLE IF NOT EXISTS poses (
    job_id TEXT NOT NULL,
    mol_id TEXT NOT NULL,
    pdb TEXT NOT NULL,
    PRIMARY KEY (job_id, mol_id)
);
"""


class JobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, dict] = {}
        self._results: Dict[str, list[MoleculeResult]] = {}
        self._poses: Dict[str, Dict[str, str]] = {}  # job_id -> mol_id -> pdb string
        self._lock = asyncio.Lock()
        self._db: Optional[sqlite3.Connection] = None
        self._max_jobs = 100
        self._ttl_hours = 24

    # ------------------------------------------------------------------ #
    # Persistence (sync; called from app lifespan before serving traffic)
    # ------------------------------------------------------------------ #

    def init_persistence(
        self, db_path: Path, max_jobs: int = 100, ttl_hours: int = 24
    ) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._max_jobs = max_jobs
        self._ttl_hours = ttl_hours
        self._restore()

    def _restore(self) -> None:
        assert self._db is not None
        for job_id, payload in self._db.execute("SELECT job_id, payload FROM jobs"):
            self._jobs[job_id] = json.loads(payload)
        for job_id, mol_id, payload in self._db.execute(
            "SELECT job_id, mol_id, payload FROM results"
        ):
            self._results.setdefault(job_id, []).append(
                MoleculeResult(**json.loads(payload))
            )
        for job_id, mol_id, pdb in self._db.execute(
            "SELECT job_id, mol_id, pdb FROM poses"
        ):
            self._poses.setdefault(job_id, {})[mol_id] = pdb
        self._evict()

    def _save_job(self, job_id: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO jobs (job_id, payload) VALUES (?, ?)",
            (job_id, json.dumps(self._jobs[job_id], default=str)),
        )
        self._db.commit()

    def _save_results(self, job_id: str) -> None:
        if self._db is None:
            return
        self._db.execute("DELETE FROM results WHERE job_id = ?", (job_id,))
        self._db.executemany(
            "INSERT INTO results (job_id, mol_id, payload) VALUES (?, ?, ?)",
            [
                (job_id, m.mol_id, m.model_dump_json())
                for m in self._results.get(job_id, [])
            ],
        )
        self._db.commit()

    def _save_pose(self, job_id: str, mol_id: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO poses (job_id, mol_id, pdb) VALUES (?, ?, ?)",
            (job_id, mol_id, self._poses[job_id][mol_id]),
        )
        self._db.commit()

    def _drop(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        self._results.pop(job_id, None)
        self._poses.pop(job_id, None)
        if self._db is not None:
            for table in ("jobs", "results", "poses"):
                self._db.execute(f"DELETE FROM {table} WHERE job_id = ?", (job_id,))
            self._db.commit()

    def _evict(self) -> None:
        """Drop jobs older than ttl_hours, then cap count at max_jobs (oldest first)."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=self._ttl_hours)
        ).isoformat()
        victims = [jid for jid, j in self._jobs.items() if j["created_at"] < cutoff]
        for jid in victims:
            self._drop(jid)
        if len(self._jobs) > self._max_jobs:
            oldest_first = sorted(
                self._jobs, key=lambda jid: self._jobs[jid]["created_at"]
            )
            for jid in oldest_first[: len(self._jobs) - self._max_jobs]:
                self._drop(jid)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def create(
        self,
        protein_filename: str,
        library_filename: str,
        top_k: int,
        submitter_ip: Optional[str] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        async with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": JobStatus.queued,
                "progress": 0.0,
                "current_stage": "Queued",
                "molecules_total": 0,
                "molecules_processed": 0,
                "error_message": None,
                "protein_filename": protein_filename,
                "library_filename": library_filename,
                "top_k": top_k,
                "submitter_ip": submitter_ip,
                "created_at": _now(),
                "updated_at": _now(),
            }
            self._evict()
            self._save_job(job_id)
        return job_id

    async def count_active(self, submitter_ip: str) -> int:
        """Jobs owned by this IP that are still queued or running."""
        terminal = (JobStatus.done, JobStatus.error)
        async with self._lock:
            return sum(
                1
                for j in self._jobs.values()
                if j.get("submitter_ip") == submitter_ip
                and j["status"] not in terminal
            )

    async def update(self, job_id: str, **kwargs: Any) -> None:
        async with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job {job_id} not found")
            self._jobs[job_id].update(kwargs)
            self._jobs[job_id]["updated_at"] = _now()
            self._save_job(job_id)

    async def get(self, job_id: str) -> Optional[JobResponse]:
        async with self._lock:
            data = self._jobs.get(job_id)
        if data is None:
            return None
        return JobResponse(**data)

    async def set_results(
        self, job_id: str, results: list[MoleculeResult]
    ) -> None:
        async with self._lock:
            self._results[job_id] = results
            self._save_results(job_id)

    async def get_results(self, job_id: str) -> Optional[list[MoleculeResult]]:
        async with self._lock:
            return self._results.get(job_id)

    async def set_pose(self, job_id: str, mol_id: str, pdb_str: str) -> None:
        async with self._lock:
            if job_id not in self._poses:
                self._poses[job_id] = {}
            self._poses[job_id][mol_id] = pdb_str
            self._save_pose(job_id, mol_id)

    async def get_pose(self, job_id: str, mol_id: str) -> Optional[str]:
        async with self._lock:
            return self._poses.get(job_id, {}).get(mol_id)

    def get_job_meta(self, job_id: str) -> Optional[dict]:
        """Synchronous read for pipeline workers."""
        return self._jobs.get(job_id)


job_store = JobStore()

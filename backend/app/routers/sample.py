from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.core.job_store import job_store
from app.schemas.models import JobResponse, JobStatus, MoleculeResult
from app.services.pipeline import run_screening_pipeline

router = APIRouter(prefix="/sample", tags=["sample"])

_DATA_DIR = Path(__file__).resolve().parents[1] / "sample_data"
_PROTEIN = _DATA_DIR / "sample_protein.pdb"
_LIBRARY = _DATA_DIR / "sample_library.smi"
_PRECOMPUTED = _DATA_DIR / "sample_results.json"

_sample_job_id: str | None = None


@router.get("", summary="Describe the bundled demo dataset")
async def sample_info() -> dict:
    """Metadata about the built-in demo dataset so the UI can describe it."""
    if not _PROTEIN.exists() or not _LIBRARY.exists():
        raise HTTPException(status_code=404, detail="No demo dataset bundled")
    compounds = sum(
        1
        for line in _LIBRARY.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    )
    return {
        "protein": "KEAP1 Kelch domain (PDB 4L7B) — the sensor that switches on your cells' own antioxidant defenses",
        "protein_file": "sample_protein.pdb",
        "library_file": "sample_library.smi",
        "compounds": compounds,
        "default_top_k": 5,
    }


@router.post("/screen", response_model=JobResponse, status_code=202)
async def run_sample_screening(
    background_tasks: BackgroundTasks, request: Request, top_k: int = 5
) -> JobResponse:
    """
    Serve the demo screening. If sample_results.json is bundled, returns the
    precomputed results instantly (no compute); otherwise falls back to
    running the real 3-tier pipeline in the background.
    """
    if not _PROTEIN.exists() or not _LIBRARY.exists():
        raise HTTPException(status_code=500, detail="Sample dataset not bundled")

    client_ip = request.client.host if request.client else "unknown"

    if _PRECOMPUTED.exists():
        global _sample_job_id
        if _sample_job_id is None or await job_store.get(_sample_job_id) is None:
            payload = json.loads(_PRECOMPUTED.read_text())
            results = [MoleculeResult(**m) for m in payload["results"]]
            job_id = await job_store.create(
                _PROTEIN.name, _LIBRARY.name, top_k, client_ip
            )
            await job_store.update(
                job_id,
                status=JobStatus.done,
                progress=100.0,
                current_stage="Done — precomputed sample results",
                molecules_total=len(results),
                molecules_processed=len(results),
            )
            await job_store.set_results(job_id, results)
            for mol_id, pose in payload.get("poses", {}).items():
                await job_store.set_pose(job_id, mol_id, pose)
            _sample_job_id = job_id
        return await job_store.get(_sample_job_id)

    protein_bytes = _PROTEIN.read_bytes()
    library_bytes = _LIBRARY.read_bytes()

    job_id = await job_store.create(_PROTEIN.name, _LIBRARY.name, top_k, client_ip)
    background_tasks.add_task(
        run_screening_pipeline,
        job_id=job_id,
        protein_bytes=protein_bytes,
        library_bytes=library_bytes,
        library_filename=_LIBRARY.name,
        top_k=top_k,
    )
    return await job_store.get(job_id)

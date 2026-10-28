from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.job_store import job_store
from app.schemas.models import JobResponse
from app.services.pipeline import run_screening_pipeline

router = APIRouter(prefix="/sample", tags=["sample"])

_DATA_DIR = Path(__file__).resolve().parents[1] / "sample_data"
_PROTEIN = _DATA_DIR / "sample_protein.pdb"
_LIBRARY = _DATA_DIR / "sample_library.smi"


@router.get("", summary="Describe the bundled demo dataset")
async def sample_info() -> dict:
    """Metadata about the built-in demo dataset so the UI can describe it."""
    compounds = sum(
        1
        for line in _LIBRARY.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    )
    return {
        "protein": "HIV-1 protease (PDB 1HSG, with bound inhibitor L-735,524)",
        "protein_file": "sample_protein.pdb",
        "library_file": "sample_library.smi",
        "compounds": compounds,
        "default_top_k": 5,
    }


@router.post("/screen", response_model=JobResponse, status_code=202)
async def run_sample_screening(
    background_tasks: BackgroundTasks, top_k: int = 5
) -> JobResponse:
    """
    Run the full 3-tier pipeline on the bundled demo dataset.
    Same flow as POST /screen but no uploads needed.
    """
    if not _PROTEIN.exists() or not _LIBRARY.exists():
        raise HTTPException(status_code=500, detail="Sample dataset not bundled")

    protein_bytes = _PROTEIN.read_bytes()
    library_bytes = _LIBRARY.read_bytes()

    job_id = await job_store.create(_PROTEIN.name, _LIBRARY.name, top_k)
    background_tasks.add_task(
        run_screening_pipeline,
        job_id=job_id,
        protein_bytes=protein_bytes,
        library_bytes=library_bytes,
        library_filename=_LIBRARY.name,
        top_k=top_k,
    )
    return await job_store.get(job_id)

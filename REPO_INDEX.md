# REPO_INDEX — virtual-screener-ai-drug-discovery

State as of 2026-10-28. Keep this file current — it describes what exists, not history.

## What this is

VirtualScreener: 3-tier virtual screening app (RDKit filters → Chemprop + DeepChem
pIC50 ensemble → AutoDock Vina docking). FastAPI backend + React/Vite frontend.

## Live

- HF Space `devartslab/virtualscreener` → https://devartslab-virtualscreener.hf.space
- Railway project `keen-adventure` (backend) — dashboard status pending owner check

## Key paths

| Path                       | Purpose                                                          |
| -------------------------- | ---------------------------------------------------------------- |
| `backend/app/routers/`     | API: screening, jobs, molecules, **sample** (demo dataset)       |
| `backend/app/sample_data/` | bundled demo dataset (protein PDB + compound .smi + results)     |
| `backend/app/services/`    | pipeline, molecular_proc, ml_scoring, docking, protein_proc      |
| `backend/requirements.txt` | latest-stable pins; torch+cpu wheels; python 3.11 (deepchem cap) |
| `frontend/src/`            | SPA: Home (upload + demo button), Results, api client            |
| `Dockerfile`               | HF Spaces all-in-one build                                       |
| `docker-compose.yml`       | local backend(:8000)+frontend(:3000) dev stack                   |

## Verification (last run 2026-10-28)

Clean rebuild on new pins: `/health` 200, `/docs` 200, SPA 200,
`POST /api/sample/screen` → job done, top-K docked with real Vina scores
(Playwright E2E: demo button → results table + 3D poses + CSV export).
Upload caps enforced: 413 on >25 MB protein / >50 MB library.
Sample target: pending re-selection (previous bundled dataset removed).
Note: job store is in-memory — container restart wipes all results.

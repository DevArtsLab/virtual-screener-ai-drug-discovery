# REPO_INDEX — virtual-screener-ai-drug-discovery

State as of 2026-10-29. Keep this file current — it describes what exists, not history.

## What this is

VirtualScreener: 3-tier virtual screening app (RDKit filters → Chemprop + DeepChem
pIC50 ensemble → AutoDock Vina docking). FastAPI backend + React/Vite frontend.

## Live

- HF Space `amirolyaei/virtualscreener` → https://amirolyaei-virtualscreener.hf.space
  (org move to `devartslab` blocked: HF requires Team/Enterprise for org Docker Spaces)
- Railway project `keen-adventure`, service `virtualscreener` — trial expired,
  being spun down; HF is the live deployment. Re-setup: GitHub link + `HF_STATIC=1`
  - public domain → :8000.

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

## Verification (last run 2026-10-29)

Clean rebuild on new pins: `/health` 200, `/docs` 200, SPA 200,
`POST /api/sample/screen` → job done, top-K docked with real Vina scores
(Playwright E2E: demo button → results table + 3D poses + CSV export).
Upload caps enforced: 413 on >25 MB protein / >50 MB library.
Sample target: KEAP1 Kelch domain (PDB 4L7B, bound inhibitor) vs 12 dietary
NRF2 activators — wellness-themed demo, bound ligand gives real pocket detection.
Job store: SQLite-backed (`backend/data/jobs.db`), survives restarts;
bounded at 100 jobs / 24 h TTL. Compute POSTs rate-limited 10/min per IP +
max 2 concurrent active jobs per IP (429 on third).
Tier 2: real Chemprop checkpoint at `backend/models/chemprop_bindingdb.pt`
(ChEMBL-trained, val_loss 0.57); DeepChem still heuristic fallback.
Fixed `base_dir` off-by-one: paths now resolve under backend root, so
models/uploads/data volumes actually mount (previously `/models` etc.).
Deployed to HF via REST commit API + git-LFS (commit `13c91cc`); fine-grained
tokens cannot `git push`. Sample endpoint serves precomputed results
(`sample_results.json`) instantly — 202 in ~0.2s verified on HF.
Offline image backup: `~/projects/backups/virtual-screener-ai-drug-discovery/virtualscreener-images.tar.gz` (646MB, `docker load`).

---
title: VirtualScreener
emoji: 🧬
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8000
pinned: false
---

# VirtualScreener — AI Drug Discovery Platform

AI-powered virtual screening: upload a protein PDB + compound library → ranked
binding-affinity predictions via a 3-tier ML + physics pipeline.

## Live deployment

- **Hugging Face Spaces:** https://devartslab-virtualscreener.hf.space
  (Docker SDK, `devartslab/virtualscreener`). Free tier hibernates after ~48h idle;
  first request wakes it (~1-2 min cold start).
- **Railway:** project `keen-adventure` (backend deploy). Status: dashboard check pending.

## Try it without files

The Home page has a **Run demo dataset** button: it instantly shows the results
of the full pipeline on a bundled sample — KEAP1 Kelch domain (PDB 4L7B), the
sensor that switches on cellular antioxidant defenses, vs a 12-compound library
of dietary NRF2 activators (sulforaphane, resveratrol, curcumin, EGCG, and
friends) — and lands on the same results view as a real upload. Results are
precomputed
(`backend/app/sample_data/sample_results.json`) so the demo costs zero compute;
if that file is removed, `POST /api/sample/screen` falls back to running the
live pipeline. API: `GET /api/sample` (metadata), `POST /api/sample/screen`.

## Pipeline

| Tier  | Tool                                   | Task                                                |
| ----- | -------------------------------------- | --------------------------------------------------- |
| **1** | RDKit                                  | Lipinski Ro5 + PAINS filter, 2D SVG rendering       |
| **2** | Chemprop D-MPNN + DeepChem AttentiveFP | ML binding affinity (pIC50), MC-Dropout uncertainty |
| **3** | AutoDock Vina                          | Physics-based docking, 3D pose generation           |

ML checkpoints are optional: without `models/chemprop_bindingdb.pt` and
`models/attentivefp/`, tier 2 falls back to a fingerprint-similarity heuristic
and tier 3 still runs real Vina docking.

## Input formats

| File             | Format                   | Notes                            |
| ---------------- | ------------------------ | -------------------------------- |
| Protein          | `.pdb`                   | From RCSB or AlphaFold           |
| Compound library | `.smi` / `.txt` / `.csv` | One `SMILES name` per line       |
| Compound library | `.sdf`                   | Standard SDF with molecule names |

Upload caps: 25 MB protein, 50 MB library, 5,000 molecules per job
(`MAX_*` env vars in `app/core/config.py`).

Example `library.smi`:

```
CC(=O)Oc1ccccc1C(=O)O aspirin
CN1C=NC2=C1C(=O)N(C(=O)N2C)C caffeine
CC(C)Cc1ccc(cc1)C(C)C(=O)O ibuprofen
```

## Model checkpoints

- **Chemprop D-MPNN:** `backend/models/chemprop_bindingdb.pt` ships in the
  repo — a real MPNN trained on ~1.5k ChEMBL binding activities (val_loss
  0.57). Retrain your own with `chemprop train -i data.csv -s smiles
--target-columns pic50` and drop the result at the same path.
- **DeepChem AttentiveFP:** checkpoints are loaded from
  `backend/models/attentivefp/` when present; otherwise tier 2 scores on
  Chemprop alone plus a fingerprint-similarity heuristic fallback.
- Deploy note: `backend/.dockerignore` excludes `models/` from image
  context — mount the dir as a volume (compose does) or remove the rule to
  bake checkpoints into the image.

## Stack

- **Backend:** FastAPI on Python 3.11 (DeepChem caps the stack at 3.11).
  Latest-stable pins — fastapi 0.162, chemprop 2.3.1, deepchem 2.8.0,
  rdkit 2026.03.x, meeko 0.8 + gemmi, scipy 1.17.1.
- **Compute:** `torch 2.15.0+cpu` / `torchvision` — CPU-only wheels via
  `download.pytorch.org/whl/cpu`; the image does not ship multi-GB CUDA deps.
- **Docking:** system `autodock-vina` binary + `openbabel` (apt), `meeko` ligand prep.
- **Frontend:** React 19 + Vite + Tailwind, NGL 3D viewer, nginx static serving.
- **Jobs:** async job store persisted to SQLite (`backend/data/jobs.db`, volume-
  mounted in compose) — `POST /api/screen` returns 202 + job_id, poll
  `GET /api/jobs/{id}`; results via `GET /api/molecules/{id}`, pose + CSV
  export endpoints. Jobs survive restarts; bounded at 100 jobs / 24 h TTL.
- **Rate limit:** compute endpoints (`POST /screen`, `POST /sample/screen`)
  are capped at 10 jobs/minute per IP (429 + `Retry-After`), and each IP may
  hold at most 2 simultaneously active jobs (`MAX_CONCURRENT_JOBS_PER_IP`).
  Upload caps (25 MB protein, 50 MB library, 5,000 molecules) still apply.

## Quick start (Docker)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000 · Backend API docs: http://localhost:8000/docs

The root `Dockerfile` is the Hugging Face Spaces build (frontend built in-image,
FastAPI serves the SPA on :8000); `docker-compose.yml` runs the split
backend+frontend dev stack.

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # Vite dev server
```

## Deployment notes

- **HF Spaces:** push `main` to the Space remote; the root Dockerfile rebuilds.
- **Railway:** deploy from the repo Dockerfile or `backend/Dockerfile`. Railway
  supports always-on services (no execution ceiling; 15-min per-request cap,
  fine here since jobs are async-polled), persistent volumes, managed
  PostgreSQL/MySQL/Redis, and `railway ssh` container access.

## Screenshots

![Home](docs/screenshots/Screenshot%202026-05-08%20at%203.31.08%E2%80%AFPM.png)
![Demo dataset flow](docs/screenshots/Screenshot%202026-05-08%20at%203.31.24%E2%80%AFPM.png)
![Results](docs/screenshots/Screenshot%202026-10-29%20at%2012.59.59%E2%80%AFAM.png)

## Repo layout

```
backend/            FastAPI app (routers, services, pipeline)
  app/sample_data/  bundled demo dataset (protein + library + precomputed results)
frontend/           React + Vite + Tailwind SPA
docs/screenshots/   UI screenshots
Dockerfile          HF Spaces all-in-one image
docker-compose.yml  local two-service dev stack
```

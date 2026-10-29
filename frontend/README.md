# VirtualScreener Frontend

React 19 + Vite + Tailwind SPA for the VirtualScreener screening pipeline.

- `src/pages/Home.tsx` — landing + upload form + "Run demo dataset" button
- `src/pages/Results.tsx` — job progress + ranked results + 3D pose viewer
- `src/api/client.ts` — typed API client (screen, jobs, molecules, sample, pose, CSV)
- `src/components/` — UploadZone, ProgressTracker, ResultsTable, MolViewer (NGL), MolCard, DruglikenessRadar

Dev: `npm install && npm run dev` — set `VITE_API_URL` to reach the backend
(default `http://localhost:8000/api`).

Prod: `npm run build` → nginx serves `dist/` (see `frontend/Dockerfile` + `nginx.conf`).

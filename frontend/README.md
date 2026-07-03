# ShiftIQ Frontend

Next.js (App Router) + TypeScript + Tailwind web UI for ShiftIQ, replacing the
tkinter desktop app. Talks to the existing FastAPI service in the parent
directory (`../api.py`) over HTTP.

## Setup

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000 — it currently redirects to
`/components-preview`, a page showing every base UI component (Days 1-3
output). Real pages (Dashboard, Jobs, Shifts, Expenses, Simulation, Goals)
land in later days per the 30-day build plan.

## Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** — theme tokens in `tailwind.config.ts`, translated from
  the desktop app's `theme.py` palette
- **lucide-react** — icons
- Base components hand-written in the shadcn/ui pattern (`src/components/ui/`)
  rather than pulled from a registry, so they stay dependency-light and easy
  to restyle.

## Talking to the API

The backend lives at `../` (FastAPI, `api.py`). Once the API client lands
(Days 4-6), the frontend expects `NEXT_PUBLIC_API_URL` in `.env.local`,
defaulting to `http://localhost:8000` for local dev. Remember the API's
`CORS_ORIGINS` env var must include whatever origin this app runs on
(`http://localhost:3000` by default).

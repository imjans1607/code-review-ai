# Frontend — Review Dashboard (Module 6)

A React dashboard that visualizes the review history stored by the backend:
per-severity totals, a findings-over-time trend, and a browsable table of past
reviews with a per-review detail panel.

## Stack

- **Vite** + **React 19** + **TypeScript**
- **Tailwind CSS v4** + **shadcn/ui** (new-york style, slate base, CSS variables)
- **Recharts** for the charts, **lucide-react** for icons

## Run it

The dashboard reads from the backend API, so start the backend first:

```bash
# 1. backend (from ../backend)
python -m uvicorn app.main:app --port 8000

# 2. dashboard (from here)
npm install
npm run dev        # http://localhost:5173
```

Vite proxies `/api/*` to the backend on port 8000 (see `vite.config.ts`), so no
CORS setup is needed in dev. To populate the dashboard, run a few reviews via
`POST /review` (the backend saves each one).

## Layout

- `src/lib/api.ts` — typed client + response types (mirrors the backend JSON).
- `src/components/ui/` — shadcn primitives (card, badge, button, table).
- `src/components/` — dashboard pieces: `StatCards`, `SeverityChart`,
  `TrendChart`, `ReviewsTable`, `ReviewDetailPanel`.
- `src/App.tsx` — composes them, loads `/stats` + `/reviews`, handles the theme.

## Build

```bash
npm run build      # type-checks (tsc) then bundles to dist/
```

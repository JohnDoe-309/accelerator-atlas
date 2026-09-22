# Accelerator Atlas — Web App

Next.js 16 (App Router) + Tailwind v4 + TanStack Table + Recharts.
Reads static JSON at build time from `public/sample/` (the committed,
founder-free public sample, `make sample`). Set `ATLAS_DATA_DIR=data` to read
the full local export in `public/data/` instead (`make export`; git-ignored).

## Local dev

```bash
# From repo root:
cd web && pnpm install && pnpm dev    # sample data, http://localhost:3000
# Full local data (needs data/accelerators.db):
make web              # installs deps, exports full data, starts dev server
```

## Environment

Create `web/.env.local`:

```
XAI_API_KEY=xai-...   # only needed for the /api/nl-filter route
```

## Pages

- `/` — Overview: KPIs, accelerator cards, industry + batch-trend charts, funding-mentions snapshot
- `/explorer` — virtualized company table w/ facet filters, NL filter bar, Funding + Stage columns, detail drawer
- `/batches` — all 81 batches, sortable, deep-linking to Explorer
- `/accelerators/[slug]` — per-accelerator deep dive (YC / EF / SPC / Speedrun)
- `/founders` — serial founders detected across programs (full data only)
- `/survivorship` — cohort outcome mix + latest-batch table + leaderboards
- `/insights` — Grok markdown narratives + budget ledger
- `/data-quality` — field coverage matrix with traffic-light thresholds
- `/about` — methodology, data sources, caveats, reproducibility

## Deploy to Vercel

```bash
cd web && npx vercel
```

No env vars are needed. `XAI_API_KEY` only enables the NL filter bar; on a
public deploy anyone can call that route with your key.

Data refreshes are manual. Only the sample is committed:

```bash
make refresh-all   # re-scrape, enrich, re-synthesize, re-export
make sample        # regenerate public/sample/
git add web/public/sample && git commit
```

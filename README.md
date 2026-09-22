# Accelerator Atlas

Accelerator Atlas puts the portfolios of four startup programs into one
SQLite database and a Next.js explorer, so you can compare them side by side:
**Y Combinator**, **Entrepreneur First**, **South Park Commons** and
**a16z Speedrun**. It covers who each program funds, in which batches and
industries, and how many of those companies are still alive.

The public demo runs on a **300-company sample** of the 7,439 companies. It
includes no founder data. See [Public sample vs full data](#public-sample-vs-full-data).

## Data

Counts come from `data/accelerators.db`. The newest row was updated on
2026-09-06, and the counts were checked against the database on 2026-09-22.

| Accelerator | Companies | Founders | Batches | Source |
|---|---:|---:|---:|---|
| Y Combinator | 6,478 | 0 | 50 | [yc-oss/api](https://github.com/yc-oss/api), a public JSON mirror of the YC directory |
| Entrepreneur First | 527 | 1,012 | 13 | joinef.com portfolio |
| a16z Speedrun | 240 | 477 | 6 | speedrun.a16z.com public companies API |
| South Park Commons | 194 | 329 | 12 | southparkcommons.com company pages |
| **Total** | **7,439** | **1,818** | **81** | |

Status across all companies: 5,106 active, 831 acquired, 23 public, 1,479 dead.

Caveats:

- **No YC founders.** The database has no founder records for YC companies.
- **EF and SPC batches are made up.** Neither program publishes cohorts, so
  their "batches" are pseudo-batches built from founding year (`EF-2024`,
  `SPC-2024`). Speedrun batches are its real cohorts, SR001–SR006.
- **Some statuses are guesses.** EF doesn't publish status, so EF companies
  default to Active. YC, SPC and Speedrun statuses come from their own
  listings. An HTTP liveness probe of company websites then relabelled 416 of
  them, mostly to Dead: 321 at YC and 95 across the other three. A dead
  domain doesn't prove a dead company.
- **Funding and traction data is thin.** Those fields are mined from
  descriptions with conservative regexes. Treat them as a floor.

## Architecture

```
public accelerator directories
        │  src/accelerator_atlas/scrapers/   yc · ef · ef_overlay · spc · speedrun
        ▼
data/accelerators.db   (SQLite, SQLAlchemy models in schema/)
        │  src/accelerator_atlas/enrich/     liveness probe, YC re-tagging, locations,
        │                                    funding/traction text, serial founders
        │  src/accelerator_atlas/grok/       xAI Grok cohort narratives (budget-capped)
        ▼
src/accelerator_atlas/export/
        ├─ to_json.py → web/public/data/     full snapshot, local only, git-ignored
        └─ sample.py  → web/public/sample/   public sample, committed
        ▼
web/   Next.js 16 · React 19 · Tailwind v4 · TanStack Table · Recharts
       Every page is prerendered at build time from the JSON files.
       No database or server is involved.
```

`src/accelerator_atlas/dashboard/` holds an older Streamlit prototype. It
reads the SQLite database directly.

## Public sample vs full data

| | Public sample (`web/public/sample/`, committed) | Full data (local only) |
|---|---|---|
| Companies | 300: 75 per accelerator, taken from its 4 most recent batches in proportion to batch size | all 7,439 |
| Company fields | name, one-liner, website, industry, location, status, founded year, batch, founder **count** | all of those, plus long descriptions, logos, company LinkedIn/X, team size, stage, funding/traction mentions, raw source payloads |
| Founders | none | 1,818 founders with names and roles, plus LinkedIn URLs for 1,464 and photo URLs for 477 |
| Aggregates | totals per accelerator and per batch, industry mix, founded-year trend, field coverage, Grok narratives. These cover the **full** dataset | same |

The sample is deterministic. It uses a fixed seed and a fixed ordering, and
its timestamp is the database snapshot time, so rerunning `make sample` on the
same database produces identical files. The export stops with an error if any
founder name, founder URL or email address appears in its output.

The full dataset is available on request through the link on the demo site.

## Running it

**Web demo only.** This needs no database and no API keys.

```bash
cd web
pnpm install
pnpm dev        # http://localhost:3000
pnpm build      # static production build
```

**Full pipeline.** This needs Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
make install        # uv sync
make refresh-all    # seed, scrape all 4 programs, enrich, Grok synthesis, export
make sample         # regenerate web/public/sample/ from data/accelerators.db
make web-dev        # dev server on the full local export (ATLAS_DATA_DIR=data)
make help           # every target
```

Notes on the pipeline:

- **Scraping.** `make refresh-all` makes live requests to the accelerator sites
  and to every company website (the liveness probe). Run it rarely and keep
  the request rate low.
- **SPC and EF caches.** The SPC scraper parses pages cached in `.firecrawl/`
  by the Firecrawl CLI, and the EF scraper builds its cache with `--fetch`.
  The cache is git-ignored, so a fresh clone has to fetch it again.
- **Grok synthesis.** This step needs `XAI_API_KEY` in a local `.env` (optional: `GROK_BUDGET_USD`, and `ACCELERATOR_ATLAS_DB` to point at a different database file).
  Every call is logged to the `grok_usage` table, and the client enforces a
  hard cap of $50 by default (set `GROK_BUDGET_USD` to change it).
  `make budget` shows spend.

## Deploying to Vercel

Set the Vercel project root directory to `web/`. `web/vercel.json` already
sets the framework (Next.js) and the pnpm build commands, and the build needs
no environment variables. `web/.vercelignore` keeps the local full export
(`public/data/`) and `.env*` files out of CLI deploys.

The `/api/nl-filter` route, which powers the natural-language filter bar on
the Explorer, is the only server-side code. It calls xAI and needs
`XAI_API_KEY`. Without the key, that one feature returns an error and
everything else still works. Anyone who can reach a public deploy can use
that route, so setting the key there lets strangers spend your xAI credits.

## About the data

Everything here was compiled from public web pages: the accelerators' own
portfolio directories, plus the community-maintained yc-oss mirror of YC's
directory. The project isn't affiliated with or endorsed by any of the four
programs. Listings change, and statuses and industry labels are
heuristic, so expect errors. The source data stays subject to each site's
terms. The MIT license below covers this code, not the data. For corrections
or removal requests, open an issue.

## License

[MIT](LICENSE) © 2026 Siddansh Bohra

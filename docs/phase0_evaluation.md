# Phase 0 — OSS Hunt & Reuse Matrix

**Status:** GATE. Awaiting human approval before Phase 1.
**Date:** 2026-04-22
**Method:** Firecrawl searches across GitHub, Kaggle, HuggingFace, plus direct scrapes of official accelerator pages and top OSS repos.

---

## Headline finding

**YC is essentially solved by reuse.** The `yc-oss/api` project ships a daily-updated static JSON API with 5,690 companies, 100% status coverage, 96% team size, 99% website. Zero scraping required. Everything else is enrichment.

SPC, Speedrun, and EF have **no meaningful OSS**. All three must be scraped from their official portfolio pages, but the pages are relatively clean and each yields useful structured data.

---

## Reuse matrix

| Source | Accelerator | Last updated | Fields captured | Completeness | License | Reusable? | Gap to fill |
|---|---|---|---|---|---|---|---|
| [yc-oss/api](https://github.com/yc-oss/api) | YC | Daily | name, slug, website, batch, status, industry, subindustry, team_size, one_liner, long_description, tags, regions, stage, top_company, isHiring, nonprofit, launched_at, url | 5,690 companies, 100% status, 96.3% team_size, 99.4% website, 100% industry | MIT-style (public API) | **Yes, primary** | Funding rounds, revenue, founder identities, LinkedIn URLs |
| [corralm/yc-scraper](https://github.com/corralm/yc-scraper) | YC | Periodic | Similar superset, but requires scraping | Unknown; yc-oss supersedes | Open | No — redundant to yc-oss | — |
| [Santhusha-bit/YC-Tracker](https://github.com/Santhusha-bit/YC-Tracker) | YC | Unknown | Scraper + tracker | Likely stale | Open | No — redundant | — |
| [akshaybhalotia/yc_company_scraper](https://github.com/akshaybhalotia/yc_company_scraper) | YC | Periodic | Barebones listing | Redundant | Open | No | — |
| [thesephist/ycvibecheck](https://github.com/thesephist/ycvibecheck) | YC | Live | Embedding-based semantic search | N/A (product, not dataset) | Open | Inspiration only | Use idea of semantic search for dashboard Explorer page |
| [jeffboudier/yc-companies-august-2025 (HF)](https://huggingface.co/datasets/jeffboudier/yc-companies-august-2025) | YC | Aug 2025 snapshot | CSV mirror of yc-oss | Snapshot | Open | No — yc-oss is fresher | — |
| [datahiveai/ycombinator-companies (HF)](https://huggingface.co/datasets/datahiveai/ycombinator-companies) | YC | Unknown | Similar snapshot | Stale | Open | No | — |
| Multiple Kaggle datasets | YC | 2024-2025 snapshots | Various | Stale | CC-BY | No | — |
| [speedrun.a16z.com/companies](https://speedrun.a16z.com/companies) | a16z Speedrun | Live | Per-cohort: name, logo, employee count, location, tags (AI/B2B/etc), 1-liner (often with ARR/funding hints), founders | ~60 visible per cohort, 6 cohorts (SR001-SR006) => ~360 companies | ToS-governed; public info | **Scrape required** | Fuller funding detail, revenue, website URLs (companies link to detail pages) |
| No OSS found for Speedrun | a16z Speedrun | — | — | — | — | — | Build from scratch |
| [southparkcommons.com/companies](https://www.southparkcommons.com/companies/) | SPC | Live | Per-company: name, logo, sector, location, 1-liner, stage (Unicorn/Series A/etc. on highlights only), founders-by-first-name | ~40 on default page, highlights section has stage labels. Full list likely in a paginated or long-scroll view | ToS-governed | **Scrape required** | Batch dates (SPC doesn't run batches like YC), funding, team size, website, founder LinkedIn |
| No OSS found for SPC | SPC | — | — | — | — | — | Build from scratch |
| [joinef.com/portfolio](https://www.joinef.com/portfolio/) | EF | Live | Per-company: name, location, industry (multi-tag), 1-liner, founded year, lead funder, founders with LinkedIn URLs | 46 per page, paginated via `?pagenum=N`. EF has funded ~600 companies globally | ToS-governed | **Scrape required** | Team size, full funding rounds, revenue, cohort assignment (EF has location+year-based cohorts e.g., EF24-LON) |
| No OSS found for EF | EF | — | — | — | — | — | Build from scratch |

---

## Per-accelerator decisions

### YC (primary)

**Decision: fully reuse `yc-oss/api`. Zero scraping.**

- Ingestion: `curl https://yc-oss.github.io/api/companies/all.json` → 5,690 records in one shot. Idempotent, free, daily-refreshed.
- Sample fields already present: `id, name, slug, former_names, website, all_locations, long_description, one_liner, team_size, industry, subindustry, tags, top_company, isHiring, nonprofit, batch, status (Active|Acquired|Public|Inactive), regions, stage, launched_at, url`.
- **Status coverage is 100%.** 3,930 Active / 1,005 Inactive / 732 Acquired / 23 Public. No status inferrer needed for YC.
- **Team size coverage 96.3%.** No LinkedIn scraping needed for YC headcount.
- Batches span Summer 2005 → Summer 2026 (current).
- Enrichment work for YC (via Firecrawl + Grok): funding rounds, revenue estimates, founder identities + LinkedIn, richer country normalization.

Estimated records: **5,690**.

### SPC (secondary)

**Decision: scrape `southparkcommons.com/companies` + each company detail page.**

- Plan: scrape index to collect slugs → scrape each `/companies/<slug>` detail page in parallel (rate-limited).
- SPC does not use discrete batches; we'll use `joined_year` derived from founding date or "Highlights" stage label as a proxy for cohort.
- Gaps: no public team size, no funding detail, first-name-only founders. Enrichment will lift this via Firecrawl search + LinkedIn single-page.

Estimated records: **~300** (SPC has been iterating for ~8 years, highly selective).

### a16z Speedrun (secondary)

**Decision: scrape `speedrun.a16z.com/companies` per cohort.**

- Filter defaults to current cohort (SR006). Need to cycle SR001-SR006 via URL parameter or Firecrawl browser interaction.
- Each card already has employee count + ARR hints in 1-liner; high signal for a new accelerator.
- Detail pages `/companies/<slug>` contain fuller info.

Estimated records: **~360** across 6 cohorts.

### EF (secondary)

**Decision: scrape `joinef.com/portfolio/?pagenum=N` iteratively.**

- Paginated via `?pagenum=1..N`. 46 companies per page. Likely ~13 pages for ~600 companies.
- **Bonus:** founder LinkedIn URLs are already in the page markup — this is richer than SPC or Speedrun.
- Cohort = `founded_year + location` proxy (EF runs location-specific cohorts, e.g. London, Bangalore, Berlin, Paris, Singapore).

Estimated records: **~600**.

---

## Grand total ingestion estimate

| Accelerator | Companies | Effort |
|---|---|---|
| YC | 5,690 | One-shot curl |
| SPC | ~300 | Scrape index + detail pages |
| Speedrun | ~360 | Scrape per cohort |
| EF | ~600 | Paginated scrape |
| **Total** | **~6,950** | — |

---

## Enrichment budget sketch

Per the confirmed Grok $50 cap:

- ~6,950 companies × ~1,500 tokens avg (normalize tags + extract funding/revenue from news blob + one-liner rewrite) = ~10.4M tokens batch.
- At Grok-4-fast indicative rates (~$0.20/M input, ~$0.50/M output, mostly input-heavy): well under $30 for full batch.
- Reserves $20 for interactive chat (NL filter + ask-anything).

**Live-metered via `grok_usage` table; hard-stops at $50.**

---

## Risks flagged

1. **Speedrun cohort cycling** may need browser interaction (JS filter). Fallback: Firecrawl `browser` mode cycles through cohorts. Minor added complexity.
2. **SPC full-list discovery** — the default `/companies/` page shows ~40; may need JS interaction or site map crawl to find all ~300.
3. **EF Cloudflare** — EF page had cookie consent popup; Firecrawl handled the scrape but worth monitoring on pagination.
4. **Grok pricing** — actual xAI list prices may differ from the indicative figures above; budget guard is model-agnostic and reads `usage` from each response.
5. **LinkedIn enrichment** — we agreed to one cautious fetch per company; for 6,950 companies with Firecrawl concurrency=2 and rate-limit=1/sec this is ~2 hours. Acceptable.

---

## Ready for approval

With your approval, Phase 1 builds the repo skeleton and Phase 2 ingests YC via `yc-oss/api` (literally minutes).

Approve to proceed.

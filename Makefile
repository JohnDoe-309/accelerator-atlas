.PHONY: install init seed scrape-yc scrape-spc scrape-speedrun scrape-ef \
  enrich liveness locations retag-yc funding-text serial-founders grok-batch export sample \
  web-dev web-build web refresh-all budget clean help

PYTHON ?= uv run python

help:
	@echo "Accelerator Atlas - available targets:"
	@echo ""
	@echo "  Data layer (Python):"
	@echo "    install          - install Python deps via uv"
	@echo "    init             - create SQLite schema"
	@echo "    seed             - upsert the 4 accelerator meta rows"
	@echo "    scrape-yc        - ingest all YC companies (yc-oss/api)"
	@echo "    scrape-spc       - scrape SPC portfolio"
	@echo "    scrape-speedrun  - scrape a16z Speedrun cohorts"
	@echo "    scrape-ef        - scrape EF portfolio + overlays"
	@echo "    liveness         - HTTP liveness probe across all companies"
	@echo "    locations        - derive hq_location + country from all_locations (free)"
	@echo "    retag-yc         - deterministic YC industry re-classification"
	@echo "    funding-text     - extract funding mentions from descriptions"
	@echo "    traction-text    - extract traction metrics (users/revenue/GMV)"
	@echo "    serial-founders  - detect founders across accelerators"
	@echo "    grok-batch       - Grok synthesis pipeline (budget-tracked)"
	@echo "    export           - dump full DB snapshot to web/public/data/ (local only)"
	@echo "    sample           - write the public, founder-free sample to web/public/sample/"
	@echo ""
	@echo "  Web app (Next.js):"
	@echo "    web              - install web deps + export + dev"
	@echo "    web-dev          - run Next.js dev server on the full export (localhost:3000)"
	@echo "    web-build        - build static Next.js bundle from the committed sample"
	@echo ""
	@echo "  Utility:"
	@echo "    refresh-all      - full end-to-end refresh"
	@echo "    budget           - show Grok spend ledger"
	@echo "    clean            - remove DB, caches, web/.next"

install:
	uv sync

init:
	$(PYTHON) -c "from accelerator_atlas.storage.db import ensure_db; ensure_db()"

seed: init
	$(PYTHON) -m accelerator_atlas.scrapers.seed_all_accelerators

scrape-yc: init
	$(PYTHON) -m accelerator_atlas.scrapers.yc

scrape-spc: init
	$(PYTHON) -m accelerator_atlas.scrapers.spc

scrape-speedrun: init
	$(PYTHON) -m accelerator_atlas.scrapers.speedrun

scrape-ef: init
	$(PYTHON) -m accelerator_atlas.scrapers.ef --fetch

liveness:
	$(PYTHON) -m accelerator_atlas.enrich.liveness

locations:
	$(PYTHON) -m accelerator_atlas.enrich.locations


retag-yc:
	$(PYTHON) -m accelerator_atlas.enrich.retag_yc

funding-text:
	$(PYTHON) -m accelerator_atlas.enrich.funding_text

traction-text:
	$(PYTHON) -m accelerator_atlas.enrich.traction_text

serial-founders:
	$(PYTHON) -m accelerator_atlas.enrich.founders

grok-batch:
	$(PYTHON) -m accelerator_atlas.grok.synthesis

export:
	$(PYTHON) -m accelerator_atlas.export.to_json

sample:
	$(PYTHON) -m accelerator_atlas.export.sample

enrich: liveness retag-yc funding-text traction-text serial-founders
	$(PYTHON) -m accelerator_atlas.scrapers.ef_overlay

web-install:
	cd web && pnpm install

web-dev: export
	cd web && ATLAS_DATA_DIR=data pnpm dev

web-build:
	cd web && pnpm build

web: web-install export web-dev

refresh-all: seed scrape-yc scrape-spc scrape-speedrun scrape-ef \
  enrich locations grok-batch export

budget:
	$(PYTHON) -c "from accelerator_atlas.grok.client import print_budget; print_budget()"

clean:
	rm -rf data/accelerators.db data/raw data/processed logs/*.log web/.next web/node_modules
	@echo "Cleaned."

"""Upsert the four accelerator meta rows.

Safe to run repeatedly. Does not touch batches or companies.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from accelerator_atlas.schema.accelerators_seed import ACCELERATORS
from accelerator_atlas.schema.models import Accelerator
from accelerator_atlas.storage.db import session_scope

logger = logging.getLogger(__name__)


def seed_accelerators() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with session_scope() as s:
        for seed in ACCELERATORS:
            existing = s.scalar(select(Accelerator).where(Accelerator.slug == seed["slug"]))
            if existing is None:
                s.add(Accelerator(**seed))
                logger.info("Inserted accelerator: %s", seed["slug"])
            else:
                for k, v in seed.items():
                    setattr(existing, k, v)
                logger.info("Updated accelerator: %s", seed["slug"])


if __name__ == "__main__":
    seed_accelerators()

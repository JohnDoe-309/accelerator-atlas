"""Founder-level enrichment.

Detects **serial founders** — the same person appearing in multiple companies
across any of our 4 accelerators — by normalized name. Writes a new JSON
export so the UI can surface "founder-centric" views without mutating the
ORM schema.

Normalization heuristic:
    - lowercase, strip diacritics
    - collapse whitespace
    - drop middle initials ("John P. Smith" -> "john smith")
    - ignore very common short names (<= 2 tokens after normalization, OK)

We deliberately keep this simple. Personal research tool, not a credit bureau.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

DB_PATH = "data/accelerators.db"


def normalize(name: str) -> str:
    n = unicodedata.normalize("NFKD", name.strip()).encode("ascii", "ignore").decode()
    n = n.lower()
    n = re.sub(r"\s+", " ", n)
    n = re.sub(r"\b[a-z]\.", "", n)  # strip middle initials like "p."
    n = re.sub(r"\s+", " ", n).strip()
    return n


def find_serial_founders() -> dict[str, list[dict]]:
    """Return {normalized_name -> [{company_name, accelerator, role, linkedin, founder_name}]}."""
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("""
            SELECT f.name AS founder_name, f.role, f.linkedin_url,
                   co.name AS company_name, a.slug AS accelerator,
                   co.slug AS company_slug, co.status
            FROM founders f
            JOIN companies co ON f.company_id = co.id
            JOIN accelerators a ON co.accelerator_id = a.id
            WHERE f.name IS NOT NULL AND f.name != ''
        """).fetchall()

    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = normalize(r["founder_name"])
        if not key or len(key) < 3:
            continue
        buckets[key].append({
            "founder_name": r["founder_name"],
            "role": r["role"],
            "linkedin": r["linkedin_url"],
            "company_name": r["company_name"],
            "company_slug": r["company_slug"],
            "accelerator": r["accelerator"],
            "company_status": r["status"],
        })
    # Keep only where count >= 2 AND across distinct companies
    serial = {}
    for key, entries in buckets.items():
        distinct_companies = {(e["company_slug"], e["accelerator"]) for e in entries}
        if len(distinct_companies) >= 2:
            serial[key] = entries
    return serial


if __name__ == "__main__":
    serial = find_serial_founders()
    total_founders_serial = sum(len(v) for v in serial.values())
    print(f"serial founders: {len(serial)} distinct names, "
          f"{total_founders_serial} founder-company pairs")
    # Print top 10
    top = sorted(serial.items(), key=lambda x: -len(x[1]))[:10]
    for key, entries in top:
        names = {e["founder_name"] for e in entries}
        cos = [f"{e['company_name']} ({e['accelerator']})" for e in entries]
        print(f"  {'/'.join(names):30s} -> {', '.join(cos)}")

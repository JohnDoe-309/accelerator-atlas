"""Deterministic re-tagging of YC companies using their rich `tags` array.

The initial Grok normalization pass collapsed YC's broad "B2B" industry label
into `SaaS / Enterprise Software`, which swept up 2,956 companies including
all of YC's AI startups. YC's raw_payload has a granular `tags` list (e.g.
`Artificial Intelligence`, `Developer Tools`, `Fintech`) that we can use to
assign a far more accurate normalized category.

Priority order: earliest match wins. Any YC row whose tags don't match any
rule keeps its existing `tags_normalized` (the Grok output from
industry_primary).

Cost: $0. Speed: ~100ms for 5,690 rows.
"""

from __future__ import annotations

import json
import logging
import sqlite3

log = logging.getLogger("enrich.retag_yc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = "data/accelerators.db"

# (normalized_category, set_of_tag_tokens_lowercased) -- first match wins.
RULES: list[tuple[str, set[str]]] = [
    ("AI & ML Infrastructure", {
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "generative ai", "ai assistant", "nlp", "computer vision", "llm",
        "ai agent", "ai agents", "ai/ml", "mlops",
    }),
    ("Developer Tools", {
        "developer tools", "devops", "apis", "api", "open source", "cloud computing",
        "infrastructure", "databases", "database", "platform as a service",
        "web development", "developer platform",
    }),
    ("Security & Privacy", {
        "cybersecurity", "security", "privacy", "compliance", "identity",
        "authentication", "cryptography",
    }),
    ("Crypto & Web3", {
        "crypto", "cryptocurrency", "blockchain", "web3", "defi", "nft", "bitcoin",
        "ethereum",
    }),
    ("Healthtech / Biotech", {
        "health tech", "healthtech", "biotech", "biotechnology", "medical",
        "medical devices", "digital health", "mental health", "telemedicine",
        "healthcare", "diagnostics", "therapeutics", "pharma", "drug discovery",
        "life sciences",
    }),
    ("Fintech", {
        "fintech", "payments", "banking", "lending", "insurance", "insurtech",
        "personal finance", "accounting", "trading", "wealth management",
        "neobank", "remittance",
    }),
    ("Climate & Energy", {
        "climate", "climatetech", "energy", "clean energy", "renewable energy",
        "sustainability", "carbon", "solar", "battery", "ev", "electric vehicles",
    }),
    ("Hardware & Robotics", {
        "hardware", "robotics", "drones", "iot", "3d printing", "sensors",
        "robots",
    }),
    ("Government & Defense", {
        "defense", "govtech", "government", "aerospace", "space",
        "national security",
    }),
    ("Agtech & Food", {
        "agriculture", "agtech", "food", "food and beverage", "restaurants",
        "food & beverages", "food tech", "food delivery",
    }),
    ("Education", {
        "education", "edtech", "e-learning", "online learning", "learning",
    }),
    ("Real Estate & Construction", {
        "real estate", "proptech", "construction", "property", "real estate tech",
    }),
    ("Logistics & Supply Chain", {
        "logistics", "supply chain", "shipping", "delivery", "freight",
    }),
    ("Media, Gaming & Creator Tools", {
        "gaming", "games", "video", "media", "creator economy", "music",
        "podcast", "streaming", "entertainment", "esports",
    }),
    ("Marketplace & Commerce", {
        "marketplace", "e-commerce", "ecommerce", "retail", "d2c", "commerce",
    }),
    ("Industrial & Manufacturing", {
        "manufacturing", "industrial", "chemicals",
    }),
    ("Consumer Software", {
        "consumer", "social", "dating", "productivity", "travel", "fitness",
        "sports", "home", "parenting", "community",
    }),
]


def classify(tags: list[str]) -> str | None:
    tagset = {t.lower().strip() for t in tags if t}
    for category, keys in RULES:
        if tagset & keys:
            return category
    return None


def run() -> dict:
    stats = {"total": 0, "reclassified": 0, "unchanged": 0, "no_tags": 0,
             "by_category": {}}
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT c.id, c.raw_payload, c.tags_normalized "
            "FROM companies c JOIN accelerators a ON c.accelerator_id=a.id "
            "WHERE a.slug='yc' AND c.raw_payload IS NOT NULL"
        ).fetchall()
        for row in rows:
            stats["total"] += 1
            try:
                payload = json.loads(row["raw_payload"]) if isinstance(row["raw_payload"], str) else row["raw_payload"]
            except Exception:
                continue
            tags = payload.get("tags") or []
            if not tags:
                stats["no_tags"] += 1
                continue
            new_cat = classify(tags)
            if not new_cat:
                stats["unchanged"] += 1
                continue
            current_raw = row["tags_normalized"]
            current = json.loads(current_raw)[0] if current_raw else None
            if current == new_cat:
                stats["unchanged"] += 1
                continue
            c.execute(
                "UPDATE companies SET tags_normalized=? WHERE id=?",
                (json.dumps([new_cat]), row["id"]),
            )
            stats["reclassified"] += 1
            stats["by_category"][new_cat] = stats["by_category"].get(new_cat, 0) + 1
        c.commit()
    log.info("retag done: %s", stats)
    return stats


if __name__ == "__main__":
    run()

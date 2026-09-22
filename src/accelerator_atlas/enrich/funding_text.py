"""Extract funding-round mentions from existing text fields.

No external scraping. Scans `one_liner` + `long_description` for money amounts
with surrounding context (e.g. "raised $5m in Series A"). The intent is to
surface what's ALREADY in the corpus, not to claim comprehensive coverage.

Every row we touch gets:
    - total_funding_usd       (numeric estimate in USD)
    - total_funding_source    (e.g. "regex:long_description")
    - total_funding_confidence (0..1)
    - last_round_type         (Pre-seed | Seed | Series A-F | Grant | Debt | ...)

Confidence is deliberately capped at 0.6 because descriptions can be aspirational
or out of date. Anything needing real precision should go through a proper
Firecrawl + Grok pipeline later.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

log = logging.getLogger("enrich.funding_text")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = "data/accelerators.db"

MULTIPLIERS = {
    "k": 1_000,
    "K": 1_000,
    "m": 1_000_000,
    "M": 1_000_000,
    "mm": 1_000_000,
    "b": 1_000_000_000,
    "B": 1_000_000_000,
    "bn": 1_000_000_000,
}

AMOUNT_NUM = r"([0-9]{1,4}(?:[\.,][0-9]{1,3})?)\s*(k|K|m|M|mm|b|B|bn|million|Million|billion|Billion|thousand|Thousand)?"

WORD_MULTIPLIER = {
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "thousand": 1_000,
}

# High-precision funding patterns. $ amount must appear in a phrase that
# unambiguously describes a raise, not a market/valuation/revenue figure.
FUNDING_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "raised",
        re.compile(
            rf"\b(?:have\s+)?(?:raise[ds]|raising|secured|closed)\s+(?:a\s+|an\s+|our\s+|their\s+|more\s+than\s+|over\s+)?"
            rf"\$\s*{AMOUNT_NUM}(?:\s+(?:in|of|from))?",
            re.I,
        ),
    ),
    (
        "round",
        re.compile(
            rf"\$\s*{AMOUNT_NUM}\s+(?:pre[- ]?seed|seed|series\s+[a-f]|round|raise|funding)",
            re.I,
        ),
    ),
    (
        "seed_of",
        re.compile(
            rf"\b(?:pre[- ]?seed|seed|series\s+[a-f])\s+(?:round|of|at)\s+\$\s*{AMOUNT_NUM}",
            re.I,
        ),
    ),
    (
        "backed_by",
        re.compile(
            rf"\bbacked\s+by\s+\$\s*{AMOUNT_NUM}\s+(?:in\s+)?(?:funding|investment|capital)",
            re.I,
        ),
    ),
    (
        "total_funding",
        re.compile(
            rf"\btotal\s+(?:funding|raised)\s*:?\s*\$\s*{AMOUNT_NUM}",
            re.I,
        ),
    ),
]

# Round-type detector — applied to the matched snippet.
ROUND_RULES: list[tuple[str, re.Pattern]] = [
    ("Series F", re.compile(r"\bseries\s+f\b", re.I)),
    ("Series E", re.compile(r"\bseries\s+e\b", re.I)),
    ("Series D", re.compile(r"\bseries\s+d\b", re.I)),
    ("Series C", re.compile(r"\bseries\s+c\b", re.I)),
    ("Series B", re.compile(r"\bseries\s+b\b", re.I)),
    ("Series A", re.compile(r"\bseries\s+a\b", re.I)),
    ("Seed", re.compile(r"\bseed\s+(?:round|funding|investment|of|at)?\b", re.I)),
    ("Pre-seed", re.compile(r"\bpre[- ]?seed\b", re.I)),
    ("Grant", re.compile(r"\bgrant(?:ed)?\b", re.I)),
    ("Debt", re.compile(r"\bdebt\s+(?:financing|round)\b", re.I)),
]

# Words near the $amount that disqualify it (market size, valuation, revenue,
# customer-traction claims, charitable giving, partnership value).
DISQUALIFIERS = re.compile(
    r"\b(valuation|valued|worth|market|industry|opportunity|tam|arr|revenue|gmv|"
    r"sales|aum|assets\s+under|spending|transactions|gdp|economy|budget|expenditure|"
    r"charity|partnership|partnerships|customers|clients|portfolio|"
    r"startups\s+that|companies\s+that|firms\s+that)\b",
    re.I,
)


@dataclass
class FundingHit:
    amount_usd: int
    round_type: str | None
    snippet: str  # ±40 char window
    confidence: float


def parse_amount(raw_num: str, suffix: str | None, word: str | None) -> int | None:
    try:
        val = float(raw_num.replace(",", ""))
    except ValueError:
        return None
    if suffix:
        if suffix in MULTIPLIERS:
            val *= MULTIPLIERS[suffix]
        elif suffix.lower() in WORD_MULTIPLIER:
            val *= WORD_MULTIPLIER[suffix.lower()]
    elif word and word.lower() in WORD_MULTIPLIER:
        val *= WORD_MULTIPLIER[word.lower()]
    elif val < 1000:
        # Too small to be plausibly a funding figure without a multiplier.
        return None
    if val < 10_000 or val > 100_000_000_000:
        return None
    return int(val)


def extract(text: str) -> list[FundingHit]:
    if not text:
        return []
    hits: list[FundingHit] = []
    for pattern_name, pat in FUNDING_PATTERNS:
        for m in pat.finditer(text):
            num, suffix = m.group(1), m.group(2)
            amount = parse_amount(num, suffix, suffix)
            if amount is None:
                continue
            # Sanity cap — no startup in our corpus plausibly raised >$50B.
            if amount > 50_000_000_000:
                continue
            start = max(0, m.start() - 60)
            end = min(len(text), m.end() + 60)
            window = text[start:end]
            if DISQUALIFIERS.search(window):
                continue
            round_type = None
            for name, rpat in ROUND_RULES:
                if rpat.search(window):
                    round_type = name
                    break
            confidence = 0.65 if round_type else 0.5
            hits.append(FundingHit(amount, round_type, window.strip(), confidence))
    return hits


def run(dry_run: bool = False) -> dict:
    stats = {"scanned": 0, "matched": 0, "by_round": {}, "sum_usd": 0}
    now = datetime.now(UTC).replace(tzinfo=None)

    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        # Reset prior (noisy) extractions so we can re-run idempotently.
        if not dry_run:
            c.execute(
                "UPDATE companies SET total_funding_usd=NULL, "
                "total_funding_source=NULL, total_funding_confidence=NULL, "
                "last_round_type=NULL WHERE total_funding_source LIKE 'regex:%'"
            )
        rows = c.execute("""
            SELECT id, one_liner, long_description
            FROM companies
            WHERE (one_liner IS NOT NULL OR long_description IS NOT NULL)
        """).fetchall()

        for row in rows:
            stats["scanned"] += 1
            text = " ".join(filter(None, [row["one_liner"], row["long_description"]]))
            hits = extract(text)
            if not hits:
                continue
            # Pick the biggest amount; assume it's "total raised" or largest round.
            best = max(hits, key=lambda h: h.amount_usd)
            stats["matched"] += 1
            if best.round_type:
                stats["by_round"][best.round_type] = stats["by_round"].get(best.round_type, 0) + 1
            stats["sum_usd"] += best.amount_usd
            if not dry_run:
                c.execute(
                    "UPDATE companies SET total_funding_usd=?, "
                    "total_funding_source=?, total_funding_confidence=?, "
                    "last_round_type=? WHERE id=?",
                    (
                        best.amount_usd,
                        "regex:description",
                        best.confidence,
                        best.round_type,
                        row["id"],
                    ),
                )
        if not dry_run:
            c.commit()
    log.info("funding text extraction: %s", stats)
    return stats


if __name__ == "__main__":
    run()

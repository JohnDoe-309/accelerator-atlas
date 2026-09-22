"""Extract traction metrics (revenue, users, customers, growth) from text fields.

Similar to funding_text.py — this is high-precision, low-recall extraction from
existing descriptions. Searches for explicit mentions of:
    - ARR / MRR / revenue (annual/monthly recurring revenue)
    - User counts (MAU, DAU, "X million users", "Y customers")
    - Growth rates ("X% MoM", "Y% YoY", "doubled every Z months")
    - Transaction volume / GMV (for marketplaces)

All extracted values are estimates based on self-reported claims in descriptions.
They represent what the company said at some point in time — not verified,
not current, not audited.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

log = logging.getLogger("enrich.traction_text")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = "data/accelerators.db"


@dataclass
class TractionHit:
    metric_type: Literal["revenue_arr", "revenue_mrr", "users", "customers", "gmv", "growth_rate"]
    value_numeric: float | int  # normalized value (e.g., 1000000 for $1M)
    value_raw: str  # original text captured
    period: str | None  # "monthly", "annual", "daily", etc.
    snippet: str  # context window
    confidence: float


# Revenue patterns
RE_ARR = re.compile(
    r"\b(\$?\s*[0-9]{1,4}(?:\.[0-9])?\s*(?:m|mm|mil|million|b|bn|billion)?\s*(?:arr|annual\s+recurring\s+revenue|annual\s+revenue))\b",
    re.I,
)
RE_MRR = re.compile(
    r"\b(\$?\s*[0-9]{1,4}(?:\.[0-9])?\s*(?:k|m|mil|million)?\s*(?:mrr|monthly\s+recurring\s+revenue|monthly\s+revenue))\b",
    re.I,
)

# User/customer patterns
RE_USERS = re.compile(
    r"\b([0-9]{1,3}(?:\.[0-9])?\s*(?:m|mil|million|k|thousand|b|bn|billion)?\s*(?:users?|customers?|clients?|maus?|daus?|subscribers?))\b",
    re.I,
)
RE_USER_COUNT = re.compile(
    r"\b([0-9,]+(?:\s*mil(?:lion)?|\s*bil(?:lion)?|\s*k)?)\s+(?:monthly|daily|weekly|active)?\s*(?:users?|customers?)\b",
    re.I,
)

# Growth patterns
RE_GROWTH = re.compile(
    r"\b([0-9]{1,3}(?:\.[0-9])?%?)\s*(?:moM|month[- ]over[- ]month|qoq|quarter[- ]over[- ]quarter|yoy|year[- ]over[- ]year|annual)\s+growth\b",
    re.I,
)

# GMV / transaction volume (marketplaces)
RE_GMV = re.compile(
    r"\b(\$?\s*[0-9]{1,4}(?:\.[0-9])?\s*(?:m|mm|mil|million|b|bn|billion)?\s*(?:gmv|gross?\s+merchandise?\s+volume|transaction(?:s)?|processed))\b",
    re.I,
)

# Disqualifiers (things that look like traction but aren't)
DISQUALIFIERS = re.compile(
    r"\b(market\s+size|tam|sam|addressable|potential|could|might|projected|estimated|forecast|target|goal|aim)\b",
    re.I,
)


def parse_money(raw: str) -> int | None:
    """Parse '$5M ARR' or '10 million ARR' into integer dollars."""
    raw = raw.lower().replace(",", "").replace("$", "").strip()
    # Extract number
    num_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
    if not num_match:
        return None
    try:
        val = float(num_match.group(1))
    except ValueError:
        return None
    # Multipliers
    if "billion" in raw or "bn" in raw or " b" in raw:
        val *= 1_000_000_000
    elif "million" in raw or "mil" in raw or " mm" in raw or " m" in raw:
        val *= 1_000_000
    elif "k" in raw or "thousand" in raw:
        val *= 1_000
    # Sanity bounds
    if val < 1_000 or val > 100_000_000_000:
        return None
    return int(val)


def parse_count(raw: str) -> int | None:
    """Parse '5M users' or '500K customers' into integer count."""
    raw = raw.lower().replace(",", "").strip()
    num_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
    if not num_match:
        return None
    try:
        val = float(num_match.group(1))
    except ValueError:
        return None
    if "billion" in raw or "bn" in raw or " b" in raw:
        val *= 1_000_000_000
    elif "million" in raw or "mil" in raw or " m" in raw:
        val *= 1_000_000
    elif "k" in raw or "thousand" in raw:
        val *= 1_000
    if val < 100 or val > 10_000_000_000:
        return None
    return int(val)


def extract(text: str) -> list[TractionHit]:
    """Extract all traction metrics from a text block."""
    if not text:
        return []
    hits: list[TractionHit] = []
    
    for pattern, metric_type, parser, period in [
        (RE_ARR, "revenue_arr", parse_money, "annual"),
        (RE_MRR, "revenue_mrr", parse_money, "monthly"),
        (RE_USERS, "users", parse_count, None),
        (RE_USER_COUNT, "users", parse_count, None),
        (RE_GMV, "gmv", parse_money, None),
    ]:
        for m in pattern.finditer(text):
            raw = m.group(0)
            window_start = max(0, m.start() - 60)
            window_end = min(len(text), m.end() + 60)
            window = text[window_start:window_end]
            
            if DISQUALIFIERS.search(window):
                continue
            
            val = parser(raw)
            if val is None:
                continue
            
            # Determine period from context
            ctx_lower = window.lower()
            det_period = period
            if "monthly" in ctx_lower or "mrr" in ctx_lower or "month" in ctx_lower:
                det_period = "monthly"
            elif "annual" in ctx_lower or "arr" in ctx_lower or "year" in ctx_lower:
                det_period = "annual"
            elif "daily" in ctx_lower or "dau" in ctx_lower:
                det_period = "daily"
            
            hits.append(TractionHit(
                metric_type=metric_type,
                value_numeric=val,
                value_raw=raw,
                period=det_period,
                snippet=window.strip(),
                confidence=0.55 if metric_type in ("revenue_arr", "revenue_mrr") else 0.45,
            ))
    
    # Growth rates (keep as percentage string for now)
    for m in RE_GROWTH.finditer(text):
        raw = m.group(0)
        window_start = max(0, m.start() - 40)
        window_end = min(len(text), m.end() + 40)
        window = text[window_start:window_end]
        
        pct_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", raw)
        if pct_match:
            try:
                pct = float(pct_match.group(1))
                if 5 <= pct <= 500:  # Sane growth range
                    hits.append(TractionHit(
                        metric_type="growth_rate",
                        value_numeric=pct,
                        value_raw=raw,
                        period=None,
                        snippet=window.strip(),
                        confidence=0.4,
                    ))
            except ValueError:
                pass
    
    return hits


def run(dry_run: bool = False) -> dict:
    stats = {
        "scanned": 0,
        "with_traction": 0,
        "by_type": {},
        "top_arr": [],
    }
    
    with sqlite3.connect(DB_PATH) as c:
        c.row_factory = sqlite3.Row
        
        # Check if traction columns exist
        cols = [row[1] for row in c.execute("PRAGMA table_info(companies)")]
        needed_cols = [
            "traction_arr_usd",
            "traction_mrr_usd", 
            "traction_users",
            "traction_customers",
            "traction_gmv_usd",
            "traction_growth_rate",
            "traction_source",
            "traction_confidence",
            "traction_snippet",
        ]
        for col in needed_cols:
            if col not in cols:
                c.execute(f"ALTER TABLE companies ADD COLUMN {col} FLOAT")
        c.commit()
        
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
            
            stats["with_traction"] += 1
            
            # Keep the highest-confidence hit per metric type
            best_by_type: dict[str, TractionHit] = {}
            for h in hits:
                if h.metric_type not in best_by_type:
                    best_by_type[h.metric_type] = h
                elif h.confidence > best_by_type[h.metric_type].confidence:
                    best_by_type[h.metric_type] = h
            
            # Update stats
            for t, h in best_by_type.items():
                stats["by_type"][t] = stats["by_type"].get(t, 0) + 1
                if t == "revenue_arr" and len(stats["top_arr"]) < 10:
                    stats["top_arr"].append((row["id"], h.value_numeric))
            
            if not dry_run:
                # Build update
                updates = {}
                for t, h in best_by_type.items():
                    if t == "revenue_arr":
                        updates["traction_arr_usd"] = h.value_numeric
                    elif t == "revenue_mrr":
                        updates["traction_mrr_usd"] = h.value_numeric
                    elif t == "users":
                        updates["traction_users"] = h.value_numeric
                    elif t == "customers":
                        updates["traction_customers"] = h.value_numeric
                    elif t == "gmv":
                        updates["traction_gmv_usd"] = h.value_numeric
                    elif t == "growth_rate":
                        updates["traction_growth_rate"] = h.value_numeric
                    updates["traction_source"] = "regex:description"
                    updates["traction_confidence"] = h.confidence
                    updates["traction_snippet"] = h.snippet[:280]
                
                if updates:
                    cols = ", ".join([f"{k}=?" for k in updates.keys()])
                    vals = list(updates.values()) + [row["id"]]
                    c.execute(f"UPDATE companies SET {cols} WHERE id=?", vals)
        
        if not dry_run:
            c.commit()
    
    stats["top_arr"] = sorted(stats["top_arr"], key=lambda x: -x[1])[:10]
    log.info("traction extraction: %s", stats)
    return stats


if __name__ == "__main__":
    run()

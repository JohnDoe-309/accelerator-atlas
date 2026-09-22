"""Derive `hq_location` and `country` from the `all_locations` string.

`all_locations` is populated for 7,252 of 7,439 companies; `hq_location` was
populated for zero and `country` for 240. Every geography filter downstream was
therefore dead code that silently scored nothing. This costs no API credits —
it is string work over data we already hold.

Format observed across all four accelerators:

    "San Francisco, CA, USA"                  city, region, country
    "San Francisco, CA, USA; Remote"          semicolon-separated alternates
    "London, England, United Kingdom"
    "London"                                  bare city (22 distinct values)
    "Remote"                                  no physical HQ

Rule: the first segment that is not "Remote" is the HQ. Country comes from the
last comma-part if it names a country, else any part that does, else a lookup
of the bare city. Anything unresolved is left NULL rather than guessed — a
wrong country is worse than a missing one for a relocation decision.
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from accelerator_atlas.schema.models import Company
from accelerator_atlas.storage.db import session_scope

log = logging.getLogger("enrich.locations")

# Canonical country names, keyed by every alias observed in the data.
COUNTRY_ALIASES: dict[str, str] = {
    "usa": "United States", "us": "United States", "u.s.": "United States",
    "u.s.a.": "United States", "united states": "United States",
    "united states of america": "United States", "america": "United States",
    "uk": "United Kingdom", "u.k.": "United Kingdom",
    "united kingdom": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom",
    "northern ireland": "United Kingdom", "great britain": "United Kingdom",
    "uae": "United Arab Emirates", "united arab emirates": "United Arab Emirates",
    "south korea": "South Korea", "korea": "South Korea",
    "republic of korea": "South Korea",
    "hong kong": "Hong Kong", "hong kong sar": "Hong Kong",
    "czechia": "Czech Republic", "czech republic": "Czech Republic",
    "the netherlands": "Netherlands", "netherlands": "Netherlands",
    "holland": "Netherlands",
}
for _c in (
    "India", "Canada", "Singapore", "France", "Germany", "Mexico", "Brazil",
    "Nigeria", "Israel", "Indonesia", "Colombia", "Spain", "Sweden",
    "Australia", "Argentina", "Chile", "Denmark", "Switzerland", "Pakistan",
    "Kenya", "Norway", "Ireland", "Philippines", "Malaysia", "Japan", "China",
    "Italy", "Portugal", "Poland", "Finland", "Belgium", "Austria", "Ghana",
    "Egypt", "South Africa", "Vietnam", "Thailand", "Turkey", "Ukraine",
    "New Zealand", "Peru", "Uruguay", "Estonia", "Lithuania", "Latvia",
    "Romania", "Bulgaria", "Greece", "Hungary", "Croatia", "Serbia", "Iceland",
    "Luxembourg", "Bangladesh", "Sri Lanka", "Nepal", "Rwanda", "Uganda",
    "Tanzania", "Senegal", "Morocco", "Tunisia", "Algeria", "Ecuador",
    "Costa Rica", "Panama", "Guatemala", "Bolivia", "Paraguay", "Venezuela",
    "Saudi Arabia", "Qatar", "Kuwait", "Bahrain", "Oman", "Jordan", "Lebanon",
    "Taiwan", "Cambodia", "Myanmar", "Mongolia", "Kazakhstan", "Georgia",
    "Armenia", "Azerbaijan", "Slovenia", "Slovakia", "Malta", "Cyprus",
    "Bermuda", "Russia", "Puerto Rico", "Iraq", "Kyrgyzstan", "Zambia",
    "Ethiopia", "Cayman Islands", "Ivory Coast", "Bhutan", "Maldives",
    "Democratic Republic of the Congo",
):
    COUNTRY_ALIASES[_c.lower()] = _c

# Bare-city values that appear with no country attached. Exhaustive against the
# 22 distinct values in the corpus; extra entries cover likely future batches.
CITY_COUNTRY: dict[str, str] = {
    "london": "United Kingdom", "san francisco": "United States",
    "paris": "France", "singapore": "Singapore", "bangalore": "India",
    "bengaluru": "India", "new york": "United States",
    "new york city": "United States", "berlin": "Germany",
    "toronto": "Canada", "hong kong": "Hong Kong",
    "los angeles": "United States", "denver": "United States",
    "miami": "United States", "vancouver": "Canada",
    "boston": "United States", "chicago": "United States",
    "seattle": "United States", "austin": "United States",
    "mumbai": "India", "delhi": "India", "new delhi": "India",
    "gurgaon": "India", "gurugram": "India", "hyderabad": "India",
    "chennai": "India", "pune": "India", "noida": "India",
    "tel aviv": "Israel", "dubai": "United Arab Emirates",
    "amsterdam": "Netherlands", "dublin": "Ireland", "sydney": "Australia",
    "melbourne": "Australia", "tokyo": "Japan", "seoul": "South Korea",
    "sao paulo": "Brazil", "são paulo": "Brazil", "mexico city": "Mexico",
    "lagos": "Nigeria", "nairobi": "Kenya", "stockholm": "Sweden",
    "zurich": "Switzerland", "munich": "Germany", "barcelona": "Spain",
    "madrid": "Spain", "milan": "Italy", "lisbon": "Portugal",
    "warsaw": "Poland", "copenhagen": "Denmark", "oslo": "Norway",
    "helsinki": "Finland", "brussels": "Belgium", "vienna": "Austria",
    "montreal": "Canada", "waterloo": "Canada", "cambridge": "United Kingdom",
    "oxford": "United Kingdom", "edinburgh": "United Kingdom",
    "manchester": "United Kingdom", "jakarta": "Indonesia",
    "manila": "Philippines", "bangkok": "Thailand", "hanoi": "Vietnam",
    "kuala lumpur": "Malaysia", "taipei": "Taiwan", "shanghai": "China",
    "beijing": "China", "shenzhen": "China", "bogota": "Colombia",
    "buenos aires": "Argentina", "santiago": "Chile", "lima": "Peru",
    "cairo": "Egypt", "cape town": "South Africa",
    "johannesburg": "South Africa", "accra": "Ghana",
}

# Values that carry no geographic meaning.
NOISE = {"remote", "other", "external", "n/a", "none", "worldwide", "global", "anywhere"}


def parse_location(all_locations: str | None) -> tuple[str | None, str | None]:
    """Return (hq_location, country). Either may be None."""
    if not all_locations:
        return None, None

    segments = [s.strip() for s in all_locations.split(";") if s.strip()]
    physical = [s for s in segments if s.lower() not in NOISE]
    if not physical:
        return None, None

    hq = physical[0]
    parts = [p.strip() for p in hq.split(",") if p.strip()]
    if not parts:
        return None, None

    # Drop trailing noise like "San Francisco, CA, USA, Remote".
    parts = [p for p in parts if p.lower() not in NOISE] or parts

    country = COUNTRY_ALIASES.get(parts[-1].lower())
    if country is None:
        for p in reversed(parts):
            if p.lower() in COUNTRY_ALIASES:
                country = COUNTRY_ALIASES[p.lower()]
                break
    if country is None:
        country = CITY_COUNTRY.get(parts[0].lower())

    hq_clean = ", ".join(parts)
    if hq_clean.lower() in NOISE:
        return None, country
    return hq_clean[:128], country


def run(*, dry_run: bool = False, batch_size: int = 500) -> dict[str, int]:
    stats = {"seen": 0, "hq_set": 0, "country_set": 0, "unresolved": 0}
    now = datetime.now(UTC)

    with session_scope() as s:
        companies = s.execute(select(Company)).scalars().all()
        for i, c in enumerate(companies, 1):
            stats["seen"] += 1
            hq, country = parse_location(c.all_locations)
            if hq and hq != c.hq_location:
                if not dry_run:
                    c.hq_location = hq
                stats["hq_set"] += 1
            if country and country != c.country:
                if not dry_run:
                    c.country = country
                stats["country_set"] += 1
            if c.all_locations and not country:
                stats["unresolved"] += 1
            if not dry_run and i % batch_size == 0:
                s.flush()
        if dry_run:
            s.rollback()
    stats["elapsed_s"] = int((datetime.now(UTC) - now).total_seconds())
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Derive hq_location + country from all_locations")
    ap.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    args = ap.parse_args()

    stats = run(dry_run=args.dry_run)
    log.info(
        "%s seen=%d hq_set=%d country_set=%d unresolved=%d",
        "DRY RUN" if args.dry_run else "wrote",
        stats["seen"], stats["hq_set"], stats["country_set"], stats["unresolved"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

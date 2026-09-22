"""Hand-curated metadata for the four accelerators.

Sources: each accelerator's public website, Wikipedia, Crunchbase summary pages.
Numbers are intentionally round/approximate where ranges are published (e.g.,
EF's investment bands vary by location). Totals reflect public figures as of
early 2026.
"""

from __future__ import annotations

ACCELERATORS: list[dict] = [
    {
        "slug": "yc",
        "name": "Y Combinator",
        "founded_year": 2005,
        "hq_location": "San Francisco, CA, USA",
        "website": "https://www.ycombinator.com",
        "founders": [
            {"name": "Paul Graham", "role": "Co-founder"},
            {"name": "Jessica Livingston", "role": "Co-founder"},
            {"name": "Robert Morris", "role": "Co-founder"},
            {"name": "Trevor Blackwell", "role": "Co-founder"},
        ],
        "program_duration_weeks": 12,
        "investment_amount_usd": 500_000,
        "investment_equity_pct": 7.0,
        "investment_terms_note": (
            "$500K total: $125K SAFE for 7% + $375K uncapped SAFE with MFN. "
            "Standard terms since 2022."
        ),
        "batch_cadence": "quarterly",
        "focus_areas": ["all sectors", "AI-heavy recent", "software", "biotech", "hard tech"],
        "description": (
            "The most prolific startup accelerator. Founded in 2005 in Cambridge MA, moved to "
            "Mountain View then SF. Alumni include Stripe, Airbnb, Dropbox, DoorDash, Coinbase, "
            "Reddit, Instacart, Twitch, Cruise. Now runs four batches a year."
        ),
        "total_companies_funded": 5690,
        "notable_alumni": [
            "Stripe", "Airbnb", "Dropbox", "DoorDash", "Coinbase", "Reddit",
            "Instacart", "Twitch", "Cruise", "Brex", "Rippling", "Faire", "Gusto",
        ],
        "data_sources": ["yc_oss_api", "ycombinator.com"],
    },
    {
        "slug": "spc",
        "name": "South Park Commons",
        "founded_year": 2016,
        "hq_location": "San Francisco, CA, USA",
        "website": "https://www.southparkcommons.com",
        "founders": [
            {"name": "Ruchi Sanghvi", "role": "Co-founder"},
            {"name": "Aditya Agarwal", "role": "Co-founder"},
        ],
        "program_duration_weeks": 26,  # Founder Fellowship is ~6 months
        "investment_amount_usd": 400_000,
        "investment_equity_pct": None,
        "investment_terms_note": (
            "Founder Fellowship: $400K for 7% post-incorporation, plus community/residency. "
            "Early Residency is equity-free pre-idea support."
        ),
        "batch_cadence": "biannual",
        "focus_areas": ["AI", "deep tech", "hard tech", "repeat founders", "pre-idea"],
        "description": (
            "Invite-only community for technical founders in the pre-idea or early-idea phase. "
            "Unusually selective; skew toward repeat founders from FAANG/unicorns. "
            "Alumni include Cognition (Devin), Replit, Vanta, Cresta, Goodfire, Gamma, Luma Labs."
        ),
        "total_companies_funded": 300,
        "notable_alumni": [
            "Cognition AI", "Replit", "Vanta", "Cresta", "Goodfire", "Gamma",
            "Luma Labs", "Baseten", "Imbue", "Density AI", "Render", "The Graph",
        ],
        "data_sources": ["southparkcommons.com"],
    },
    {
        "slug": "a16z_speedrun",
        "name": "a16z Speedrun",
        "founded_year": 2023,
        "hq_location": "San Francisco, CA, USA",
        "website": "https://speedrun.a16z.com",
        "founders": [
            {"name": "Andrew Chen", "role": "General Partner (Lead)"},
            {"name": "Jonathan Lai", "role": "Partner"},
        ],
        "program_duration_weeks": 12,
        "investment_amount_usd": 1_000_000,
        "investment_equity_pct": None,
        "investment_terms_note": (
            "$1M uncapped SAFE (originally $750K, raised to $1M). "
            "Focused on games, media, consumer tech, and AI at the intersection of culture."
        ),
        "batch_cadence": "biannual",
        "focus_areas": ["games", "consumer", "AI", "media", "tools for creators"],
        "description": (
            "Andreessen Horowitz's dedicated accelerator for the intersection of tech and "
            "entertainment. Launched 2023 and has run cohorts SR001-SR006. Focuses on "
            "games, creator tools, AI consumer, and deep tech experiences."
        ),
        "total_companies_funded": 360,
        "notable_alumni": [],  # still too young for well-known exits
        "data_sources": ["speedrun.a16z.com"],
    },
    {
        "slug": "ef",
        "name": "Entrepreneur First",
        "founded_year": 2011,
        "hq_location": "London, UK",
        "website": "https://www.joinef.com",
        "founders": [
            {"name": "Matt Clifford", "role": "Co-founder / CEO"},
            {"name": "Alice Bentinck", "role": "Co-founder"},
        ],
        "program_duration_weeks": 13,
        "investment_amount_usd": 125_000,  # ~GBP 100K
        "investment_equity_pct": 10.0,
        "investment_terms_note": (
            "Approx GBP 100K (~$125K) for 10%. Unique: recruits individuals pre-cofounder, "
            "pre-idea. Team formation and idea discovery happen inside the program."
        ),
        "batch_cadence": "biannual per location",
        "focus_areas": ["AI", "deep tech", "SaaS", "fintech", "healthcare"],
        "description": (
            "The world's first 'talent investor'. Funds individual exceptional technical and "
            "commercial founders before they have a cofounder or idea, then helps them form "
            "teams and companies in-program. Operates in London, Paris, Berlin, Bangalore, "
            "Singapore, Toronto. Alumni include Tractable, Cleo, PolyAI, Aztec, Accurx, "
            "Magic Pony (acquired by Twitter)."
        ),
        "total_companies_funded": 600,
        "notable_alumni": [
            "Tractable", "Cleo", "PolyAI", "Aztec", "Accurx", "Omnipresent",
            "Permutive", "Magic Pony Technology",
        ],
        "data_sources": ["joinef.com"],
    },
]


ACCELERATOR_BY_SLUG = {a["slug"]: a for a in ACCELERATORS}

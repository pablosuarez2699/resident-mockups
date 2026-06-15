from dataclasses import dataclass, field
from typing import List


@dataclass
class SectorConfig:
    name: str
    display_name: str
    apollo_keywords: List[str]
    apollo_industries: List[str]
    target_titles: List[str]
    base_score: int
    score_weights: dict = field(default_factory=dict)
    employee_min: int = 10
    employee_max: int = 500
    hardware_required: bool = False
    # B2B-specific search terms for Google Places Text Search (free path)
    google_search_terms: List[str] = field(default_factory=list)


# Major Canadian metros used to generate city-targeted search variants. These
# widen the pool of fresh companies once the national-level terms get exhausted
# by the dedup cache. Ordered by business density.
CANADIAN_METROS = [
    "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
    "Ottawa", "Mississauga", "Winnipeg", "Hamilton", "Quebec City",
    "Brampton", "Surrey", "Laval", "Markham", "Vaughan",
]


def _with_city_variants(base_terms, city_templates):
    """National terms first, then `template Cityname` variants for each metro.
    The fetcher consumes terms in order and stops at the per-sector target, so
    city variants act as fresh-lead reserves drawn on only when needed."""
    expanded = list(base_terms)
    for template in city_templates:
        for city in CANADIAN_METROS:
            expanded.append(f"{template} {city}")
    return expanded


DEFAULT_TITLES = [
    "Purchasing Manager",
    "Head of Operations",
    "Logistics Manager",
    "Procurement Manager",
    "VP Operations",
    "COO",
    "Director of Operations",
    "Supply Chain Manager",
    "Director of Logistics",
    "Operations Manager",
    "Warehouse Manager",
    "Director of Supply Chain",
    "Procurement Director",
]

SECTOR_CONFIGS = {
    "retail": SectorConfig(
        name="retail",
        display_name="Retail / E-Commerce",
        apollo_keywords=["ecommerce", "online retail", "consumer goods", "shopify", "woocommerce"],
        apollo_industries=["retail", "consumer goods", "apparel & fashion", "sporting goods"],
        target_titles=DEFAULT_TITLES + ["E-Commerce Manager", "Fulfillment Manager"],
        base_score=3,
        score_weights={
            "has_ecommerce_tech": 2,
            "employee_20_plus": 1,
            "has_phone": 1,
            "has_email": 1,
        },
        google_search_terms=_with_city_variants(
            [
                "B2B consumer goods distributor Canada",
                "wholesale retail supplier Canada",
                "e-commerce fulfillment company Canada",
                "product importer exporter Canada",
                # B2C / DTC high-volume shippers (gated by shipping-volume filter)
                "online store Canada ships nationwide",
                "direct-to-consumer brand Canada",
                "online retailer Canada shipping",
                "subscription box company Canada",
            ],
            ["consumer goods distributor", "wholesale supplier", "e-commerce fulfillment company"],
        ),
    ),
    "healthcare": SectorConfig(
        name="healthcare",
        display_name="Healthcare / Medical Supply",
        apollo_keywords=["medical supply", "lab supply", "diagnostics", "medical device", "pharmaceutical distribution"],
        apollo_industries=["medical devices", "hospital & health care", "health, wellness and fitness", "pharmaceuticals"],
        target_titles=DEFAULT_TITLES + ["Lab Manager", "Medical Supply Manager"],
        base_score=4,
        score_weights={
            "multi_location": 2,
            "employee_50_plus": 1,
            "has_phone": 1,
            "has_email": 1,
        },
        google_search_terms=_with_city_variants(
            [
                "medical supply company Canada",
                "pharmaceutical distributor Canada",
                "lab supply company Canada",
                "medical device manufacturer Canada",
            ],
            ["medical supply company", "pharmaceutical distributor", "lab supply company"],
        ),
    ),
    "tech": SectorConfig(
        name="tech",
        display_name="Technology / Hardware",
        apollo_keywords=["hardware", "IoT", "electronics", "device", "manufacturing", "circuit board"],
        apollo_industries=["computer hardware", "electronics", "semiconductors", "electrical/electronic manufacturing"],
        target_titles=DEFAULT_TITLES,
        base_score=2,
        score_weights={
            "hardware_keyword_match": 3,
            "employee_20_plus": 1,
            "has_phone": 1,
            "has_email": 1,
        },
        hardware_required=True,
        google_search_terms=_with_city_variants(
            [
                "electronics manufacturer Canada",
                "hardware manufacturer Canada",
                "IoT device company Canada",
                "electronic components distributor Canada",
            ],
            ["electronics manufacturer", "hardware manufacturer", "electronic components distributor"],
        ),
    ),
    "industrial": SectorConfig(
        name="industrial",
        display_name="Industrial / Distribution",
        apollo_keywords=["distribution", "warehouse", "wholesale", "manufacturing", "fulfillment"],
        apollo_industries=["wholesale", "logistics and supply chain", "warehousing", "industrial automation", "machinery"],
        target_titles=DEFAULT_TITLES + ["Distribution Manager", "Plant Manager"],
        base_score=5,
        score_weights={
            "distribution_keyword": 2,
            "employee_20_plus": 1,
            "has_phone": 1,
            "has_email": 1,
        },
        google_search_terms=_with_city_variants(
            [
                "industrial distributor Canada",
                "wholesale distributor Canada",
                "warehouse logistics company Canada",
                "manufacturing company Canada",
                "industrial supplier Canada",
            ],
            ["industrial distributor", "wholesale distributor", "manufacturing company", "industrial supplier"],
        ),
    ),
}

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
    ),
}

"""Canada-wide geo grid for Places locationBias sweeps.

Each zone is a search circle. Big metros are split into sub-zones (industrial
suburbs rank poorly in city-level text queries, so tighter circles surface
companies that never crack the top-60 for "distributor Toronto"). Mid-size
cities get one wider circle. Radius is capped at 50 km by the Places API.

Ordering is deliberate: metro industrial belts first (highest business
density), then mid-size cities, then smaller regional centres — the fetcher
walks the list in order and stops as soon as the batch target is met.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class GeoZone:
    name: str
    lat: float
    lng: float
    radius_m: int  # max 50_000 per Places API


GRID_ZONES: List[GeoZone] = [
    # --- Greater Toronto Area sub-zones ---
    GeoZone("Toronto-Etobicoke", 43.6435, -79.5656, 12_000),
    GeoZone("Toronto-Scarborough", 43.7764, -79.2318, 12_000),
    GeoZone("Toronto-NorthYork", 43.7615, -79.4111, 10_000),
    GeoZone("Mississauga", 43.5890, -79.6441, 15_000),
    GeoZone("Brampton", 43.7315, -79.7624, 15_000),
    GeoZone("Vaughan-Concord", 43.8361, -79.5083, 12_000),
    GeoZone("Markham-Richmond Hill", 43.8561, -79.3370, 12_000),
    GeoZone("Oakville-Burlington", 43.4185, -79.7370, 15_000),
    GeoZone("Hamilton", 43.2557, -79.8711, 20_000),
    GeoZone("Oshawa-Whitby", 43.8971, -78.8658, 15_000),
    # --- Greater Montreal sub-zones ---
    GeoZone("Montreal-SaintLaurent", 45.5000, -73.7000, 10_000),
    GeoZone("Montreal-Anjou-East", 45.6100, -73.5600, 12_000),
    GeoZone("Montreal-Dorval-Lachine", 45.4470, -73.7440, 10_000),
    GeoZone("Montreal-Downtown-Plateau", 45.5088, -73.5878, 8_000),
    GeoZone("Montreal-LaSalle-Verdun", 45.4300, -73.6200, 8_000),
    GeoZone("Montreal-Nord-Montreal", 45.6000, -73.6300, 8_000),
    GeoZone("Laval", 45.6066, -73.7124, 15_000),
    GeoZone("Longueuil-SouthShore", 45.5312, -73.5181, 15_000),
    GeoZone("Brossard-LaPrairie", 45.4500, -73.4660, 12_000),
    GeoZone("Boucherville-Varennes", 45.6100, -73.4300, 12_000),
    GeoZone("Terrebonne-Mascouche", 45.7000, -73.6400, 15_000),
    GeoZone("Repentigny", 45.7420, -73.4500, 12_000),
    GeoZone("Vaudreuil-Dorion", 45.4000, -74.0300, 15_000),
    GeoZone("Saint-Jerome", 45.7800, -74.0030, 15_000),
    GeoZone("Saint-Eustache-Deux-Montagnes", 45.5650, -73.9050, 12_000),
    GeoZone("Saint-Hyacinthe", 45.6300, -72.9500, 20_000),
    GeoZone("Salaberry-de-Valleyfield", 45.2500, -74.1300, 20_000),
    GeoZone("Granby", 45.4000, -72.7300, 20_000),
    GeoZone("Saint-Jean-sur-Richelieu", 45.3070, -73.2620, 18_000),
    GeoZone("Joliette", 46.0200, -73.4400, 20_000),
    GeoZone("Sorel-Tracy", 46.0400, -73.1100, 20_000),
    # --- Greater Vancouver sub-zones ---
    GeoZone("Burnaby", 49.2488, -122.9805, 10_000),
    GeoZone("Richmond BC", 49.1666, -123.1336, 10_000),
    GeoZone("Surrey", 49.1913, -122.8490, 15_000),
    GeoZone("Delta-Tilbury", 49.0847, -123.0587, 12_000),
    GeoZone("Langley", 49.1044, -122.6603, 12_000),
    GeoZone("Coquitlam-PortCoquitlam", 49.2838, -122.7932, 12_000),
    # --- Alberta ---
    GeoZone("Calgary-NE", 51.0920, -113.9860, 15_000),
    GeoZone("Calgary-SE-Foothills", 50.9870, -113.9950, 15_000),
    GeoZone("Edmonton-South", 53.4700, -113.4900, 15_000),
    GeoZone("Edmonton-West", 53.5560, -113.6250, 15_000),
    GeoZone("Nisku-Leduc", 53.3200, -113.5500, 12_000),
    GeoZone("Red Deer", 52.2681, -113.8112, 25_000),
    GeoZone("Lethbridge", 49.6942, -112.8328, 25_000),
    GeoZone("Medicine Hat", 50.0405, -110.6764, 25_000),
    # --- Other major cities ---
    GeoZone("Ottawa", 45.4215, -75.6972, 30_000),
    GeoZone("Quebec City", 46.8139, -71.2080, 30_000),
    GeoZone("Winnipeg", 49.8951, -97.1384, 30_000),
    GeoZone("Halifax-Dartmouth", 44.6820, -63.5850, 30_000),
    # --- Southwestern Ontario belt ---
    GeoZone("Kitchener-Waterloo-Cambridge", 43.4516, -80.4925, 20_000),
    GeoZone("Guelph", 43.5448, -80.2482, 15_000),
    GeoZone("London ON", 42.9849, -81.2453, 25_000),
    GeoZone("Windsor ON", 42.3149, -83.0364, 25_000),
    GeoZone("Sarnia", 42.9745, -82.4066, 25_000),
    GeoZone("Brantford", 43.1394, -80.2644, 15_000),
    GeoZone("St. Catharines-Niagara", 43.1594, -79.2469, 20_000),
    GeoZone("Barrie", 44.3894, -79.6903, 20_000),
    GeoZone("Kingston ON", 44.2312, -76.4860, 25_000),
    GeoZone("Peterborough", 44.3091, -78.3197, 25_000),
    # --- Quebec regional ---
    GeoZone("Sherbrooke", 45.4042, -71.8929, 25_000),
    GeoZone("Trois-Rivieres", 46.3432, -72.5420, 25_000),
    GeoZone("Drummondville", 45.8833, -72.4834, 25_000),
    GeoZone("Saguenay", 48.4280, -71.0686, 30_000),
    GeoZone("Gatineau", 45.4765, -75.7013, 20_000),
    # --- Prairies / Sask / Manitoba ---
    GeoZone("Saskatoon", 52.1332, -106.6700, 25_000),
    GeoZone("Regina", 50.4452, -104.6189, 25_000),
    GeoZone("Brandon MB", 49.8485, -99.9501, 25_000),
    # --- BC interior / island ---
    GeoZone("Kelowna", 49.8880, -119.4960, 25_000),
    GeoZone("Kamloops", 50.6745, -120.3273, 25_000),
    GeoZone("Abbotsford-Chilliwack", 49.0504, -122.3045, 20_000),
    GeoZone("Victoria", 48.4284, -123.3656, 25_000),
    GeoZone("Nanaimo", 49.1659, -123.9401, 25_000),
    GeoZone("Prince George", 53.9171, -122.7497, 30_000),
    # --- Atlantic ---
    GeoZone("Moncton", 46.0878, -64.7782, 25_000),
    GeoZone("Saint John NB", 45.2733, -66.0633, 25_000),
    GeoZone("Fredericton", 45.9636, -66.6431, 25_000),
    GeoZone("Charlottetown", 46.2382, -63.1311, 25_000),
    GeoZone("St. John's NL", 47.5615, -52.7126, 30_000),
    # --- Northern Ontario ---
    GeoZone("Sudbury", 46.4917, -80.9930, 30_000),
    GeoZone("Thunder Bay", 48.3809, -89.2477, 30_000),
    GeoZone("Sault Ste. Marie", 46.5219, -84.3461, 25_000),
]


# Named region presets for `--region`. Each maps to the GeoZone names that
# make up that market, so a run can be geographically scoped (e.g. a rep
# working only the Montreal territory). Zone lists are matched exactly.
REGIONS = {
    "montreal": [
        "Montreal-SaintLaurent", "Montreal-Anjou-East", "Montreal-Dorval-Lachine",
        "Montreal-Downtown-Plateau", "Montreal-LaSalle-Verdun", "Montreal-Nord-Montreal",
        "Laval", "Longueuil-SouthShore", "Brossard-LaPrairie",
        "Boucherville-Varennes", "Terrebonne-Mascouche", "Repentigny",
        "Vaudreuil-Dorion", "Saint-Jerome", "Saint-Eustache-Deux-Montagnes",
        "Saint-Hyacinthe", "Salaberry-de-Valleyfield", "Granby",
        "Saint-Jean-sur-Richelieu", "Joliette", "Sorel-Tracy",
    ],
    "toronto": [
        "Toronto-Etobicoke", "Toronto-Scarborough", "Toronto-NorthYork",
        "Mississauga", "Brampton", "Vaughan-Concord", "Markham-Richmond Hill",
        "Oakville-Burlington", "Hamilton", "Oshawa-Whitby",
    ],
    "vancouver": [
        "Burnaby", "Richmond BC", "Surrey", "Delta-Tilbury", "Langley",
        "Coquitlam-PortCoquitlam", "Abbotsford-Chilliwack",
    ],
    "calgary": ["Calgary-NE", "Calgary-SE-Foothills"],
    "edmonton": ["Edmonton-South", "Edmonton-West", "Nisku-Leduc"],
    "ottawa": ["Ottawa", "Gatineau"],
    "quebec": [
        "Quebec City", "Sherbrooke", "Trois-Rivieres", "Drummondville", "Saguenay",
    ],
}


def zones_for_region(region: str):
    """Return the GeoZones for a named region, or [] if unknown."""
    names = set(REGIONS.get(region.lower().strip(), []))
    return [z for z in GRID_ZONES if z.name in names]

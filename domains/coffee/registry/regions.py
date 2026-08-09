"""Geographic region definitions — maps origins to climate extraction bounding boxes."""
from dataclasses import dataclass


@dataclass
class Region:
    """A geographic area used for CHIRPS/NDVI climate data extraction."""

    region_id: str
    name: str
    asset_id: str        # links to Asset
    # WGS84 bounding box
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


# Minas Gerais, Brazil — primary Arabica-producing state, used for CHIRPS extraction
MINAS_GERAIS = Region(
    region_id="brazil:minas_gerais",
    name="Minas Gerais",
    asset_id="coffee:origin:brazil:arabica",
    lat_min=-22.9,
    lat_max=-14.2,
    lon_min=-51.0,
    lon_max=-39.8,
)

# Vietnam Central Highlands — primary Robusta-producing region
VIETNAM_CENTRAL_HIGHLANDS = Region(
    region_id="vietnam:central_highlands",
    name="Vietnam Central Highlands",
    asset_id="coffee:origin:vietnam:robusta",
    lat_min=10.5,
    lat_max=15.5,
    lon_min=107.0,
    lon_max=109.0,
)

# Kodagu, Karnataka, India — largest India coffee district (~30% of national
# output), both Arabica and Robusta grown here. Bbox for netcdf-fallback/
# documentation parity only — the live GEE path in chirps_india.py uses its own
# GAUL level-2 (district) admin-name constants, same split as MINAS_GERAIS.
KODAGU = Region(
    region_id="india:kodagu",
    name="Kodagu",
    asset_id="coffee:origin:india:arabica",
    lat_min=11.85,
    lat_max=12.75,
    lon_min=75.35,
    lon_max=76.15,
)

# Chikmagalur and Hassan, Karnataka, India — the second- and third-largest India
# coffee districts by production (see coffee_board_india_supply.py). Same bbox
# caveat as KODAGU — netcdf-fallback/documentation parity only.
CHIKMAGALUR = Region(
    region_id="india:chikmagalur",
    name="Chikmagalur",
    asset_id="coffee:origin:india:arabica",
    lat_min=12.90,
    lat_max=13.70,
    lon_min=75.30,
    lon_max=76.10,
)

HASSAN = Region(
    region_id="india:hassan",
    name="Hassan",
    asset_id="coffee:origin:india:arabica",
    lat_min=12.60,
    lat_max=13.30,
    lon_min=75.70,
    lon_max=76.50,
)

ALL_REGIONS: list[Region] = [
    MINAS_GERAIS,
    VIETNAM_CENTRAL_HIGHLANDS,
    KODAGU,
    CHIKMAGALUR,
    HASSAN,
]

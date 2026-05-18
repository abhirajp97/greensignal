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

ALL_REGIONS: list[Region] = [MINAS_GERAIS, VIETNAM_CENTRAL_HIGHLANDS]

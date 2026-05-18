"""Coffee asset registry — canonical Asset definitions for all tracked origins."""
from core.models.asset import Asset

BRAZIL_ARABICA = Asset(
    asset_id="coffee:origin:brazil:arabica",
    domain="coffee",
    asset_type="origin",
    name="Brazil Arabica",
    unit="lb",
    metadata={"country": "Brazil", "species": "arabica", "regions": [
        "minas_gerais", "cerrado", "sul_de_minas",
    ]},
)

COLOMBIA_ARABICA = Asset(
    asset_id="coffee:origin:colombia:arabica",
    domain="coffee",
    asset_type="origin",
    name="Colombia Arabica",
    unit="lb",
    metadata={"country": "Colombia", "species": "arabica", "regions": ["huila", "nariño", "cauca"]},
)

ETHIOPIA_ARABICA = Asset(
    asset_id="coffee:origin:ethiopia:arabica",
    domain="coffee",
    asset_type="origin",
    name="Ethiopia Arabica",
    unit="lb",
    metadata={"country": "Ethiopia", "species": "arabica", "regions": [
        "yirgacheffe", "sidama", "guji",
    ]},
)

VIETNAM_ROBUSTA = Asset(
    asset_id="coffee:origin:vietnam:robusta",
    domain="coffee",
    asset_type="origin",
    name="Vietnam Robusta",
    unit="lb",
    metadata={"country": "Vietnam", "species": "robusta", "regions": ["central_highlands"]},
)

ICE_ARABICA_BENCHMARK = Asset(
    asset_id="coffee:benchmark:ice:arabica",
    domain="coffee",
    asset_type="benchmark",
    name="ICE Arabica C",
    unit="lb",
    metadata={"exchange": "ICE", "ticker": "KC=F", "nasdaq_series": "CHRIS/ICE_KC1"},
)

ALL_ASSETS: list[Asset] = [
    BRAZIL_ARABICA,
    COLOMBIA_ARABICA,
    ETHIOPIA_ARABICA,
    VIETNAM_ROBUSTA,
    ICE_ARABICA_BENCHMARK,
]

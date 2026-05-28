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

WB_ARABICA_BENCHMARK = Asset(
    asset_id="coffee:benchmark:wb:arabica",
    domain="coffee",
    asset_type="benchmark",
    name="World Bank Coffee Arabica (Other Mild Arabicas)",
    unit="lb",
    metadata={
        "source": "World Bank Pink Sheet",
        "wb_code": "COFFEE_ARABIC",
        "description": (
            "Monthly average physical spot price for Other Mild Arabicas "
            "(Colombia, Kenya, Tanzania). Proxy for ICO Arabica indicator. "
            "Converted from $/kg to USc/lb."
        ),
    },
)

WB_ROBUSTA_BENCHMARK = Asset(
    asset_id="coffee:benchmark:wb:robusta",
    domain="coffee",
    asset_type="benchmark",
    name="World Bank Coffee Robusta",
    unit="lb",
    metadata={
        "source": "World Bank Pink Sheet",
        "wb_code": "COFFEE_ROBUS",
        "description": (
            "Monthly average physical spot price for Robusta coffee "
            "(Vietnam, Uganda). Proxy for ICO Robusta indicator. "
            "Converted from $/kg to USc/lb."
        ),
    },
)

ENSO_ONI = Asset(
    asset_id="climate:enso:oni",
    domain="coffee",
    asset_type="climate_signal",
    name="NOAA Oceanic Nino Index (ONI)",
    unit="degC",
    metadata={
        "source": "NOAA Climate Prediction Center",
        "url": "https://cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
        "description": (
            "3-month running mean of ERSST.v5 SST anomalies in the Nino 3.4 region "
            "(5N-5S, 120-170W). Positive = El Nino (warming), negative = La Nina (cooling). "
            "Applied with 18- and 24-month lags for coffee procurement signal."
        ),
    },
)

ALL_ASSETS: list[Asset] = [
    BRAZIL_ARABICA,
    COLOMBIA_ARABICA,
    ETHIOPIA_ARABICA,
    VIETNAM_ROBUSTA,
    ICE_ARABICA_BENCHMARK,
    WB_ARABICA_BENCHMARK,
    WB_ROBUSTA_BENCHMARK,
    ENSO_ONI,
]

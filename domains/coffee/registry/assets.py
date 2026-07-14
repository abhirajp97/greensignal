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

COT_KC = Asset(
    asset_id="coffee:cot:kc",
    domain="coffee",
    asset_type="positioning_signal",
    name="CFTC COT Managed Money Net — ICE Coffee C",
    unit="contracts",
    metadata={
        "source": "CFTC Disaggregated Commitments of Traders (futures-only)",
        "url": "https://www.cftc.gov/files/dea/history",
        "market": "COFFEE C - ICE FUTURES U.S.",
        "description": (
            "Weekly (Tuesday) net managed-money position (long - short) in ICE "
            "Coffee C futures, from the CFTC disaggregated report. Used as a "
            "contrarian signal: extreme spec positioning often precedes reversals. "
            "Convert to a 0-100 COT index over a trailing window before scoring."
        ),
    },
)

USDA_STU = Asset(
    asset_id="coffee:supply:world_stu",
    domain="coffee",
    asset_type="supply_signal",
    name="USDA PSD World Coffee Stocks-to-Use %",
    unit="percent",
    metadata={
        "source": "USDA Foreign Agricultural Service — PSD Online (bulk CSV)",
        "url": "https://apps.fas.usda.gov/psdonline/downloads/psd_coffee_csv.zip",
        "commodity_code": 711100,
        "description": (
            "World coffee ending stocks as a percent of domestic consumption, "
            "aggregated across all reporting countries per marketing year "
            "(no World row in PSD — summed from Attribute 176 Ending Stocks and "
            "125 Domestic Consumption). A low buffer (tight S/U) historically "
            "precedes higher prices. Annual; values are retroactively revised."
        ),
    },
)

USDA_STU_VINTAGE = Asset(
    asset_id="coffee:supply:world_stu_vintage",
    domain="coffee",
    asset_type="supply_signal",
    name="USDA Coffee: World Markets and Trade — World Stocks-to-Use % (vintage-dated)",
    unit="percent",
    metadata={
        "source": (
            "USDA Foreign Agricultural Service — Coffee: World Markets and "
            "Trade (semiannual circular)"
        ),
        "url": "https://esmis.nal.usda.gov/publication/coffee-world-markets-and-trade",
        "description": (
            "World coffee ending stocks as a percent of domestic consumption, "
            "computed from the 'Total' Ending Stocks and 'Total' Domestic "
            "Consumption rows of each semiannual (Jun/Dec) WMT circular. Unlike "
            "USDA_STU (the PSD bulk file, always the latest-revised vintage), "
            "each observation here is dated to the report's own publication "
            "date and uses only that report's own newest-column estimate — a "
            "genuinely point-in-time (vintage-aware) series with no look-ahead."
        ),
    },
)

CHIRPS_MINAS = Asset(
    asset_id="climate:chirps:minas_gerais",
    domain="coffee",
    asset_type="climate_signal",
    name="CHIRPS Rainfall — Minas Gerais (Brazil Arabica)",
    unit="mm",
    metadata={
        "source": "UCSB CHIRPS via Google Earth Engine",
        "gee_collection": "UCSB-CHG/CHIRPS/PENTAD",
        "region": "FAO GAUL level-1 ADM1_NAME='Minas Gerais'",
        "description": (
            "Monthly area-mean precipitation (mm) over Minas Gerais, Brazil's "
            "primary Arabica state. Below-normal rainfall during the Sep-Nov "
            "flowering season threatens the next crop and is bullish for price. "
            "Returns raw monthly rainfall; anomaly and flowering-season risk are "
            "derived downstream (see drought_risk_score)."
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
    COT_KC,
    USDA_STU,
    USDA_STU_VINTAGE,
    CHIRPS_MINAS,
]

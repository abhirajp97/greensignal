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

INDIA_ARABICA = Asset(
    asset_id="coffee:origin:india:arabica",
    domain="coffee",
    asset_type="origin",
    name="India Arabica (Karnataka)",
    unit="inr_per_50kg",
    metadata={
        "country": "India",
        "species": "arabica",
        "regions": ["kodagu"],
        "growing_system": "shade_grown",
        "price_series": (
            "Genuine India-origin: 'Raw Coffee Price (Karnataka)' Parchment/Cherry "
            "grades from coffee_board_india_price.py (Coffee Board of India's Daily "
            "Market Report archive, 2012-present). Task 0's original audit found no "
            "usable India-origin source and fell back to a WB global-benchmark proxy "
            "— superseded once the real Coffee Board archive was found; see "
            "docs/india_origin_signal_plan_v2_full_build.md"
        ),
    },
)

INDIA_ROBUSTA = Asset(
    asset_id="coffee:origin:india:robusta",
    domain="coffee",
    asset_type="origin",
    name="India Robusta (Karnataka)",
    unit="inr_per_50kg",
    metadata={
        "country": "India",
        "species": "robusta",
        "regions": ["kodagu"],
        "growing_system": "shade_grown",
        "price_series": (
            "Genuine India-origin: 'Raw Coffee Price (Karnataka)' Parchment/Cherry "
            "grades from coffee_board_india_price.py (Coffee Board of India's Daily "
            "Market Report archive, 2012-present). Task 0's original audit found no "
            "usable India-origin source and fell back to a WB global-benchmark proxy "
            "— superseded once the real Coffee Board archive was found; see "
            "docs/india_origin_signal_plan_v2_full_build.md"
        ),
    },
)

INDIA_PRODUCTION = Asset(
    asset_id="coffee:supply:india:production",
    domain="coffee",
    asset_type="supply_signal",
    name="India Coffee Production — National + District Estimates",
    unit="metric_tons",
    metadata={
        "source": "Coffee Board of India — semiannual 'Database on Coffee' PDF circular",
        "url": "https://coffeeboard.gov.in/database-coffee.html",
        "description": (
            "National and district-level (Chikkamagaluru, Kodagu, Hassan, Wayanad, "
            "Travancore, Nilliampathy + Tamil Nadu districts) production estimates "
            "in metric tons, by species. Each observation is dated to its own "
            "report's publication month and carries that report's own newest "
            "marketing-year column — vintage-aware, mirrors usda_coffee_wmt.py's "
            "no-look-ahead approach rather than USDA PSD's always-latest-revised one."
        ),
    },
)

CHIRPS_KODAGU = Asset(
    asset_id="climate:chirps:kodagu",
    domain="coffee",
    asset_type="climate_signal",
    name="CHIRPS Rainfall — Kodagu (India Arabica/Robusta)",
    unit="mm",
    metadata={
        "source": "UCSB CHIRPS via Google Earth Engine",
        "gee_collection": "UCSB-CHG/CHIRPS/PENTAD",
        "region": "FAO GAUL level-2 ADM2_NAME='Kodagu'",
        "description": (
            "Monthly area-mean precipitation (mm) over Kodagu, India's largest "
            "coffee district (~30% of national output, both Arabica and Robusta "
            "grown there). Below-normal rainfall during the Feb-Mar blossom "
            "shower window threatens flowering and is bullish for price. Returns "
            "raw monthly rainfall; anomaly and risk are derived downstream, "
            "mirroring CHIRPS_MINAS."
        ),
    },
)

CHIRPS_CHIKMAGALUR = Asset(
    asset_id="climate:chirps:chikmagalur",
    domain="coffee",
    asset_type="climate_signal",
    name="CHIRPS Rainfall — Chikmagalur (India Arabica/Robusta)",
    unit="mm",
    metadata={
        "source": "UCSB CHIRPS via Google Earth Engine",
        "gee_collection": "UCSB-CHG/CHIRPS/PENTAD",
        "region": "FAO GAUL level-2 ADM2_NAME='Chikmagalur'",
        "description": (
            "Monthly area-mean precipitation (mm) over Chikmagalur, India's "
            "second-largest coffee district by production (~85,155 MT in "
            "2023-24 per coffee_board_india_supply.py, vs Kodagu's 132,620 MT). "
            "GAUL's own spelling is 'Chikmagalur' — differs from Coffee Board's "
            "'Chikkamagaluru' (see coffee_board_india_supply.py's _REGION_ALIASES). "
            "Part of the production-weighted multi-district climate signal — see "
            "chirps_india.py's district parameter."
        ),
    },
)

CHIRPS_HASSAN = Asset(
    asset_id="climate:chirps:hassan",
    domain="coffee",
    asset_type="climate_signal",
    name="CHIRPS Rainfall — Hassan (India Arabica/Robusta)",
    unit="mm",
    metadata={
        "source": "UCSB CHIRPS via Google Earth Engine",
        "gee_collection": "UCSB-CHG/CHIRPS/PENTAD",
        "region": "FAO GAUL level-2 ADM2_NAME='Hassan'",
        "description": (
            "Monthly area-mean precipitation (mm) over Hassan, India's third "
            "coffee district by production (~36,800 MT in 2023-24 per "
            "coffee_board_india_supply.py). Part of the production-weighted "
            "multi-district climate signal — see chirps_india.py's district "
            "parameter."
        ),
    },
)

FX_USD_INR = Asset(
    asset_id="fx:usd_inr",
    domain="coffee",
    asset_type="fx_signal",
    name="USD/INR Exchange Rate",
    unit="inr_per_usd",
    metadata={
        "source": "Yahoo Finance",
        "ticker": "INR=X",
        "description": (
            "Used to express India origin prices comparably to the "
            "USD-denominated global benchmark. Not an input to the composite "
            "formula itself (price_position and climate_risk are both "
            "currency-invariant) — card-copy framing only."
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
    INDIA_ARABICA,
    INDIA_ROBUSTA,
    INDIA_PRODUCTION,
    CHIRPS_KODAGU,
    CHIRPS_CHIKMAGALUR,
    CHIRPS_HASSAN,
    FX_USD_INR,
]

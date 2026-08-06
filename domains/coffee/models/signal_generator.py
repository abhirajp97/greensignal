"""Composite signal generator — the core Phase 0 formula implemented end-to-end."""

from datetime import date

from core.models.recommendation import Recommendation
from core.services.recommendation_engine import (
    build_recommendation,
    build_recommendation_from_multiplier,
)
from domains.coffee.features.climate_features import climate_risk_score


def generate_signal(
    asset_id: str,
    signal_date: date,
    price_position: float,
    stu_risk: float,
    enso_risk: float,
    brazil_drought_risk: float,
    cot_contrarian: float,
) -> Recommendation:
    """Generate a Buy / Neutral / Caution recommendation using the composite formula.

    multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk_score)
    Range: 0.4x (strong caution) → 2.3x (high conviction buy)
    """
    c_risk = climate_risk_score(stu_risk, enso_risk, brazil_drought_risk, cot_contrarian)
    return build_recommendation(asset_id, signal_date, price_position, c_risk)


def generate_india_signal(
    asset_id: str,
    signal_date: date,
    price_position: float,
    climate_risk: float,
    confidence: float = 0.7,
) -> Recommendation:
    """Generate a Buy / Neutral / Caution recommendation for an India origin.

    **Superseded by `generate_india_signal_v3` below** — this v2 formula's
    Kodagu local-climate hypothesis did not clear notebook 09's backtest gate
    for either species (see CLAUDE.md's India Origin Signal section). Kept,
    not deleted, since it's still a real demo-purposes composite and the
    notebook 09 §6-7/§14 pass-through diagnosis that superseded it was itself
    only possible by having this version's real output to test against.

    Reuses the composite formula's *shape*, not generate_signal()'s Brazil-coupled
    four-input climate_risk_score() — India has one climate input (Kodagu rainfall,
    see domains/coffee/sources/chirps_india.py), so there's nothing to weight-combine.
    `climate_risk` is that source's own drought_risk_score() output, fed straight in.

    multiplier = (1.5 - price_position) * (1.0 + 0.65 * climate_risk)
    Additive to this module — generate_signal() (Brazil) is untouched.

    `confidence` should reflect validation status (lower under "accumulating
    validation" if the notebook 09 backtest gate hasn't passed on adequate
    history yet) — see docs/india_origin_signal_plan_v2_full_build.md §6.2.
    """
    return build_recommendation(asset_id, signal_date, price_position, climate_risk, confidence)


INDIA_V3_WEIGHTS = {"price_pos": 0.361, "stu_stress": 0.148, "l3_risk": 0.491}
"""India-specific r-proportional weights (notebook 09 §13-§15), refit on
India's own forward-6m Arabica price — NOT inherited from Brazil's
`climate_features.WEIGHTS`. `enso_risk` and `cot_momentum` were tested and
dropped: leave-one-out ablation showed they contribute ~nothing (delta
0.000) or actively hurt (dropping cot_momentum: +0.043) respectively.
Walk-forward validated (weights refit on trailing data only each year, no
look-ahead): r=+0.553 (p<0.0001, n=96 months, 8 test years 2017-2024) —
stronger out-of-sample than in-sample (+0.505), a good sign against
overfitting, not a red flag."""


def generate_india_signal_v3(
    asset_id: str,
    signal_date: date,
    price_position: float,
    stu_stress: float,
    l3_risk: float,
    confidence: float = 0.4,
) -> Recommendation:
    """India Arabica timing signal — v3, notebook 09 §16's walk-forward-validated
    replacement for the v2 additive 2-input composite (`generate_india_signal` above).

    Two structural differences from `generate_india_signal()` and from
    Brazil's `generate_signal()`, both load-bearing findings from notebook 09
    §11-§12, not stylistic choices:

    1. **`price_position` is momentum-signed here, not contrarian.** Brazil's
       `(1.5 - price_position)` term assumes mean-reversion — validated for
       global Arabica's own ~24-month cycle, notebook 01 — but India's price
       position correlates *positively* with forward India price at 3-12m
       horizons (r=+0.347 @ 6m). Feeding `price_position` in raw, not
       transformed, preserves that sign; do not wrap it in `1.5 - x` here.
    2. **Additive weighted-sum, not conditional-multiplicative.** Brazil's
       `(1.5 - price_position) * (1 + 0.65 * climate_risk_score)` multiplies
       a contrarian term against an amplifying one; for India the contrarian
       term is wrong-signed and large enough to flip the whole product's
       sign even though most of the raw sub-signals are right-signed
       (§12's root-cause finding — the §10 straight test of Brazil's own
       formula, translated through the pass-through equation, FAILed
       decisively, r=−0.250, precisely because of this). A plain
       r-proportional weighted sum avoids that failure mode.

    `l3_risk` is **Brazil's own** Minas Gerais flowering-deficit drought risk
    (`domains/coffee/sources/chirps.py`), reused here as a proxy for *global*
    Arabica supply risk — not a Kodagu/India-local climate input. This was
    the single strongest raw sub-signal against forward India price in the
    decomposition that led to this formula (r=+0.620 @ 12m) — because Brazil
    dominates world Arabica production, its own crop risk is a better global-
    fundamentals proxy than India's own ~3.5%-of-world-production climate.
    **India's own Kodagu climate/supply data (`chirps_india.py`,
    `coffee_board_india_supply.py`) is deliberately NOT an input to this
    formula** — see notebook 09 §6-7's pass-through finding for why local
    India climate didn't clear its own gate in the first place.

    `stu_stress` should be `domains.coffee.sources.usda_coffee_wmt.stu_wmt_stress_score()`
    — the same true-vintage global stocks-to-use stress score behind the
    Brazil composite's `stu_risk` weight (`climate_features.py::WEIGHTS`),
    not an India-specific supply metric.

    Not the same formula shape as `build_recommendation()`, so this function
    computes its own weighted-sum score and hands the resulting multiplier to
    `build_recommendation_from_multiplier()` rather than `build_recommendation()`.

    `confidence` defaults lower (0.4) than Brazil's typical 0.7 or even India
    v2's 0.7 — this is a single walk-forward test on ~8 years of India-
    specific data, real and promising but meaningfully earlier-stage than
    Brazil's multi-notebook, multi-session validation (notebook 09 §16's own
    framing). Arabica-only; not validated for Robusta.
    """
    score = (
        INDIA_V3_WEIGHTS["price_pos"] * price_position
        + INDIA_V3_WEIGHTS["stu_stress"] * stu_stress
        + INDIA_V3_WEIGHTS["l3_risk"] * l3_risk
    )
    # Rescale the [0,1] additive score (weights sum to 1.0) onto
    # build_recommendation()'s multiplier convention, where 1.0 is neutral —
    # the blend's own natural midpoint (score=0.5) maps to multiplier=1.0.
    multiplier = score * 2.0

    return build_recommendation_from_multiplier(
        asset_id,
        signal_date,
        multiplier,
        signal_inputs={
            "price_position": price_position,
            "stu_stress": stu_stress,
            "l3_risk": l3_risk,
            "india_composite_score": score,
        },
        rationale=_india_v3_rationale(price_position, l3_risk),
        confidence=confidence,
    )


def _india_v3_rationale(price_position: float, l3_risk: float) -> str:
    if price_position > 0.7:
        price_note = "India's price has been climbing, and that trend has tended to continue"
    elif price_position < 0.3:
        price_note = "India's price has been soft, and that trend has tended to continue"
    else:
        price_note = "India's price is in the middle of its recent range"

    if l3_risk >= 0.6:
        supply_note = (
            "Brazil's crop — the world's largest — is showing drought stress, "
            "a global supply risk that tends to show up in India's price too"
        )
    elif l3_risk <= 0.3:
        supply_note = "Brazil's crop conditions look healthy, easing global supply risk"
    else:
        supply_note = "Brazil's crop conditions are mixed"

    return f"{price_note}. {supply_note}."

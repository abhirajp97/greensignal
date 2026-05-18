# GreenSignal Procurement Intelligence Architecture

**Purpose:** This document prepares a coding agent to build GreenSignal as a focused coffee purchasing intelligence product while keeping the infrastructure reusable for adjacent specialty commodity domains, starting with cacao.

**Primary product:** GreenSignal — purchasing intelligence for small-to-mid specialty coffee roasters.

**Expansion path:** Cacao / craft chocolate first, because it shares the closest market structure with coffee: origin-specific pricing, climate sensitivity, specialty buyers, small-business procurement pain, and similar public-data availability.

---

## 1. Product Strategy

### 1.1 Core Principle

Build a **vertical product with a horizontal core**.

- The user-facing product should feel purpose-built for coffee roasters.
- The internal infrastructure should use reusable procurement-intelligence abstractions.
- Do not launch as a generic commodity intelligence platform.
- Do not over-generalize the MVP.
- Generalize only the engineering interfaces that are clearly reusable.

### 1.2 Key Architecture Idea

```text
Domain-specific ingestion
    → Canonical data model
    → Domain-specific feature engineering
    → Shared scenario / risk / recommendation objects
    → Domain-specific UI and product language
```

For example:

```text
Coffee data fetchers
    → market_observations / feature_observations
    → coffee-specific price, supply, and climate features
    → generic forecasts, risk signals, recommendations, decision memos
    → coffee roaster dashboard

Cacao data fetchers
    → market_observations / feature_observations
    → cacao-specific price, supply, and climate features
    → generic forecasts, risk signals, recommendations, decision memos
    → chocolate maker dashboard
```

### 1.3 What Should Be Reusable

Generalize these:

| Shared Component | Purpose |
|---|---|
| Source run logging | Track ingestion jobs, failures, freshness, and record counts |
| Data freshness checks | Detect stale or missing data |
| Time-series storage | Store prices, supply metrics, climate signals, and other observations |
| Forecast storage | Store prediction outputs and backtest metadata |
| Risk signal schema | Standard structure for risk outputs |
| Scenario engine | Reusable "what if" calculations |
| Recommendation schema | Standard action + confidence + rationale object |
| Decision memo generation | Convert data into buyer-friendly explanations |
| Chart and card components | Reusable dashboard UI primitives |

### 1.4 What Should Stay Domain-Specific

Keep these domain-specific:

| Domain-Specific Layer | Coffee Example | Cacao Example |
|---|---|---|
| Data fetchers | ICE Coffee C, ICO, USDA, NOAA, CHIRPS | ICE Cocoa, ICCO, FAOSTAT/USDA, NOAA, CHIRPS |
| Asset taxonomy | Brazil Arabica, Colombia Arabica, Ethiopia | Ghana cocoa, Côte d'Ivoire cocoa, Ecuador fine flavor cacao |
| Feature engineering | Rainfall anomaly for coffee regions, ENSO impact by origin | West African rainfall anomaly, disease/pod rot risk, export arrivals |
| Recommendation rules | Buy / Neutral / Caution | Buy / Neutral / Caution |
| UI language | "origin risk", "green coffee margin" | "origin risk", "cacao bean margin" |
| Outreach and positioning | Specialty roasters | Bean-to-bar chocolate makers |

---

## 2. High-Level Repo Structure

Use a modular monorepo.

```text
greensignal/
  README.md
  pyproject.toml
  .env.example

  apps/
    web/                         # React/Vite frontend
      src/
        components/
        pages/
        api/
        charts/
        domain/
          coffee/
          cacao/

    api/                         # FastAPI backend
      main.py
      routes/
        health.py
        coffee.py
        cacao.py
        admin.py

  core/
    models/                      # canonical schemas
      asset.py
      observation.py
      forecast.py
      risk_signal.py
      recommendation.py
      scenario.py
      source_run.py
      source_config.py

    services/
      data_quality.py
      forecasting.py
      scenario_engine.py
      recommendation_engine.py
      explanation_engine.py
      freshness.py

    storage/
      db.py
      repositories.py
      migrations/

    utils/
      dates.py
      units.py
      logging.py

  domains/
    coffee/
      registry/
        assets.py
        regions.py

      sources/
        ice_coffee_c.py
        liffe_robusta.py
        ico_reports.py
        usda_psd.py
        noaa_enso.py
        chirps.py
        modis_ndvi.py

      features/
        price_features.py
        climate_features.py
        supply_features.py
        margin_features.py

      models/
        forecaster.py
        risk_scorer.py
        signal_generator.py

      routes/
        coffee_routes.py

    cacao/
      registry/
        assets.py
        regions.py

      sources/
        ice_cocoa.py
        icco_reports.py
        faostat.py
        usda_psd.py
        noaa_enso.py
        chirps.py
        modis_ndvi.py

      features/
        price_features.py
        climate_features.py
        supply_features.py
        margin_features.py

      models/
        forecaster.py
        risk_scorer.py
        signal_generator.py

      routes/
        cacao_routes.py

  jobs/
    coffee/
      daily_prices.py
      monthly_supply.py
      monthly_climate.py
      weekly_forecasts.py
      weekly_recommendations.py

    cacao/
      daily_prices.py
      monthly_supply.py
      monthly_climate.py
      weekly_forecasts.py
      weekly_recommendations.py

  notebooks/
    coffee_backtests/
    coffee_data_validation/
    cacao_exploration/

  tests/
    core/
    domains/
      coffee/
      cacao/
```

### 2.1 Important Repo Principle

The `core/` package must not import from `domains/coffee/` or `domains/cacao/`.

Allowed direction:

```text
domains/* → core
apps/* → core and domains
jobs/* → core and domains
```

Disallowed direction:

```text
core → domains/*
```

---

## 3. Canonical Objects: Reusable Layer

These are the shared objects all domains should produce or consume.

### 3.1 Asset

An `Asset` is something a buyer may procure or monitor.

For coffee, an asset may be:

- Brazil Arabica
- Colombia Arabica
- Ethiopia natural specialty coffee
- Robusta benchmark

For cacao, an asset may be:

- Ghana cocoa
- Côte d'Ivoire cocoa
- Ecuador fine flavor cacao
- ICE Cocoa benchmark

Canonical shape:

```json
{
  "asset_id": "coffee:origin:brazil:arabica",
  "domain": "coffee",
  "asset_type": "origin",
  "name": "Brazil Arabica",
  "unit": "lb",
  "metadata": {
    "country": "Brazil",
    "species": "arabica",
    "regions": ["cerrado", "sul_de_minas"]
  }
}
```

Cacao example:

```json
{
  "asset_id": "cacao:origin:ghana:bulk",
  "domain": "cacao",
  "asset_type": "origin",
  "name": "Ghana Cocoa",
  "unit": "metric_ton",
  "metadata": {
    "country": "Ghana",
    "market_segment": "bulk",
    "regions": ["ashanti", "western", "eastern"]
  }
}
```

### 3.2 MarketObservation

A `MarketObservation` stores price-like or market-quoted data.

Coffee example:

```json
{
  "asset_id": "coffee:benchmark:arabica_c",
  "timestamp": "2026-05-17",
  "metric": "futures_settlement_price",
  "value": 3.82,
  "unit": "usd_per_lb",
  "source": "ICE",
  "frequency": "daily",
  "metadata": {
    "contract": "Coffee C",
    "month": "front_month"
  }
}
```

Cacao example:

```json
{
  "asset_id": "cacao:benchmark:ice_cocoa",
  "timestamp": "2026-05-17",
  "metric": "futures_settlement_price",
  "value": 9200,
  "unit": "usd_per_metric_ton",
  "source": "ICE",
  "frequency": "daily",
  "metadata": {
    "contract": "ICE Cocoa",
    "month": "front_month"
  }
}
```

### 3.3 FeatureObservation

A `FeatureObservation` stores explanatory signals used for forecasting, risk scoring, or recommendations.

Coffee example:

```json
{
  "asset_id": "coffee:origin:brazil:arabica",
  "timestamp": "2026-05-01",
  "feature_name": "rainfall_anomaly_90d",
  "value": -0.42,
  "unit": "z_score",
  "source": "CHIRPS",
  "metadata": {
    "regions": ["cerrado", "sul_de_minas"]
  }
}
```

Cacao example:

```json
{
  "asset_id": "cacao:origin:ghana:bulk",
  "timestamp": "2026-05-01",
  "feature_name": "rainfall_anomaly_90d",
  "value": 0.31,
  "unit": "z_score",
  "source": "CHIRPS",
  "metadata": {
    "regions": ["ashanti", "western", "eastern"]
  }
}
```

### 3.4 Forecast

A `Forecast` stores model-generated future estimates.

Coffee example:

```json
{
  "asset_id": "coffee:origin:colombia:arabica",
  "generated_at": "2026-05-17T00:00:00Z",
  "target_metric": "estimated_origin_price",
  "horizon_days": 90,
  "p10": 3.55,
  "p50": 3.95,
  "p90": 4.35,
  "model_name": "coffee_arimax_v1",
  "model_version": "2026-05-17",
  "backtest_metrics": {
    "mae": 0.18,
    "mape": 0.074,
    "directional_accuracy": 0.62
  }
}
```

Cacao example:

```json
{
  "asset_id": "cacao:origin:ghana:bulk",
  "generated_at": "2026-05-17T00:00:00Z",
  "target_metric": "estimated_origin_price",
  "horizon_days": 90,
  "p10": 8100,
  "p50": 8900,
  "p90": 9800,
  "model_name": "cacao_arimax_v1",
  "model_version": "2026-05-17",
  "backtest_metrics": {
    "mae": 430,
    "mape": 0.069,
    "directional_accuracy": 0.59
  }
}
```

### 3.5 RiskSignal

A `RiskSignal` represents a risk that should affect procurement decisions.

Coffee example:

```json
{
  "asset_id": "coffee:origin:brazil:arabica",
  "generated_at": "2026-05-17T00:00:00Z",
  "risk_type": "supply_risk",
  "severity": "medium",
  "score": 0.63,
  "time_horizon": "90d",
  "explanation": "Rainfall anomaly and seasonal climate signals indicate elevated supply risk.",
  "supporting_features": {
    "rainfall_anomaly_90d": -0.42,
    "enso_state": "la_nina_watch",
    "price_percentile_2y": 0.71
  }
}
```

Cacao example:

```json
{
  "asset_id": "cacao:origin:ghana:bulk",
  "generated_at": "2026-05-17T00:00:00Z",
  "risk_type": "origin_supply_risk",
  "severity": "high",
  "score": 0.78,
  "time_horizon": "90d",
  "explanation": "Rainfall and production signals indicate elevated risk for West African cocoa supply.",
  "supporting_features": {
    "rainfall_anomaly_90d": 0.31,
    "production_revision_yoy": -0.08,
    "price_percentile_2y": 0.87
  }
}
```

### 3.6 Scenario

A `Scenario` models financial impact under a buyer-relevant assumption.

Coffee example:

```json
{
  "domain": "coffee",
  "asset_id": "coffee:origin:ethiopia:arabica",
  "scenario_type": "price_shock",
  "name": "Green coffee price rises 20%",
  "inputs": {
    "monthly_green_lbs": 440,
    "current_price_per_lb": 4.39,
    "shock_pct": 0.20,
    "retail_price_change_pct": 0.00
  },
  "outputs": {
    "monthly_cost_increase": 386.32,
    "annualized_cost_increase": 4635.84,
    "margin_impact_pct": -0.07
  }
}
```

Cacao example:

```json
{
  "domain": "cacao",
  "asset_id": "cacao:origin:ghana:bulk",
  "scenario_type": "price_shock",
  "name": "Cocoa bean price rises 20%",
  "inputs": {
    "monthly_cacao_kg": 500,
    "current_price_per_kg": 9.20,
    "shock_pct": 0.20,
    "retail_price_change_pct": 0.00
  },
  "outputs": {
    "monthly_cost_increase": 920.00,
    "annualized_cost_increase": 11040.00,
    "margin_impact_pct": -0.09
  }
}
```

### 3.7 Recommendation

A `Recommendation` is the final buyer-facing action object.

Coffee example:

```json
{
  "domain": "coffee",
  "asset_id": "coffee:origin:colombia:arabica",
  "generated_at": "2026-05-17T00:00:00Z",
  "action": "buy_forward",
  "label": "Buy",
  "confidence": 0.71,
  "time_horizon": "90d",
  "expected_value": 4200,
  "downside_risk": 1600,
  "explanation": "Current prices are below the 2-year range midpoint while climate risk is rising.",
  "supporting_data": {
    "price_percentile_2y": 0.43,
    "price_momentum_30d": 0.08,
    "climate_risk_score": 0.64
  }
}
```

Cacao example:

```json
{
  "domain": "cacao",
  "asset_id": "cacao:origin:ghana:bulk",
  "generated_at": "2026-05-17T00:00:00Z",
  "action": "buy_forward",
  "label": "Caution: consider partial forward buy",
  "confidence": 0.66,
  "time_horizon": "90d",
  "expected_value": 6200,
  "downside_risk": 2400,
  "explanation": "Cocoa prices are already elevated, but supply risk remains high. Consider partial coverage rather than full spot exposure.",
  "supporting_data": {
    "price_percentile_2y": 0.87,
    "climate_risk_score": 0.78,
    "production_revision_yoy": -0.08
  }
}
```

---

## 4. Database Schema

Use Postgres/Supabase for v1.

### 4.1 Assets

```sql
CREATE TABLE assets (
  asset_id TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  name TEXT NOT NULL,
  unit TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 Market Observations

```sql
CREATE TABLE market_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id TEXT REFERENCES assets(asset_id),
  timestamp TIMESTAMPTZ NOT NULL,
  metric TEXT NOT NULL,
  value NUMERIC NOT NULL,
  unit TEXT,
  source TEXT NOT NULL,
  frequency TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(asset_id, timestamp, metric, source)
);
```

### 4.3 Feature Observations

```sql
CREATE TABLE feature_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id TEXT REFERENCES assets(asset_id),
  timestamp TIMESTAMPTZ NOT NULL,
  feature_name TEXT NOT NULL,
  value NUMERIC,
  unit TEXT,
  source TEXT NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(asset_id, timestamp, feature_name, source)
);
```

### 4.4 Forecasts

```sql
CREATE TABLE forecasts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id TEXT REFERENCES assets(asset_id),
  generated_at TIMESTAMPTZ NOT NULL,
  target_metric TEXT NOT NULL,
  horizon_days INTEGER NOT NULL,
  p10 NUMERIC,
  p50 NUMERIC,
  p90 NUMERIC,
  model_name TEXT,
  model_version TEXT,
  backtest_metrics JSONB,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.5 Risk Signals

```sql
CREATE TABLE risk_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id TEXT REFERENCES assets(asset_id),
  generated_at TIMESTAMPTZ NOT NULL,
  risk_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  score NUMERIC,
  time_horizon TEXT,
  explanation TEXT,
  supporting_features JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.6 Recommendations

```sql
CREATE TABLE recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain TEXT NOT NULL,
  asset_id TEXT REFERENCES assets(asset_id),
  generated_at TIMESTAMPTZ NOT NULL,
  action TEXT NOT NULL,
  label TEXT NOT NULL,
  confidence NUMERIC,
  time_horizon TEXT,
  expected_value NUMERIC,
  downside_risk NUMERIC,
  explanation TEXT,
  supporting_data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 5. Scheduler and Run Logging

The platform should support sources with different update cadences.

Coffee examples:

| Source | Cadence |
|---|---|
| ICE Coffee C futures | Daily |
| LIFFE Robusta futures | Daily |
| ICO reports | Monthly |
| USDA/FAS/PSD | Monthly or periodic |
| NOAA ENSO | Weekly/monthly |
| CHIRPS rainfall | Monthly or dekadal |
| MODIS/NDVI | Weekly/monthly |
| Forecast generation | Weekly |
| Risk score generation | Weekly or on source update |
| Recommendation generation | Weekly or on source update |

Cacao examples:

| Source | Cadence |
|---|---|
| ICE Cocoa futures | Daily |
| ICCO reports | Monthly/quarterly |
| FAOSTAT/USDA | Periodic |
| NOAA ENSO | Weekly/monthly |
| CHIRPS rainfall | Monthly or dekadal |
| MODIS/NDVI | Weekly/monthly |
| Forecast generation | Weekly |
| Risk score generation | Weekly or on source update |
| Recommendation generation | Weekly or on source update |

### 5.1 Source Config Table

```sql
CREATE TABLE source_config (
  source_name TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  cadence TEXT NOT NULL,
  freshness_sla_hours INTEGER NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  last_successful_run_at TIMESTAMPTZ,
  next_run_at TIMESTAMPTZ,
  owner TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Example rows:

```sql
INSERT INTO source_config (
  source_name, domain, cadence, freshness_sla_hours, enabled, owner
) VALUES
  ('ice_coffee_c', 'coffee', 'daily', 36, TRUE, 'data'),
  ('ico_reports', 'coffee', 'monthly', 1080, TRUE, 'data'),
  ('chirps_coffee_regions', 'coffee', 'monthly', 1080, TRUE, 'data'),
  ('ice_cocoa', 'cacao', 'daily', 36, TRUE, 'data'),
  ('icco_reports', 'cacao', 'monthly', 1440, TRUE, 'data');
```

### 5.2 Source Run Log Table

```sql
CREATE TABLE source_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain TEXT NOT NULL,
  source_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL,
  records_fetched INTEGER,
  records_inserted INTEGER,
  records_updated INTEGER,
  records_failed INTEGER,
  data_start_date TIMESTAMPTZ,
  data_end_date TIMESTAMPTZ,
  error_message TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Recommended `status` values:

```text
started
success
partial_success
failed
skipped
```

### 5.3 Source Freshness Rules

Each ingestion source must have:

- expected cadence
- maximum stale duration
- last successful run
- current freshness status

Freshness statuses:

```text
fresh
stale
missing
failed
disabled
```

Example logic:

```python
from datetime import datetime, timezone

def get_freshness_status(last_successful_run_at, freshness_sla_hours, enabled=True):
    if not enabled:
        return "disabled"

    if last_successful_run_at is None:
        return "missing"

    now = datetime.now(timezone.utc)
    age_hours = (now - last_successful_run_at).total_seconds() / 3600

    if age_hours > freshness_sla_hours:
        return "stale"

    return "fresh"
```

---

## 6. Data Engineering Plan

### 6.1 Principles

1. Source-specific fetchers should produce normalized records.
2. All raw source data should be stored or cached when practical.
3. Processed data should be inserted into canonical tables.
4. Every job should log success/failure in `source_runs`.
5. Jobs should be idempotent.
6. Duplicate records should be handled through database uniqueness constraints.
7. Missing data should not crash the whole pipeline.
8. Data quality checks should run after ingestion.
9. Forecasts and recommendations should include model version and supporting data.
10. Do not build heavy orchestration infrastructure until necessary.

### 6.2 Initial Orchestration

For v1, use simple scheduled jobs:

- GitHub Actions cron
- or a lightweight VPS cron
- or Supabase scheduled functions if convenient

Do not start with Airflow. Add Prefect or Dagster only after the number of jobs and dependencies becomes hard to manage.

### 6.3 Data Ingestion Flow

Every source adapter should follow this shape:

```text
fetch raw data
    → validate basic source response
    → parse into source-specific intermediate records
    → map into canonical observations
    → upsert into Postgres
    → run data quality checks
    → log source run
```

### 6.4 Source Adapter Interface

```python
from abc import ABC, abstractmethod

class SourceAdapter(ABC):
    source_name: str
    domain: str

    @abstractmethod
    def fetch(self):
        """Fetch raw source data."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw_data):
        """Parse raw data into source-specific records."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, parsed_records) -> list[dict]:
        """Map parsed records into canonical observation dictionaries."""
        raise NotImplementedError

    def run(self, repository, run_logger):
        run_id = run_logger.start(domain=self.domain, source_name=self.source_name)

        try:
            raw = self.fetch()
            parsed = self.parse(raw)
            normalized = self.normalize(parsed)

            result = repository.upsert_observations(normalized)

            run_logger.success(
                run_id=run_id,
                records_fetched=len(parsed),
                records_inserted=result.inserted,
                records_updated=result.updated,
            )

            return result

        except Exception as exc:
            run_logger.failure(run_id=run_id, error_message=str(exc))
            raise
```

### 6.5 Coffee Data Engineering Plan

#### Sources

| Source | Output Table | Notes |
|---|---|---|
| ICE Coffee C | `market_observations` | Daily benchmark price |
| LIFFE Robusta | `market_observations` | Daily robusta benchmark |
| ICO reports | `feature_observations` | Monthly price/supply/trade indicators |
| USDA/FAS/PSD | `feature_observations` | Production, consumption, stocks |
| NOAA ENSO | `feature_observations` | ENSO state/index |
| CHIRPS | `feature_observations` | Rainfall anomalies by coffee-growing region |
| MODIS/NDVI | `feature_observations` | Vegetation health by origin region |

#### Coffee Feature Jobs

Generate these features:

```text
price_percentile_52w
price_percentile_2y
price_momentum_30d
price_momentum_90d
volatility_90d
futures_curve_slope
origin_supply_growth_yoy
rainfall_anomaly_30d
rainfall_anomaly_90d
vegetation_health_score
enso_state
climate_risk_score
margin_compression_score
```

#### Coffee Recommendation Jobs

Generate:

```text
Buy
Neutral
Caution
Avoid large forward buy
Consider partial forward buy
Monitor supply risk
Margin compression warning
```

### 6.6 Cacao Data Engineering Plan

#### Sources

| Source | Output Table | Notes |
|---|---|---|
| ICE Cocoa | `market_observations` | Daily benchmark price |
| ICCO reports | `feature_observations` | Monthly/quarterly market commentary, supply/demand |
| FAOSTAT / USDA | `feature_observations` | Production and country-level supply data |
| NOAA ENSO | `feature_observations` | Climate state |
| CHIRPS | `feature_observations` | Rainfall anomalies in cacao-growing regions |
| MODIS/NDVI | `feature_observations` | Vegetation health by cacao origin |
| Export arrivals / origin reports | `feature_observations` | Optional v2 data if available |

#### Cacao Feature Jobs

Generate these features:

```text
price_percentile_52w
price_percentile_2y
price_momentum_30d
price_momentum_90d
volatility_90d
futures_curve_slope
origin_supply_growth_yoy
rainfall_anomaly_30d
rainfall_anomaly_90d
vegetation_health_score
enso_state
west_africa_supply_risk_score
margin_compression_score
```

#### Cacao Recommendation Jobs

Generate:

```text
Buy
Neutral
Caution
Consider partial forward buy
Monitor West Africa supply risk
Margin compression warning
```

### 6.7 Data Quality Checks

Implement checks at three levels.

#### Source-Level Checks

```text
Did the source return data?
Did the response schema match expectations?
Are required columns present?
Are timestamps parseable?
Are numeric values parseable?
```

#### Observation-Level Checks

```text
Is asset_id valid?
Is timestamp non-null?
Is metric/feature name non-null?
Is value numeric when required?
Is unit present?
Is source present?
```

#### Domain-Level Checks

Coffee examples:

```text
Coffee futures price should not be negative.
Daily price change above threshold should be flagged.
Missing more than N daily prices should trigger stale warning.
Rainfall anomaly values should be in plausible range.
Origin mapping should exist before feature generation.
```

Cacao examples:

```text
Cocoa futures price should not be negative.
Daily price change above threshold should be flagged.
Missing ICCO/production data should not block benchmark price updates.
Rainfall anomaly values should be in plausible range.
Origin mapping should exist before feature generation.
```

---

## 7. Important Design Rule

Never write coffee-specific or cacao-specific logic in `core/`.

### 7.1 Bad Pattern

Do not do this:

```python
def generate_risk_score(asset, features):
    if asset.domain == "coffee" and asset.metadata["country"] == "Brazil":
        return brazil_coffee_drought_score(features)

    if asset.domain == "cacao" and asset.metadata["country"] == "Ghana":
        return ghana_cacao_supply_score(features)
```

This makes the core brittle.

### 7.2 Good Pattern

Use domain adapters:

```python
class DomainAdapter:
    domain: str

    def build_features(self, asset_id: str):
        raise NotImplementedError

    def generate_forecast(self, asset_id: str, features: dict):
        raise NotImplementedError

    def generate_risk_signals(self, asset_id: str, features: dict):
        raise NotImplementedError

    def generate_recommendations(
        self,
        asset_id: str,
        features: dict,
        forecasts: list,
        risk_signals: list,
        scenarios: list,
    ):
        raise NotImplementedError
```

Coffee implementation:

```python
class CoffeeAdapter(DomainAdapter):
    domain = "coffee"

    def build_features(self, asset_id: str):
        return build_coffee_features(asset_id)

    def generate_forecast(self, asset_id: str, features: dict):
        return coffee_forecaster.forecast(asset_id, features)

    def generate_risk_signals(self, asset_id: str, features: dict):
        return coffee_risk_scorer.score(asset_id, features)

    def generate_recommendations(
        self,
        asset_id: str,
        features: dict,
        forecasts: list,
        risk_signals: list,
        scenarios: list,
    ):
        return coffee_signal_generator.generate(
            asset_id=asset_id,
            features=features,
            forecasts=forecasts,
            risk_signals=risk_signals,
            scenarios=scenarios,
        )
```

Cacao implementation:

```python
class CacaoAdapter(DomainAdapter):
    domain = "cacao"

    def build_features(self, asset_id: str):
        return build_cacao_features(asset_id)

    def generate_forecast(self, asset_id: str, features: dict):
        return cacao_forecaster.forecast(asset_id, features)

    def generate_risk_signals(self, asset_id: str, features: dict):
        return cacao_risk_scorer.score(asset_id, features)

    def generate_recommendations(
        self,
        asset_id: str,
        features: dict,
        forecasts: list,
        risk_signals: list,
        scenarios: list,
    ):
        return cacao_signal_generator.generate(
            asset_id=asset_id,
            features=features,
            forecasts=forecasts,
            risk_signals=risk_signals,
            scenarios=scenarios,
        )
```

Core orchestrator:

```python
def run_domain_recommendation_pipeline(domain_adapter: DomainAdapter, asset_ids: list[str]):
    for asset_id in asset_ids:
        features = domain_adapter.build_features(asset_id)
        forecasts = [domain_adapter.generate_forecast(asset_id, features)]
        risk_signals = domain_adapter.generate_risk_signals(asset_id, features)
        scenarios = scenario_engine.generate_default_scenarios(
            domain=domain_adapter.domain,
            asset_id=asset_id,
            features=features,
            forecasts=forecasts,
            risk_signals=risk_signals,
        )
        recommendations = domain_adapter.generate_recommendations(
            asset_id=asset_id,
            features=features,
            forecasts=forecasts,
            risk_signals=risk_signals,
            scenarios=scenarios,
        )

        recommendation_repository.save_many(recommendations)
```

---

## 8. API Design

### 8.1 Shared API Pattern

```text
GET /api/{domain}/assets
GET /api/{domain}/assets/{asset_id}/price
GET /api/{domain}/assets/{asset_id}/features
GET /api/{domain}/assets/{asset_id}/forecast
GET /api/{domain}/assets/{asset_id}/risk
GET /api/{domain}/assets/{asset_id}/recommendation
POST /api/{domain}/calculator/margin
```

### 8.2 Coffee v1 Routes

```text
GET /api/coffee/origins
GET /api/coffee/origins/{origin_id}/price
GET /api/coffee/origins/{origin_id}/forecast
GET /api/coffee/origins/{origin_id}/risk
GET /api/coffee/origins/{origin_id}/signal
POST /api/coffee/calculator/margin
```

### 8.3 Cacao Future Routes

```text
GET /api/cacao/origins
GET /api/cacao/origins/{origin_id}/price
GET /api/cacao/origins/{origin_id}/forecast
GET /api/cacao/origins/{origin_id}/risk
GET /api/cacao/origins/{origin_id}/signal
POST /api/cacao/calculator/margin
```

---

## 9. MVP Build Plan

### Phase 1: Coffee Product Only, Modular Internals

Build:

```text
core/
domains/coffee/
apps/api/
apps/web/
jobs/coffee/
```

Do not build cacao UI yet. Only add cacao-ready abstractions.

Deliver:

- coffee asset registry
- coffee ingestion jobs
- source run logging
- data freshness checks
- canonical observations
- coffee feature generation
- coffee forecast storage
- coffee risk signals
- coffee recommendation cards
- margin calculator
- roaster-facing dashboard

### Phase 2: Extract Reusable Core

After coffee v1 works, move repeated logic into `core/`.

Prioritize:

- source run logging
- data validation
- data freshness checks
- scenario engine
- recommendation object
- explanation templates
- chart API response patterns

### Phase 3: Add Cacao as First Expansion Domain

Add:

```text
domains/cacao/
jobs/cacao/
apps/api/routes/cacao.py
apps/web/domain/cacao/
```

Reuse:

- canonical data model
- source run logging
- freshness checks
- forecasts table
- risk signals table
- recommendations table
- scenario engine
- margin calculator patterns

Create cacao-specific:

- asset registry
- source adapters
- climate region mappings
- feature engineering
- risk scoring
- recommendation rules
- UI copy

---

## 10. Coding Agent Instructions

### 10.1 Build Priorities

1. Create the canonical models and database schema.
2. Implement source run logging and freshness checks.
3. Implement coffee asset registry.
4. Implement one coffee price source adapter.
5. Implement one climate feature source adapter.
6. Implement normalized insertion into `market_observations` and `feature_observations`.
7. Implement data quality checks.
8. Implement coffee feature generation.
9. Implement basic forecast storage.
10. Implement rule-based coffee risk scoring.
11. Implement Buy / Neutral / Caution recommendation generation.
12. Build FastAPI routes for coffee.
13. Build basic React dashboard.
14. Add margin calculator.
15. Add tests for all canonical models and ingestion adapters.

### 10.2 Do Not Build Yet

Do not build:

- Generic commodity dashboard
- Compute procurement integration
- Full marketplace
- User-uploaded purchase history
- Importer/broker integrations
- Complex multi-tenant enterprise permissions
- Airflow deployment
- Advanced ML models before baseline models work
- Fully automated trading or purchasing actions

### 10.3 Required Engineering Behaviors

- Use typed Python.
- Use Pydantic models for API contracts.
- Use database uniqueness constraints to make ingestion idempotent.
- Log every source run.
- Store model version with every forecast.
- Store supporting features with every risk signal and recommendation.
- Keep domain-specific logic out of `core/`.
- Write tests for source normalization.
- Write tests for feature generation.
- Write tests for recommendation logic.
- Treat missing data gracefully.

---

## 11. Example Coffee Recommendation Logic v1

Start with simple, explainable rules.

Inputs:

```text
price_percentile_2y
price_momentum_30d
price_momentum_90d
climate_risk_score
volatility_90d
margin_compression_score
```

Basic logic:

```python
def generate_coffee_signal(features: dict) -> dict:
    price_percentile = features["price_percentile_2y"]
    momentum_30d = features["price_momentum_30d"]
    climate_risk = features["climate_risk_score"]
    margin_compression = features["margin_compression_score"]

    score = 0.0

    # Lower current price relative to history increases buy attractiveness.
    if price_percentile < 0.35:
        score += 0.30
    elif price_percentile > 0.75:
        score -= 0.20

    # Rising momentum may increase urgency.
    if momentum_30d > 0.05:
        score += 0.15

    # Higher climate risk may increase forward-buy attractiveness,
    # but only if price is not already extremely elevated.
    if climate_risk > 0.65 and price_percentile < 0.80:
        score += 0.25

    # Margin compression increases the need for planning.
    if margin_compression > 0.60:
        score += 0.10

    if score >= 0.45:
        label = "Buy"
        action = "consider_forward_buy"
    elif score <= -0.10:
        label = "Caution"
        action = "avoid_large_forward_buy"
    else:
        label = "Neutral"
        action = "monitor"

    return {
        "label": label,
        "action": action,
        "confidence": min(max(abs(score), 0.30), 0.85),
        "supporting_data": features,
    }
```

Important: v1 recommendations should be framed as decision support, not as guaranteed price predictions.

---

## 12. Example Cacao Recommendation Logic v1

Use the same structure, but cacao-specific features.

Inputs:

```text
price_percentile_2y
price_momentum_30d
west_africa_supply_risk_score
rainfall_anomaly_90d
production_revision_yoy
margin_compression_score
```

Basic logic:

```python
def generate_cacao_signal(features: dict) -> dict:
    price_percentile = features["price_percentile_2y"]
    momentum_30d = features["price_momentum_30d"]
    supply_risk = features["west_africa_supply_risk_score"]
    production_revision = features["production_revision_yoy"]
    margin_compression = features["margin_compression_score"]

    score = 0.0

    if price_percentile < 0.35:
        score += 0.25
    elif price_percentile > 0.85:
        score -= 0.10

    if momentum_30d > 0.05:
        score += 0.10

    if supply_risk > 0.70:
        score += 0.25

    if production_revision < -0.05:
        score += 0.15

    if margin_compression > 0.60:
        score += 0.10

    if score >= 0.45:
        label = "Buy"
        action = "consider_partial_forward_buy"
    elif score <= -0.05:
        label = "Caution"
        action = "avoid_large_forward_buy"
    else:
        label = "Neutral"
        action = "monitor"

    return {
        "label": label,
        "action": action,
        "confidence": min(max(abs(score), 0.30), 0.85),
        "supporting_data": features,
    }
```

---

## 13. Frontend Plan

### 13.1 Shared Components

Create reusable UI components:

```text
MetricCard
PriceChart
ForecastBandChart
RiskSignalCard
RecommendationCard
ScenarioCalculator
SourceFreshnessBadge
AssetSelector
```

### 13.2 Coffee Screens

Coffee MVP pages:

```text
/coffee
/coffee/origins/{origin_id}
/coffee/margin-calculator
/coffee/source-health
```

Coffee dashboard should include:

- current benchmark price
- origin cards
- 52-week range indicator
- 12-month price chart
- 30/60/90-day forecast
- climate/origin risk score
- buy/neutral/caution recommendation
- plain-language explanation
- margin calculator

### 13.3 Cacao Screens

Do not build immediately. Future pages:

```text
/cacao
/cacao/origins/{origin_id}
/cacao/margin-calculator
/cacao/source-health
```

Reuse the coffee layout with cacao-specific copy and assets.

---

## 14. Final Architecture Summary

The correct architecture is:

```text
Vertical product, horizontal core.
```

GreenSignal should launch as a coffee-specific product.

Internally, the system should use general procurement-intelligence primitives:

- assets
- market observations
- feature observations
- forecasts
- risk signals
- scenarios
- recommendations
- source configs
- source runs

The first expansion domain should be cacao because it is structurally closest to coffee.

Do not overbuild a generic product. Build GreenSignal well, but keep the data model and pipeline clean enough that cacao can be added without rewriting the system.

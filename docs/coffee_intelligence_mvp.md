# GreenSignal: Coffee Purchasing Intelligence — MVP Document

---

## 1. What This Is

A purchasing intelligence tool for small-to-mid specialty coffee roasters. It aggregates public commodity price data, climate signals, and supply indicators into actionable purchasing recommendations — helping roasters decide *when* to buy green coffee, *how much* to buy forward, and *which origins* are supply-risky right now.

The core value proposition in one sentence: **broker-independent, ML-powered purchasing intelligence that gives small roasters the same decision support large roasters have in-house.**

---

## 2. The ROI Case (Honest Numbers)

### Real price data
- Median specialty green coffee price in 2024/25: **$4.39/lb** (Specialty Coffee Transaction Guide)
- ICO Composite Price (commodity grade): **$3.37/lb** as of March 2025
- Year-over-year price change 2024–2025: **+76.4%** on commodity, +7.6% on retail
- In February 2025, C-market price exceeded $4.40/lb — up 70% from the prior three years

### ROI by roaster size

| Roaster Size | Green Coffee/Month | Annual Green Coffee Spend | 5% Better Timing | 10% Better Timing |
|---|---|---|---|---|
| Small (100kg/mo) | 220 lbs | ~$11,600 | $580/yr | $1,160/yr |
| Small-mid (200kg/mo) | 440 lbs | ~$23,200 | $1,160/yr | $2,320/yr |
| Mid (500kg/mo) | 1,100 lbs | ~$58,000 | $2,900/yr | $5,800/yr |

At $99/month subscription ($1,188/yr): a 200kg/month roaster breaks even at ~5% timing improvement. Plausible. A 500kg/month roaster gets clear positive ROI.

### The spike scenario (strongest case)
The real value isn't marginal improvement — it's avoiding catastrophic margin compression during price spikes. A roaster who bought 3 months of supply *before* the 2024 Arabica price spike vs. one who bought spot during the spike:
- On $50K annual green coffee spend: **difference of $15,000–35,000** in that one year
- One good forward-buying decision can justify years of subscription

### The margin squeeze reality
Roasters are raising retail prices 7.6% year-over-year while green coffee costs rise 76.4%. That gap is not sustainable. Any tool that helps manage the timing of green coffee purchases is protecting their core margin.

### Suggested pricing
- **Free tier**: price dashboard, 2 origins, 30-day history
- **Pro ($79/mo)**: full origin coverage, 90-day forecast, purchasing recommendations
- **Growth ($149/mo)**: all origins, 12-month forecast, margin calculator, forward-buying scenarios, origin risk scores

Target customer: roasters buying 150kg+ per month (where ROI is clear).

---

## 3. Data Pipeline Feasibility

### Available public data sources

**Price data**
| Source | Data | Access | Cost |
|---|---|---|---|
| ICE Futures (Intercontinental Exchange) | Arabica C-market daily prices, futures curves | Quandl/Nasdaq Data Link API, Yahoo Finance | Free tier available |
| LIFFE (London) | Robusta futures | Quandl | Free tier available |
| ICO (International Coffee Organization) | Monthly production, trade, price data by origin | Direct download (CSV/Excel) | Free |
| USDA Foreign Agricultural Service | Global production estimates by country | PSD Online API | Free |

**Climate and supply signals**
| Source | Data | Access | Cost |
|---|---|---|---|
| NOAA ENSO | El Niño/La Niña index (critical for Vietnam, Indonesia, Peru) | API | Free |
| CHIRPS | Rainfall anomaly data at 0.05° resolution for any origin region | API | Free |
| MODIS/Sentinel-2 | Vegetation indices (NDVI) for coffee-growing regions | Google Earth Engine | Free (with account) |
| Global Drought Monitor | Drought severity indices | Web + download | Free |
| NOAA Climate Prediction Center | Seasonal outlook (90-day precipitation/temp forecasts) | API | Free |

**Trade and logistics**
| Source | Data | Access | Cost |
|---|---|---|---|
| USDA WASDE | Monthly world supply/demand estimates | API | Free |
| Port of Hamburg / Santos shipping data | Partial shipping delay indicators | Some free proxies | Mixed |

### Verdict on feasibility
The core data pipeline — price history + climate signals + supply indicators — is **entirely buildable from public free sources.** You do not need expensive data providers to build a credible v1. The primary engineering work is:
1. Ingestion and normalization across sources (different update frequencies, formats)
2. Mapping climate regions to origin-specific signals (e.g., Brazilian Cerrado drought → Arabica supply risk)
3. Time-series forecasting model on price data with climate features as covariates
4. Clean API layer for the frontend

The model architecture — time series forecasting with exogenous climate variables — is well-suited to tools like Prophet (Meta), NeuralProphet, or a custom ARIMA-X model. BoTorch/Optuna for hyperparameter tuning. This is tractable solo ML work.

---

## 4. Commodity Generalizability

The same data pipeline architecture applies across multiple commodity markets. Here's an honest assessment:

### Strong fit: Cacao / Craft Chocolate
- **Structure**: Identical to coffee. Origin-specific, climate-sensitive, specialty tier with passionate small producers.
- **Data**: ICE Cocoa futures (public), ICCO (International Cocoa Organization) reports, same climate sources
- **Buyers**: Small bean-to-bar chocolate makers face the identical purchasing intelligence gap
- **Verdict**: Direct port of the coffee product. Same community structure, reachable through similar channels. Natural first expansion after coffee.

### Strong fit: Shrimp / Specialty Seafood
- **Structure**: El Niño/La Niña directly impacts Pacific shrimp supply. Disease outbreaks (EMS) have precursor signals. Seasonal supply patterns are well-documented.
- **Data**: NOAA fisheries data, FAO aquaculture production, CME shrimp futures (limited), ENSO indices are the primary driver
- **Buyers**: Restaurant seafood buyers, small seafood distributors, specialty fish wholesalers
- **Why it's interesting for you specifically**: Your ShrimpShield background means you already understand the domain. The same climate-signal logic that makes coffee pricing predictable applies strongly to shrimp — El Niño effects on Pacific shrimp are well-documented and lead by 3-6 months.
- **Verdict**: Strong fit. Different data sources but same ML architecture. The ShrimpShield research is a head start on domain understanding.

### Weak fit: Metals
- **Why it's weak**: LME metals markets are liquid and well-covered by Bloomberg, Reuters, and dozens of specialized services. Buyers are generally larger and more sophisticated. The climate signal is largely absent — metals pricing is driven by geopolitics, energy costs, and industrial demand, not weather. Small jewelry makers or fabricators might theoretically benefit, but the market is more efficient and the edge smaller.
- **Verdict**: Not worth pursuing with this architecture.

### Weak fit: Electricity
- **Why it's weak**: Electricity is hyper-localized (varies by grid/state/hour), real-time, and heavily regulated. The problem structure is fundamentally different from agricultural commodities. Energy management software (AutoGrid, EnerNOC, etc.) already serves this space well.
- **Verdict**: Different problem entirely. Skip.

### Expansion roadmap
**Phase 1**: Coffee (acute pain, reachable community, data pipeline buildable now)
**Phase 2**: Cacao (direct port, same architecture, adjacent community)
**Phase 3**: Specialty seafood (different data sources, Abhiraj's domain background, restaurant buyer market)
**Long term**: Platform for specialty agricultural commodity buyers — a single product serving coffee roasters, chocolate makers, and seafood buyers with origin-specific purchasing intelligence.

---

## 5. MVP Feature Set

### What to build first (v1)

**Core: Price intelligence dashboard**
- Current price by origin (Ethiopia, Colombia, Guatemala, Brazil, Kenya — top 5 specialty origins)
- Price vs. 52-week range (simple visual: low / mid / high indicator)
- Price trend chart (12 months historical)
- Basic 30/60/90-day price forecast with confidence band

**Purchasing signal**
- A simple Buy / Neutral / Caution signal per origin, derived from:
  - Current price position relative to 2-year historical range
  - Trend direction (rising / stable / falling)
  - Climate risk score for current season
- One-line plain-language explanation: *"Ethiopia prices are near a 2-year low. Current La Niña conditions suggest stable supply through Q3. Lean towards buying."*

**Origin risk monitor**
- Climate risk score per origin (updated monthly from ENSO + CHIRPS)
- Simple risk flags: drought, excessive rainfall, disease pressure (where data exists)

**Margin calculator**
- Input: current retail bag price, batch size, green coffee cost per lb
- Output: current margin, margin at +10%/+20%/+30% green coffee price
- Forward scenario: "If I lock in 3 months supply at today's price, here's my margin floor"

### What to defer (v2+)
- Personalized recommendations based on purchasing history (requires user data accumulation)
- Automatic forward contract recommendations
- Integration with importers/brokers
- Cacao/seafood expansion
- Multi-user / team features

---

## 6. Technical Architecture

```
Data Layer (ingestion + normalization)
├── ICE Futures price feed (daily) → price_history table
├── ICO monthly reports (parser) → origin_supply table  
├── USDA WASDE (monthly) → global_supply table
├── NOAA ENSO index (monthly) → climate_signals table
├── CHIRPS rainfall anomaly (monthly, by region) → rainfall_anomaly table
└── MODIS NDVI (monthly, by region) → vegetation_health table

ML Layer
├── Time series model per origin (price forecast)
│   └── NeuralProphet or ARIMA-X with climate features as covariates
├── Climate risk scorer (rule-based + lightweight ML)
│   └── ENSO state × regional rainfall anomaly → risk score
└── Buy/Neutral/Caution signal generator
    └── Combines price position, trend, climate risk

API Layer (FastAPI)
├── /origins/{origin}/price — current price + history
├── /origins/{origin}/forecast — 90-day forecast
├── /origins/{origin}/signal — buy/neutral/caution
├── /origins/{origin}/risk — climate risk score
└── /calculator/margin — margin scenario calculation

Frontend (React + Vite — your existing stack)
├── Origin dashboard
├── Signal cards
├── Price charts (Recharts — already in BotanistAI)
└── Margin calculator
```

**Infrastructure**: Vercel (frontend + serverless functions — your existing stack). Supabase for data storage. Python scripts on a simple cron (GitHub Actions or a lightweight VPS) for daily/monthly data ingestion.

**Estimated build time for v1**: 6-8 weeks solo. Data pipeline is the bulk of the work (3-4 weeks). Frontend is fast given your existing stack.

---

## 7. Target Customers: Outreach List

### ICP (Ideal Customer Profile)
- Owner-operated specialty roastery
- Buying 100–500kg green coffee per month
- Specialty/direct trade focused (means they're already thinking about green coffee quality and sourcing)
- Active on Instagram (owner runs the account — directly reachable)
- Not yet acquired by a larger group

### Specific roasters to contact first

These are small-to-mid owner-operated roasters with direct trade focus and Instagram presence. They're sophisticated enough to understand pricing intelligence but small enough to lack it internally.

| Roaster | Location | Why They're a Good Target |
|---|---|---|
| **Camber Coffee** | Bellingham, WA | Owner-operated, quality-focused, approachable scale |
| **Sweet Bloom Coffee Roasters** | Lakewood, CO | Small, direct trade emphasis, transparency-focused |
| **Parlor Coffee** | Brooklyn, NY | Small, direct trade, owner active on social |
| **Stamp Act Coffee** | Seattle, WA | Founded by industry veteran, thoughtful sourcing |
| **Passenger Coffee** | Lancaster, PA | Quality control focus, independent |
| **Velo Coffee Roasters** | Chattanooga, TN | Small, community-focused |
| **Chrome Yellow Coffee** | Atlanta, GA | Small, owner-operated |
| **Bird Rock Coffee Roasters** | San Diego, CA | Direct trade, 25+ coffees 90+ score, independent |
| **Ritual Coffee Roasters** | San Francisco, CA | Direct trade since 2007, independent |
| **Madcap Coffee** | Grand Rapids, MI | Direct trade, mid-size, quality-focused |
| **Heart Coffee Roasters** | Portland, OR | Thoughtful sourcing, quality-focused |
| **Metric Coffee** | Chicago, IL | "Radical transparency," direct trade |
| **Victrola Coffee Roasters** | Seattle, WA | Independent, quality-focused |
| **Red Rooster Coffee** | Floyd, VA | Sustainability focus, 40+ 90-point coffees |
| **JBC Coffee Roasters** | Madison, WI | Long-standing, independent, quality awards |

### How to find more
- **Instagram**: Search #greencoffee #coffeeroaster #directtrade. Look for accounts where the owner posts personally about sourcing trips, green coffee lots, and price increases.
- **Roast Magazine**: Publishes annual Micro Roaster / Small Roaster of the Year — these are exactly the profile you want.
- **SCA member directory**: Searchable database of specialty coffee businesses.
- **coffeebeaned.com**: Has a US roaster list by state — good for geographic targeting.

### Outreach approach
Don't sell. Open with genuine curiosity about their business and pricing challenges. The 2024-2025 price spike gives you a natural, timely opener:

> *"Hi [name], I'm building a green coffee purchasing intelligence tool for independent roasters — helping with timing decisions and origin risk signals. Given what's happened to Arabica prices in the past 18 months, I'm talking to roasters about how they navigate purchasing decisions. Would you have 20 minutes for a call? Happy to share what I'm building in exchange for your perspective."*

Aim for 5-10 discovery conversations before building. Each conversation will sharpen the product before you've written a line of code.

---

## 8. Risks

### 1. Price forecasting accuracy
**The risk**: Commodity markets are notoriously difficult to predict. If the forecast is wrong consistently, the product loses credibility fast.

**Mitigation**: Don't position as a price prediction tool. Position as *context and decision support*. The value is "here's where prices are relative to history, here's the climate risk picture, here's what buying forward would mean for your margin" — not "prices will be X in 3 months." Frame confidence intervals clearly. Accuracy on directional signals (rising / stable / falling) over 60-90 day windows is more achievable than point forecasts.

### 2. Cropster expanding into this
**The risk**: Cropster is explicitly building a "Coffee OS." They have the roaster relationships and could add purchasing intelligence as a feature.

**Mitigation**: They're operationally focused (what happened during the roast) and enterprise-oriented. Purchasing intelligence is a different data domain requiring different expertise. You can move faster. If they do expand here, it validates the pain and potentially makes you an acquisition target.

### 3. Small market ceiling
**The risk**: ~5,000-8,000 addressable roasters in the US, global ceiling of $15-20M ARR in coffee alone.

**Mitigation**: This is fine for a solo developer building a profitable business. The expansion to cacao, specialty seafood, and other agricultural commodities multiplies the TAM. The data infrastructure built for coffee is largely reusable.

### 4. Data access changes
**The risk**: Public data sources change APIs, add paywalls, or degrade quality.

**Mitigation**: Use multiple redundant sources for critical price data. ICE futures data is available through multiple resellers. ICO and USDA data is unlikely to disappear. Build the ingestion layer to be source-agnostic.

### 5. Behavior change is hard
**The risk**: Roasters may look at the signal and still buy the way they always have. Changing purchasing behavior is a habit problem, not an information problem.

**Mitigation**: Make the recommendations extremely specific and actionable ("you typically buy 80kg of this Ethiopia lot monthly — consider buying 160kg now at today's price before Q3 supply tightens") rather than generic signals. Friction-to-action must be near zero.

### 6. You don't know coffee yet
**The risk**: Building for a domain you don't know is risky — you might solve the wrong problem.

**Mitigation**: Do 5-10 roaster conversations before building. The data pipeline work (ingestion, normalization, exploratory analysis) can proceed in parallel — it teaches you the domain while building the product foundation.

---

## 9. Build Sequence

1. **Data exploration** (Week 1-2): Pull ICE futures data, ICO reports, USDA WASDE. Build internal notebooks exploring price history, volatility by origin, correlations with climate indices. Learn the domain through the data.
2. **Roaster conversations** (Week 1-4, parallel): 5-10 calls using the outreach template above. Validate the pain, understand their actual purchasing workflow.
3. **Data pipeline** (Week 3-6): Build ingestion, normalization, and storage. Automate daily/monthly updates.
4. **Forecasting model** (Week 5-7): Time series model per origin with climate covariates. Evaluate on held-out data.
5. **Signal generator** (Week 6-7): Buy/Neutral/Caution logic combining price position, trend, and climate risk.
6. **Frontend v1** (Week 7-8): Price dashboard, signal cards, margin calculator. Your existing React/Vite/Recharts stack.
7. **Soft launch to 3-5 beta roasters** (Week 9): Free access in exchange for feedback and a testimonial if it's useful.

---

*Document version: May 2026 | Next review: after first 5 roaster conversations*

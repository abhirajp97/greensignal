# GreenSignal — Complete Math & Algorithms Reference

**Every formula, equation, and statistical concept used in the product**  
*Written for someone who understands statistics but not quantitative finance*

---

## How to Use This Document

This is a reference, not a textbook. Each section explains:
1. **What the concept is** — plain language
2. **The formula** — exact equation
3. **How it's used in GreenSignal** — concrete application
4. **Python implementation** — runnable code

Start with Section 1 (statistical foundations) if anything feels unfamiliar. Everything else builds on it.

---

## Section 1 — Statistical Foundations

### 1.1 Pearson Correlation Coefficient

**What it is:** Measures the linear relationship between two variables. How much does knowing X tell you about Y?

$$r = \frac{\sum_{i=1}^{n}(x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i - \bar{x})^2 \cdot \sum_{i=1}^{n}(y_i - \bar{y})^2}}$$

**In plain English:** Subtract the mean from each observation (so you're working with deviations). Multiply the deviations together. Normalise by the product of the standard deviations. Result is always between −1 and +1.

**GreenSignal use:** Testing whether each signal (ENSO, CHIRPS, STU, COT) actually moves with coffee prices.

**Interpretation guide:**
- r = 0: no linear relationship
- r = +0.35: moderate positive — both tend to move in the same direction
- r = −0.35: moderate negative — when one rises, the other tends to fall
- p < 0.05: the probability of seeing this r by chance (if there's truly no relationship) is less than 5%

```python
from scipy import stats
import pandas as pd

def correlation_report(df, target_col, signal_cols):
    results = []
    for col in signal_cols:
        valid = df[[target_col, col]].dropna()
        r, p = stats.pearsonr(valid[target_col], valid[col])
        r_sp, _ = stats.spearmanr(valid[target_col], valid[col])
        results.append({
            "signal": col,
            "pearson_r": round(r, 3),
            "spearman_r": round(r_sp, 3),  # rank-based, robust to outliers
            "r_squared": round(r**2, 3),   # % of variance explained
            "p_value": round(p, 4),
            "significant": p < 0.05,
            "n": len(valid)
        })
    return pd.DataFrame(results).sort_values("pearson_r", key=abs, ascending=False)
```

### 1.2 Spearman Rank Correlation

**What it is:** Same idea as Pearson, but operates on the *ranks* of values rather than the values themselves. More robust to outliers and non-linear relationships.

$$r_s = 1 - \frac{6 \sum d_i^2}{n(n^2-1)}$$

where d_i = difference in ranks of each paired observation.

**When to use instead of Pearson:** When you have extreme values (coffee prices in 2024 are 3× the historical mean — that's an outlier that distorts Pearson). When the relationship might not be linear.

**GreenSignal use:** Cross-check on all signal correlations. If Pearson and Spearman give very different results, there are outliers driving the Pearson result.

### 1.3 Partial Correlation

**What it is:** The correlation between two variables *after removing the influence of a third variable*. This is how we tested whether Brazil CHIRPS adds information beyond ENSO.

**Process:**
1. Regress Brazil CHIRPS on ENSO → get residuals (the part of CHIRPS not explained by ENSO)
2. Correlate those residuals with coffee price changes
3. If the residual correlation is significant, CHIRPS adds independent information

```python
import statsmodels.api as sm
import numpy as np

def partial_correlation(y, x1, x2, df):
    """
    Correlation between y and x1, after controlling for x2.
    Tests: does x1 add information beyond what x2 already provides?
    """
    valid = df[[y, x1, x2]].dropna()
    # Regress x1 on x2
    X = sm.add_constant(valid[x2])
    model = sm.OLS(valid[x1], X).fit()
    x1_residuals = model.resid   # part of x1 not explained by x2
    # Correlate residuals with y
    r, p = stats.pearsonr(valid[y], x1_residuals)
    return r, p

# Example: does Brazil CHIRPS add info beyond ENSO?
r_partial, p_partial = partial_correlation(
    "yoy_price_change", "brazil_rainfall", "enso_oni", df=monthly_data
)
print(f"Brazil CHIRPS after ENSO: r={r_partial:.3f}, p={p_partial:.4f}")
```

### 1.4 p-value and Statistical Significance

**What it is:** The probability of observing a correlation at least this large *if the true correlation is zero*. Not the probability that the correlation is real — a common misunderstanding.

**Threshold conventions:**
- p < 0.05: conventionally "significant" (5% false-positive rate)
- p < 0.01: strong significance
- p < 0.001: very strong significance (annotated as ***)

**Important caveat for time series:** Standard p-values assume independent observations. Monthly coffee prices are autocorrelated (January price predicts February price). This inflates the apparent sample size, making p-values too small. Always verify with time-aware methods (see Section 3).

---

## Section 2 — Price Signal Mathematics

### 2.1 Rolling Price Position (The Core Signal)

**What it is:** Where current price sits within its historical range, normalised to 0–1. This is the single most important signal in GreenSignal.

$$\text{position}(t, W) = \frac{P_t - \min_{[t-W, t]}(P)}{\max_{[t-W, t]}(P) - \min_{[t-W, t]}(P)}$$

where:
- P_t = current price
- W = lookback window (252 trading days = 52 weeks; 504 = 2 years)
- Result: 0 = current price equals the W-period low; 1 = equals the W-period high

**GreenSignal use:** Core Layer 1 signal. Position < 0.25 → BUY signal. Position > 0.75 → CAUTION.

```python
def price_position(prices: pd.Series, window: int = 252) -> pd.Series:
    """
    Rolling price position in [0, 1].
    window: lookback in trading days (252 ≈ 1 year, 504 ≈ 2 years)
    """
    roll_min = prices.rolling(window, min_periods=window // 2).min()
    roll_max = prices.rolling(window, min_periods=window // 2).max()
    position = (prices - roll_min) / (roll_max - roll_min + 1e-9)
    return position.clip(0, 1)

# Apply at multiple windows for robustness
arabica["pos_52w"] = price_position(arabica["price"], window=252)
arabica["pos_2y"]  = price_position(arabica["price"], window=504)
arabica["pos_3y"]  = price_position(arabica["price"], window=756)
```

**Why multiple windows?** The 52-week position is more reactive (fires more signals). The 2-year position is more conservative (only fires at genuine multi-year lows). Use both: 52-week for timing, 2-year for confirmation.

### 2.2 Simple Moving Average (SMA)

$$\text{SMA}(t, W) = \frac{1}{W} \sum_{i=0}^{W-1} P_{t-i}$$

**GreenSignal use:** Trend direction filter. Price above 200-day SMA = uptrend. Price below = downtrend. This modifies signal conviction — a BUY signal in an uptrend is stronger than a BUY in a downtrend.

```python
arabica["ma_50d"]  = arabica["price"].rolling(50).mean()
arabica["ma_200d"] = arabica["price"].rolling(200).mean()
arabica["in_uptrend"] = (arabica["price"] > arabica["ma_200d"]).astype(int)
```

### 2.3 Exponential Moving Average (EMA)

$$\text{EMA}(t) = \alpha \cdot P_t + (1-\alpha) \cdot \text{EMA}(t-1)$$

where $\alpha = \frac{2}{W+1}$ and W is the "equivalent" window.

**Difference from SMA:** EMA gives more weight to recent observations. For fast-moving commodity markets, EMA often more relevant than SMA.

```python
arabica["ema_21d"] = arabica["price"].ewm(span=21, adjust=False).mean()
arabica["ema_50d"] = arabica["price"].ewm(span=50, adjust=False).mean()
# EMA crossover: short EMA crossing above long EMA = momentum signal
arabica["ema_cross"] = (arabica["ema_21d"] > arabica["ema_50d"]).astype(int)
```

### 2.4 Price Returns and Log Returns

**Simple return:**
$$r_t = \frac{P_t - P_{t-1}}{P_{t-1}} = \frac{P_t}{P_{t-1}} - 1$$

**Log return:**
$$\ln r_t = \ln\left(\frac{P_t}{P_{t-1}}\right) = \ln(P_t) - \ln(P_{t-1})$$

**Why log returns?** They are additive over time (simple returns are multiplicative). They are approximately normally distributed (simple returns are not). Price models should almost always work on log prices or log returns.

```python
arabica["return_1d"]  = arabica["price"].pct_change(1)
arabica["log_return"] = np.log(arabica["price"]).diff(1)
# Multi-period returns
arabica["return_1m"]  = arabica["price"].pct_change(21)   # ~1 month
arabica["return_3m"]  = arabica["price"].pct_change(63)   # ~3 months
arabica["return_12m"] = arabica["price"].pct_change(252)  # YoY
```

### 2.5 Relative Strength Index (RSI)

$$\text{RSI} = 100 - \frac{100}{1 + \text{RS}}, \quad \text{RS} = \frac{\text{avg gain over W periods}}{\text{avg loss over W periods}}$$

**Interpretation:** RSI > 70 = overbought (momentum is exhausted upward). RSI < 30 = oversold. Standard window: 14 days.

**GreenSignal use:** Supporting momentum signal. A BUY from price position combined with RSI < 40 is a stronger signal than position alone.

```python
def compute_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    delta = prices.diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    avg_gain = gains.ewm(com=window-1, adjust=False).mean()
    avg_loss = losses.ewm(com=window-1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

arabica["rsi_14d"] = compute_rsi(arabica["price"], 14)
```

### 2.6 Bollinger Bands

$$\text{Upper band} = \text{SMA}(W) + k \cdot \sigma(W)$$
$$\text{Lower band} = \text{SMA}(W) - k \cdot \sigma(W)$$

where k = 2 (standard), σ(W) = rolling standard deviation over W periods.

**GreenSignal use:** Price touching or below lower band = potential mean-reversion buy. Price above upper band = caution. Particularly useful combined with the price position signal.

```python
def bollinger_bands(prices: pd.Series, window: int = 20, k: float = 2.0):
    sma   = prices.rolling(window).mean()
    sigma = prices.rolling(window).std()
    return sma + k*sigma, sma, sma - k*sigma  # upper, mid, lower

arabica["bb_upper"], arabica["bb_mid"], arabica["bb_lower"] = \
    bollinger_bands(arabica["price"], window=20)
arabica["bb_position"] = (arabica["price"] - arabica["bb_lower"]) / \
                          (arabica["bb_upper"] - arabica["bb_lower"] + 1e-9)
```

### 2.7 Realised Volatility

$$\sigma_{\text{annualised}} = \sqrt{252} \cdot \text{std}(\{r_t, r_{t-1}, \ldots, r_{t-W+1}\})$$

**GreenSignal use:** Volatility regime detection. High volatility = larger uncertainty bands on forecasts. Periods of rising volatility often precede large price moves — a risk signal in itself.

```python
arabica["vol_21d"]  = arabica["return_1d"].rolling(21).std()  * np.sqrt(252)
arabica["vol_63d"]  = arabica["return_1d"].rolling(63).std()  * np.sqrt(252)
arabica["vol_rising"] = (arabica["vol_21d"] > arabica["vol_63d"]).astype(int)
```

---

## Section 3 — Time Series Analysis

### 3.1 Autocorrelation

**What it is:** The correlation of a time series with its own past values at lag k.

$$\rho_k = \text{Corr}(P_t, P_{t-k}) = \frac{\text{Cov}(P_t, P_{t-k})}{\text{Var}(P_t)}$$

**Why it matters:** If monthly coffee prices are autocorrelated at lag 1 (ρ₁ = 0.9), it means last month's price is a strong predictor of this month's. Standard statistical tests assume no autocorrelation. Ignoring autocorrelation inflates sample sizes and makes everything look more significant than it is.

```python
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import acf, pacf
import matplotlib.pyplot as plt

# Check autocorrelation structure
acf_vals = acf(monthly_prices, nlags=24)
pacf_vals = pacf(monthly_prices, nlags=24)

# Durbin-Watson test: values near 2.0 = no autocorrelation
# Values near 0 = strong positive autocorrelation
dw = durbin_watson(monthly_prices.diff().dropna())
print(f"Durbin-Watson: {dw:.3f}")  # want near 2.0 for residuals
```

### 3.2 Stationarity and the ADF Test

**What it is:** A time series is *stationary* if its statistical properties (mean, variance) don't change over time. Most price series are NOT stationary (they trend). Models require stationarity or explicit modelling of trends.

**Augmented Dickey-Fuller (ADF) test:**
- H₀: the series has a unit root (is non-stationary, has a trend)
- H₁: the series is stationary
- If p < 0.05: reject H₀ → series is stationary

```python
from statsmodels.tsa.stattools import adfuller

def test_stationarity(series: pd.Series, name: str = ""):
    result = adfuller(series.dropna())
    print(f"\n{name} ADF Test:")
    print(f"  ADF statistic: {result[0]:.4f}")
    print(f"  p-value:       {result[1]:.4f}")
    print(f"  Conclusion:    {'Stationary' if result[1] < 0.05 else 'NON-STATIONARY'}")
    return result[1] < 0.05

# Raw prices are almost certainly non-stationary
test_stationarity(arabica["price"], "Raw price")
# First differences (returns) should be stationary
test_stationarity(arabica["price"].diff().dropna(), "Price returns")
# Log prices
test_stationarity(np.log(arabica["price"]), "Log price")
```

**Rule of thumb:** Use price returns (or log returns) in regression models, not raw prices. Use raw prices for position signals (where trend is intentional).

### 3.3 Lag Selection for Cross-Correlation

**Cross-correlation function (CCF):** Correlation between signal X at time t and outcome Y at time t+k, for all lags k.

$$\text{CCF}(k) = \text{Corr}(X_t, Y_{t+k})$$

Positive k = X leads Y (X is a leading indicator). Negative k = X lags Y.

```python
def lag_correlation_profile(X: pd.Series, Y: pd.Series,
                              max_lag: int = 24) -> pd.DataFrame:
    """
    For each lag 0..max_lag: correlate X_shifted with Y.
    Positive lag = X measured earlier predicts Y today.
    """
    results = []
    for lag in range(max_lag + 1):
        X_shifted = X.shift(lag)
        valid = Y.notna() & X_shifted.notna()
        if valid.sum() > 20:
            r, p = stats.pearsonr(Y[valid], X_shifted[valid])
            results.append({"lag": lag, "r": r, "p": p, "n": valid.sum()})
    df = pd.DataFrame(results)
    best_lag = df.loc[df["r"].abs().idxmax(), "lag"]
    return df, best_lag

# Example: ENSO leads coffee prices by how many months?
enso_lags, best_enso_lag = lag_correlation_profile(
    enso["oni"], monthly_prices.pct_change(12), max_lag=24
)
print(f"Best ENSO lag: {best_enso_lag} months")
```

---

## Section 4 — Supply Signal Mathematics

### 4.1 Stocks-to-Use Ratio

$$\text{STU}(t) = \frac{\text{Ending Stocks}_t}{\text{Total Consumption}_t} \times 100\%$$

**Source:** USDA PSD (Production, Supply, and Distribution) monthly report.

**Interpretation:** Inventory coverage expressed as a percentage of annual consumption. Below 20% = historically associated with price spikes. Below 15% = critical.

```python
supply_df["stocks_to_use_pct"] = (
    supply_df["ending_stocks_mbags"] / supply_df["world_consumption_mbags"] * 100
)

# Signal: distance from 20% threshold (negative = more bullish)
supply_df["stu_below_20"] = (20 - supply_df["stocks_to_use_pct"]).clip(lower=0)
supply_df["stu_risk"] = (20 - supply_df["stocks_to_use_pct"]).clip(0, 15) / 15
```

### 4.2 Year-on-Year Production Change

$$\Delta \text{Production}_t = \frac{\text{Production}_t - \text{Production}_{t-1}}{\text{Production}_{t-1}} \times 100\%$$

**GreenSignal use:** Conab Brazil releases (January, May, September). A revision of −5M bags or more is a significant bullish signal — the market hadn't priced in that much supply reduction.

```python
conab_df["production_yoy_pct"] = conab_df["estimate_mbags"].pct_change() * 100
# Large negative revision = buy signal
conab_df["large_downward_revision"] = (conab_df["production_yoy_pct"] < -5).astype(int)
```

### 4.3 Export Pace vs. Seasonal Baseline

$$\text{Export Pace Index}(t) = \frac{\text{Actual Exports}_{t}}{\text{5-Year Average Exports for Month}_{t}} \times 100$$

**Interpretation:** Index > 110 = exports running ahead of pace (depletes stocks faster → bullish for price). Index < 90 = slow exports (stocks building → bearish).

```python
def export_pace_index(exports: pd.Series) -> pd.Series:
    exports_df = exports.to_frame("exports")
    exports_df["month"] = exports_df.index.month
    # 5-year rolling average by month
    monthly_avg = exports_df.groupby("month")["exports"].transform(
        lambda x: x.rolling(5, min_periods=2).mean()
    )
    return (exports_df["exports"] / monthly_avg * 100)
```

---

## Section 5 — Climate Signal Processing

### 5.1 Rainfall Anomaly Calculation

$$\text{Anomaly}(t) = R(t) - \bar{R}_{\text{month}(t)}$$

where R(t) is actual precipitation and $\bar{R}_{\text{month}}$ is the climatological monthly mean (typically 1981–2010 or 1991–2020 baseline).

**Percentage anomaly:**
$$\text{Anomaly\%}(t) = \frac{R(t) - \bar{R}_{\text{month}(t)}}{\bar{R}_{\text{month}(t)}} \times 100\%$$

```python
def compute_rainfall_anomaly(precip: pd.Series,
                              baseline_start: int = 1991,
                              baseline_end: int = 2020) -> pd.DataFrame:
    df = precip.to_frame("precip")
    df["month"] = df.index.month

    # Compute climatological mean by month over baseline period
    baseline = df[df.index.year.isin(range(baseline_start, baseline_end+1))]
    clim_mean = baseline.groupby("month")["precip"].mean()

    df["clim_mean"]     = df["month"].map(clim_mean)
    df["anom_mm"]       = df["precip"] - df["clim_mean"]
    df["anom_pct"]      = df["anom_mm"] / (df["clim_mean"] + 1e-9) * 100
    df["is_drought"]    = df["anom_pct"] < -30  # >30% below normal
    df["is_extreme"]    = df["anom_pct"] < -50  # >50% below normal
    return df
```

### 5.2 ENSO Classification

$$\text{Phase} = \begin{cases} \text{La Niña} & \text{if ONI} \leq -0.5 \text{ for } \geq 5 \text{ consecutive seasons} \\ \text{El Niño} & \text{if ONI} \geq +0.5 \text{ for } \geq 5 \text{ consecutive seasons} \\ \text{Neutral} & \text{otherwise} \end{cases}$$

where ONI = 3-month rolling mean of Niño 3.4 SST anomaly.

**GreenSignal use:** For the product, simplified to threshold classification per month. The persistence requirement is important for major events but less critical for a monthly signal.

```python
def classify_enso(oni: pd.Series) -> pd.Series:
    """Simple monthly ENSO classification."""
    return pd.cut(oni, bins=[-99, -0.5, 0.5, 99],
                  labels=["la_nina", "neutral", "el_nino"])

enso["phase"] = classify_enso(enso["oni"])
# For each origin, translate phase to supply risk
def brazil_enso_risk(oni_val: float) -> float:
    """El Niño = drought risk for Brazil Arabica (moderate)."""
    return max(0, min(1, (oni_val - 0.3) / 2.0))  # increases with El Niño strength

def vietnam_enso_risk(oni_val: float) -> float:
    """La Niña = drought risk for Vietnam Robusta (stronger relationship)."""
    return max(0, min(1, (-oni_val - 0.3) / 1.5))  # increases with La Niña strength
```

### 5.3 NDVI Anomaly (Vegetation Health)

$$\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$$

where NIR = near-infrared reflectance, Red = red band reflectance (both from satellite imagery).

**Interpretation:** NDVI ranges −1 to +1. Dense green vegetation ≈ 0.6–0.9. Sparse vegetation ≈ 0.2–0.5. Bare soil ≈ 0.

**NDVI anomaly:**
$$\text{NDVI anomaly}(t) = \text{NDVI}(t) - \overline{\text{NDVI}}_{\text{month}(t)}$$

**GreenSignal use:** NDVI for coffee-growing regions (extracted from MODIS MOD13A3 via Google Earth Engine) provides the earliest drought signal — 4–8 weeks before rainfall anomalies become apparent in CHIRPS.

```python
# Google Earth Engine implementation (requires ee account):
"""
import ee
ee.Initialize()

# Brazil NDVI time series
brazil_region = ee.Geometry.Rectangle([-52, -25, -40, -14])
modis = ee.ImageCollection("MODIS/061/MOD13A3")

def get_monthly_ndvi(img):
    mean = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=brazil_region,
        scale=1000
    ).get("NDVI")
    return ee.Feature(None, {"date": img.date().format("YYYY-MM"), "ndvi": mean})

ndvi_series = modis.filterDate("2010-01-01", "2025-04-01") \
                   .map(get_monthly_ndvi)
"""
```

---

## Section 6 — COT Signal Mathematics

### 6.1 COT Index

**What it is:** Where current speculative positioning sits in its historical range. Works exactly like the price position signal, but applied to futures positioning data.

$$\text{COT Index}(t, W) = \frac{\text{Net}_{t} - \min_{[t-W,t]}(\text{Net})}{\max_{[t-W,t]}(\text{Net}) - \min_{[t-W,t]}(\text{Net})} \times 100$$

where Net = speculative (non-commercial) net long contracts, W = 3-year rolling window (156 weeks).

**Interpretation:** Index > 75 = speculators are more net long than at 75% of all weeks in the past 3 years (crowded). Index < 25 = more net short than 75% of recent weeks (pessimistic). Both extremes are contrarian signals.

```python
def cot_index(net_positions: pd.Series, window: int = 156) -> pd.Series:
    """
    Rolling COT index (0-100) for speculative net positions.
    window: 156 weeks = 3 years
    """
    roll_min = net_positions.rolling(window, min_periods=52).min()
    roll_max = net_positions.rolling(window, min_periods=52).max()
    return ((net_positions - roll_min) / (roll_max - roll_min + 1e-9) * 100).clip(0, 100)

cot["spec_cot_idx"] = cot_index(cot["spec_net"], window=156)
cot["comm_cot_idx"] = cot_index(cot["comm_net"], window=156)
```

### 6.2 COT Signal as a Contrarian Indicator

**The contrarian logic:** Speculators (non-commercials) are trend-following — they buy when prices rise and sell when they fall. At extremes, they become the majority of the market's price momentum. When too many speculators are positioned the same way, there's no one left to buy (or sell), and the trend reverses.

**Translating to a buy/caution signal:**

```python
def cot_to_signal_component(cot_index_val: float) -> float:
    """
    Converts COT index to a 0-1 risk component for the composite signal.
    0 = contrarian BUY (specs are light/short)
    1 = contrarian CAUTION (specs are very crowded long)
    Neutral zone: 25-75 (no strong contrarian signal)
    """
    if cot_index_val < 25:
        return max(0, cot_index_val / 25) * 0.3      # scale to 0-0.3 in buy zone
    elif cot_index_val > 75:
        return 0.7 + (cot_index_val - 75) / 25 * 0.3 # scale to 0.7-1.0 in caution zone
    else:
        return 0.3 + (cot_index_val - 25) / 50 * 0.4 # linear in neutral zone
```

### 6.3 Where to Get COT Data

**Source:** CFTC (Commodity Futures Trading Commission)
**URL:** `cftc.gov/MarketReports/CommitmentsofTraders`
**Published:** Every Friday for Tuesday positions
**Format:** CSV download, also available as API

**Ticker for coffee:** ICE Arabica (KC) — commodity code 083731

```python
import requests, io

def fetch_cot_coffee(year: int) -> pd.DataFrame:
    """
    Download annual COT data from CFTC.
    Free, no API key needed.
    """
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_xls_{year}.zip"
    # Full historical files also at:
    # https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm

    response = requests.get(url, timeout=30)
    # Unzip and read
    import zipfile
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        filename = [f for f in z.namelist() if f.endswith('.csv')][0]
        df = pd.read_csv(z.open(filename))

    # Filter to coffee
    coffee_cot = df[df["Market_and_Exchange_Names"].str.contains("COFFEE", na=False)].copy()
    coffee_cot["Date"] = pd.to_datetime(coffee_cot["As_of_Date_In_Form_YYMMDD"],
                                         format="%y%m%d")
    coffee_cot = coffee_cot.set_index("Date")

    # Key columns
    return coffee_cot[[
        "NonComm_Positions_Long_All",   # speculative longs
        "NonComm_Positions_Short_All",  # speculative shorts
        "Comm_Positions_Long_All",      # commercial longs
        "Comm_Positions_Short_All",     # commercial shorts
        "Open_Interest_All"
    ]].copy()

# Then compute net positions
def compute_net_positions(cot_df: pd.DataFrame) -> pd.DataFrame:
    cot_df["spec_net"] = (cot_df["NonComm_Positions_Long_All"] -
                           cot_df["NonComm_Positions_Short_All"])
    cot_df["comm_net"] = (cot_df["Comm_Positions_Long_All"] -
                           cot_df["Comm_Positions_Short_All"])
    cot_df["spec_cot_idx"] = cot_index(cot_df["spec_net"])
    return cot_df
```

---

## Section 7 — Composite Signal Construction

### 7.1 Supply Risk Score (Layer 2)

Combines STU, ENSO, CHIRPS, and COT into a single climate/supply risk score:

$$\text{ClimateRisk}(t) = w_1 \cdot r_{\text{STU}}(t) + w_2 \cdot r_{\text{ENSO}}(t) + w_3 \cdot r_{\text{CHIRPS}}(t) + w_4 \cdot r_{\text{COT}}(t)$$

where each r is normalised to [0, 1] and weights $\sum w_i = 1$.

**Current calibrated weights:**

| Component | Weight | Rationale |
|-----------|--------|-----------|
| Stocks-to-use (STU) | 0.38 | Strongest single fundamental signal (r = −0.35) |
| ENSO lag 18m | 0.24 | Real climate leading indicator (r = −0.30) |
| Brazil CHIRPS | 0.22 | Early supply warning, idiosyncratic drought events |
| COT contrarian | 0.16 | Market positioning signal (r = +0.15) |

```python
def compute_climate_risk(row: pd.Series) -> float:
    """
    Composite supply/climate risk score [0, 1].
    0 = low risk (ample supply, no climate stress, specs light)
    1 = high risk (tight supply, climate stress, specs crowded)
    """
    # STU risk: tight supply increases risk
    stu_pct = row.get("stocks_to_use_pct", 30)
    stu_risk = max(0.0, min(1.0, (25.0 - stu_pct) / 15.0))  # 0 at 25%, 1.0 at 10%

    # ENSO: strong La Niña (negative ONI) increases Vietnam supply risk
    oni_18m   = row.get("oni_lag18", 0)
    enso_risk = max(0.0, min(1.0, (-oni_18m + 0.5) / 2.0))

    # Brazil CHIRPS: drought during flowering season increases Arabica supply risk
    br_rain   = row.get("brazil_rain", 0)
    br_risk   = max(0.0, min(1.0, -br_rain / 60.0))
    if row.name.month in [9, 10, 11]:  # flowering season amplifier
        br_risk = min(1.0, br_risk * 1.5)

    # COT: high speculative index = crowded = contrarian caution
    cot_idx   = row.get("cot_spec_cot_idx", 50)
    cot_signal = cot_idx / 100.0  # 0 = buy, 1 = caution

    return 0.38*stu_risk + 0.24*enso_risk + 0.22*br_risk + 0.16*cot_signal
```

### 7.2 Final Signal Multiplier

$$\text{multiplier}(t) = \max\left(0.4, \min\left(2.3, \underbrace{(1.5 - \text{position}(t))}_{\text{price timing}} \times \underbrace{(1.0 + 0.65 \times \text{ClimateRisk}(t))}_{\text{conviction amplifier}}\right)\right)$$

**Intuition:**
- At position = 0 (52-week low), price timing = 1.5
- At position = 1 (52-week high), price timing = 0.5
- Climate risk = 0 (no risk) → amplifier = 1.0 (no change)
- Climate risk = 1 (maximum risk) → amplifier = 1.65 (65% boost to conviction)

**Resulting multiplier range:**
- Low price + high climate risk: 1.5 × 1.65 = 2.48 → capped at 2.3 (strong buy)
- High price + low climate risk: 0.5 × 1.0 = 0.5 (reduce exposure)
- High price + high climate risk: 0.5 × 1.65 = 0.83 (slight caution — but supply risk means can't fully avoid)

### 7.3 Translating Multiplier to Signal Label

```python
def multiplier_to_signal(mult_normalised: float) -> str:
    """
    mult_normalised: multiplier / mean_multiplier (so 1.0 = average)
    """
    if mult_normalised > 1.25:
        return "BUY"
    elif mult_normalised < 0.80:
        return "CAUTION"
    else:
        return "NEUTRAL"

def generate_signal_text(row: pd.Series, signal: str) -> str:
    """
    Generate plain-language explanation for the signal.
    Called per origin per week.
    """
    origin = row.get("origin", "this origin")
    price  = row.get("price", 0)
    pos_52 = row.get("pos_52w", 0.5)
    stu    = row.get("stocks_to_use_pct", 25)
    oni    = row.get("oni_lag18", 0)
    cot_i  = row.get("cot_spec_cot_idx", 50)

    parts = []
    parts.append(f"{origin.title()} is currently at ${price:.2f}/lb, "
                 f"in the bottom {pos_52*100:.0f}% of its 2-year range.")
    if stu < 20:
        parts.append(f"Global coffee stocks are critically tight at {stu:.0f}% of annual use.")
    if oni < -0.8:
        parts.append(f"La Niña conditions suggest Robusta supply pressure in 12–18 months.")
    if cot_i > 75:
        parts.append(f"Speculators are heavily long — crowded positioning.")
    elif cot_i < 25:
        parts.append(f"Speculators are lightly positioned — market is pessimistic.")

    if signal == "BUY":
        parts.append("Recommendation: consider buying 2–3 months forward.")
    elif signal == "CAUTION":
        parts.append("Recommendation: buy only near-term needs at current prices.")

    return " ".join(parts)
```

---

## Section 8 — Forecasting Models

### 8.1 ARIMA/SARIMA (Baseline Model)

**ARIMA(p, d, q):** Autoregressive Integrated Moving Average.
- **p** = autoregressive order (how many past values to use)
- **d** = differencing order (usually 1 for price series — makes it stationary)
- **q** = moving average order (how many past errors to use)

$$\Delta P_t = c + \phi_1 \Delta P_{t-1} + \ldots + \phi_p \Delta P_{t-p} + \epsilon_t + \theta_1 \epsilon_{t-1} + \ldots + \theta_q \epsilon_{t-q}$$

**SARIMA(p,d,q)(P,D,Q)[m]:** Adds seasonal components with period m (12 months for monthly coffee data).

**SARIMAX:** Adds external regressors (ENSO, CHIRPS, STU) → the version to use.

```python
from statsmodels.tsa.statespace.sarimax import SARIMAX

def fit_sarimax(prices: pd.Series, exog: pd.DataFrame = None,
                 order=(1,1,1), seasonal_order=(1,1,1,12)):
    model = SARIMAX(
        prices,
        exog=exog,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    result = model.fit(disp=False)
    return result

# Auto-select p, d, q
from pmdarima import auto_arima
auto_model = auto_arima(
    monthly_prices,
    exogenous=climate_features,
    seasonal=True,
    m=12,                   # monthly seasonality
    information_criterion="aic",
    stepwise=True
)
print(auto_model.summary())
```

**When to use:** SARIMAX is the baseline. If LightGBM doesn't outperform it on held-out data, use SARIMAX — simpler, more interpretable, easier to explain.

### 8.2 LightGBM (Primary Forecast Model)

**What it is:** Gradient boosted decision trees. Works by sequentially training trees where each new tree corrects the residuals of the previous ensemble.

**Loss function for regression:**
$$L = \frac{1}{n} \sum_{i=1}^{n} (y_i - \hat{y}_i)^2 \quad \text{(MSE, standard)}$$

For quantile regression (confidence intervals):
$$L_\tau = \frac{1}{n} \sum_{i=1}^{n} \rho_\tau(y_i - \hat{y}_i)$$

where $\rho_\tau(u) = u(\tau - \mathbf{1}[u < 0])$ and τ is the quantile (e.g., 0.1, 0.5, 0.9).

```python
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit

def train_forecast_model(X: pd.DataFrame, y: pd.Series,
                          n_splits: int = 5):
    """
    Walk-forward cross-validation for time series.
    TimeSeriesSplit ensures we never train on future data.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        # Train median model (q=0.5)
        model_mid = lgb.LGBMRegressor(
            objective="quantile", alpha=0.5,
            n_estimators=200, learning_rate=0.05,
            num_leaves=15, min_child_samples=10,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1
        )
        model_mid.fit(X_train, y_train)

        # Directional accuracy (did we get the sign right?)
        y_pred = model_mid.predict(X_val)
        dir_acc = np.mean(np.sign(y_pred) == np.sign(y_val))
        scores.append({"fold": fold, "directional_accuracy": dir_acc,
                       "n_val": len(y_val)})

    return pd.DataFrame(scores)

def build_quantile_forecaster(X_train, y_train, quantiles=[0.1, 0.5, 0.9]):
    """Train separate models for each quantile to get confidence intervals."""
    models = {}
    for q in quantiles:
        m = lgb.LGBMRegressor(
            objective="quantile", alpha=q,
            n_estimators=300, learning_rate=0.03,
            num_leaves=15, min_child_samples=10,
            random_state=42, verbose=-1
        )
        m.fit(X_train, y_train)
        models[q] = m
    return models
```

### 8.3 Walk-Forward Validation (Critical for Time Series)

**The look-ahead bias problem:** If you train on data from 2010–2025 and evaluate on 2015–2020, you're using future data to predict the past. All backtests look great this way. They're meaningless.

**Walk-forward validation:** At each evaluation point, train only on data available *before* that point.

```python
def walk_forward_backtest(prices: pd.Series, features: pd.DataFrame,
                           train_window: int = 60,  # months
                           predict_horizon: int = 3  # months forward
                           ) -> pd.DataFrame:
    """
    True walk-forward backtest.
    At each month t, train on [t-train_window, t-1], predict [t, t+horizon].
    """
    results = []
    n = len(prices)

    for i in range(train_window, n - predict_horizon):
        # Training data: only past observations
        train_prices   = prices.iloc[:i]
        train_features = features.iloc[:i]

        # Fit model
        model = lgb.LGBMRegressor(n_estimators=100, verbose=-1)
        model.fit(train_features, train_prices.pct_change(predict_horizon).dropna())

        # Predict next horizon
        X_pred = features.iloc[[i]]
        y_pred = model.predict(X_pred)[0]
        y_actual = (prices.iloc[i + predict_horizon] / prices.iloc[i]) - 1

        results.append({
            "date": prices.index[i],
            "predicted_return": y_pred,
            "actual_return": y_actual,
            "direction_correct": np.sign(y_pred) == np.sign(y_actual)
        })

    df = pd.DataFrame(results).set_index("date")
    print(f"Walk-forward directional accuracy: {df['direction_correct'].mean():.2%}")
    return df
```

### 8.4 Evaluation Metrics

**Mean Absolute Error (MAE):**
$$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|$$

**Mean Absolute Percentage Error (MAPE):**
$$\text{MAPE} = \frac{100}{n} \sum_{i=1}^{n} \left|\frac{y_i - \hat{y}_i}{y_i}\right|$$

**Directional accuracy:**
$$\text{DA} = \frac{1}{n} \sum_{i=1}^{n} \mathbf{1}[\text{sign}(\hat{y}_i) = \text{sign}(y_i)]$$

**Target for GreenSignal:** directional accuracy > 53% on 60-day forward price direction. Random baseline is 50%. Even 55% adds meaningful value for purchasing decisions.

**Pinball loss (for quantile calibration):**
$$L_\tau(y, \hat{y}) = (y - \hat{y})(\tau - \mathbf{1}[y < \hat{y}])$$

A 90th percentile forecast is well-calibrated if the actual value falls above it exactly 10% of the time.

```python
def evaluate_forecast(y_true: pd.Series, y_pred: pd.Series,
                       y_lower: pd.Series, y_upper: pd.Series) -> dict:
    """Comprehensive forecast evaluation."""
    mae  = np.mean(np.abs(y_true - y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    dir_acc = np.mean(np.sign(y_pred) == np.sign(y_true))

    # Coverage: % of actuals within confidence interval
    coverage = np.mean((y_true >= y_lower) & (y_true <= y_upper))

    # Interval width (narrower = more useful, if coverage is maintained)
    avg_width = (y_upper - y_lower).mean()

    return {"MAE": round(mae, 4), "MAPE": round(mape, 2),
            "Directional Accuracy": round(dir_acc, 3),
            "CI Coverage (target 80%)": round(coverage, 3),
            "Avg CI Width": round(avg_width, 4)}
```

---

## Section 9 — Feature Engineering Checklist

Every feature that goes into the model, with the exact formula.

### Price Features (Daily → Monthly)

| Feature | Formula | Notes |
|---------|---------|-------|
| `price_log` | log(close) | Stabilise variance |
| `return_1m` | price / price.shift(21) − 1 | Monthly momentum |
| `return_3m` | price / price.shift(63) − 1 | Quarterly momentum |
| `return_12m` | price / price.shift(252) − 1 | YoY change |
| `vol_21d` | std(return_1d, 21) × √252 | Annualised volatility |
| `pos_52w` | (p − min_252) / (max_252 − min_252) | Core timing signal |
| `pos_2y` | (p − min_504) / (max_504 − min_504) | Long-range position |
| `ma50_cross` | 1 if price > SMA50 else 0 | Trend binary |
| `rsi_14` | RSI formula above | Momentum oscillator |
| `bb_pct` | (p − lower) / (upper − lower) | Bollinger position |

### Climate Features (Monthly, Lagged)

| Feature | Source | Lag | Formula |
|---------|--------|-----|---------|
| `oni_lag6..24` | NOAA | 6, 12, 18, 24m | oni.shift(lag) |
| `enso_phase` | NOAA | 0 | cut(oni, [-99,-0.5,0.5,99]) |
| `brazil_anom` | CHIRPS | 0 | precip − clim_mean |
| `brazil_anom_flower` | CHIRPS | 0 | brazil_anom × is_flowering_month |
| `vietnam_anom` | CHIRPS | 0 | precip − clim_mean |
| `brazil_ndvi_anom` | MODIS | 0 | ndvi − clim_ndvi_mean |

### Supply Features (Annual, Forward-filled)

| Feature | Source | Formula |
|---------|--------|---------|
| `stocks_to_use_pct` | USDA PSD | ending_stocks / consumption × 100 |
| `stu_below_20` | USDA PSD | max(0, 20 − stu) |
| `production_revision` | Conab | current_estimate − prior_estimate |
| `brazil_export_pace` | Cecafé | actual_exports / 5yr_avg_exports × 100 |
| `ice_stocks_yoy` | ICE/ICO | stocks.pct_change(52) for weekly series |

### COT Features (Weekly → Monthly)

| Feature | Source | Formula |
|---------|--------|---------|
| `spec_net` | CFTC | NonComm_Long − NonComm_Short |
| `spec_cot_idx` | CFTC | cot_index(spec_net, 156) |
| `comm_net` | CFTC | Comm_Long − Comm_Short |
| `oi_change_4w` | CFTC | open_interest.pct_change(4) |

### Macro Features (Weekly → Monthly)

| Feature | Source | Formula |
|---------|--------|---------|
| `brl_usd` | FRED | BRL per USD |
| `usd_index` | FRED | DXY (USD strength index) |
| `brl_change_3m` | FRED | brl_usd.pct_change(3) |

---

## Section 10 — Calibration and Honest Uncertainty

### 10.1 Why Calibration Matters

An overconfident signal destroys trust. If the model says "90% probability prices will rise" and it's wrong 40% of the time, roasters will stop using it. Calibration means the stated probability matches the observed frequency.

### 10.2 Reliability Diagram (Calibration Plot)

```python
from sklearn.calibration import calibration_curve
import matplotlib.pyplot as plt

def plot_calibration(y_true_binary, y_prob, n_bins=10):
    """
    y_true_binary: 1 if price rose, 0 if fell
    y_prob: model's predicted probability of price rise
    """
    fraction_pos, mean_pred = calibration_curve(y_true_binary, y_prob,
                                                  n_bins=n_bins, strategy="quantile")
    plt.plot([0,1],[0,1],"k--",label="Perfect calibration")
    plt.plot(mean_pred, fraction_pos, "s-", label="Model")
    plt.xlabel("Predicted probability")
    plt.ylabel("Observed frequency")
    plt.title("Calibration Curve")
    plt.legend()
    # If model line is below the diagonal: overconfident (says 70% but only 50% occur)
    # If model line is above the diagonal: underconfident
```

### 10.3 Confidence Interval Width by Regime

In high-volatility regimes, confidence intervals should be wider. Never show a tight CI when volatility is high — it's false precision.

```python
def adaptive_confidence_interval(base_forecast: float,
                                   current_vol: float,
                                   long_run_vol: float,
                                   base_width: float = 0.15) -> tuple:
    """
    Scale confidence interval width by current vs. long-run volatility.
    If current vol is 2× normal, intervals should be ~2× wider.
    """
    vol_ratio = current_vol / (long_run_vol + 1e-9)
    adjusted_width = base_width * max(0.7, min(3.0, vol_ratio))
    return (base_forecast - adjusted_width/2,
            base_forecast + adjusted_width/2)
```

---

## Section 11 — Backtest Methodology

### 11.1 The Cost-Improvement Backtest

```python
def cost_improvement_backtest(prices: pd.Series,
                               signal_fn,
                               min_mult: float = 0.4,
                               max_mult: float = 2.3) -> dict:
    """
    Simulate a roaster who adjusts monthly purchase volume based on signal.
    min_mult: minimum purchase fraction (at CAUTION)
    max_mult: maximum purchase fraction (at strong BUY)
    Total annual volume is normalised to 1.0/month average.
    """
    monthly = prices.resample("MS").mean().dropna()
    multipliers = monthly.apply(signal_fn)

    # Normalise so mean purchase = 1.0 unit per month (same total volume)
    multipliers = multipliers / multipliers.mean()

    naive_cost    = monthly.mean()
    strategy_cost = (monthly * multipliers).sum() / multipliers.sum()
    improvement   = (naive_cost - strategy_cost) / naive_cost * 100

    return {
        "naive_avg_price":    round(naive_cost, 4),
        "strategy_avg_price": round(strategy_cost, 4),
        "improvement_pct":    round(improvement, 2),
        "n_buy":              (multipliers > 1.2).sum(),
        "n_caution":          (multipliers < 0.8).sum(),
        "n_neutral":          ((multipliers >= 0.8) & (multipliers <= 1.2)).sum(),
    }
```

### 11.2 Forward Prescience Test

```python
def prescience_test(prices: pd.Series,
                     signal_fn,
                     forward_months: int = 3) -> dict:
    """
    For BUY months: what does price do over the next N months?
    Prescience = forward return conditional on BUY signal.
    If > unconditional forward return: signal has predictive power.
    """
    monthly = prices.resample("MS").mean().dropna()
    multipliers = monthly.apply(signal_fn)
    mults_n = multipliers / multipliers.mean()

    fwd_return = monthly.shift(-forward_months) / monthly - 1

    buy_idx     = mults_n[mults_n > 1.2].index
    caution_idx = mults_n[mults_n < 0.8].index

    unconditional_fwd = fwd_return.mean() * 100

    return {
        "unconditional_fwd_return_pct": round(unconditional_fwd, 2),
        "buy_fwd_return_pct":     round(fwd_return[buy_idx].mean() * 100, 2),
        "caution_fwd_return_pct": round(fwd_return[caution_idx].mean() * 100, 2),
        "prescience_ratio":       round(fwd_return[buy_idx].mean() /
                                        (unconditional_fwd/100 + 1e-9), 2)
    }
```

---

## Quick Reference: Key Thresholds

| Signal | Buy Zone | Neutral | Caution Zone |
|--------|----------|---------|--------------|
| Price position 52w | < 0.25 | 0.25–0.75 | > 0.75 |
| Stocks-to-use % | < 20% | 20–28% | > 28% |
| COT Index (spec) | < 25 | 25–75 | > 75 |
| RSI 14d | < 35 | 35–65 | > 65 |
| ENSO ONI | La Niña < −0.5 | −0.5 to +0.5 | El Niño > +0.5 |
| Brazil CHIRPS (flowering) | < −40mm | −40 to +40mm | > +50mm (excess) |

---

*GreenSignal · Math & Algorithms Reference · May 2026*

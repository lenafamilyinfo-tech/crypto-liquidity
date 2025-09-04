# crypto_liquidity_dashboard.py
# ——————————————————————————————————————————
# Pro Liquidity Dashboard (CoinGecko + Binance) — no API keys
# Features:
# - Auto-refresh (every 15s) with pause toggle
# - BTC / ETH / Altcoins / Stablecoins liquidity deltas
# - Dominance (BTC, ETH, Stable, Alts)
# - Multi-source data: CoinGecko (market caps) + Binance (24h volume & price change)
# - Clean UI with KPIs + charts + final market verdict
# ——————————————————————————————————————————

import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional

import requests
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# -------------------------- Config --------------------------
st.set_page_config(page_title="Crypto Liquidity Pro", page_icon="💧", layout="wide")

CG_BASE = "https://api.coingecko.com/api/v3"
BINANCE_BASE = "https://api.binance.com"

# A basket of major stables — add/remove as needed
STABLE_IDS = [
    "tether",               # USDT
    "usd-coin",             # USDC
    "dai",                  # DAI
    "true-usd",             # TUSD (low/liquidity lately)
    "first-digital-usd",    # FDUSD
    "paypal-usd",           # PYUSD
    "ethena-usde"           # USDe
]

# Timeframe options (minutes)
TF_OPTIONS = {
    "15 دقیقه": 15,
    "1 ساعت": 60,
    "4 ساعت": 240,
    "24 ساعت": 1440,
}

REFRESH_MS_DEFAULT = 15000  # 15s

# -------------------------- Helpers --------------------------
def cg_get(path: str, params: dict = None, retries: int = 3, timeout: int = 20):
    url = f"{CG_BASE}{path}"
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.8 * (i + 1))
        except requests.RequestException:
            time.sleep(0.8 * (i + 1))
    return None

def binance_get(path: str, params: dict = None, retries: int = 2, timeout: int = 10):
    url = f"{BINANCE_BASE}{path}"
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.5 * (i + 1))
        except requests.RequestException:
            time.sleep(0.5 * (i + 1))
    return None

def get_global_snapshot():
    """CoinGecko /global → total cap & dominance"""
    data = cg_get("/global")
    if not data: 
        return None
    d = data.get("data", {})
    total = d.get("total_market_cap", {}).get("usd")
    btc_dom = d.get("market_cap_percentage", {}).get("btc")
    eth_dom = d.get("market_cap_percentage", {}).get("eth")
    return {"total": total, "btc_dom": btc_dom, "eth_dom": eth_dom}

def get_simple_caps(ids: List[str]) -> Dict[str, float]:
    """Get current market caps for a list of ids via /simple/price"""
    params = {
        "ids": ",".join(ids),
        "vs_currencies": "usd",
        "include_market_cap": "true",
    }
    data = cg_get("/simple/price", params=params) or {}
    out = {}
    for cid, vals in data.items():
        out[cid] = vals.get("usd_market_cap", 0.0) or 0.0
    return out

def get_market_caps_history(coin_id: str, minutes_back: int) -> Optional[Tuple[int, float]]:
    """
    Return (ts_ms_prev, mcap_prev) for `minutes_back` minutes ago using /market_chart.
    """
    # For <= 24h we can use 'minutely' granularity (days=1)
    params = {"vs_currency": "usd", "days": 1, "interval": "minutely"}
    data = cg_get(f"/coins/{coin_id}/market_chart", params=params) or {}
    caps = data.get("market_caps", [])
    if not caps:
        return None

    target_ms = int((datetime.now(timezone.utc) - timedelta(minutes=minutes_back)).timestamp() * 1000)

    # find last value <= target_ms
    prev = None
    for ts, val in caps:
        if ts <= target_ms:
            prev = (ts, float(val))
        else:
            break
    return prev

def pretty_usd(x: Optional[float]) -> str:
    if x is None:
        return "N/A"
    s = abs(x)
    if s >= 1e12: return f"${x/1e12:.2f}T"
    if s >= 1e9:  return f"${x/1e9:.2f}B"
    if s >= 1e6:  return f"${x/1e6:.2f}M"
    if s >= 1e3:  return f"${x/1e3:.2f}K"
    return f"${x:,.0f}"

def decide_flow(d_total, d_btc, d_eth, d_stable, d_alt):
    tol = 5e6  # $5M noise tolerance
    if any(v is None for v in [d_btc, d_eth, d_stable, d_alt]):
        return "داده کافی نیست", "gray", "دیتای یکی از بخش‌ها ناقص است."

    if d_total is not None:
        # Total-based decision preferred when available
        if d_total > tol:
            # inflow
            leader = max(
                [("BTC", d_btc), ("ETH", d_eth), ("Alts", d_alt), ("Stables", d_stable)],
                key=lambda x: x[1]
            )[0]
            if leader == "Stables":
                return "ورود نقدینگی + تمرکز روی استیبل؟", "orange", "کل بازار مثبت اما استیبل‌ها نیز در حال رشدند."
            return f"ورود نقدینگی → تمرکز بر {leader}", "green", "رشد خالص سرمایه در بازار مشاهده می‌شود."
        elif d_total < -tol:
            if d_stable > tol:
                return "خروج نقدینگی → پناه به استیبل‌کوین‌ها", "red", "سرمایه از کریپتو خارج و به استیبل منتقل می‌شود."
            return "خروج نقدینگی از کل بازار", "red", "کاهش خالص سرمایه در بازار."
        # near zero
        # rotation scenario
    # Rotation (no big net change)
    if d_btc > tol and d_alt < -tol:
        return "چرخش از آلت‌ها به بیت‌کوین", "orange", "پول از آلت‌ها به BTC می‌چرخد."
    if d_alt > tol and d_btc < -tol:
        return "چرخش از بیت‌کوین به آلت‌ها", "orange", "پول از BTC به آلت‌ها می‌چرخد."
    if d_eth > tol and (d_btc < tol) and (d_alt < tol):
        return "تمرکز نسبی روی اتریوم", "orange", "ETH نسبت به بقیه قوی‌تر است."
    if d_stable > tol and max(d_btc, d_eth, d_alt) < tol:
        return "بی‌تصمیمی بازار / پناه کوتاه‌مدت به استیبل", "gray", "رشد استیبل‌ها بدون رشد بخش‌های ریسکی."
    return "خنثی", "gray", "تغییر معناداری دیده نمی‌شود."

# -------------------------- Core Analysis --------------------------
def analyze(window_minutes: int):
    # 1) Snapshot now
    gl = get_global_snapshot()
    if not gl or not gl["total"]:
        return None

    total_now = float(gl["total"])
    btc_dom_now = float(gl["btc_dom"] or 0.0)
    eth_dom_now = float(gl["eth_dom"] or 0.0)

    # BTC/ETH current caps
    caps_now = get_simple_caps(["bitcoin", "ethereum"])
    btc_now = caps_now.get("bitcoin", 0.0)
    eth_now = caps_now.get("ethereum", 0.0)

    # Stables current cap
    st_map_now = get_simple_caps(STABLE_IDS)
    stable_now = float(sum(st_map_now.values()))

    # Altcoins current cap (residual)
    alt_now = max(total_now - btc_now - stable_now, 0.0)

    # 2) Previous values (minutes back) from history
    btc_prev_t = get_market_caps_history("bitcoin", window_minutes)
    eth_prev_t = get_market_caps_history("ethereum", window_minutes)

    # Stable basket previous
    stable_prev_sum = 0.0
    have_any_stable_prev = False
    for sid in STABLE_IDS:
        pv = get_market_caps_history(sid, window_minutes)
        if pv:
            stable_prev_sum += float(pv[1])
            have_any_stable_prev = True
    stable_prev = stable_prev_sum if have_any_stable_prev else None

    # 3) Deltas
    d_btc = (btc_now - btc_prev_t[1]) if (btc_now and btc_prev_t) else None
    d_eth = (eth_now - eth_prev_t[1]) if (eth_now and eth_prev_t) else None
    d_stable = (stable_now - stable_prev) if (stable_now and stable_prev is not None) else None

    # Alt delta inferred from ETH as proxy within alts
    # Avoid division by zero and clip ETH share within alts to reasonable range
    eth_share_in_alts_now = (eth_now / alt_now) if (alt_now and eth_now) else 0.35
    eth_share_in_alts_now = float(np.clip(eth_share_in_alts_now, 0.15, 0.65))
    d_alt = (d_eth / eth_share_in_alts_now) if (d_eth is not None) else None

    # Total delta as sum (best-effort)
    d_total = None
    if all(v is not None for v in [d_btc, d_stable, d_alt]):
        d_total = d_btc + d_stable + d_alt

    # Dominances now
    stable_dom_now = (stable_now / total_now * 100.0) if total_now else None
    alt_dom_now = 100.0 - (btc_dom_now or 0.0) - (stable_dom_now or 0.0)

    # 4) Binance 24h stats for additional context (not used directly in deltas)
    b_btc = binance_get("/api/v3/ticker/24hr", {"symbol": "BTCUSDT"}) or {}
    b_eth = binance_get("/api/v3/ticker/24hr", {"symbol": "ETHUSDT"}) or {}
    btc_change = float(b_btc.get("priceChangePercent") or 0.0)
    eth_change = float(b_eth.get("priceChangePercent") or 0.0)
    btc_qvol  = float(b_btc.get("quoteVolume") or 0.0)   # USDT volume
    eth_qvol  = float(b_eth.get("quoteVolume") or 0.0)

    return {
        "now": {
            "total": total_now,
            "btc": btc_now,
            "eth": eth_now,
            "stable": stable_now,
            "alt": alt_now,
            "dom": {
                "btc": btc_dom_now,
                "eth": eth_dom_now,
                "stable": stable_dom_now,
                "alt": alt_dom_now
            }
        },
        "deltas": {
            "total": d_total,
            "btc": d_btc,
            "eth": d_eth,
            "stable": d_stable,
            "alt": d_alt
        },
        "binance": {
            "btc_change_24h": btc_change,
            "eth_change_24h": eth_change,
            "btc_quote_vol_24h": btc_qvol,
            "eth_quote_vol_24h": eth_qvol
        }
    }

# -------------------------- UI --------------------------
# Sidebar controls
with st.sidebar:
    st.header("⚙️ تنظیمات")
    tf_label = st.selectbox("تایم‌فریم تغییرات", list(TF_OPTIONS.keys()), index=1)
    window_minutes = TF_OPTIONS[tf_label]

    auto_refresh = st.toggle("آپدیت خودکار هر ۱۵ ثانیه", value=True)
    refresh_ms = st.slider("فاصله‌ی رفرش (میلی‌ثانیه)", min_value=5000, max_value=60000, value=REFRESH_MS_DEFAULT, step=1000)
    st.caption("اگر اینترنت ضعیف است، فاصله‌ی رفرش را بیشتر کن.")

    st.markdown("---")
    st.caption("منابع داده: CoinGecko (مارکت‌کپ/دامیننس) + Binance (حجم/تغییر 24h). \nنتایج تقریبی‌اند؛ مناسب تصمیم‌گیری مالی مستقل نیستند.")

# Auto refresh
if auto_refresh:
    st.autorefresh(interval=refresh_ms, key="auto_refresh_key")

st.title("💧 Crypto Liquidity — نسخه حرفه‌ای (Multi-Source)")

# Run analysis
with st.spinner("در حال جمع‌آوری داده از چند منبع..."):
    res = analyze(window_minutes)

if not res:
    st.error("❌ خطا در دریافت داده‌ها. چند ثانیه دیگر دوباره تلاش کن.")
    st.stop()

now = res["now"]
d = res["deltas"]
bn = res["binance"]

# Store timeseries in session_state for live charts
if "ts" not in st.session_state:
    st.session_state.ts = []

timestamp = datetime.now().strftime("%H:%M:%S")
st.session_state.ts.append({
    "t": timestamp,
    "ΔTotal": d["total"],
    "ΔBTC": d["btc"],
    "ΔETH": d["eth"],
    "ΔStable": d["stable"],
    "ΔAlt": d["alt"]
})
# keep last 200 points
st.session_state.ts = st.session_state.ts[-200:]

# -------------------------- KPIs --------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("کل بازار", pretty_usd(now["total"]))
c2.metric("BTC", pretty_usd(now["btc"]))
c3.metric("ETH", pretty_usd(now["eth"]))
c4.metric("Stablecoins", pretty_usd(now["stable"]))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Dominance BTC", f"{now['dom']['btc']:.2f}%")
c2.metric("Dominance ETH", f"{now['dom']['eth']:.2f}%")
c3.metric("Dominance Stable", f"{now['dom']['stable']:.2f}%")
c4.metric("Dominance Alts", f"{now['dom']['alt']:.2f}%")

# Binance context row
bc1, bc2, bc3, bc4 = st.columns(4)
bc1.metric("BTC 24h %", f"{bn['btc_change_24h']:.2f}%")
bc2.metric("ETH 24h %", f"{bn['eth_change_24h']:.2f}%")
bc3.metric("BTC 24h Quote Vol", pretty_usd(bn["btc_quote_vol_24h"]))
bc4.metric("ETH 24h Quote Vol", pretty_usd(bn["eth_quote_vol_24h"]))

# -------------------------- Verdict --------------------------
verdict_msg, verdict_color, verdict_note = decide_flow(d["total"], d["btc"], d["eth"], d["stable"], d["alt"])
st.markdown(
    f"""
    <div style="padding:14px;border-radius:14px;border:1px solid #e5e7eb;background:#0b1220;">
      <h2 style="margin:0;text-align:center;color:{verdict_color}">نتیجه بازار: {verdict_msg}</h2>
      <p style="margin:8px 0 0;color:#94a3b8;text-align:center">{verdict_note} — بازه: {tf_label}</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("")

# -------------------------- Delta Bars --------------------------
bars = pd.DataFrame({
    "بخش": ["Total","BTC","ETH","Stable","Alts"],
    "تغییر (USD)": [
        d["total"] if d["total"] is not None else 0,
        d["btc"] if d["btc"] is not None else 0,
        d["eth"] if d["eth"] is not None else 0,
        d["stable"] if d["stable"] is not None else 0,
        d["alt"] if d["alt"] is not None else 0,
    ]
})

fig_bars = px.bar(
    bars, x="بخش", y="تغییر (USD)",
    title=f"تغییرات نقدینگی طی {tf_label}",
)
fig_bars.update_layout(margin=dict(l=10,r=10,t=40,b=0), height=320)
st.plotly_chart(fig_bars, use_container_width=True)

# -------------------------- Live Line (session series) --------------------------
ts_df = pd.DataFrame(st.session_state.ts)
for col in ["ΔTotal","ΔBTC","ΔETH","ΔStable","ΔAlt"]:
    ts_df[col] = ts_df[col].fillna(0.0)

fig_line = go.Figure()
fig_line.add_trace(go.Scatter(x=ts_df["t"], y=ts_df["ΔTotal"], mode="lines+markers", name="ΔTotal"))
fig_line.add_trace(go.Scatter(x=ts_df["t"], y=ts_df["ΔBTC"], mode="lines+markers", name="ΔBTC"))
fig_line.add_trace(go.Scatter(x=ts_df["t"], y=ts_df["ΔETH"], mode="lines+markers", name="ΔETH"))
fig_line.add_trace(go.Scatter(x=ts_df["t"], y=ts_df["ΔStable"], mode="lines+markers", name="ΔStable"))
fig_line.add_trace(go.Scatter(x=ts_df["t"], y=ts_df["ΔAlt"], mode="lines+markers", name="ΔAlt"))
fig_line.update_layout(
    title="نمایش زنده تغییرات (از زمان اجرای صفحه)",
    margin=dict(l=10,r=10,t=40,b=0), height=330,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_line, use_container_width=True)

# -------------------------- Composition Pie --------------------------
pie_df = pd.DataFrame({
    "بخش": ["BTC","Stablecoins","Altcoins"],
    "MCap (USD)": [now["btc"], now["stable"], now["alt"]]
})
fig_pie = px.pie(pie_df, values="MCap (USD)", names="بخش", title="ترکیب فعلی بازار")
fig_pie.update_layout(margin=dict(l=10,r=10,t=40,b=0), height=320)
st.plotly_chart(fig_pie, use_container_width=True)

# Footer
st.caption("⚠️ این داشبورد از چند منبع عمومی استفاده می‌کند (CoinGecko + Binance)."
           " اعداد تقریبی‌اند و برای تصمیم‌گیری مالی کافی نیستند.")

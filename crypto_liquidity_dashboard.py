# crypto_liquidity_dashboard.py
import streamlit as st
import requests
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import pandas as pd

st.set_page_config(page_title="Crypto Liquidity Flow", layout="wide")

CG_BASE = "https://api.coingecko.com/api/v3"
STABLES = ["tether","usd-coin","dai"]

def cg_get(path, params=None):
    url = CG_BASE + path
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None

def fetch_snapshot():
    g = cg_get("/global")
    if not g: return None
    data = g.get("data", {})
    total = data.get("total_market_cap", {}).get("usd", 0)
    btc_dom = data.get("market_cap_percentage", {}).get("btc", 0)
    # sum stable marketcaps
    stable_mcap = 0
    for s in STABLES:
        coin = cg_get(f"/coins/{s}")
        try:
            stable_mcap += coin["market_data"]["market_cap"]["usd"]
        except:
            pass
    return {"total": total, "btc_dom": btc_dom, "stable_mcap": stable_mcap}

def analyze_snapshot(snap):
    total = snap["total"]
    stable = snap["stable_mcap"]
    btc_dom = snap["btc_dom"]
    if total == 0:
        return "داده کافی نیست", "gray"
    # ساده و قابل‌فهم
    if stable / total > 0.12:
        return "خروج نقدینگی → تجمع در استیبل‌کوین‌ها", "red"
    if btc_dom > 50:
        return "ورود نقدینگی با تمرکز روی بیت‌کوین", "orange"
    return "ورود نقدینگی به آلت‌کوین‌ها / ریسک‌پذیری افزایش یافته", "green"

# UI
st.title("📊 Crypto Liquidity Flow — جریان نقدینگی بازار")
tf = st.selectbox("تایم‌فریم رو انتخاب کن", ["15m","1h","4h","24h","7d"], index=3)
st.caption("منبع: CoinGecko — خروجی تخمینی است. برای تصمیم‌گیری مالی مستقل استفاده نکنید.")

if st.button("به‌روزرسانی"):
    with st.spinner("دریافت داده..."):
        snap = fetch_snapshot()
    if not snap:
        st.error("خطا در دریافت داده. دوباره تلاش کن.")
    else:
        st.metric("مارکت‌کپ کل (تخمینی)", f"{snap['total'] / 1e9:.2f} میلیارد دلار")
        st.metric("مجموع استیبل‌کوین‌ها (تخمینی)", f"{snap['stable_mcap'] / 1e9:.2f} میلیارد دلار")
        st.metric("دومیننس بیت‌کوین", f"{snap['btc_dom']:.2f}%")
        msg, color = analyze_snapshot(snap)
        st.markdown(f"<h2 style='color:{color};text-align:center'>{msg}</h2>", unsafe_allow_html=True)

        # نمودار ساده برای نمایش سهم‌ها
        btc_mcap = snap['total'] * snap['btc_dom'] / 100.0
        alt_mcap = max(snap['total'] - btc_mcap - snap['stable_mcap'], 0)
        df = pd.DataFrame({
            "component": ["Bitcoin", "Stablecoins", "Altcoins"],
            "mcap": [btc_mcap/1e9, snap['stable_mcap']/1e9, alt_mcap/1e9]
        })
        fig, ax = plt.subplots(figsize=(6,3))
        ax.pie(df["mcap"], labels=df["component"], autopct='%1.1f%%')
        ax.set_title(f"تقسیم‌بندی بازار (میلیارد دلار) — {tf}")
        st.pyplot(fig)

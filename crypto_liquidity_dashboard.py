import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# ==============================
# تنظیمات اولیه صفحه
# ==============================
st.set_page_config(
    page_title="Crypto Liquidity Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 داشبورد ورود و خروج نقدینگی بازار ارز دیجیتال")

# ==============================
# تنظیمات رفرش خودکار
# ==============================
refresh_ms = st.sidebar.number_input(
    "⏱️ فاصله‌ی رفرش (میلی‌ثانیه)",
    min_value=5000,
    max_value=60000,
    step=5000,
    value=15000
)

auto_refresh = st.sidebar.checkbox("فعال‌سازی رفرش خودکار", value=True)

if auto_refresh:
    refresh_code = f"""
        <script>
        function autoRefresh() {{
            window.location.reload();
        }}
        setInterval(autoRefresh, {refresh_ms});
        </script>
    """
    st.markdown(refresh_code, unsafe_allow_html=True)

# ==============================
# توابع کمکی برای گرفتن داده
# ==============================
def get_data_from_coingecko():
    url = "https://api.coingecko.com/api/v3/global"
    try:
        data = requests.get(url).json()
        return data["data"]
    except Exception as e:
        st.error("❌ خطا در گرفتن داده از CoinGecko")
        return None

def get_binance_volume(symbol="BTCUSDT"):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        return float(requests.get(url).json()["quoteVolume"])
    except:
        return None

# ==============================
# گرفتن داده‌ها
# ==============================
cg_data = get_data_from_coingecko()

if cg_data:
    total_mcap = cg_data["total_market_cap"]["usd"]
    btc_dominance = cg_data["market_cap_percentage"]["btc"]
    eth_dominance = cg_data["market_cap_percentage"]["eth"]
    stable_dominance = sum([cg_data["market_cap_percentage"].get(s, 0)
                            for s in ["usdt", "usdc", "busd", "dai"]])

    # محاسبه مارکت کپ‌های جدا
    btc_mcap = total_mcap * (btc_dominance / 100)
    eth_mcap = total_mcap * (eth_dominance / 100)
    stable_mcap = total_mcap * (stable_dominance / 100)
    alt_mcap = total_mcap - (btc_mcap + eth_mcap + stable_mcap)

    # گرفتن حجم معاملات بایننس
    btc_vol = get_binance_volume("BTCUSDT")
    eth_vol = get_binance_volume("ETHUSDT")
    usdt_vol = get_binance_volume("USDTUSDT")  # معمولاً صفره ولی برای مثال

    # ==============================
    # نمایش شاخص‌های کلیدی
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔵 مارکت‌کپ بیت‌کوین", f"${btc_mcap:,.0f}")
    col2.metric("🟣 مارکت‌کپ اتریوم", f"${eth_mcap:,.0f}")
    col3.metric("🟢 مارکت‌کپ استیبل‌کوین‌ها", f"${stable_mcap:,.0f}")
    col4.metric("🟡 مارکت‌کپ آلت‌کوین‌ها", f"${alt_mcap:,.0f}")

    # ==============================
    # نمودار سهم بازار
    # ==============================
    st.subheader("📈 دامیننس بازار")
    fig, ax = plt.subplots()
    labels = ["BTC", "ETH", "Stables", "Altcoins"]
    values = [btc_dominance, eth_dominance, stable_dominance,
              100 - (btc_dominance + eth_dominance + stable_dominance)]
    ax.pie(values, labels=labels, autopct='%1.1f%%',
           startangle=90, colors=["gold", "purple", "green", "blue"])
    st.pyplot(fig)

    # ==============================
    # نتیجه نهایی
    # ==============================
    st.subheader("📊 نتیجه بازار")
    direction = ""
    if btc_dominance > eth_dominance and btc_dominance > stable_dominance:
        direction = "🚀 ورود نقدینگی به بیت‌کوین"
        color = "green"
    elif eth_dominance > btc_dominance and eth_dominance > stable_dominance:
        direction = "🔥 ورود نقدینگی به اتریوم"
        color = "orange"
    elif stable_dominance > 20:  # یعنی پول رفته تو استیبل‌ها
        direction = "⚠️ خروج نقدینگی به سمت استیبل‌کوین‌ها"
        color = "red"
    else:
        direction = "🔄 توزیع نقدینگی بیشتر روی آلت‌کوین‌هاست"
        color = "blue"

    st.markdown(f"<h2 style='color:{color}'>{direction}</h2>",
                unsafe_allow_html=True)

else:
    st.error("❌ داده‌ها بارگذاری نشد. دوباره امتحان کنید.")

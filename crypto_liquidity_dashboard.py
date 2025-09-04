import requests
import pandas as pd
import streamlit as st
import plotly.express as px

# ==============================
# Binance API - Get OHLCV Data
# ==============================
def get_binance_ohlcv(symbol="BTCUSDT", interval="1h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data, columns=[
        "time_open","open","high","low","close","volume",
        "time_close","qav","num_trades","taker_base_vol","taker_quote_vol","ignore"
    ])
    df["time_open"] = pd.to_datetime(df["time_open"], unit="ms")
    df["volume"] = df["volume"].astype(float)
    df["close"] = df["close"].astype(float)
    return df[["time_open", "close", "volume"]]

# ==============================
# Streamlit App
# ==============================
st.set_page_config(page_title="📊 Crypto Liquidity Dashboard", layout="wide")

st.title("📊 داشبورد ورود و خروج نقدینگی")
st.markdown("این داشبورد حجم معاملات و جهت نقدینگی رو در تایم‌فریم‌های مختلف نشون میده.")

# انتخاب تایم‌فریم
interval = st.sidebar.selectbox("⏳ تایم‌فریم", ["1h", "4h", "1d"])
limit = st.sidebar.slider("📅 تعداد کندل‌ها", 50, 500, 200)

# کوین‌ها
coins = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "USDT": "BUSDUSDT",   # استیبل کوین
    "BNB (Altcoin)": "BNBUSDT"  # شاخص نمونه برای آلت‌کوین
}

# نمایش دیتا برای هر کوین
for name, symbol in coins.items():
    st.subheader(f"{name} ({symbol}) - تایم‌فریم {interval}")
    df = get_binance_ohlcv(symbol, interval, limit)

    col1, col2 = st.columns([2, 1])

    with col1:
        fig_vol = px.bar(df, x="time_open", y="volume",
                         title=f"حجم معاملات {name}",
                         labels={"time_open": "زمان", "volume": "حجم"})
        st.plotly_chart(fig_vol, use_container_width=True)

    with col2:
        fig_price = px.line(df, x="time_open", y="close",
                            title=f"قیمت {name}",
                            labels={"time_open": "زمان", "close": "قیمت"})
        st.plotly_chart(fig_price, use_container_width=True)

    # نتیجه جهت نقدینگی
    avg_volume = df["volume"].mean()
    last_volume = df["volume"].iloc[-1]
    if last_volume > avg_volume * 1.2:
        st.success(f"✅ نقدینگی قوی در حال ورود به {name} است.")
    elif last_volume < avg_volume * 0.8:
        st.error(f"⚠️ احتمال خروج نقدینگی از {name}.")
    else:
        st.info(f"ℹ️ وضعیت نقدینگی {name} نرمال است.")

st.markdown("---")
st.caption("منبع داده: Binance API (Real-time)")

import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ta.volume import OnBalanceVolumeIndicator, money_flow_index

# ==============================
# CryptoCompare API - Get OHLCV Data
# ==============================
@st.cache_data(ttl=60)
def get_cryptocompare_ohlcv(symbol="BTC", vs_currency="USDT", interval="hour", limit=200):
    if interval == "1h":
        url = "https://min-api.cryptocompare.com/data/v2/histohour"
    elif interval == "4h":
        url = "https://min-api.cryptocompare.com/data/v2/histohour"
        limit = limit * 4
    elif interval == "1d":
        url = "https://min-api.cryptocompare.com/data/v2/histoday"
    else:
        st.error("تایم‌فریم نامعتبر")
        return pd.DataFrame()

    params = {"fsym": symbol, "tsym": vs_currency, "limit": limit}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"خطا در ارتباط با API CryptoCompare: {e}")
        return pd.DataFrame()

    if not data or 'Data' not in data or 'Data' not in data['Data'] or not data['Data']['Data']:
        st.warning(f"هیچ داده‌ای برای نماد {symbol} و تایم‌فریم {interval} دریافت نشد. لطفا نماد یا تایم‌فریم را بررسی کنید.")
        return pd.DataFrame()

    df = pd.DataFrame(data['Data']['Data'])
    
    # Rename and clean up columns to match previous code logic
    df = df[['time', 'open', 'high', 'low', 'close', 'volumefrom']]
    df.rename(columns={'time': 'time_open', 'volumefrom': 'volume'}, inplace=True)
    
    df["time_open"] = pd.to_datetime(df["time_open"], unit="s")
    
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df.dropna(subset=numeric_cols, inplace=True)

    if df.empty:
        st.warning("داده‌های دریافت شده قابل پردازش نبودند.")
        return pd.DataFrame()
        
    # Recalculate indicators and volume direction on the new data
    df["volume_direction"] = df.apply(lambda row: row["volume"] if row["close"] >= row["open"] else -row["volume"], axis=1)

    if len(df) > 1:
        df["obv"] = OnBalanceVolumeIndicator(close=df["close"], volume=df["volume"]).on_balance_volume()
        df["mfi"] = money_flow_index(high=df["high"], low=df["low"], close=df["close"], volume=df["volume"])
    else:
        df["obv"] = pd.Series([0] * len(df))
        df["mfi"] = pd.Series([0] * len(df))
        
    return df

# ==============================
# Streamlit App
# ==============================
st.set_page_config(page_title="📊 Crypto Liquidity Dashboard", layout="wide")

st.title("📊 داشبورد ورود و خروج نقدینگی")
st.markdown("این داشبورد با استفاده از داده‌های حجم و شاخص‌های تحلیلی، جهت نقدینگی رو نشون میده.")

# Sidebar controls
st.sidebar.header("تنظیمات")
interval = st.sidebar.selectbox("⏳ تایم‌فریم", ["1h", "4h", "1d"])
limit = st.sidebar.slider("📅 تعداد کندل‌ها", 50, 500, 200)

# Coin selection
coins = {
    "BTC": "BTC",
    "ETH": "ETH",
    "BNB": "BNB",
    "XRP": "XRP",
    "DOGE": "DOGE"
}
selected_coin = st.sidebar.selectbox("💰 انتخاب کوین", list(coins.keys()))
symbol = coins[selected_coin]

# Get data
df = get_cryptocompare_ohlcv(symbol, "USDT", interval, limit)

# Only display charts if DataFrame is not empty
if not df.empty:
    st.subheader(f"تحلیل نقدینگی {selected_coin} - تایم‌فریم {interval}")

    # Display charts
    fig_price = go.Figure(data=[go.Candlestick(
        x=df['time_open'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='green',
        decreasing_line_color='red'
    )])
    fig_price.update_layout(title=f'نمودار شمعی قیمت {selected_coin}',
                            xaxis_rangeslider_visible=False)

    fig_vol = go.Figure(data=[go.Bar(
        x=df['time_open'],
        y=df['volume'],
        marker_color=['green' if close >= open else 'red' for open, close in zip(df['open'], df['close'])]
    )])
    fig_vol.update_layout(title=f'نمودار حجم {selected_coin}',
                          xaxis_title='زمان', yaxis_title='حجم')

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig_price, use_container_width=True)
    with col2:
        st.plotly_chart(fig_vol, use_container_width=True)

    # Display indicators
    st.subheader("شاخص‌های نقدینگی")
    col3, col4 = st.columns(2)

    if len(df) > 1:
        with col3:
            try:
                current_obv = df['obv'].iloc[-1]
                obv_delta = df['obv'].diff().iloc[-1]
                st.metric("شاخص OBV", f"{current_obv:,.0f}", f"{obv_delta:,.0f}")
                st.caption("افزایش OBV نشان‌دهنده ورود نقدینگی است.")
            except IndexError:
                st.info("داده کافی برای محاسبه OBV وجود ندارد.")

        with col4:
            try:
                current_mfi = df['mfi'].iloc[-1]
                st.metric("شاخص MFI", f"{current_mfi:.2f}")
                st.caption("بالاتر از ۸۰ فشار خرید و پایین‌تر از ۲۰ فشار فروش را نشان می‌دهد.")
            except IndexError:
                st.info("داده کافی برای محاسبه MFI وجود ندارد.")
    else:
        st.info("داده کافی برای نمایش شاخص‌ها وجود ندارد.")

    st.markdown("---")
    st.caption("منبع داده: CryptoCompare API (Real-time)")
else:
    st.info("در حال حاضر داده‌ای برای نمایش موجود نیست. لطفاً تنظیمات را بررسی کنید.")

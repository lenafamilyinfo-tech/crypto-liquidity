import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ta.volume import OnBalanceVolumeIndicator, money_flow_index

# ==============================
# Binance API - Get OHLCV Data
# ==============================
@st.cache_data(ttl=60)
def get_binance_ohlcv(symbol="BTCUSDT", interval="1h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"خطا در ارتباط با API بایننس: {e}")
        return pd.DataFrame()

    if not data:
        st.warning(f"هیچ داده‌ای برای نماد {symbol} و تایم‌فریم {interval} دریافت نشد. لطفا نماد یا تایم‌فریم را بررسی کنید.")
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=[
        "time_open","open","high","low","close","volume",
        "time_close","qav","num_trades","taker_base_vol","taker_quote_vol","ignore"
    ])
    
    df["time_open"] = pd.to_datetime(df["time_open"], unit="ms")
    
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df.dropna(subset=numeric_cols, inplace=True)

    if df.empty:
        st.warning("داده‌های دریافت شده قابل پردازش نبودند.")
        return pd.DataFrame()

    # Calculate volume direction
    df["volume_direction"] = df.apply(lambda row: row["volume"] if row["close"] >= row["open"] else -row["volume"], axis=1)
    
    # Calculate indicators
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
interval = st.sidebar.selectbox("⏳ تایم‌فریم", ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"])
limit = st.sidebar.slider("📅 تعداد کندل‌ها", 50, 500, 200)

# Coin selection
coins = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
    "DOGE": "DOGEUSDT"
}
selected_coin = st.sidebar.selectbox("💰 انتخاب کوین", list(coins.keys()))
symbol = coins[selected_coin]

# Get data
df = get_binance_ohlcv(symbol, interval, limit)

# Only display charts if DataFrame is not empty
if not df.empty:
    st.subheader(f"تحلیل نقدینگی {selected_coin} ({symbol}) - تایم‌فریم {interval}")

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
    st.caption("منبع داده: Binance API (Real-time)")
else:
    st.info("در حال حاضر داده‌ای برای نمایش موجود نیست. لطفاً تنظیمات را بررسی کنید.")

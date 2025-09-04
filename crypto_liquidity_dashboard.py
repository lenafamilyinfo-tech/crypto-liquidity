import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from ta.volume import OnBalanceVolumeIndicator, money_flow_index

# ==============================
# Binance API - Get OHLCV Data
# ==============================
@st.cache_data
def get_binance_ohlcv(symbol="BTCUSDT", interval="1h", limit=200):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data, columns=[
        "time_open","open","high","low","close","volume",
        "time_close","qav","num_trades","taker_base_vol","taker_quote_vol","ignore"
    ])
    df["time_open"] = pd.to_datetime(df["time_open"], unit="ms")
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    
    # Calculate volume direction
    df["volume_direction"] = df.apply(lambda row: row["volume"] if row["close"] >= row["open"] else -row["volume"], axis=1)
    
    # Calculate indicators
    df["obv"] = OnBalanceVolumeIndicator(close=df["close"], volume=df["volume"]).on_balance_volume()
    df["mfi"] = money_flow_index(high=df["high"], low=df["low"], close=df["close"], volume=df["volume"])
    
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
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT"
}
selected_coin = st.sidebar.selectbox("💰 انتخاب کوین", list(coins.keys()))
symbol = coins[selected_coin]

# Get data
df = get_binance_ohlcv(symbol, interval, limit)

st.subheader(f"تحلیل نقدینگی {selected_coin} ({symbol}) - تایم‌فریم {interval}")

# Display charts
fig_price = go.Figure(data=[go.Candlestick(
    x=df['time_open'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close']
)])
fig_price.update_layout(title=f'نمودار شمعی قیمت و حجم {selected_coin}',
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
with col3:
    st.metric("شاخص OBV", f"{df['obv'].iloc[-1]:,.0f}", f"{df['obv'].diff().iloc[-1]:,.0f}")
    st.caption("افزایش OBV نشان‌دهنده ورود نقدینگی است.")
with col4:
    st.metric("شاخص MFI", f"{df['mfi'].iloc[-1]:.2f}")
    st.caption("بالاتر از ۸۰ فشار خرید و پایین‌تر از ۲۰ فشار فروش را نشان می‌دهد.")

st.markdown("---")
st.caption("منبع داده: Binance API (Real-time)")

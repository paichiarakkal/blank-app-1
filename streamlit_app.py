import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import yfinance as yf
import urllib.parse
import os
import plotly.graph_objects as fgo
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SETTINGS ---
WA_PHONE = "971551347989"
WA_API_KEY = "7463030"

# ടെലിഗ്രാം അലേർട്ടിനായുള്ള കോൺഫിഗറേഷൻ (നിങ്ങളുടെ ടോക്കണും ചാറ്റ് ഐഡിയും ഇവിടെ നൽകാം)
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

USERS = {"faisal": "faisal147", "shabana": "shabana123", "admin": "paichi786"}
LOG_FILE = "paichi_signals_log.csv"
ALERT_FILE = "paichi_price_alerts.csv"
JOURNAL_FILE = "trade_history_v2.csv" # പഴയ ജേർണൽ ഫയൽ നെയിം തന്നെ ഉപയോഗിക്കുന്നു

st.set_page_config(page_title="PAICHI GOLD TRADING v10.0", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh_v10")

# --- 2. 💾 FILE MEMORY FUNCTIONS ---
def get_stored_signal(asset_name):
    filename = f"sig_{asset_name.replace(' ', '_')}.txt"
    if os.path.exists(filename):
        with open(filename, "r") as f: return f.read().strip()
    return ""

def save_signal_to_file(asset_name, signal_text):
    filename = f"sig_{asset_name.replace(' ', '_')}.txt"
    with open(filename, "w") as f: f.write(signal_text)

def log_signal_to_csv(asset_name, signal, price, rsi, t1, t2, sl):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    new_data = pd.DataFrame([[now, asset_name, signal, price, rsi, t1, t2, sl]], 
                            columns=['Time', 'Asset', 'Signal', 'Price', 'RSI', 'Target 1', 'Target 2', 'StopLoss'])
    if not os.path.exists(LOG_FILE): new_data.to_csv(LOG_FILE, index=False)
    else: new_data.to_csv(LOG_FILE, mode='a', header=False, index=False)

def save_to_journal(asset, action, price, qty, pnl):
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    df_new = pd.DataFrame([[date, asset, action, price, price, qty, pnl, "Disciplined"]], 
                          columns=['Date', 'Item', 'Type', 'Entry', 'Exit', 'Qty', 'P&L', 'Mood'])
    if not os.path.isfile(JOURNAL_FILE): df_new.to_csv(JOURNAL_FILE, index=False)
    else: df_new.to_csv(JOURNAL_FILE, mode='a', header=False, index=False)

# --- 3. 🎨 PREMIUM DESIGN ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #0f0214, #1d0030, #05000a); color: #fff; }
    [data-testid="stSidebar"] { background: rgba(0,0,0,0.92) !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 10px; font-weight: bold; width: 100%; height: 40px; font-size: 15px; }
    .terminal-banner { background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 15px; border-left: 10px solid #FFD700; margin-bottom: 25px; text-align: center; }
    .purple-box { background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 20px; border: 2px solid rgba(255, 215, 0, 0.15); text-align: center; margin-bottom: 15px; }
    h1, h2, h3, p, label { color: white !important; font-weight: bold !important; }
    div[data-testid="stSlider"] label { color: #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""

# --- 4. 🚀 NOTIFICATION ENGINES ---
def send_whatsapp(message_text):
    url = f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={urllib.parse.quote(message_text)}&apikey={WA_API_KEY}"
    try: requests.get(url, timeout=10)
    except: pass

def send_telegram(message_text):
    if TELEGRAM_BOT_TOKEN != "YOUR_TELEGRAM_BOT_TOKEN":
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={urllib.parse.quote(message_text)}&parse_mode=Markdown"
        try: requests.get(url, timeout=10)
        except: pass

# --- 5. 📊 SUPERTREND & MULTI-INDICATOR CALCULATION ---
def get_supertrend_and_indicators(df, rsi_period):
    # RSI & EMA 20
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001)).iloc[-1]))
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    
    # Simple Supertrend Logic (ATR based)
    high, low, close = df['High'], df['Low'], df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=10).mean()
    
    hl2 = (high + low) / 2
    upper_band = hl2 + (3 * atr)
    lower_band = hl2 - (3 * atr)
    
    supertrend = pd.Series(index=df.index, dtype=float)
    trend = 1
    for i in range(1, len(df)):
        if close.iloc[i] > upper_band.iloc[i-1]: trend = 1
        elif close.iloc[i] < lower_band.iloc[i-1]: trend = -1
        supertrend.iloc[i] = lower_band.iloc[i] if trend == 1 else upper_band.iloc[i]
        
    return rsi, ema20.iloc[-1], supertrend.iloc[-1], trend

def get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval):
    try:
        symbols = {"Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "Crude Fut": "CL=F"}
        results = []
        history_period = "5d" if selected_interval in ["5m", "15m"] else "1mo"
        
        for name, sym in symbols.items():
            df = yf.Ticker(sym).history(period=history_period, interval=selected_interval)
            if df.empty: continue
            
            last_p = df['Close'].iloc[-1]
            h, l, c = df['High'].iloc[-2], df['Low'].iloc[-2], df['Close'].iloc[-2]
            
            pivot = (h + l + c) / 3
            r1, r2, s1, s2 = (2*pivot)-l, pivot+(h-l), (2*pivot)-h, pivot-(h-l)
            
            rsi, ema20_val, st_val, trend = get_supertrend_and_indicators(df, rsi_period)
            
            if name == "Crude Fut":
                last_p, pivot, r1, r2, s1, s2, ema20_val, st_val = [x * 83.5 * 1.15 for x in [last_p, pivot, r1, r2, s1, s2, ema20_val, st_val]]

            # Multi-Condition Setup (Pivot + RSI + EMA + Supertrend)
            if last_p > pivot and rsi > buy_level and last_p > ema20_val and trend == 1:
                signal, color, icon, t1, t2, sl = "🚀 BUY", "#00FF00", "🟢", r1, r2, s1
            elif last_p < pivot and rsi < sell_level and last_p < ema20_val and trend == -1:
                signal, color, icon, t1, t2, sl = "📉 SELL", "#FF3131", "🔴", s1, s2, r1
            else:
                signal, color, icon, t1, t2, sl = "⚖️ WAIT", "#FFFF00", "🟡", 0, 0, 0
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon, "t1": t1, "t2": t2, "sl": sl, "df": df})
        return results
    except: return None

# --- 6. MAIN APP TERMINAL ---
if not st.session_state.auth:
    st.markdown('<div style="text-align:center; padding-top:50px;"><h1>🔐 PAICHI TRADING BOT LOGIN</h1></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        u = st.text_input("Username").lower()
        p = st.text_input("Password", type="password")
        if st.button("LOGIN TO TERMINAL"):
            if USERS.get(u) == p:
                st.session_state.auth, st.session_state.user = True, u
                st.rerun()
            else: st.error("Access Denied!")
else:
    curr_user = st.session_state.user
    st.markdown(f'''<div class="terminal-banner">
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v10.0</span><br>
        <span style="font-size:14px; color:#E0B0FF;">Welcome, {curr_user.capitalize()} | 📊 Pro Candlesticks & Telegram Connected</span>
    </div>''', unsafe_allow_html=True)

    # Sidebar settings
    st.sidebar.markdown("<h2>🛠️ Strategy Tweak</h2>", unsafe_allow_html=True)
    selected_interval = st.sidebar.selectbox("Interval:", options=["5m", "15m", "30m", "1h"], index=0)
    rsi_period = st.sidebar.slider("RSI Period:", 5, 30, 14)
    buy_level = st.sidebar.slider("RSI BUY Level:", 50, 80, 55)
    sell_level = st.sidebar.slider("RSI SELL Level:", 20, 50, 45)
    
    st.sidebar.write("---")
    if st.sidebar.button("Logout"):
        st.session_state.auth = False
        st.rerun()

    markets = get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval)

    # --- 🤖 AUTOMATIC ALERTS & ENGINE LOG ---
    if markets:
        for m in markets:
            paya_signal = get_stored_signal(m["name"])
            if paya_signal != m["signal"]:
                save_signal_to_file(m["name"], m["signal"])
                if m["signal"] != "⚖️ WAIT":
                    log_signal_to_csv(m["name"], m["signal"], m["price"], m["rsi"], m["t1"], m["t2"], m["sl"])
                    now_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                    msg = (
                        f"{m['icon']} *PAICHI V10 SIGNAL* {m['icon']}\n\n"
                        f"📦 *Asset:* {m['name']}\n🚦 *Signal:* {m['signal']}\n"
                        f"💰 *Price:* ₹{m['price']:,.2f}\n📊 *RSI:* {m['rsi']:.1f}\n"
                        f"🎯 *T1:* ₹{m['t1']:,.2f} | *T2:* ₹{m['t2']:,.2f}\n"
                        f"🛑 *SL:* ₹{m['sl']:,.2f}\n⏰ *Time:* {now_time}"
                    )
                    send_whatsapp(msg)
                    send_telegram(msg)

    # --- TABS DISPLAY ---
    tab1, tab2, tab3, tab4 = st.tabs(["📈 LIVE TERMINAL", "📊 INTERACTIVE CHARTS", "📋 SIGNAL LOGS", "🔔 PRICE ALERTS"])

    with tab1:
        if markets:
            cols = st.columns(3)
            for i, m in enumerate(markets):
                with cols[i]:
                    st.markdown(f"""<div class="purple-box" style="border-color: {m['color']} !important;">
                        <h2 style="color:#E0B0FF !important; margin-bottom:0;">{m["name"]}</h2>
                        <h1 style="color:{m["color"]} !important; font-size:42px; margin:10px 0;">{m["signal"]}</h1>
                        <h2 style="color:#FFD700 !important; font-size:30px; margin-bottom:5px;">₹{m["price"]:,.2f}</h2>
                        <p style="color:#aaa; font-size:13px; margin-bottom:10px;">RSI: {m["rsi"]:.1f}</p>
                        {"<div style='text-align:left; background:rgba(0,0,0,0.4); padding:10px; border-radius:10px; font-size:13px; margin-bottom:10px;'>"
                          f"🎯 <b>T1:</b> ₹{m['t1']:,.2f}<br>"
                          f"🎯 <b>T2:</b> ₹{m['t2']:,.2f}<br>"
                          f"🛑 <b>SL:</b> ₹{m['sl']:,.2f}</div>" if m["signal"] != "⚖️ WAIT" else ""}
                    </div>""", unsafe_allow_html=True)
        else: st.warning("Loading Terminal...")

    with tab2:
        st.subheader("Professional Candlestick Chart Window")
        if markets:
            selected_chart = st.selectbox("Select Asset to View Chart:", [m["name"] for m in markets])
            m_chart_data = next(x for x in markets if x["name"] == selected_chart)
            chart_df = m_chart_data["df"]
            
            # Plotly Candlestick Chart
            fig = fgo.Figure(data=[fgo.Candlestick(x=chart_df.index,
                            open=chart_df['Open'], high=chart_df['High'],
                            low=chart_df['Low'], close=chart_df['Close'], name='Candlestick')])
            fig.update_layout(theme="dark", xaxis_rangeslider_visible=False, template="plotly_dark",
                              margin=dict(l=20, r=20, t=20, b=20), height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Automated History & Direct Journal Booking")
        if os.path.exists(LOG_FILE):
            log_df = pd.read_csv(LOG_FILE)
            st.dataframe(log_df.iloc[::-1], use_container_width=True)
            
            st.write("---")
            st.markdown("### 📝 Quick Book Trade into Journal")
            c1, c2, c3 = st.columns(3)
            j_asset = c1.selectbox("Choose Asset", log_df['Asset'].unique())
            j_qty = c2.number_input("Quantity", min_value=1, value=10)
            j_pnl = c3.number_input("P&L Realized (₹)", value=0.0)
            
            if st.button("➕ Book to Option Journal"):
                last_price_str = log_df[log_df['Asset'] == j_asset].iloc[-1]['Price'].replace('₹','').replace(',','')
                save_to_journal(j_asset, "AUTO-BOT", float(last_price_str), j_qty, j_pnl)
                st.success("Successfully logged into trade_history_v2.csv! 🎉")
        else: st.write("No signals recorded yet.")

    with tab4:
        st.subheader("Set Custom Price Alerts")
        if markets:
            c1, c2, c3 = st.columns(3)
            a_asset = c1.selectbox("Alert Asset", [m["name"] for m in markets])
            a_cond = c2.selectbox("Condition Mode", ["Above", "Below"])
            a_price = c3.number_input("Trigger Target (₹)", min_value=0.0, value=float(next(x for x in markets if x["name"] == a_asset)["price"]))
            
            if st.button("⏰ Active Alert Now"):
                alert_df = pd.DataFrame([[a_asset, a_cond, a_price]], columns=["Asset", "Condition", "TargetPrice"])
                if not os.path.exists(ALERT_FILE): alert_df.to_csv(ALERT_FILE, index=False)
                else: alert_df.to_csv(ALERT_FILE, mode='a', header=False, index=False)
                st.success("Alert Active! ✅")
                st.rerun()

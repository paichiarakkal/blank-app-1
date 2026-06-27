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
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

USERS = {"faisal": "faisal147", "shabana": "shabana123", "admin": "paichi786"}
LOG_FILE = "paichi_signals_log.csv"
ALERT_FILE = "paichi_price_alerts.csv"
JOURNAL_FILE = "trade_history_v2.csv"
POSITION_FILE = "paichi_live_positions.csv" # ഓട്ടോപൈലറ്റ് പൊസിഷനുകൾ സൂക്ഷിക്കാൻ

st.set_page_config(page_title="PAICHI GOLD TRADING v12.0", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh_v12")

# --- 2. 💾 FILE MEMORY & AUTO-PILOT FUNCTIONS ---
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

def get_live_positions():
    if os.path.exists(POSITION_FILE): return pd.read_csv(POSITION_FILE)
    return pd.DataFrame(columns=['Asset', 'Type', 'EntryPrice', 'Qty', 'SL', 'T1', 'T2'])

def manage_autopilot_execution(asset_name, signal, price, sl, t1, t2, qty):
    positions = get_live_positions()
    now_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # 1. നിലവിൽ ഒരു പൊസിഷൻ ഉണ്ടെങ്കിൽ അത് ക്ലോസ് ചെയ്യേണ്ടതുണ്ടോ എന്ന് നോക്കുക (Target അല്ലെങ്കിൽ StopLoss ഹിറ്റ് ആയാൽ)
    if not positions.empty and asset_name in positions['Asset'].values:
        pos = positions[positions['Asset'] == asset_name].iloc[0]
        closed = False
        pnl = 0.0
        
        if pos['Type'] == '🚀 BUY':
            if price >= pos['T1']: # Target 1 Hit
                closed, pnl = True, (price - pos['EntryPrice']) * pos['Qty']
                msg_status = f"🎯 *AUTO-PILOT TARGET 1 HIT!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price <= pos['SL']: # Stop Loss Hit
                closed, pnl = True, (price - pos['EntryPrice']) * pos['Qty']
                msg_status = f"🛑 *AUTO-PILOT STOP-LOSS HIT!* 🛑\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
        
        elif pos['Type'] == '📉 SELL':
            if price <= pos['T1']: # Target 1 Hit for Short Sell
                closed, pnl = True, (pos['EntryPrice'] - price) * pos['Qty']
                msg_status = f"🎯 *AUTO-PILOT TARGET 1 HIT!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price >= pos['SL']: # Stop Loss Hit for Short Sell
                closed, pnl = True, (pos['EntryPrice'] - price) * pos['Qty']
                msg_status = f"🛑 *AUTO-PILOT STOP-LOSS HIT!* 🛑\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
                
        if closed:
            # ജേർണലിലേക്ക് മാറ്റുക
            date = datetime.now().strftime("%Y-%m-%d %H:%M")
            df_j = pd.DataFrame([[date, asset_name, f"AUTO-EXIT", pos['EntryPrice'], price, pos['Qty'], pnl, "Auto-Pilot"]], 
                                  columns=['Date', 'Item', 'Type', 'Entry', 'Exit', 'Qty', 'P&L', 'Mood'])
            if not os.path.isfile(JOURNAL_FILE): df_j.to_csv(JOURNAL_FILE, index=False)
            else: df_j.to_csv(JOURNAL_FILE, mode='a', header=False, index=False)
            
            # പൊസിഷൻ ഫയലിൽ നിന്ന് നീക്കുക
            positions = positions[positions['Asset'] != asset_name]
            positions.to_csv(POSITION_FILE, index=False)
            send_whatsapp(msg_status)
            return
            
    # 2. പുതിയ സിഗ്നൽ വരികയും നിലവിൽ ആ അസറ്റിൽ ഓർഡറുകൾ ഒന്നും ഇല്ലാതിരിക്കുകയും ചെയ്താൽ പുതിയ ട്രേഡ് എടുക്കുക
    if signal != "⚖️ WAIT" and (positions.empty or asset_name not in positions['Asset'].values):
        new_pos = pd.DataFrame([[asset_name, signal, price, qty, sl, t1, t2]], columns=positions.columns)
        if positions.empty: new_pos.to_csv(POSITION_FILE, index=False)
        else: new_pos.to_csv(POSITION_FILE, mode='a', header=False, index=False)
        
        order_msg = f"🤖 *AUTO-PILOT ORDER EXECUTED* 🤖\n\n📦 Asset: {asset_name}\n🚦 Order: {signal}\n💰 Entry Price: ₹{price:,.2f}\n🔢 Qty: {qty}\n🛑 SL: ₹{sl:,.2f}\n🎯 T1: ₹{t1:,.2f}"
        send_whatsapp(order_msg)

# --- 3. 🎨 DESIGN & STYLES ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #05000c, #10001e, #020005); color: #fff; }
    [data-testid="stSidebar"] { background: rgba(0,0,0,0.95) !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 10px; font-weight: bold; }
    .terminal-banner { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 15px; border-left: 10px solid #FFD700; text-align: center; }
    .purple-box { background: rgba(255, 255, 255, 0.03); padding: 20px; border-radius: 20px; border: 2px solid rgba(255, 215, 0, 0.15); text-align: center; margin-bottom: 15px; }
    h1, h2, h3, p, label { color: white !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""

def send_whatsapp(message_text):
    url = f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={urllib.parse.quote(message_text)}&apikey={WA_API_KEY}"
    try: requests.get(url, timeout=10)
    except: pass

# --- 4. 📊 ADVANCED ENGINE ---
def get_supertrend_and_indicators(df, rsi_period):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001)).iloc[-1]))
    ema20 = df['Close'].ewm(span=20, adjust=False).mean()
    
    high, low, close = df['High'], df['Low'], df['Close']
    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(window=10).mean()
    hl2 = (high + low) / 2
    upper_band = hl2 + (3 * atr)
    
    trend = 1
    for i in range(1, len(df)):
        if close.iloc[i] < upper_band.iloc[i-1]: trend = -1
    return rsi, ema20.iloc[-1], trend

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
            rsi, ema20_val, trend = get_supertrend_and_indicators(df, rsi_period)
            
            if name == "Crude Fut":
                last_p, pivot, r1, r2, s1, s2, ema20_val = [x * 83.5 * 1.15 for x in [last_p, pivot, r1, r2, s1, s2, ema20_val]]

            if last_p > pivot and rsi > buy_level and last_p > ema20_val and trend == 1:
                signal, color, icon, t1, t2, sl = "🚀 BUY", "#00FF00", "🟢", r1, r2, s1
            elif last_p < pivot and rsi < sell_level and last_p < ema20_val and trend == -1:
                signal, color, icon, t1, t2, sl = "📉 SELL", "#FF3131", "🔴", s1, s2, r1
            else:
                signal, color, icon, t1, t2, sl = "⚖️ WAIT", "#FFFF00", "🟡", 0, 0, 0
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon, "t1": t1, "t2": t2, "sl": sl, "df": df})
        return results
    except: return None

# --- 5. MAIN INTERFACE ---
if not st.session_state.auth:
    st.markdown('<div style="text-align:center; padding-top:50px;"><h1>🔐 PAICHI BOT SIGN-IN</h1></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        u = st.text_input("Username").lower()
        p = st.text_input("Password", type="password")
        if st.button("LOGIN"):
            if USERS.get(u) == p: st.session_state.auth, st.session_state.user = True, u; st.rerun()
            else: st.error("Access Denied!")
else:
    st.markdown(f'''<div class="terminal-banner">
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v12.0</span><br>
        <span style="font-size:14px; color:#9bf4ff;">🤖 AUTO-PILOT MODE ACTIVE (Automated Tracking & Execution Enabled)</span>
    </div>''', unsafe_allow_html=True)

    # Sidebar settings
    st.sidebar.markdown("<h2>🛠️ Settings</h2>", unsafe_allow_html=True)
    auto_pilot_on = st.sidebar.toggle("🤖 ACTIVATE AUTO-PILOT MODE", value=True)
    auto_qty = st.sidebar.number_input("Fixed Auto-Pilot Lot Size:", min_value=1, value=10)
    
    st.sidebar.write("---")
    selected_interval = st.sidebar.selectbox("Interval:", options=["5m", "15m", "30m", "1h"])
    rsi_period = st.sidebar.slider("RSI Period:", 5, 30, 14)
    buy_level = st.sidebar.slider("RSI BUY:", 50, 80, 55)
    sell_level = st.sidebar.slider("RSI SELL:", 20, 50, 45)

    markets = get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval)

    # --- ⚙️ AUTO PILOT CORE CONTROLLER ---
    if markets and auto_pilot_on:
        for m in markets:
            manage_autopilot_execution(m["name"], m["signal"], m["price"], m["sl"], m["t1"], m["t2"], auto_qty)
            paya_signal = get_stored_signal(m["name"])
            if paya_signal != m["signal"]:
                save_signal_to_file(m["name"], m["signal"])
                if m["signal"] != "⚖️ WAIT":
                    log_signal_to_csv(m["name"], m["signal"], m["price"], m["rsi"], m["t1"], m["t2"], m["sl"])

    # --- TABS ---
    tab1, tab2, tab3, tab4 = st.tabs(["🤖 LIVE AUTOPILOT POSITIONS", "📊 CHARTS", "📋 LOGS & JOURNAL", "🔔 PRICE ALERTS"])

    with tab1:
        st.subheader("💼 Active Auto-Pilot Bot Positions")
        positions_df = get_live_positions()
        if not positions_df.empty:
            st.dataframe(positions_df, use_container_width=True)
            if st.button("🚨 EMERGENCY SQUARE OFF ALL"):
                os.remove(POSITION_FILE)
                st.success("All bot positions closed immediately!")
                st.rerun()
        else: st.info("No active bot trades right now. Monitoring market for criteria setup...")

        st.write("---")
        if markets:
            cols = st.columns(3)
            for i, m in enumerate(markets):
                with cols[i]:
                    st.markdown(f"""<div class="purple-box" style="border-color: {m['color']} !important;">
                        <h3>{m["name"]}</h3>
                        <h1 style="color:{m["color"]}; font-size:40px;">{m["signal"]}</h1>
                        <h2 style="color:#FFD700;">₹{m["price"]:,.2f}</h2>
                        <p style="color:#aaa; font-size:13px;">RSI: {m["rsi"]:.1f}</p>
                    </div>""", unsafe_allow_html=True)

    with tab2:
        if markets:
            selected_chart = st.selectbox("View Chart:", [m["name"] for m in markets])
            m_chart_data = next(x for x in markets if x["name"] == selected_chart)
            chart_df = m_chart_data["df"]
            fig = fgo.Figure(data=[fgo.Candlestick(x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'])])
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("📜 Auto-Pilot Trade History Log")
        if os.path.exists(LOG_FILE):
            st.dataframe(pd.read_csv(LOG_FILE).iloc[::-1], use_container_width=True)
        if os.path.exists(JOURNAL_FILE):
            st.subheader("📓 Option Trade Journal Status")
            st.dataframe(pd.read_csv(JOURNAL_FILE).iloc[::-1], use_container_width=True)

    with tab4:
        st.subheader("Set Alerts")
        if markets:
            c1, c2, c3 = st.columns(3)
            a_asset = c1.selectbox("Asset", [m["name"] for m in markets])
            a_cond = c2.selectbox("Condition", ["Above", "Below"])
            a_price = c3.number_input("Target Price (₹)", min_value=0.0, value=float(next(x for x in markets if x["name"] == a_asset)["price"]))
            if st.button("⏰ Active Alert"):
                alert_df = pd.DataFrame([[a_asset, a_cond, a_price]], columns=["Asset", "Condition", "TargetPrice"])
                if not os.path.exists(ALERT_FILE): alert_df.to_csv(ALERT_FILE, index=False)
                else: alert_df.to_csv(ALERT_FILE, mode='a', header=False, index=False)
                st.success("Alert Active!")

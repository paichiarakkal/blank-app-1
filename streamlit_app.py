import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import yfinance as yf
import urllib.parse
import os
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SETTINGS ---
WA_PHONE = "971551347989"
WA_API_KEY = "7463030"

USERS = {"faisal": "faisal147", "shabana": "shabana123", "admin": "paichi786"}
LOG_FILE = "paichi_signals_log.csv"
ALERT_FILE = "paichi_price_alerts.csv"

st.set_page_config(page_title="PAICHI GOLD TRADING v9.0", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh_v9")

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
    new_data = pd.DataFrame([[now, asset_name, signal, f"₹{price:,.2f}", f"{rsi:.2f}", f"₹{t1:,.2f}", f"₹{t2:,.2f}", f"₹{sl:,.2f}"]], 
                            columns=['Time', 'Asset', 'Signal', 'Price', 'RSI', 'Target 1', 'Target 2', 'StopLoss'])
    if not os.path.exists(LOG_FILE): new_data.to_csv(LOG_FILE, index=False)
    else: new_data.to_csv(LOG_FILE, mode='a', header=False, index=False)

# --- 3. 🎨 PREMIUM DESIGN ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #1f0326, #32014c, #0b0114); color: #fff; }
    [data-testid="stSidebar"] { background: rgba(0,0,0,0.9) !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 10px; font-weight: bold; width: 100%; height: 45px; font-size: 16px; }
    .terminal-banner { background: rgba(255, 255, 255, 0.04); padding: 20px; border-radius: 15px; border-left: 10px solid #FFD700; margin-bottom: 25px; text-align: center; }
    .purple-box { background: rgba(255, 255, 255, 0.04); padding: 20px; border-radius: 20px; border: 2px solid rgba(255, 215, 0, 0.2); text-align: center; margin-bottom: 15px; }
    h1, h2, h3, p, label { color: white !important; font-weight: bold !important; }
    div[data-testid="stSlider"] label { color: #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""

def send_callmebot_whatsapp(message_text):
    url = f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={urllib.parse.quote(message_text)}&apikey={WA_API_KEY}"
    try: return requests.get(url, timeout=10).status_code == 200
    except: return False

# --- 4. 📈 ADVANCED TRIPLE ADVISOR ENGINE ---
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
            
            # Pivot Point, Support, Resistance Levels
            pivot = (h + l + c) / 3
            r1 = (2 * pivot) - l
            r2 = pivot + (h - l)
            s1 = (2 * pivot) - h
            s2 = pivot - (h - l)
            
            # Indicators: RSI & EMA 20
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001)).iloc[-1]))
            ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
            
            if name == "Crude Fut":
                last_p, pivot, r1, r2, s1, s2, ema20 = [x * 83.5 * 1.15 for x in [last_p, pivot, r1, r2, s1, s2, ema20]]

            # Strategy Logic (Pivot + RSI + EMA)
            if last_p > pivot and rsi > buy_level and last_p > ema20:
                signal, color, icon, t1, t2, sl = "🚀 BUY", "#00FF00", "🟢", r1, r2, s1
            elif last_p < pivot and rsi < sell_level and last_p < ema20:
                signal, color, icon, t1, t2, sl = "📉 SELL", "#FF3131", "🔴", s1, s2, r1
            else:
                signal, color, icon, t1, t2, sl = "⚖️ WAIT", "#FFFF00", "🟡", 0, 0, 0
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon, "t1": t1, "t2": t2, "sl": sl})
        return results
    except: return None

# --- 5. MAIN APP INTERFACE ---
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
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v9.0</span><br>
        <span style="font-size:14px; color:#E0B0FF;">Welcome, {curr_user.capitalize()} | 🛠️ Multi-Indicator & Logs Active</span>
    </div>''', unsafe_allow_html=True)

    # Sidebar parameters
    st.sidebar.markdown("## 🛠️ Strategy Tweak")
    selected_interval = st.sidebar.selectbox("Interval:", options=["5m", "15m", "30m", "1h"], index=0)
    rsi_period = st.sidebar.slider("RSI Period:", 5, 30, 14)
    buy_level = st.sidebar.slider("RSI BUY Level:", 50, 80, 55)
    sell_level = st.sidebar.slider("RSI SELL Level:", 20, 50, 45)
    
    st.sidebar.write("---")
    if st.sidebar.button("Logout"):
        st.session_state.auth = False
        st.rerun()

    # Engine calculation
    markets = get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval)

    # --- 🤖 AUTOMATIC ALERTS & LOG SYSTEM ---
    if markets:
        for m in markets:
            paya_signal = get_stored_signal(m["name"])
            if paya_signal != m["signal"]:
                save_signal_to_file(m["name"], m["signal"])
                if m["signal"] != "⚖️ WAIT":
                    log_signal_to_csv(m["name"], m["signal"], m["price"], m["rsi"], m["t1"], m["t2"], m["sl"])
                    now_time = datetime.now().strftime('%Y-%m-%d %H:%M')
                    msg = (
                        f"{m['icon']} *PAICHI AUTO SIGNAL* {m['icon']}\n\n"
                        f"📦 *Asset:* {m['name']}\n🚦 *Signal:* {m['signal']}\n"
                        f"💰 *Price:* ₹{m['price']:,.2f}\n📊 *RSI:* {m['rsi']:.1f}\n"
                        f"🎯 *Target 1:* ₹{m['t1']:,.2f}\n🎯 *Target 2:* ₹{m['t2']:,.2f}\n"
                        f"🛑 *StopLoss:* ₹{m['sl']:,.2f}\n⏰ *Time:* {now_time}"
                    )
                    send_callmebot_whatsapp(msg)

    # --- 🔔 CUSTOM PRICE ALERTS CHECKER ---
    if markets and os.path.exists(ALERT_FILE):
        try:
            alerts_df = pd.read_csv(ALERT_FILE)
            active_alerts = []
            for idx, row in alerts_df.iterrows():
                m_data = next((x for x in markets if x["name"] == row["Asset"]), None)
                if m_data:
                    triggered = False
                    if row["Condition"] == "Above" and m_data["price"] >= row["TargetPrice"]: triggered = True
                    elif row["Condition"] == "Below" and m_data["price"] <= row["TargetPrice"]: triggered = True
                    
                    if triggered:
                        alert_msg = f"🔔 *PRICE ALERT TRIGGERED!* 🔔\n\nAsset: {row['Asset']}\nPrice reached {row['Condition']} ₹{row['TargetPrice']:,.2f}\nCurrent Price: ₹{m_data['price']:,.2f}"
                        send_callmebot_whatsapp(alert_msg)
                    else: active_alerts.append(row.values.tolist())
            if active_alerts: pd.DataFrame(active_alerts, columns=alerts_df.columns).to_csv(ALERT_FILE, index=False)
            else: os.remove(ALERT_FILE)
        except: pass

    # --- TABS FOR DISPLAY ---
    tab1, tab2, tab3 = st.tabs(["📈 LIVE MONITOR", "📋 SIGNAL LOGS", "🔔 PRICE ALERTS"])

    with tab1:
        st.info(f"⚙️ Settings ➡️ Interval: {selected_interval} | RSI: {rsi_period} | BUY: >{buy_level} | SELL: <{sell_level}")
        if markets:
            cols = st.columns(3)
            for i, m in enumerate(markets):
                with cols[i]:
                    st.markdown(f"""<div class="purple-box" style="border-color: {m['color']} !important;">
                        <h2 style="color:#E0B0FF !important; margin-bottom:0;">{m["name"]}</h2>
                        <h1 style="color:{m["color"]} !important; font-size:42px; margin:10px 0;">{m["signal"]}</h1>
                        <h2 style="color:#FFD700 !important; font-size:30px; margin-bottom:5px;">₹{m["price"]:,.2f}</h2>
                        <p style="color:#aaa; font-size:13px; margin-bottom:10px;">RSI: {m["rsi"]:.1f}</p>
                        {"<div style='text-align:left; background:rgba(0,0,0,0.4); padding:10px; border-radius:10px; font-size:13px;'>"
                          f"🎯 <b>T1:</b> ₹{m['t1']:,.2f}<br>"
                          f"🎯 <b>T2:</b> ₹{m['t2']:,.2f}<br>"
                          f"🛑 <b>SL:</b> ₹{m['sl']:,.2f}</div>" if m["signal"] != "⚖️ WAIT" else ""}
                    </div>""", unsafe_allow_html=True)
        else: st.warning("Loading Market Terminal...")

    with tab2:
        st.subheader("Automated Trade History Log")
        if os.path.exists(LOG_FILE):
            log_df = pd.read_csv(LOG_FILE)
            st.dataframe(log_df.iloc[::-1], use_container_width=True)
            if st.button("🗑️ Clear Logs"):
                os.remove(LOG_FILE)
                st.rerun()
        else: st.write("No signals recorded yet.")

    with tab3:
        st.subheader("Set Custom Price Alerts")
        if markets:
            c1, c2, c3 = st.columns(3)
            a_asset = c1.selectbox("Asset", [m["name"] for m in markets])
            a_cond = c2.selectbox("Condition", ["Above", "Below"])
            a_price = c3.number_input("Trigger Price (₹)", min_value=0.0, value=float(next(x for x in markets if x["name"] == a_asset)["price"]))
            
            if st.button("⏰ Set Alert"):
                alert_df = pd.DataFrame([[a_asset, a_cond, a_price]], columns=["Asset", "Condition", "TargetPrice"])
                if not os.path.exists(ALERT_FILE): alert_df.to_csv(ALERT_FILE, index=False)
                else: alert_df.to_csv(ALERT_FILE, mode='a', header=False, index=False)
                st.success("Alert Set Successfully! ✅")
                st.rerun()
        
        st.write("---")
        st.subheader("Active Price Alerts")
        if os.path.exists(ALERT_FILE):
            st.dataframe(pd.read_csv(ALERT_FILE), use_container_width=True)

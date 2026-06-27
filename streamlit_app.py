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

st.set_page_config(page_title="PAICHI GOLD TRADING v8.0", layout="wide")
# 60 സെക്കൻഡിൽ പേജ് ഓട്ടോ റിഫ്രഷ് ചെയ്യും
st_autorefresh(interval=60000, key="auto_refresh_v8")

# --- 2. 💾 PERMANENT FILE MEMORY FUNCTION ---
def get_stored_signal(asset_name):
    filename = f"sig_{asset_name.replace(' ', '_')}.txt"
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return f.read().strip()
    return ""

def save_signal_to_file(asset_name, signal_text):
    filename = f"sig_{asset_name.replace(' ', '_')}.txt"
    with open(filename, "w") as f:
        f.write(signal_text)

# --- 3. 🎨 PREMIUM DESIGN ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #2D0844, #4B0082, #1A0521); color: #fff; }
    [data-testid="stSidebar"] { background: rgba(0,0,0,0.85) !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 10px; font-weight: bold; width: 100%; height: 50px; font-size: 18px; }
    .terminal-banner { background: rgba(255, 255, 255, 0.05); padding: 25px; border-radius: 15px; border-left: 10px solid #FFD700; margin-bottom: 25px; text-align: center; }
    .purple-box { background: rgba(255, 255, 255, 0.05); padding: 25px; border-radius: 25px; border: 2px solid rgba(255, 215, 0, 0.3); text-align: center; margin-bottom: 20px; }
    h1, h2, h3, p, label { color: white !important; font-weight: bold !important; }
    div[data-testid="stSlider"] label { color: #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""

# --- 4. 🚀 CALLMEBOT ENGINE ---
def send_callmebot_whatsapp(message_text):
    url = f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={urllib.parse.quote(message_text)}&apikey={WA_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except:
        return False

# --- 5. 📈 TRIPLE ADVISOR ENGINE (WITH LIVE PARAMETERS) ---
def get_triple_advisor(rsi_period, buy_level, sell_level, selected_interval):
    try:
        symbols = {"Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "Crude Fut": "CL=F"}
        results = []
        
        # ടൈംഫ്രെയിമിന് അനുസരിച്ച് ഹിസ്റ്ററി പിരീഡ് സെറ്റ് ചെയ്യുന്നു
        history_period = "5d" if selected_interval in ["5m", "15m"] else "1mo"
        
        for name, sym in symbols.items():
            df = yf.Ticker(sym).history(period=history_period, interval=selected_interval)
            if df.empty: continue
            last_p = df['Close'].iloc[-1]
            h, l, c = df['High'].iloc[-2], df['Low'].iloc[-2], df['Close'].iloc[-2]
            pivot = (h + l + c) / 3
            
            # RSI കണക്കുകൂട്ടൽ
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
            
            # സീറോ എറർ വരാതിരിക്കാൻ ഒരു ചെറിയ വാല്യൂ വെച്ച് മാറ്റിസ്ഥാപിക്കുന്നു
            loss_fixed = loss.replace(0, 0.00001)
            rsi = 100 - (100 / (1 + (gain / loss_fixed).iloc[-1]))
            
            # ലൈവ് പാരാമീറ്ററുകൾ വെച്ചുള്ള കണ്ടീഷൻ
            if last_p > pivot and rsi > buy_level: signal, color, icon = "🚀 BUY", "#00FF00", "🟢"
            elif last_p < pivot and rsi < sell_level: signal, color, icon = "📉 SELL", "#FF3131", "🔴"
            else: signal, color, icon = "⚖️ WAIT", "#FFFF00", "🟡"
            
            if name == "Crude Fut": 
                last_p = last_p * 83.5 * 1.15
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon})
        return results
    except:
        return None

# --- 6. MAIN APP ---
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
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v8.5</span><br>
        <span style="font-size:14px; color:#E0B0FF;">Welcome, {curr_user.capitalize()} | 🤖 Hard-Drive Auto-Alerts Enabled</span>
    </div>''', unsafe_allow_html=True)

    # --- 🛠️ SIDEBAR: LIVE PARAMETER TWEAK ---
    st.sidebar.markdown("## 🛠️ Strategy Parameters")
    
    # 1. ടൈംഫ്രെയിം സെലക്ഷൻ
    selected_interval = st.sidebar.selectbox(
        "Select Timeframe (Interval):",
        options=["5m", "15m", "30m", "1h"],
        index=0
    )
    
    # 2. RSI പിരീഡ് സ്ലൈഡർ
    rsi_period = st.sidebar.slider("RSI Period (Length):", min_value=5, max_value=30, value=14, step=1)
    
    # 3. BUY/SELL ലെവലുകൾ
    buy_level = st.sidebar.slider("RSI BUY Trigger Level:", min_value=50, max_value=80, value=55, step=1)
    sell_level = st.sidebar.slider("RSI SELL Trigger Level:", min_value=20, max_value=50, value=45, step=1)
    
    st.sidebar.write("---")
    if st.sidebar.button("Logout"): 
        st.session_state.auth = False
        st.rerun()

    # സൈഡ്‌ബാറിലെ പുതിയ വാല്യൂസ് എഞ്ചിനിലേക്ക് പാസ്സ് ചെയ്യുന്നു
    markets = get_triple_advisor(rsi_period, buy_level, sell_level, selected_interval)
    
    # --- 🤖 AUTOMATIC ALERT CHECKER (PERMANENT) ---
    if markets:
        for m in markets:
            asset_name = m["name"]
            current_signal = m["signal"]
            
            paya_signal = get_stored_signal(asset_name)
            
            if paya_signal != current_signal:
                now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                auto_msg = (
                    f"{m['icon']} *AUTOMATIC SIGNAL ALERT* {m['icon']}\n\n"
                    f"📦 *Asset:* {asset_name}\n"
                    f"🚦 *New Signal:* {current_signal}\n"
                    f"💰 *Price:* ₹{m['price']:,.2f}\n"
                    f"📊 *RSI ({rsi_period}):* {m['rsi']:.2f}\n"
                    f"⏱️ *Timeframe:* {selected_interval}\n"
                    f"⏰ *Time:* {now_time}\n\n"
                    f"🤖 _Paichi Engine Auto-Notification_"
                )
                send_callmebot_whatsapp(auto_msg)
                save_signal_to_file(asset_name, current_signal)

    # --- LIVE DISPLAY ---
    st.subheader(f"Live Market Signals ({selected_interval} - Auto-Updates Every 60s)")
    
    # നിലവിലുള്ള സെറ്റിങ്സ് സ്ക്രീനിൽ കാണിക്കാൻ ഒരു ചെറിയ ഇൻഫോ ബോക്സ്
    st.info(f"⚙️ Active Settings ➡️ Interval: {selected_interval} | RSI Length: {rsi_period} | BUY Trigger: >{buy_level} | SELL Trigger: <{sell_level}")
    
    if markets:
        cols = st.columns(3)
        for i, m in enumerate(markets):
            with cols[i]:
                st.markdown(f"""<div class="purple-box" style="border-color: {m['color']} !important;">
                    <h2 style="color:#E0B0FF !important;">{m["name"]}</h2>
                    <h1 style="color:{m["color"]} !important; font-size:48px;">{m["signal"]}</h1>
                    <h1 style="color:#FFD700 !important; font-size:38px;">₹{m["price"]:,.2f}</h1>
                    <span style="color:#aaa; font-size:14px;">RSI ({rsi_period}): {m["rsi"]:.2f}</span>
                </div>""", unsafe_allow_html=True)
    else:
        st.warning("Fetching Market Data...")

    st.write("---")
    st.subheader("Manual Backup Controls")
    if markets:
        selected_market = st.selectbox("Select Asset for Manual Alert", [m["name"] for m in markets])
        market_data = next(item for item in markets if item["name"] == selected_market)
        
        if st.button(f"🚀 Force Send {market_data['name']} Signal"):
            now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            wa_msg = f"{market_data['icon']} *MANUAL SIGNAL* {market_data['icon']}\n\nAsset: {market_data['name']}\nSignal: {market_data['signal']}\nPrice: ₹{market_data['price']:,.2f}\nTime: {now_time}"
            if send_callmebot_whatsapp(wa_msg):
                st.success("Manual Alert Sent! ✅")

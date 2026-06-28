import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import yfinance as yf
import os
import plotly.graph_objects as fgo
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SETTINGS ---
# നിങ്ങളുടെ ഒറിജിനൽ ടോക്കണും ചാറ്റ് ഐഡിയും ഇവിടെ ഫിക്സ് ചെയ്തു ഭായ്!
TELEGRAM_BOT_TOKEN = "8638662433:AAFZVhOjRXSkbu0UmKcOZskjoWuO271Zbc8"
TELEGRAM_CHAT_ID = "6091133068" 

USERS = {"faisal": "faisal147", "shabana": "shabana123", "admin": "paichi786"}
LOG_FILE = "paichi_signals_log.csv"
ALERT_FILE = "paichi_price_alerts.csv"
JOURNAL_FILE = "trade_history_v2.csv"
POSITION_FILE = "paichi_live_positions.csv"

st.set_page_config(page_title="PAICHI GOLD TRADING v13.0", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh_v13_ultimate")

# --- 2. 🤖 TELEGRAM TWO-WAY CONTROL (INBOUND) ---
# ടെലിഗ്രാമിൽ വരുന്ന /status കമാൻഡുകൾ റീഡ് ചെയ്ത് മറുപടി അയക്കുന്ന സിസ്റ്റം
def check_telegram_inbound_commands():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        res = requests.get(url, params={"offset": -1, "timeout": 1}, timeout=5).json()
        if res.get("ok") and res.get("result"):
            last_update = res["result"][-1]
            msg = last_update.get("message", {})
            text = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))
            update_id = last_update.get("update_id")
            
            if chat_id == TELEGRAM_CHAT_ID and st.session_state.get("last_update_id") != update_id:
                st.session_state.last_update_id = update_id
                
                if text == "/status":
                    pos_df = get_live_positions()
                    if pos_df.empty:
                        reply = "💼 *PAICHI STATUS REPORT:*\n\nനിലവിൽ ആക്റ്റീവ് പൊസിഷനുകൾ ഒന്നുമില്ല ഭായ്! മാർക്കറ്റ് നിരീക്ഷിച്ചുകൊണ്ടിരിക്കുന്നു. 🕵️‍♂️"
                    else:
                        reply = "💼 *PAICHI ACTIVE POSITIONS:*\n\n"
                        for _, row in pos_df.iterrows():
                            reply += f"📦 *{row['Asset']}*\n🚦 {row['Type']}\n💰 Entry: ₹{row['EntryPrice']:.2f}\n🛑 Current SL: ₹{row['SL']:.2f}\n🎯 T1: ₹{row['T1']:.2f}\n\n"
                    
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", 
                                  json={"chat_id": TELEGRAM_CHAT_ID, "text": reply, "parse_mode": "Markdown"})
    except:
        pass

# --- 3. 💾 FILE MEMORY & INTERFACE HELPERS ---
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

# --- 4. 📈 TRAILING STOP-LOSS & ADVANCED AUTOPILOT ENGINE ---
def manage_autopilot_execution(asset_name, signal, price, sl, t1, t2, qty):
    positions = get_live_positions()
    
    if not positions.empty and asset_name in positions['Asset'].values:
        idx = positions[positions['Asset'] == asset_name].index[0]
        pos = positions.loc[idx]
        closed = False
        pnl = 0.0
        
        if pos['Type'] == '🚀 BUY':
            # Trailing SL: പ്രോഫിറ്റ് മുകളിലേക്ക് പോകുമ്പോൾ സ്റ്റോപ്പ് ലോസും തനിയെ മുകളിലേക്ക് മാറുന്നു (TSL)
            new_sl = price - (pos['EntryPrice'] - pos['SL'])
            if new_sl > pos['SL'] and price > pos['EntryPrice']:
                positions.at[idx, 'SL'] = new_sl
                positions.to_csv(POSITION_FILE, index=False)
            
            if price >= pos['T1']:
                closed, pnl = True, (price - pos['EntryPrice']) * pos['Qty']
                msg_status = f"🎯 *AUTO-PILOT TARGET 1 HIT (BUY)!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price <= positions.at[idx, 'SL']:
                closed, pnl = True, (positions.at[idx, 'SL'] - pos['EntryPrice']) * pos['Qty']
                msg_status = f"🛑 *TRAILING STOP-LOSS HIT (BUY)!* 🛑\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
        
        elif pos['Type'] == '📉 SELL':
            # Trailing SL for Sell
            new_sl = price + (pos['SL'] - pos['EntryPrice'])
            if new_sl < pos['SL'] and price < pos['EntryPrice']:
                positions.at[idx, 'SL'] = new_sl
                positions.to_csv(POSITION_FILE, index=False)
                
            if price <= pos['T1']:
                closed, pnl = True, (pos['EntryPrice'] - price) * pos['Qty']
                msg_status = f"🎯 *AUTO-PILOT TARGET 1 HIT (SELL)!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price >= positions.at[idx, 'SL']:
                closed, pnl = True, (pos['EntryPrice'] - positions.at[idx, 'SL']) * pos['Qty']
                msg_status = f"🛑 *TRAILING STOP-LOSS HIT (SELL)!* 🛑\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
                
        if closed:
            date = datetime.now().strftime("%Y-%m-%d %H:%M")
            df_j = pd.DataFrame([[date, asset_name, f"AUTO-EXIT", pos['EntryPrice'], price, pos['Qty'], pnl, "Auto-TSL"]], 
                                  columns=['Date', 'Item', 'Type', 'Entry', 'Exit', 'Qty', 'P&L', 'Mood'])
            if not os.path.isfile(JOURNAL_FILE): df_j.to_csv(JOURNAL_FILE, index=False)
            else: df_j.to_csv(JOURNAL_FILE, mode='a', header=False, index=False)
            
            positions = positions[positions['Asset'] != asset_name]
            positions.to_csv(POSITION_FILE, index=False)
            send_telegram_with_inline_buttons(msg_status, asset_name)
            return
            
    if signal != "⚖️ WAIT" and (positions.empty or asset_name not in positions['Asset'].values):
        new_pos = pd.DataFrame([[asset_name, signal, price, qty, sl, t1, t2]], columns=positions.columns)
        if positions.empty: new_pos.to_csv(POSITION_FILE, index=False)
        else: new_pos.to_csv(POSITION_FILE, mode='a', header=False, index=False)
        
        order_msg = f"🤖 *AUTO-PILOT ORDER EXECUTED* 🤖\n\n📦 Asset: {asset_name}\n🚦 Order: {signal}\n💰 Entry Price: ₹{price:,.2f}\n🔢 Qty: {qty}\n🛑 Initial SL: ₹{sl:,.2f}\n🎯 T1: ₹{t1:,.2f}"
        send_telegram_with_inline_buttons(order_msg, asset_name)

# --- 5. 📱 TELEGRAM ENGINE WITH BUTTONS ---
def send_telegram_with_inline_buttons(message_text, asset_name):
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📈 View Live Chart", "url": f"https://faisal-trader-bot.t.me"},
                {"text": "✅ Trade Synced", "callback_data": f"done_{asset_name}"}
            ]
        ]
    }
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# --- 6. 📊 MULTI-INDICATOR SCANNERS (RSI + MACD + EMA) ---
def calculate_indicators(df, rsi_period):
    # RSI Calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001)).iloc[-1]))
    
    # EMA 20 & EMA 50
    ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    
    # MACD Calculation
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    macd_val = macd_line.iloc[-1]
    macd_sig = signal_line.iloc[-1]
    
    return rsi, ema20, ema50, macd_val, macd_sig

def get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval):
    try:
        # അന്താരാഷ്ട്ര ഗോൾഡ് (GC=F) ഇതിലേക്ക് പ്രധാനമായി ചേർത്തു ഭായ്!
        symbols = {"Paichi Gold (USD)": "GC=F", "Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "Crude Fut": "CL=F"}
        results = []
        history_period = "5d" if selected_interval in ["5m", "15m"] else "1mo"
        
        for name, sym in symbols.items():
            df = yf.Ticker(sym).history(period=history_period, interval=selected_interval)
            if df.empty: continue
            
            last_p = df['Close'].iloc[-1]
            h, l, c = df['High'].iloc[-2], df['Low'].iloc[-2], df['Close'].iloc[-2]
            
            pivot = (h + l + c) / 3
            r1, r2, s1, s2 = (2*pivot)-l, pivot+(h-l), (2*pivot)-h, pivot-(h-l)
            
            rsi, ema20, ema50, macd_val, macd_sig = calculate_indicators(df, rsi_period)
            
            # കറൻസി കൺവേർഷൻ ഫോർ ക്രൂഡ് ഓയിൽ & ഗോൾഡ്
            if name in ["Crude Fut", "Paichi Gold (USD)"]:
                last_p, pivot, r1, r2, s1, s2, ema20 = [x * 83.5 for x in [last_p, pivot, r1, r2, s1, s2, ema20]]

            # 🛠️ MULTI-INDICATOR STRATEGY CONFIRMATION
            # Buy: Price > EMA20, EMA20 > EMA50, RSI > buy_level, MACD > Signal Line
            if last_p > ema20 and ema20 > ema50 and rsi > buy_level and macd_val > macd_sig:
                signal, color, icon, t1, t2, sl = "🚀 BUY", "#00FF00", "🟢", r1, r2, s1
            # Sell: Price < EMA20, EMA20 < EMA50, RSI < sell_level, MACD < Signal Line
            elif last_p < ema20 and ema20 < ema50 and rsi < sell_level and macd_val < macd_sig:
                signal, color, icon, t1, t2, sl = "📉 SELL", "#FF3131", "🔴", s1, s2, r1
            else:
                signal, color, icon, t1, t2, sl = "⚖️ WAIT", "#FFFF00", "🟡", 0, 0, 0
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon, "t1": t1, "t2": t2, "sl": sl, "df": df})
        return results
    except: return None

# --- 7. 🎨 DESIGN & STYLES ---
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

# --- 8. MAIN INTERFACE CONTROLLER ---
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
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v13.0</span><br>
        <span style="font-size:14px; color:#9bf4ff;">🤖 GOLD & MULTI-INDICATOR ULTIMATE AUTOPILOT ACTIVE</span>
    </div>''', unsafe_allow_html=True)

    # ബാക്ക്ഗ്രൗണ്ടിൽ ടെലിഗ്രാം കമാൻഡുകൾ റൺ ചെയ്യുന്നു
    check_telegram_inbound_commands()

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
        st.subheader("💼 Active Trailing Stop-Loss Positions")
        positions_df = get_live_positions()
        if not positions_df.empty:
            st.dataframe(positions_df, use_container_width=True)
            if st.button("🚨 EMERGENCY SQUARE OFF ALL"):
                if os.path.exists(POSITION_FILE): os.remove(POSITION_FILE)
                st.success("All bot positions closed immediately!")
                st.rerun()
        else: st.info("No active bot trades right now. Multi-indicator scanning in progress...")

        st.write("---")
        if markets:
            cols = st.columns(len(markets))
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
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
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

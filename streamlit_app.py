import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import yfinance as yf
import os
import plotly.graph_objects as fgo
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SETTINGS ---
# Streamlit Secrets-ൽ നിന്ന് സുരക്ഷിതമായി ഡാറ്റ റീഡ് ചെയ്യുന്നു
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# USERS ഡിക്‌ഷ്ണറി secrets-ൽ നിന്ന് എടുക്കുന്നു
USERS = dict(st.secrets["USERS"])

LOG_FILE = "paichi_signals_log.csv"
ALERT_FILE = "paichi_price_alerts.csv"
JOURNAL_FILE = "trade_history_v2.csv"
POSITION_FILE = "paichi_live_positions.csv"

st.set_page_config(page_title="PAICHI GOLD TRADING v13.5", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh_v13_5")

# --- 2. 🤖 TELEGRAM TWO-WAY CONTROL (INBOUND) ---
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
    except Exception:
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

def get_live_positions():
    if os.path.exists(POSITION_FILE): return pd.read_csv(POSITION_FILE)
    return pd.DataFrame(columns=['Asset', 'Type', 'EntryPrice', 'Qty', 'SL', 'T1', 'T2'])

# --- 4. 📈 TRAILING STOP-LOSS & AUTOPILOT ENGINE ---
def manage_autopilot_execution(asset_name, signal, price, sl, t1, t2, qty):
    positions = get_live_positions()
    
    if not positions.empty and asset_name in positions['Asset'].values:
        idx = positions[positions['Asset'] == asset_name].index[0]
        pos = positions.loc[idx]
        closed = False
        pnl = 0.0
        
        if pos['Type'] == '🚀 BUY':
            new_sl = price - (pos['EntryPrice'] - pos['SL'])
            if new_sl > pos['SL'] and price > pos['EntryPrice']:
                positions.at[idx, 'SL'] = new_sl
                positions.to_csv(POSITION_FILE, index=False)
            
            if price >= pos['T1']:
                closed, pnl = True, (price - pos['EntryPrice']) * pos['Qty']
                msg_status = f"🎯 *TARGET 1 HIT (BUY)!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price <= positions.at[idx, 'SL']:
                closed, pnl = True, (positions.at[idx, 'SL'] - pos['EntryPrice']) * pos['Qty']
                msg_status = f"🛑 *TRAILING SL HIT (BUY)!* 🛑\n\nAsset: {asset_name}\nExit: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
        
        elif pos['Type'] == '📉 SELL':
            new_sl = price + (pos['SL'] - pos['EntryPrice'])
            if new_sl < pos['SL'] and price < pos['Price']:
                positions.at[idx, 'SL'] = new_sl
                positions.to_csv(POSITION_FILE, index=False)
                
            if price <= pos['T1']:
                closed, pnl = True, (pos['EntryPrice'] - price) * pos['Qty']
                msg_status = f"🎯 *TARGET 1 HIT (SELL)!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price >= positions.at[idx, 'SL']:
                closed, pnl = True, (pos['EntryPrice'] - positions.at[idx, 'SL']) * pos['Qty']
                msg_status = f"🛑 *TRAILING SL HIT (SELL)!* 🛑\n\nAsset: {asset_name}\nExit: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
                
        if closed:
            date = datetime.now().strftime("%Y-%m-%d %H:%M")
            df_j = pd.DataFrame([[date, asset_name, "AUTO-EXIT", pos['EntryPrice'], price, pos['Qty'], pnl, "Auto-TSL"]], 
                                  columns=['Date', 'Item', 'Type', 'Entry', 'Exit', 'Qty', 'P&L', 'Mood'])
            if not os.path.isfile(JOURNAL_FILE): df_j.to_csv(JOURNAL_FILE, index=False)
            else: df_j.to_csv(JOURNAL_FILE, mode='a', header=False, index=False)
            
            positions = positions[positions['Asset'] != asset_name]
            positions.to_csv(POSITION_FILE, index=False)
            send_telegram_signal(msg_status)
            return
            
    if signal != "⚖️ WAIT" and (positions.empty or asset_name not in positions['Asset'].values):
        new_pos = pd.DataFrame([[asset_name, signal, price, qty, sl, t1, t2]], columns=positions.columns)
        if positions.empty: new_pos.to_csv(POSITION_FILE, index=False)
        else: new_pos.to_csv(POSITION_FILE, mode='a', header=False, index=False)
        
        order_msg = f"🤖 *AUTO-PILOT ORDER EXECUTED* 🤖\n\n📦 Asset: {asset_name}\n🚦 Order: {signal}\n💰 Entry: ₹{price:,.2f}\n🔢 Qty: {qty}\n🛑 Initial SL: ₹{sl:,.2f}\n🎯 T1: ₹{t1:,.2f}"
        send_telegram_signal(order_msg)

def send_telegram_signal(message_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message_text, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception: pass

# --- 5. 📊 MULTI-INDICATOR CONFIRMATION ENGINE ---
def calculate_indicators(df, rsi_period):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rsi_series = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001))))
    
    ema20_series = df['Close'].ewm(span=20, adjust=False).mean()
    ema50_series = df['Close'].ewm(span=50, adjust=False).mean()
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    return rsi_series, ema20_series, ema50_series, macd_line, signal_line

def get_usd_inr_rate():
    try:
        return yf.Ticker("INR=X").history(period="1d")["Close"].iloc[-1]
    except Exception:
        return 83.5  # താൽക്കാലിക നിരക്ക്

def get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval):
    try:
        symbols = {"Paichi Gold (USD)": "GC=F", "Nifty 50": "^NSEI", "Bank Nifty": "^NSEBANK", "Crude Fut": "CL=F"}
        results = []
        history_period = "5d" if selected_interval in ["5m", "15m"] else "1mo"
        usd_rate = get_usd_inr_rate()
        
        for name, sym in symbols.items():
            df = yf.Ticker(sym).history(period=history_period, interval=selected_interval)
            if df.empty: continue
            
            rsi_s, ema20_s, ema50_s, macd_l, sig_l = calculate_indicators(df, rsi_period)
            df['EMA20'] = ema20_s
            df['EMA50'] = ema50_s
            
            last_p = df['Close'].iloc[-1]
            h, l, c = df['High'].iloc[-2], df['Low'].iloc[-2], df['Close'].iloc[-2]
            
            pivot = (h + l + c) / 3
            r1, r2, s1, s2 = (2*pivot)-l, pivot+(h-l), (2*pivot)-h, pivot-(h-l)
            
            rsi, ema20, ema50 = rsi_s.iloc[-1], ema20_s.iloc[-1], ema50_s.iloc[-1]
            macd_val, macd_sig = macd_l.iloc[-1], sig_l.iloc[-1]
            
            if name in ["Crude Fut", "Paichi Gold (USD)"]:
                last_p, pivot, r1, r2, s1, s2, ema20, ema50 = [x * usd_rate for x in [last_p, pivot, r1, r2, s1, s2, ema20, ema50]]
                df['Open'] *= usd_rate; df['High'] *= usd_rate; df['Low'] *= usd_rate; df['Close'] *= usd_rate
                df['EMA20'] *= usd_rate; df['EMA50'] *= usd_rate

            if last_p > ema20 and ema20 > ema50 and rsi > buy_level and macd_val > macd_sig:
                signal, color, icon, t1, t2, sl = "🚀 BUY", "#00FF00", "🟢", r1, r2, s1
            elif last_p < ema20 and ema20 < ema50 and rsi < sell_level and macd_val < macd_sig:
                signal, color, icon, t1, t2, sl = "📉 SELL", "#FF3131", "🔴", s1, s2, r1
            else:
                signal, color, icon, t1, t2, sl = "⚖️ WAIT", "#FFFF00", "🟡", 0, 0, 0
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon, "t1": t1, "t2": t2, "sl": sl, "df": df})
        return results
    except Exception:
        return None

# --- 6.🎨 DESIGN & CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #05000c, #10001e, #020005); color: #fff; }
    [data-testid="stSidebar"] { background: rgba(0,0,0,0.95) !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 10px; font-weight: bold; }
    .terminal-banner { background: rgba(255, 255, 255, 0.03); padding: 15px; border-radius: 15px; border-left: 10px solid #FFD700; text-align: center; }
    .purple-box { background: rgba(255, 255, 255, 0.04); padding: 20px; border-radius: 20px; border: 2px solid rgba(255, 215, 0, 0.15); text-align: center; margin-bottom: 15px; }
    h1, h2, h3, p, label { color: white !important; font-weight: bold !important; }
    </style>
    """, unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False

# --- 7. INTERFACE CONTROLLER ---
if not st.session_state.auth:
    st.markdown('<div style="text-align:center; padding-top:50px;"><h1>🔐 PAICHI BOT SIGN-IN</h1></div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        u = st.text_input("Username").lower()
        p = st.text_input("Password", type="password")
        if st.button("LOGIN"):
            if USERS.get(u) == p: 
                st.session_state.auth = True
                st.rerun()
            else: st.error("Access Denied!")
else:
    st.markdown(f'''<div class="terminal-banner">
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v13.5</span><br>
        <span style="font-size:14px; color:#9bf4ff;">🤖 GOLD & MULTI-INDICATOR ULTIMATE AUTOPILOT ACTIVE</span>
    </div>''', unsafe_allow_html=True)

    check_telegram_inbound_commands()

    st.sidebar.markdown("<h2>🛠️ Ultimate Config</h2>", unsafe_allow_html=True)
    auto_pilot_on = st.sidebar.toggle("🤖 ACTIVATE AUTOPILOT WITH TSL", value=True)
    auto_qty = st.sidebar.number_input("Fixed Lot Size:", min_value=1, value=10)
    
    st.sidebar.write("---")
    selected_interval = st.sidebar.selectbox("Timeframe Interval:", options=["5m", "15m", "30m", "1h"])
    rsi_period = st.sidebar.slider("RSI Period:", 5, 30, 14)
    buy_level = st.sidebar.slider("RSI Entry BUY:", 50, 80, 55)
    sell_level = st.sidebar.slider("RSI Entry SELL:", 20, 50, 45)

    markets = get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval)

    if markets and auto_pilot_on:
        for m in markets:
            manage_autopilot_execution(m["name"], m["signal"], m["price"], m["sl"], m["t1"], m["t2"], auto_qty)
            paya_signal = get_stored_signal(m["name"])
            if paya_signal != m["signal"]:
                save_signal_to_file(m["name"], m["signal"])

    tab1, tab2, tab3 = st.tabs(["🤖 LIVE ENGINE & POSITIONS", "📊 ADVANCED CANDLESTICK CHARTS", "📋 SYSTEM LOGS"])

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
                        <h1 style="color:{m["color"]}; font-size:36px;">{m["signal"]}</h1>
                        <h2 style="color:#FFD700;">₹{m["price"]:,.2f}</h2>
                        <p style="color:#aaa; font-size:12px;">RSI: {m["rsi"]:.1f}</p>
                    </div>""", unsafe_allow_html=True)

    with tab2:
        if markets:
            selected_chart = st.selectbox("View Advanced Chart:", [m["name"] for m in markets])
            m_chart_data = next(x for x in markets if x["name"] == selected_chart)
            chart_df = m_chart_data["df"]
            
            fig = fgo.Figure(data=[fgo.Candlestick(
                x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'], name="Candlestick"
            )])
            fig.add_trace(fgo.Scatter(x=chart_df.index, y=chart_df['EMA20'], mode='lines', name='EMA 20', line=dict(color='#ff9900', width=1.5)))
            fig.add_trace(fgo.Scatter(x=chart_df.index, y=chart_df['EMA50'], mode='lines', name='EMA 50', line=dict(color='#00e6ff', width=1.5)))
            
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=500, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("📓 Option Trade Journal Status")
        if os.path.exists(JOURNAL_FILE):
            st.dataframe(pd.read_csv(JOURNAL_FILE).iloc[::-1], use_container_width=True)
        else:
            st.info("No logs available yet.")

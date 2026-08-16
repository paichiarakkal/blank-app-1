import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import yfinance as yf
import os
import plotly.graph_objects as fgo
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIG & SETTINGS ---
TELEGRAM_BOT_TOKEN = "8894050413:AAHLuvE68UCPKOdi7mFbfwY6YP4W8711qes"
TELEGRAM_CHAT_ID = "6091133068" 

USERS = {"faisal": "faisal147", "shabana": "shabana123", "admin": "paichi786"}
LOG_FILE = "paichi_signals_log.csv"
ALERT_FILE = "paichi_price_alerts.csv"
JOURNAL_FILE = "trade_history_v2.csv"
POSITION_FILE = "paichi_live_positions.csv"

st.set_page_config(page_title="PAICHI GOLD TRADING v13.0", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh_v13")

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

def get_live_positions():
    if os.path.exists(POSITION_FILE): return pd.read_csv(POSITION_FILE)
    return pd.DataFrame(columns=['Asset', 'Type', 'EntryPrice', 'Qty', 'SL', 'T1', 'T2'])

def send_telegram_signal(message_text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message_text, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# --- 4. 📓 IMPROVED TRADE JOURNAL ENGINE ---
def log_trade_to_journal(asset_name, trade_type, entry_price, exit_price, qty, pnl, exit_reason="Auto-Exit"):
    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    invested_amount = entry_price * qty
    roi_percent = (pnl / invested_amount * 100) if invested_amount > 0 else 0.0
    status = "WIN 🎯" if pnl > 0 else ("LOSS 🛑" if pnl < 0 else "BREAKEVEN ⚖️")
    
    journal_data = {
        'Timestamp': [date_now],
        'Asset': [asset_name],
        'Type': [trade_type],
        'Entry Price': [round(entry_price, 2)],
        'Exit Price': [round(exit_price, 2)],
        'Quantity': [qty],
        'P&L (₹)': [round(pnl, 2)],
        'ROI (%)': [f"{roi_percent:.2f}%"],
        'Status': [status],
        'Exit Reason': [exit_reason]
    }
    
    df_new = pd.DataFrame(journal_data)
    
    if not os.path.isfile(JOURNAL_FILE):
        df_new.to_csv(JOURNAL_FILE, index=False)
    else:
        df_new.to_csv(JOURNAL_FILE, mode='a', header=False, index=False)

# --- 5. 📈 TRAILING STOP-LOSS & AUTOPILOT ENGINE ---
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
            if new_sl < pos['SL'] and price < pos['EntryPrice']:
                positions.at[idx, 'SL'] = new_sl
                positions.to_csv(POSITION_FILE, index=False)
                
            if price <= pos['T1']:
                closed, pnl = True, (pos['EntryPrice'] - price) * pos['Qty']
                msg_status = f"🎯 *TARGET 1 HIT (SELL)!* 🎯\n\nAsset: {asset_name}\nExit Price: ₹{price:,.2f}\nP&L: +₹{pnl:,.2f}"
            elif price >= positions.at[idx, 'SL']:
                closed, pnl = True, (pos['EntryPrice'] - positions.at[idx, 'SL']) * pos['Qty']
                msg_status = f"🛑 *TRAILING SL HIT (SELL)!* 🛑\n\nAsset: {asset_name}\nExit: ₹{price:,.2f}\nP&L: ₹{pnl:,.2f}"
                
        if closed:
            log_trade_to_journal(
                asset_name=asset_name, 
                trade_type=pos['Type'], 
                entry_price=pos['EntryPrice'], 
                exit_price=price, 
                qty=pos['Qty'], 
                pnl=pnl, 
                exit_reason="Auto-TSL/Target"
            )
            
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

# --- 6. 📊 MULTI-INDICATOR CONFIRMATION ENGINE ---
def calculate_indicators(df, rsi_period):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.00001)).iloc[-1]))
    
    ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    
    macd_val = macd_line.iloc[-1]
    macd_sig = signal_line.iloc[-1]
    
    return rsi, ema20, ema50, macd_val, macd_sig

def get_advanced_advisor(rsi_period, buy_level, sell_level, selected_interval):
    try:
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
            
            if name in ["Crude Fut", "Paichi Gold (USD)"]:
                last_p, pivot, r1, r2, s1, s2, ema20 = [x * 83.5 for x in [last_p, pivot, r1, r2, s1, s2, ema20]]

            if last_p > ema20 and ema20 > ema50 and rsi > buy_level and macd_val > macd_sig:
                signal, color, icon, t1, t2, sl = "🚀 BUY", "#00FF00", "🟢", r1, r2, s1
            elif last_p < ema20 and ema20 < ema50 and rsi < sell_level and macd_val < macd_sig:
                signal, color, icon, t1, t2, sl = "📉 SELL", "#FF3131", "🔴", s1, s2, r1
            else:
                signal, color, icon, t1, t2, sl = "⚖️ WAIT", "#FFFF00", "🟡", 0, 0, 0
                
            results.append({"name": name, "price": last_p, "signal": signal, "rsi": rsi, "color": color, "icon": icon, "t1": t1, "t2": t2, "sl": sl, "df": df})
        return results
    except: return None

# --- 7. 🎨 DESIGN & CUSTOM CSS ---
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

# --- 8. INTERFACE CONTROLLER ---
if not st.session_state.auth:
    st.markdown('<div style="text-align:center; padding-top:50px;"><h1>🔐 PAICHI BOT v13.0 SIGN-IN</h1></div>', unsafe_allow_html=True)
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
        <span style="font-size:24px; color: #FFD700; font-weight:bold;">🚀 PAICHI AUTOMATIC TRADING TERMINAL v13.0</span><br>
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

    tab1, tab2, tab3 = st.tabs(["🤖 LIVE ENGINE & POSITIONS", "📊 ADVANCED CANDLESTICK CHARTS", "📋 SYSTEM LOGS & JOURNAL"])

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
            
            fig = fgo.Figure(data=[fgo.Candlestick(x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'])])
            fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=450, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("📓 Advanced Trade Journal & Performance Analytics")
        
        with st.expander("➕ Add Manual Trade to Journal"):
            with st.form("manual_trade_form"):
                col_a, col_b, col_c = st.columns(3)
                m_asset = col_a.selectbox("Asset", ["Paichi Gold (USD)", "Nifty 50", "Bank Nifty", "Crude Fut"])
                m_type = col_b.selectbox("Type", ["🚀 BUY", "📉 SELL"])
                m_qty = col_c.number_input("Qty", min_value=1, value=10)
                
                col_d, col_e, col_f = st.columns(3)
                m_entry = col_d.number_input("Entry Price", value=0.0)
                m_exit = col_e.number_input("Exit Price", value=0.0)
                m_reason = col_f.text_input("Reason / Note", value="Manual Trade")
                
                if st.form_submit_button("Save Trade Log"):
                    m_pnl = (m_exit - m_entry) * m_qty if m_type == "🚀 BUY" else (m_entry - m_exit) * m_qty
                    log_trade_to_journal(m_asset, m_type, m_entry, m_exit, m_qty, m_pnl, m_reason)
                    st.success("Manual trade successfully logged!")
                    st.rerun()

        st.write("---")
        
        if os.path.exists(JOURNAL_FILE):
            j_df = pd.read_csv(JOURNAL_FILE)
            
            if not j_df.empty:
                total_pnl = j_df['P&L (₹)'].sum()
                total_trades = len(j_df)
                win_trades = len(j_df[j_df['P&L (₹)'] > 0])
                win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Overall Realized P&L", f"₹{total_pnl:,.2f}")
                m2.metric("Total Executed Trades", total_trades)
                m3.metric("Win Rate", f"{win_rate:.1f}%")
                
                st.write("### 📜 Trade History Log")
                st.dataframe(j_df.iloc[::-1], use_container_width=True)
            else:
                st.info("Journal is currently empty.")
        else:
            st.info("No journal logs found.")

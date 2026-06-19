import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import random
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF
import io
import urllib.parse
import threading
import re
from streamlit_calendar import calendar

# --- 1. CONFIG & SETTINGS ---
CSV_URL = "https://docs.google.com/spreadsheets/d/1Ocd6zjmBuQOtOcWBAJZUxhRJjqxRfRgKCvBQTIrJTIY/export?format=csv"
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbx32NCrmb5UhcyEIFVhoO3mZzTjYnKuLm_MPjaNiJztGkj-fiOvlSTsXcZ_BCUKRxKWAg/exec"

# WhatsApp API Config (CallMeBot)
WA_PHONE = "971551347989"
WA_API_KEY = "7463030"

USERS = {"faisal": "faisal147", "shabana": "shabana123", "admin": "paichi786"}

st.set_page_config(page_title="PAICHI TRADING PRO v8.8", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh")

# --- 2. 🎨 PREMIUM DARK DESIGN (61170.jpg മാതൃകയിൽ) ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #0F2027, #203A43, #2C5364); color: #fff; }
    [data-testid="stSidebar"] { background: rgba(0,0,0,0.85) !important; }
    .stButton>button { background-color: #00FFCC; color: #000; border-radius: 10px; font-weight: bold; width: 100%; }
    .balance-banner { background: rgba(255, 255, 255, 0.05); padding: 25px; border-radius: 15px; border-left: 10px solid #00FFCC; margin-bottom: 25px; text-align: center; }
    .purple-box { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 25px; border: 2px solid rgba(0, 255, 204, 0.3); text-align: center; margin-bottom: 20px; }
    h1, h2, h3, p, label { color: white !important; font-weight: bold !important; }
    .stDataFrame { background: white; border-radius: 10px; color: black; }
    
    /* 61170.jpg-ൽ ഉള്ളതുപോലെയുള്ള ഡാർക്ക് കലണ്ടർ ഡിസൈൻ */
    .fc { background: #13112c !important; border-radius: 10px; padding: 15px; border: 1px solid #ffffff30; }
    .fc td, .fc th { border: 1px solid #ffffff40 !important; }
    .fc-col-header-cell { background: #1f1a40 !important; color: #fff !important; }
    .fc-daygrid-day-number { color: #fff !important; font-weight: bold; padding: 5px !important; }
    .fc-daygrid-day { min-height: 95px !important; background: #0c0a1f !important; }
    .fc-day-today { background: #25204e !important; }
    
    /* ബട്ടണുകൾ തിങ്ങിനിറയാതിരിക്കാൻ ചെറിയ മാർജിൻ */
    .fc-event { margin-top: 4px !important; margin-bottom: 4px !important; padding: 2px 5px !important; font-size: 13px !important; font-weight: bold !important; border-radius: 4px !important; }
    </style>
    """, unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = ""

# --- 3. 📊 SMART ENGINES ---

def send_whatsapp_auto(message):
    url = f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={urllib.parse.quote(message)}&apikey={WA_API_KEY}"
    try: requests.get(url, timeout=10)
    except: pass

def send_to_sheet_direct(script, debit, credit):
    payload = {"script": script, "debit": debit, "credit": credit}
    try:
        res = requests.post(WEBAPP_URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=15)
        if res.status_code == 200: return True
    except: pass
    return False

def get_totals():
    try:
        df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
        df.columns = df.columns.str.strip()
        t_loss = pd.to_numeric(df.iloc[:, 2], errors='coerce').fillna(0).sum()
        t_profit = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).sum()
        net_amt = t_profit - t_loss
        return float(t_profit), float(t_loss), float(net_amt)
    except: 
        return 0.0, 0.0, 0.0

def create_pdf(df):
    try:
        pdf = FPDF()
        pdf.add_page(); pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="PAICHI TRADING REPORT", ln=True, align='C'); pdf.ln(10)
        cols = df.columns.tolist()
        pdf.set_font("Arial", 'B', 10)
        for col in cols: pdf.cell(38, 10, txt=str(col), border=1)
        pdf.ln(); pdf.set_font("Arial", size=9)
        for _, row in df.iterrows():
            for col in cols:
                val = str(row[col]).encode('ascii', 'ignore').decode('ascii')
                pdf.cell(38, 10, txt=val, border=1)
            pdf.ln()
        return pdf.output(dest='S').encode('latin-1')
    except: return None

def parse_mixed_dates(date_series):
    parsed_dates = []
    for val in date_series:
        val_str = str(val).strip()
        dt = pd.NaT
        try:
            dt = pd.to_datetime(val_str, errors='coerce')
        except: pass
        parsed_dates.append(dt)
    return pd.Series(parsed_dates)

# --- 4. APP MAIN ---
if not st.session_state.auth:
    st.title("🔐 PAICHI TRADING LOGIN")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    if st.button("LOGIN"):
        if USERS.get(u) == p:
            st.session_state.auth, st.session_state.user = True, u
            st.rerun()
        else: st.error("Access Denied!")
else:
    curr_user = st.session_state.user
    t_profit, t_loss, net_p_and_l = get_totals()
    
    st.markdown(f'''<div class="balance-banner">
        <span style="font-size:20px; color: #00FFCC;">Net Trading P&L Balance</span><br>
        <span style="font-size:40px; color:#FFD700; font-weight:bold;">₹{net_p_and_l:,.2f}</span>
    </div>''', unsafe_allow_html=True)

    if curr_user == "shabana": 
        menu_options = ["💰 Add Trade", "📅 Calendar"]
    else: 
        menu_options = ["🏠 Dashboard", "💰 Add Trade", "📅 Calendar", "📊 Report", "🔍 History"]

    page = st.sidebar.radio("Menu", menu_options)
    if st.sidebar.button("Logout"): st.session_state.auth = False; st.rerun()

    # --- PAGES ---
    if page == "🏠 Dashboard":
        st.title("Trading Overview")
        st.markdown(f"""<div class="purple-box">
            <h2 style="color: #00FF00;">Total Profits: ₹{t_profit:,.2f}</h2>
            <h2 style="color: #FF3131;">Total Losses: ₹{t_loss:,.2f}</h2>
        </div>""", unsafe_allow_html=True)

    elif page == "💰 Add Trade":
        st.title("Log New Trade 📈")
        with st.form("trade_form", clear_on_submit=True):
            strike_price = st.text_input("Strike Price / Script Name (e.g., Nifty 24000 CE)")
            am_str = st.text_input("Amount (തുക)")
            ty = st.radio("Result Type", ["Profit (Credit)", "Loss (Debit)"], horizontal=True)
            
            if st.form_submit_button("SAVE TRADE & NOTIFY"):
                try:
                    am = float(am_str.strip().replace(',', ''))
                    if strike_price and am > 0:
                        c_val, d_val = (am, "") if "Profit" in ty else ("", am)
                        success = send_to_sheet_direct(strike_price, d_val, c_val)
                        status_icon = "🟢" if "Profit" in ty else "🔴"
                        msg = f"{status_icon} *Paichi Trade Entry*\n📝 Script: {strike_price}\n💰 P&L: ₹{am} ({ty})\n👤 Trader: {curr_user}"
                        threading.Thread(target=send_whatsapp_auto, args=(msg,)).start()
                        st.success("Trade Logged & WhatsApp Notification Sent! ✅")
                        st.rerun()
                    else: st.error("വിവരങ്ങൾ പൂർണ്ണമായി നൽകുക!")
                except: st.error("തുക കൃത്യമായി നമ്പർ ആയി നൽകുക!")

    elif page == "📅 Calendar":
        st.title("P&L Calendar View 📅")
        try:
            df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
            df.columns = df.columns.str.strip()
            
            df[df.columns[0]] = parse_mixed_dates(df[df.columns[0]])
            df = df.dropna(subset=[df.columns[0]])
            
            df.iloc[:, 2] = pd.to_numeric(df.iloc[:, 2], errors='coerce').fillna(0)
            df.iloc[:, 3] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0)
            
            # ഒരേ ദിവസത്തെ ഡാറ്റ ഒന്നിച്ച് കൂട്ടുന്നു
            daily_summary = df.groupby(df.columns[0]).agg({df.columns[2]: 'sum', df.columns[3]: 'sum'}).reset_index()
            
            calendar_events = []
            for _, row in daily_summary.iterrows():
                date_str = row[df.columns[0]].strftime('%Y-%m-%d')
                total_loss = float(row[df.columns[2]])
                total_profit = float(row[df.columns[3]])
                
                # 💡 ഒരേ ദിവസത്തെ Net P&L കറക്റ്റ് ആയി കണക്കാക്കുന്നു (കുത്തിക്കിടക്കുന്നത് ഒഴിവാക്കാൻ)
                net_day_pnl = total_profit - total_loss
                
                if net_day_pnl > 0:
                    calendar_events.append({
                        "id": f"pnl_{date_str}",
                        "title": f" +₹{net_day_pnl:,.0f}",
                        "start": date_str,
                        "backgroundColor": "#198754",
                        "borderColor": "#198754",
                        "textColor": "white"
                    })
                elif net_day_pnl < 0:
                    calendar_events.append({
                        "id": f"pnl_{date_str}",
                        "title": f" -₹{abs(net_day_pnl):,.0f}",
                        "start": date_str,
                        "backgroundColor": "#dc3545",
                        "borderColor": "#dc3545",
                        "textColor": "white"
                    })
            
            calendar_options = {
                "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"},
                "initialView": "dayGridMonth",
                "selectable": True,
            }
            
            cal_data = calendar(events=calendar_events, options=calendar_options, key="trading_pnl_calendar")
            
            if cal_data.get("eventClick"):
                clicked_date = cal_data["eventClick"]["event"]["start"].split("T")[0]
                clicked_dt = pd.to_datetime(clicked_date)
                
                st.markdown("---")
                # 61170.jpg-ൽ ഉള്ളതുപോലെ ഭംഗിയുള്ള വലിയ ഹെഡിങ് സ്റ്റൈൽ
                st.markdown(f"## 📋 Details for {clicked_dt.strftime('%d %B %Y')}")
                
                day_entries = df[df[df.columns[0]].dt.strftime('%Y-%m-%d') == clicked_date].copy()
                
                if not day_entries.empty:
                    # 61170.jpg-ൽ ഉള്ളതുപോലെ Download ബട്ടൺ ഡിസൈൻ
                    csv_data = day_entries.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download This Day's Data",
                        data=csv_data,
                        file_name=f"Trading_{clicked_date}.csv",
                        mime="text/csv"
                    )
                    
                    day_entries[df.columns[0]] = day_entries[df.columns[0]].dt.strftime('%d/%m/%Y')
                    show_df = day_entries[[df.columns[0], df.columns[1], df.columns[2], df.columns[3]]]
                    show_df.columns = ['Date', 'Script/Strike Price', 'Loss (Debit)', 'Profit (Credit)']
                    st.dataframe(show_df.reset_index(drop=True), use_container_width=True)
                else:
                    st.info("No details found for this day.")
        except Exception as e:
            st.error("കലണ്ടർ ഡാറ്റ ലോഡ് ചെയ്യാൻ കഴിഞ്ഞില്ല!")

    elif page == "📊 Report":
        st.title("Profit Analysis")
        df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
        if len(df.columns) >= 4:
            df.iloc[:, 3] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0)
            if not df[df.iloc[:, 3] > 0].empty:
                fig = px.pie(df[df.iloc[:, 3] > 0], values=df.columns[3], names=df.columns[1], hole=0.4, title="Profit Distribution")
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("No profit data available for chart analysis.")
        else: st.info("No data available.")

    elif page == "🔍 History":
        st.title("Trade Log History")
        df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
        pdf_bytes = create_pdf(df)
        if pdf_bytes: st.download_button("📥 Download PDF Report", pdf_bytes, "Trading_Report.pdf", "application/pdf")
        st.dataframe(df.iloc[::-1], use_container_width=True)

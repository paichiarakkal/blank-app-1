import streamlit as st
import google.generativeai as genai
import pandas as pd
import requests
from datetime import datetime
import random
import plotly.express as px
from streamlit_mic_recorder import speech_to_text
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF
import re
import urllib.parse
import threading
from streamlit_calendar import calendar

# --- CONFIG & SETTINGS ---
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRccfZch3jSdHqrScpqsR_j3FSd70NbELC1j6_nPi-MQXdrhVr3BPcKoI1nub4mQql727pQRPWYk9C-/pub?gid=1583146028&single=true&output=csv"
FORM_API = "https://docs.google.com/forms/d/e/1FAIpQLSfLySolQSiRXV0wELNPhUBlKJh77RnJKWc2-uqAM0TPNG3Q5A/formResponse"
WA_PHONE, WA_API_KEY = "971551347989", "7463030"

# 🔑 USERS & 4-DIGIT PIN SETTINGS
USER_PINS = {
    "faisal": "1470",
    "shabana": "1230",
    "admin": "7860"
}

# 🖼️ PERMANENT BACKGROUND PHOTO FROM GITHUB
BG_IMAGE_URL = "https://raw.githubusercontent.com/paichiarakkal/paichiarakkal/main/profile.jpg"

# --- TWILIO WHATSAPP RECEIVER ---
try:
    from flask import Flask, request
    from twilio.twiml.messaging_response import MessagingResponse
    flask_app = Flask(__name__)

    @flask_app.route("/whatsapp", methods=['POST'])
    def whatsapp_reply():
        incoming = request.values.get('Body', '').lower().strip()
        resp = MessagingResponse()
        msg = resp.message()
        if "balance" in incoming or "ബാലൻസ്" in incoming:
            try:
                df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
                t_in = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0).sum()
                t_out = pd.to_numeric(df.iloc[:, 2], errors='coerce').fillna(0).sum()
                msg.body(f"📊 *Paichi Finance Update*\n\n💰 Total Credit: ₹{t_in:,.2f}\n📉 Total Debit: ₹{t_out:,.2f}\n💵 *Available Balance: ₹{t_in - t_out:,.2f}*")
            except: msg.body("⚠️ ഡാറ്റ എടുക്കാൻ കഴിഞ്ഞില്ല.")
        else: msg.body("🤖 ഹലോ! ബാലൻസ് അറിയാൻ *Balance* എന്ന് അയക്കൂ.")
        return str(resp)

    if not any(t.name == "FlaskThread" for t in threading.enumerate()):
        threading.Thread(target=lambda: flask_app.run(port=5000, host="0.0.0.0", debug=False, use_reloader=False), name="FlaskThread", daemon=True).start()
except: pass

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="PAICHI EXPENSES v3.0", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh")

# INJECT CSS WITH PERMANENT BACKGROUND
st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: linear-gradient(rgba(0, 0, 0, 0.70), rgba(0, 0, 0, 0.70)), url("{BG_IMAGE_URL}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    [data-testid="stHeader"] {{
        background-color: rgba(0,0,0,0);
    }}
    [data-testid="stSidebar"] {{
        background: rgba(0, 0, 0, 0.85) !important;
    }}
    .stButton>button {{
        background-color: #FFD700;
        color: #000;
        border-radius: 10px;
        font-weight: bold;
        width: 100%;
        transition: 0.3s;
    }}
    .stButton>button:hover {{
        background-color: #FFF;
        color: #000;
        box-shadow: 0px 0px 10px #FFD700;
    }}
    .balance-banner {{
        background: rgba(0, 0, 0, 0.65);
        backdrop-filter: blur(10px);
        padding: 25px;
        border-radius: 15px;
        border-left: 10px solid #FFD700;
        margin-bottom: 25px;
        text-align: center;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.5);
    }}
    .purple-box {{
        background: rgba(0, 0, 0, 0.65);
        backdrop-filter: blur(10px);
        padding: 20px;
        border-radius: 25px;
        border: 2px solid rgba(255, 215, 0, 0.3);
        text-align: center;
        margin-bottom: 20px;
    }}
    .category-box {{
        background: rgba(0, 0, 0, 0.65);
        backdrop-filter: blur(10px);
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        border-bottom: 4px solid #FFD700;
        margin-bottom: 15px;
    }}
    .alert-banner {{
        background-color: #ff4d4d;
        color: white;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin-bottom: 20px;
    }}
    .login-card {{
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(10px);
        padding: 25px;
        border-radius: 20px;
        border: 1px solid rgba(255, 215, 0, 0.4);
        box-shadow: 0px 8px 32px 0 rgba(0, 0, 0, 0.7);
        max-width: 450px;
        margin: auto;
        margin-top: 30px;
    }}
    .login-title {{
        text-align: center;
        font-size: 22px;
        font-weight: bold;
        color: #FFD700 !important;
        margin-bottom: 15px;
    }}
    h1, h2, h3, p, label {{
        color: white !important;
        font-weight: bold !important;
    }}
    .stDataFrame {{
        background: white;
        border-radius: 10px;
        color: black;
    }}
    </style>
""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth, st.session_state.user = False, ""

# --- DYNAMIC APP SETTINGS ---
if 'custom_alert_text' not in st.session_state: 
    st.session_state.custom_alert_text = "Shop kuri book"
if 'low_limit' not in st.session_state: 
    st.session_state.low_limit = 6000

# --- HELPER FUNCTIONS ---
def send_whatsapp_auto(msg):
    threading.Thread(target=lambda: requests.get(f"https://api.callmebot.com/whatsapp.php?phone={WA_PHONE}&text={urllib.parse.quote(msg)}&apikey={WA_API_KEY}", timeout=10)).start()

def parse_mixed_dates(date_series):
    parsed = []
    for val in date_series:
        dt = pd.to_datetime(str(val).strip(), errors='coerce')
        if not pd.isna(dt) and dt.year == 2026 and dt.month < 4: dt = datetime(2026, dt.day, dt.month)
        if pd.isna(dt): dt = pd.to_datetime(str(val).strip(), dayfirst=True, errors='coerce')
        parsed.append(dt)
    return pd.Series(parsed)

@st.cache_data(ttl=10)
def load_data():
    try:
        df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
        df.columns = df.columns.str.strip()
        df['Date'] = parse_mixed_dates(df['Date'])
        df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def create_pdf(df):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, txt="PAICHI FINANCE REPORT", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 10)
        widths = {"Date": 30, "Item": 85, "Debit": 35, "Credit": 35}
        for col in widths: pdf.cell(widths[col], 10, txt=col, border=1, align='C')
        pdf.ln()
        pdf.set_font("Arial", size=9)
        for _, row in df.iterrows():
            if pdf.get_y() > 260: pdf.add_page()
            y_start = pdf.get_y()
            pdf.cell(30, 10, txt=str(row['Date']), border=0)
            x_after_date = pdf.get_x()
            pdf.multi_cell(85, 5, txt=str(row['Item']).encode('ascii', 'ignore').decode('ascii'), border=0)
            h = max(10, pdf.get_y() - y_start)
            pdf.set_xy(x_after_date + 85, y_start)
            pdf.cell(35, h, txt=str(row['Debit']), border=0, align='R')
            pdf.cell(35, h, txt=str(row['Credit']), border=0, align='R')
            pdf.set_xy(10, y_start)
            for w in widths.values(): pdf.cell(w, h, txt="", border=1)
            pdf.set_y(y_start + h)
        return bytes(pdf.output())
    except: return None

# --- 🔒 PIN LOGIN SCREEN ---
if not st.session_state.auth:
    st.markdown('<div class="login-card"><div class="login-title">🔐 PAICHI EXPENSES</div>', unsafe_allow_html=True)
    
    u = st.selectbox("👤 Select User", ["faisal", "shabana", "admin"]).lower()
    pin = st.text_input("🔑 Enter 4-Digit PIN", type="password", max_chars=4)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("UNLOCK APP 🔓"):
        if USER_PINS.get(u) == pin:
            st.session_state.auth, st.session_state.user = True, u
            st.rerun()
        else:
            st.error("❌ Incorrect PIN! Try again.")
            
    st.markdown('</div>', unsafe_allow_html=True)
else:
    df = load_data()
    t_in, t_out = (df['Credit'].sum(), df['Debit'].sum()) if not df.empty else (0.0, 0.0)
    bal = t_in - t_out
    
    # ⚙️ SIDEBAR SETTINGS
    if st.session_state.user != "shabana":
        with st.sidebar.expander("⚙️ Alert & Expense Settings"):
            st.session_state.custom_alert_text = st.text_area("Custom Alert Message", value=st.session_state.custom_alert_text)
            st.session_state.low_limit = st.number_input("Low Balance Limit (₹)", value=st.session_state.low_limit)
    
    # ⚠️ ALERT BANNER
    if bal < st.session_state.low_limit:
        st.markdown(f'<div class="alert-banner">⚠️ ശ്രദ്ധിക്കുക: അക്കൗണ്ട് ബാലൻസ് കുറവാണ് {st.session_state.custom_alert_text} (₹{bal:,.2f})! അത്യാവശ്യ കാര്യങ്ങൾക്കായി ഫണ്ട് സൂക്ഷിക്കുക.</div>', unsafe_allow_html=True)

    st.markdown(f'<div class="balance-banner"><span style="font-size:20px; color:#E0B0FF;">Available Balance</span><br><span style="font-size:40px; color:#FFD700; font-weight:bold;">₹{bal:,.2f}</span></div>', unsafe_allow_html=True)
    
    menu = ["💰 Add Entry", "📅 Calendar", "📊 Report", "🔍 History", "🤝 Debt Tracker"]
    if st.session_state.user != "shabana": menu.insert(0, "🏠 Dashboard")
    page = st.sidebar.radio("Menu", menu)
    if st.sidebar.button("Logout"): st.session_state.auth = False; st.rerun()

    # --- DASHBOARD ---
    if page == "🏠 Dashboard" and not df.empty:
        st.title("Financial Overview")
        st.markdown(f'<div class="purple-box"><h2 style="color:#00FF00;">Total Credit: ₹{t_in:,.2f}</h2><h2 style="color:#FF3131;">Total Debit: ₹{t_out:,.2f}</h2></div>', unsafe_allow_html=True)
        
        st.subheader("🗂️ Categorywise Expense Breakdown")
        
        def extract_cat(x):
            item_text = str(x).lower()
            if any(w in item_text for w in ["food", "ഭക്ഷണം", "ചായ", "ഹോട്ടൽ", "ബിരിയാണി", "mess"]): return "Food"
            elif any(w in item_text for w in ["shop", "കട", "സാധനങ്ങൾ", "സൂപ്പർമാർക്കറ്റ്", "groceries"]): return "Shop"
            elif any(w in item_text for w in ["fish", "മീൻ", "ഇറച്ചി", "ചിക്കൻ", "meat"]): return "Fish"
            elif any(w in item_text for w in ["travel", "യാത്ര", "പെട്രോൾ", "വണ്ടി", "ടാക്സി", "petrol", "diesel"]): return "Travel"
            elif any(w in item_text for w in ["rent", "വാടക", "റൂം"]): return "Rent"
            
            return x.split(']')[1].split(':')[0].strip().capitalize() if ']' in str(x) and ':' in str(x) else (str(x).split(':')[0].strip().capitalize() if ':' in str(x) else "Others")

        df['Cat'] = df['Item'].apply(extract_cat)
        cats = df[~df['Item'].str.contains('total', case=False, na=False)].groupby('Cat')['Debit'].sum().to_dict()
        cols = st.columns(3)
        for idx, (c_name, c_amt) in enumerate(cats.items()):
            if c_amt > 0:
                with cols[idx % 3]: st.markdown(f'<div class="category-box"><span style="font-size:16px; color:#aaa;">Total {c_name}</span><br><span style="font-size:24px; color:#FFF; font-weight:bold;">₹{c_amt:,.2f}</span></div>', unsafe_allow_html=True)

    # --- ADD ENTRY ---
    elif page == "💰 Add Entry":
        st.title("Smart Voice Entry 🎙️")
        v_raw = speech_to_text(language='ml', key='voice_v9')
        v_cat, v_amt, v_desc, v_type = "Others", "", "", "Debit"
        
        if v_raw:
            raw = v_raw.lower().replace('.', '').replace(',', '')
            nums = re.findall(r'\d+', raw)
            v_amt = nums[0] if nums else ""
            v_desc = re.sub(r'\d+', '', raw).strip()
            
            if any(x in raw for x in ["food", "ഭക്ഷണം", "ചായ", "ഹോട്ടൽ", "ബിരിയാണി", "mess"]): v_cat = "Food"
            elif any(x in raw for x in ["shop", "കട", "സാധനങ്ങൾ", "സൂപ്പർമാർക്കറ്റ്", "groceries"]): v_cat = "Shop"
            elif any(x in raw for x in ["fish", "മീൻ", "ഇറച്ചി", "ചിക്കൻ", "meat"]): v_cat = "Fish"
            elif any(x in raw for x in ["travel", "യാത്ര", "പെട്രോൾ", "വണ്ടി", "ടാക്സി", "petrol"]): v_cat = "Travel"
            elif any(x in raw for x in ["rent", "വാടക", "റൂം"]): v_cat = "Rent"
            
            if any(x in raw for x in ["കിട്ടി", "വന്നു", "തന്നു", "ക്രെഡിറ്റ്", "credit"]): v_type = "Credit"

        with st.form("entry_form", clear_on_submit=True):
            it = st.text_input("Description", value=v_desc)
            am_str = st.text_input("Amount", value=str(v_amt))
            cat = st.selectbox("Category", ["Food", "Shop", "Fish", "Travel", "Rent", "Others"], index=["Food", "Shop", "Fish", "Travel", "Rent", "Others"].index(v_cat))
            ty = st.radio("Type", ["Debit", "Credit"], horizontal=True, index=0 if v_type == "Debit" else 1)
            if st.form_submit_button("SAVE & NOTIFY"):
                try:
                    am = float(am_str.strip().replace(',', ''))
                    payload = {"entry.1044099436": datetime.now().strftime("%Y-%m-%d"), "entry.2013476337": f"[{st.session_state.user.capitalize()}] {cat}: {it}", "entry.1460982454": am if ty=="Debit" else 0, "entry.1221658767": 0 if ty=="Debit" else am}
                    threading.Thread(target=lambda: requests.post(FORM_API, data=payload, timeout=10)).start()
                    
                    send_whatsapp_auto(f"✅ *Paichi Entry*\n📝 Item: {it}\n💰 Amt: ₹{am}\n👤 User: {st.session_state.user}")
                    st.success("Saved! ✅"); st.rerun()
                except: st.error("Error! Valid amount required.")

    # --- CALENDAR ---
    elif page == "📅 Calendar" and not df.empty:
        st.title("P&L Calendar View 📅")
        df_cal = df.dropna(subset=['Date'])
        summary = df_cal.groupby(df_cal['Date'].dt.strftime('%Y-%m-%d')).agg({'Debit': 'sum', 'Credit': 'sum'}).reset_index()
        events = []
        for _, row in summary.iterrows():
            if row['Credit'] > 0: events.append({"title": f" +₹{row['Credit']:,.0f}", "start": row['Date'], "backgroundColor": "#198754", "borderColor": "#198754", "textColor": "white"})
            if row['Debit'] > 0: events.append({"title": f" -₹{row['Debit']:,.0f}", "start": row['Date'], "backgroundColor": "#dc3545", "borderColor": "#dc3545", "textColor": "white"})
        
        cal_data = calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "initialView": "dayGridMonth", "selectable": True}, key="pnl_calendar")
        if cal_data.get("eventClick"):
            dt_click = cal_data["eventClick"]["event"]["start"].split("T")[0]
            st.markdown("---"); st.subheader(f"📋 Details for {pd.to_datetime(dt_click).strftime('%d %B %Y')}")
            day_df = df_cal[df_cal['Date'].dt.strftime('%Y-%m-%d') == dt_click].copy()
            if not day_df.empty:
                day_df['Date'] = day_df['Date'].dt.strftime('%d/%m/%Y')
                st.download_button("📥 Download This Day's Data", day_df[['Date', 'Item', 'Debit', 'Credit']].to_csv(index=False).encode('utf-8'), f"Transactions_{dt_click}.csv", "text/csv")
                st.dataframe(day_df[['Date', 'Item', 'Debit', 'Credit']], use_container_width=True)

    # --- REPORT & HISTORY ---
    elif (page == "📊 Report" or page == "🔍 History") and not df.empty:
        df_rep = df[(df['Date'].dt.year == 2026) & (df['Date'].dt.month >= 4)].copy()
        df_rep['Month'] = df_rep['Date'].dt.strftime('%B %Y')
        months = df_rep.dropna(subset=['Month']).sort_values(by='Date', ascending=False)['Month'].unique()
        
        if len(months) == 0: st.warning("No data found from April 2026 onwards!")
        else:
            sel_m = st.selectbox("Select Month", months, key=f"{page}_select")
            m_df = df_rep[df_rep['Month'] == sel_m].copy()
            
            search_query = st.text_input("🔍 Search items (e.g. Fish, Petrol, Travel)...", "").strip().lower()
            filter_type = st.selectbox("Filter Type", ["All", "Debit Only", "Credit Only"])
            
            if search_query:
                m_df = m_df[m_df['Item'].str.lower().str.contains(search_query, na=False)]
            if filter_type == "Debit Only":
                m_df = m_df[m_df['Debit'] > 0]
            elif filter_type == "Credit Only":
                m_df = m_df[m_df['Credit'] > 0]

            m_deb, m_crd = m_df['Debit'].sum(), m_df['Credit'].sum()
            
            if page == "📊 Report":
                st.title("Monthly Expense Analysis")
                c1, c2, c3 = st.columns(3)
                c1.markdown(f'<div class="purple-box"><h3 style="color:#00FF00;">Total Credit</h3><h1 style="color:#00FF00;">₹{m_crd:,.2f}</h1></div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="purple-box"><h3 style="color:#FF3131;">Total Expense</h3><h1 style="color:#FF3131;">₹{m_deb:,.2f}</h1></div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="purple-box"><h3 style="color:#FFD700;">Net Savings</h3><h1 style="color:#FFD700;">₹{m_crd - m_deb:,.2f}</h1></div>', unsafe_allow_html=True)
                if m_deb > 0:
                    m_df['Cat'] = m_df['Item'].apply(lambda x: x.split(':')[0] if ':' in str(x) else 'Others')
                    st.plotly_chart(px.pie(m_df[m_df['Debit'] > 0], values='Debit', names='Cat', hole=0.4, title=f"{sel_m} Expense Split").update_traces(textposition='inside', textinfo='percent+label'), use_container_width=True)

            clean_df = m_df.drop(columns=['Month'], errors='ignore')
            pdf_df = clean_df.copy()
            pdf_df['Date'] = pdf_df['Date'].dt.strftime('%d/%m/%Y')
            csv_bytes = clean_df.to_csv(index=False).encode('utf-8')
            
            if page == "📊 Report":
                st.download_button("📥 Download Excel/CSV Report", csv_bytes, f"Report_{sel_m.replace(' ', '_')}.csv", "text/csv")
            else:
                st.title("Transaction History")
                col_p, col_c = st.columns(2)
                pdf_b = create_pdf(pdf_df)
                if pdf_b: col_p.download_button(f"📄 Download PDF", pdf_b, f"History_{sel_m.replace(' ', '_')}.pdf", "application/pdf")
                col_c.download_button("📥 Download CSV (Excel)", csv_bytes, f"History_{sel_m.replace(' ', '_')}.csv", "text/csv")
            
            clean_df['Date'] = clean_df['Date'].dt.strftime('%d/%m/%Y')
            st.dataframe(clean_df.iloc[::-1], use_container_width=True)

    # --- DEBT TRACKER ---
    elif page == "🤝 Debt Tracker":
        st.title("🤝 Debt Tracker & Summary")
        st.info("ഇവിടെ നിങ്ങളുടെ കടം വാങ്ങിയതും നൽകിയതുമായ വിവരങ്ങൾ കാണാം.")
# ============================================
# 🤖 SMART AI AGENT (Using your existing Gemini Model)
# ============================================

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Paichi Smart Agent")

# നിങ്ങളുടെ API Key ഇവിടെ നൽകുക (അല്ലെങ്കിൽ st.secrets-ൽ നിന്ന് എടുക്കാം)
# GEMINI_API_KEY = "YOUR_API_KEY_HERE" 
if "GEMINI_API_KEY" in st.secrets:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    GEMINI_API_KEY = "" # നിങ്ങളുടെ ഫോണിലെ API Key ഇവിടെ കോപ്പി ചെയ്യുക

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- AI ഏജന്റിന് നൽകുന്ന ടൂളുകൾ (Tools) ---
# നിങ്ങളുടെ ആപ്പിൽ ഇപ്പോൾ ഉള്ള ഫംഗ്ഷനുകൾ തന്നെയാണ് ഇവിടെയും ഉപയോഗിക്കുന്നത്
def ai_add_entry(amount: float, category: str, description: str, type: str = "Debit"):
    try:
        payload = {
            "entry.1044099436": datetime.now().strftime("%Y-%m-%d"), 
            "entry.2013476337": f"[{st.session_state.user.capitalize()}] {category}: {description}", 
            "entry.1460982454": amount if type == "Debit" else 0, 
            "entry.1221658767": 0 if type == "Debit" else amount
        }
        requests.post(FORM_API, data=payload, timeout=10)
        send_whatsapp_auto(f"✅ *Auto Entry Added*\n📝 {description}\n💰 ₹{amount}\n🗂️ {category}")
        return "Success"
    except:
        return "Error"

def ai_send_whatsapp(message: str):
    try:
        send_whatsapp_auto(message)
        return "Success"
    except:
        return "Error"

# Gemini-ക്ക് ഈ ടൂളുകൾ മനസ്സിലാകുന്ന രീതിയിൽ (JSON Format) നിർവചിക്കുന്നു
from google.generativeai.types import FunctionDeclaration, Tool

tools = [
    Tool(
        function_declarations=[
            FunctionDeclaration(
                name="ai_add_entry",
                description="Add a new expense or income to the database.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "amount": {"type": "NUMBER", "description": "Amount spent or received."},
                        "category": {"type": "STRING", "description": "Food, Shop, Travel, etc."},
                        "description": {"type": "STRING", "description": "Details like 'Tea' or 'Petrol'."},
                        "type": {"type": "STRING", "description": "Debit or Credit."}
                    },
                    "required": ["amount", "category", "description"]
                }
            ),
            FunctionDeclaration(
                name="ai_send_whatsapp",
                description="Send a WhatsApp message to the user.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "message": {"type": "STRING", "description": "Message content."}
                    },
                    "required": ["message"]
                }
            )
        ]
    )
]

# നിങ്ങളുടെ ഫോണിലുള്ള മോഡൽ ലോഡ് ചെയ്യുന്നു
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # 'gemini-1.5-flash' ആണ് നിങ്ങളുടെ ഫോണിൽ ഉള്ളത്
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools=tools,
        system_instruction="നീയാണ് PAICHI EXPENSES എന്ന ആപ്പിന്റെ AI മാനേജർ. യൂസർ ചെലവ് ചേർക്കാൻ പറഞ്ഞാൽ 'ai_add_entry' ടൂൾ ഉപയോഗിക്കണം. വാട്സാപ്പിൽ മെസ്സേജ് അയക്കാൻ പറഞ്ഞാൽ 'ai_send_whatsapp' ടൂൾ ഉപയോഗിക്കണം."
    )
else:
    st.sidebar.warning("⚠️ API Key നൽകിയിട്ടില്ല.")

# --- ചാറ്റ് ഇന്റർഫേസ് ---
for message in st.session_state.messages:
    with st.sidebar.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.sidebar.chat_input("Ask or give a command..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.sidebar.chat_message("user"):
        st.markdown(prompt)

    if GEMINI_API_KEY:
        with st.sidebar.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = model.generate_content(prompt)
                    
                    # AI ടൂൾ വിളിക്കാൻ തീരുമാനിച്ചോ എന്ന് പരിശോധിക്കുന്നു
                    if response.candidates[0].content.parts[0].function_call:
                        func_call = response.candidates[0].content.parts[0].function_call
                        func_name = func_call.name
                        args = func_call.args
                        
                        st.write(f"⚙️ *Working on: {func_name}*")
                        
                        if func_name == "ai_add_entry":
                            ai_add_entry(args["amount"], args["category"], args["description"], args.get("type", "Debit"))
                            reply = f"ശരി, {args['description']} ന് {args['amount']} ചേർത്തിട്ടുണ്ട്! ✅"
                        elif func_name == "ai_send_whatsapp":
                            ai_send_whatsapp(args["message"])
                            reply = "വാട്സാപ്പിൽ മെസ്സേജ് അയച്ചു! 📱"
                        else:
                            reply = "എനിക്ക് അത് ചെയ്യാൻ സാധിക്കില്ല."
                            
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    
                    else:
                        # ടൂൾ വേണ്ടെങ്കിൽ സാധാരണ മറുപടി
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        
                except Exception as e:
                    st.error(f"Error: {e}")
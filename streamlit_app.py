import streamlit as st
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
import google.generativeai as genai  # AI ചാറ്റിന് വേണ്ടി

# --- CONFIG & SETTINGS ---
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRccfZch3jSdHqrScpqsR_j3FSd70NbELC1j6_nPi-MQXdrhVr3BPcKoI1nub4mQql727pQRPWYk9C-/pub?gid=1583146028&single=true&output=csv"
FORM_API = "https://docs.google.com/forms/d/e/1FAIpQLSfLySolQSiRXV0wELNPhUBlKJh77RnJKWc2-uqAM0TPNG3Q5A/formResponse"
WA_PHONE, WA_API_KEY = "971551347989", "7463030"

USER_PINS = {
    "faisal": "1470",
    "shabana": "1230",
    "admin": "7860"
}

BG_IMAGE_URL = "https://raw.githubusercontent.com/paichiarakkal/paichiarakkal/main/profile.jpg"

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="PAICHI EXPENSES", layout="wide")
st_autorefresh(interval=60000, key="auto_refresh")

st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: linear-gradient(rgba(0, 0, 0, 0.70), rgba(0, 0, 0, 0.70)), url("{BG_IMAGE_URL}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    [data-testid="stHeader"] {{ background-color: rgba(0,0,0,0); }}
    [data-testid="stSidebar"] {{ background: rgba(0, 0, 0, 0.85) !important; }}
    .stButton>button {{
        background-color: #FFD700; color: #000; border-radius: 10px; font-weight: bold; width: 100%;
    }}
    .balance-banner {{
        background: rgba(0, 0, 0, 0.65); backdrop-filter: blur(10px); padding: 25px;
        border-radius: 15px; border-left: 10px solid #FFD700; margin-bottom: 25px;
        text-align: center; box-shadow: 0px 4px 15px rgba(0,0,0,0.5);
    }}
    .purple-box {{
        background: rgba(0, 0, 0, 0.65); backdrop-filter: blur(10px); padding: 20px;
        border-radius: 25px; border: 2px solid rgba(255, 215, 0, 0.3); text-align: center; margin-bottom: 20px;
    }}
    .alert-banner {{
        background-color: #ff4d4d; color: white; padding: 10px; border-radius: 10px;
        text-align: center; font-weight: bold; margin-bottom: 20px;
    }}
    h1, h2, h3, p, label {{ color: white !important; font-weight: bold !important; }}
    .stDataFrame {{ background: white; border-radius: 10px; color: black; }}
    </style>
""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth, st.session_state.user = False, ""
if 'custom_alert_text' not in st.session_state: st.session_state.custom_alert_text = "Shop kuri book"
if 'low_limit' not in st.session_state: st.session_state.low_limit = 6000

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
    st.title("🔐 PAICHI EXPENSES LOGIN")
    u = st.selectbox("👤 Select User", ["faisal", "shabana", "admin"]).lower()
    pin = st.text_input("🔑 Enter 4-Digit PIN", type="password", max_chars=4)
    
    if st.button("UNLOCK APP 🔓"):
        if USER_PINS.get(u) == pin:
            st.session_state.auth, st.session_state.user = True, u
            st.rerun()
        else:
            st.error("❌ Incorrect PIN! Try again.")
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
    
    menu = ["💰 Add Entry", "📅 Calendar", "📊 Report", "🔍 History", "🤝 Debt Tracker", "🤖 AI Advisor"]
    if st.session_state.user != "shabana": menu.insert(0, "🏠 Dashboard")
    page = st.sidebar.radio("Menu", menu)
    if st.sidebar.button("Logout"): st.session_state.auth = False; st.rerun()

    # --- DASHBOARD ---
    if page == "🏠 Dashboard" and not df.empty:
        st.title("Financial Overview")
        st.markdown(f'<div class="purple-box"><h2 style="color:#00FF00;">Total Credit: ₹{t_in:,.2f}</h2><h2 style="color:#FF3131;">Total Debit: ₹{t_out:,.2f}</h2></div>', unsafe_allow_html=True)

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

    # --- REPORT & HISTORY ---
    elif (page == "📊 Report" or page == "🔍 History") and not df.empty:
        df_rep = df[(df['Date'].dt.year == 2026) & (df['Date'].dt.month >= 4)].copy()
        df_rep['Month'] = df_rep['Date'].dt.strftime('%B %Y')
        months = df_rep.dropna(subset=['Month']).sort_values(by='Date', ascending=False)['Month'].unique()
        
        if len(months) == 0: st.warning("No data found from April 2026 onwards!")
        else:
            sel_m = st.selectbox("Select Month", months, key=f"{page}_select")
            m_df = df_rep[df_rep['Month'] == sel_m].copy()
            m_deb, m_crd = m_df['Debit'].sum(), m_df['Credit'].sum()
            
            if page == "📊 Report":
                st.title("Monthly Expense Analysis")
                c1, c2, c3 = st.columns(3)
                c1.markdown(f'<div class="purple-box"><h3 style="color:#00FF00;">Total Credit</h3><h1 style="color:#00FF00;">₹{m_crd:,.2f}</h1></div>', unsafe_allow_html=True)
                c2.markdown(f'<div class="purple-box"><h3 style="color:#FF3131;">Total Expense</h3><h1 style="color:#FF3131;">₹{m_deb:,.2f}</h1></div>', unsafe_allow_html=True)
                c3.markdown(f'<div class="purple-box"><h3 style="color:#FFD700;">Net Savings</h3><h1 style="color:#FFD700;">₹{m_crd - m_deb:,.2f}</h1></div>', unsafe_allow_html=True)
                if m_deb > 0:
                    m_df['Cat'] = m_df['Item'].apply(lambda x: x.split(':')[0] if ':' in str(x) else 'Others')
                    st.plotly_chart(px.pie(m_df[m_df['Debit'] > 0], values='Debit', names='Cat', hole=0.4, title=f"{sel_m} Expense Split"), use_container_width=True)
            
            clean_df = m_df.drop(columns=['Month'], errors='ignore')
            clean_df['Date'] = clean_df['Date'].dt.strftime('%d/%m/%Y')
            st.dataframe(clean_df.iloc[::-1], use_container_width=True)

    # --- DEBT TRACKER ---
    elif page == "🤝 Debt Tracker":
        st.title("🤝 Debt Tracker & Summary")
        st.info("ഇവിടെ നിങ്ങളുടെ കടം വാങ്ങിയതും നൽകിയതുമായവിവരങ്ങൾ കാണാം.")

    # --- AI ADVISOR ---
    elif page == "🤖 AI Advisor":
        st.title("🤖 PAICHI AI Financial Advisor")
        st.markdown("നിങ്ങളുടെ ചെലവുകളെക്കുറിച്ച് AI-നോട് ചോദിക്കാം. (ഉദാ: 'ഈ മാസം ഞാൻ എവിടെയാണ് കൂടുതൽ ചെലവാക്കിയത്?')")
        
        GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
        
        if "ai_messages" not in st.session_state:
            st.session_state.ai_messages = []

        for msg in st.session_state.ai_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask about your expenses..."):
            st.session_state.ai_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            if not df.empty:
                with st.spinner("AI ആലോചിക്കുന്നു..."):
                    try:
                        genai.configure(api_key=GEMINI_API_KEY)
                        model = genai.GenerativeModel('gemini-3.8-flash')
                        
                        df_summary = df[['Date', 'Item', 'Debit', 'Credit']].tail(50).to_string()
                        
                        system_prompt = f"""
                        നീ ഒരു സ്മാർട്ട് ഫിനാൻസ് അസിസ്റ്റന്റ് ആണ്. 
                        Data:
                        {df_summary}
                        
                        Total Income: {t_in}
                        Total Expense: {t_out}
                        Current Balance: {bal}
                        
                        യൂസറുടെ ചോദ്യം: "{prompt}"
                        
                        മുകളിലുള്ള ഡാറ്റ മാത്രം ഉപയോഗിച്ച്, മലയാളത്തിൽ വ്യക്തമായി മറുപടി നൽകുക. 
                        """
                        
                        response = model.generate_content(system_prompt)
                        ai_reply = response.text
                        
                        st.session_state.ai_messages.append({"role": "assistant", "content": ai_reply})
                        with st.chat_message("assistant"):
                            st.markdown(ai_reply)
                            
                    except Exception as e:
                        st.error(f"AI Error: {e}")
            else:
                st.warning("ഡാറ്റ ലഭ്യമല്ല.")

    # --- SIDEBAR AI CHATBOT (Optional - എപ്പോഴും കാണാൻ) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("💬 Quick AI Chat")
    sidebar_prompt = st.sidebar.text_input("Ask AI:", key="sidebar_ai")
    if st.sidebar.button("Send 🚀", key="sidebar_send"):
        if sidebar_prompt and not df.empty:
            with st.sidebar.spinner("AI ചിന്തിക്കുന്നു..."):
                try:
                    genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))
                    model = genai.GenerativeModel('gemini-pro')
                    df_summary = df[['Item', 'Debit', 'Credit']].tail(20).to_string()
                    res = model.generate_content(f"Data: {df_summary}\nBalance: {bal}\nQuestion: {sidebar_prompt}\nAnswer in Malayalam.")
                    st.sidebar.success(res.text)
                except Exception as e:
                    st.sidebar.error("Error: " + str(e))
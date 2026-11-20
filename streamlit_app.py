import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta
import random
import plotly.express as px
from streamlit_mic_recorder import speech_to_text
from streamlit_autorefresh import st_autorefresh
from fpdf import FPDF
import re
import json
import time
import hashlib
import hmac
import base64
import sqlite3
from groq import Groq
from streamlit_calendar import calendar
from twilio.rest import Client

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="PAICHI EXPENSES", layout="wide")

# --- CONFIG & SETTINGS ---
WA_PHONE = st.secrets.get("DEFAULT_WA_PHONE", "")
BG_IMAGE_URL = "https://raw.githubusercontent.com/paichiarakkal/paichiarakkal/main/profile.jpg"
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
SECRET_KEY = st.secrets.get("SESSION_SECRET_KEY", "paichi_expenses_secure_key_2026")
DB_FILE = "paichi_users.db"

# --- TIMEZONE SETUP (GST - Dubai Time) ---
GST = timezone(timedelta(hours=4))

st_autorefresh(interval=60000, key="auto_refresh")

# ============================================
# 🗄️ DATABASE SETUP (SQLite for Multi-User)
# ============================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            sheet_url TEXT DEFAULT '',
            csv_url TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

init_db()

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def db_get_user(username: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username, password_hash, sheet_url, csv_url FROM users WHERE username = ?", (username.strip().lower(),))
    row = c.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "password_hash": row[1], "sheet_url": row[2], "csv_url": row[3]}
    return None

def db_create_user(username: str, password: str, sheet_url: str = "", csv_url: str = ""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO users (username, password_hash, sheet_url, csv_url) VALUES (?, ?, ?, ?)",
        (username.strip().lower(), hash_password(password), sheet_url.strip(), csv_url.strip())
    )
    conn.commit()
    conn.close()

def db_update_password(username: str, new_password: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hash_password(new_password), username.strip().lower()))
    conn.commit()
    conn.close()

def db_update_links(username: str, sheet_url: str, csv_url: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET sheet_url = ?, csv_url = ? WHERE username = ?", (sheet_url.strip(), csv_url.strip(), username.strip().lower()))
    conn.commit()
    conn.close()

# ============================================
# 🔐 SIGNED TOKEN SESSION (Query Params)
# ============================================
def create_session_token(username: str) -> str:
    u = username.strip().lower()
    sig = hmac.new(SECRET_KEY.encode("utf-8"), u.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    raw = f"{u}:{sig}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")

def verify_session_token(token: str):
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        u, sig = decoded.split(":", 1)
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), u.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
        if hmac.compare_digest(sig, expected_sig):
            return u
    except Exception:
        pass
    return None

def restore_session_from_url():
    if not st.session_state.get("auth", False):
        token = st.query_params.get("session", "")
        if token:
            valid_user = verify_session_token(token)
            if valid_user and db_get_user(valid_user):
                st.session_state.auth = True
                st.session_state.user = valid_user

def set_persistent_login(username: str):
    u = username.strip().lower()
    st.session_state.auth = True
    st.session_state.user = u
    st.query_params["session"] = create_session_token(u)

def clear_persistent_login():
    st.session_state.auth = False
    st.session_state.user = ""
    if "session" in st.query_params:
        del st.query_params["session"]

# ============================================
# 🎨 3D GLASSMORPHISM CSS
# ============================================
st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{ 
        background-image: linear-gradient(rgba(10, 10, 25, 0.85), rgba(10, 10, 25, 0.95)), url("{BG_IMAGE_URL}"); 
        background-size: cover; background-attachment: fixed; background-position: center;
    }}
    [data-testid="stSidebar"] {{ 
        background: rgba(20, 20, 35, 0.6) !important; backdrop-filter: blur(15px);
        border-right: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 5px 0 15px rgba(0,0,0,0.5);
    }}
    .stButton>button {{ 
        background: linear-gradient(135deg, #FFD700, #FFA500); color: #000; border-radius: 12px; 
        font-weight: bold; width: 100%; border: none; padding: 10px;
        box-shadow: 0 4px 15px rgba(255, 215, 0, 0.4), inset 0 -3px 0 rgba(0,0,0,0.2);
        transition: all 0.2s ease;
    }}
    .stButton>button:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(255, 215, 0, 0.6); }}
    .glass-card {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 25px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); margin-bottom: 25px; text-align: center; }}
    .balance-banner {{ background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.02)); backdrop-filter: blur(10px); padding: 30px; border-radius: 20px; border-left: 8px solid #FFD700; text-align: center; margin-bottom: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
    .category-box {{ background: rgba(0, 0, 0, 0.5); padding: 20px; border-radius: 15px; text-align: center; border-bottom: 4px solid #FFD700; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
    .alert-banner {{ background: linear-gradient(90deg, #ff4d4d, #cc0000); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255, 77, 77, 0.4); }}
    .login-card {{ background: rgba(20, 20, 35, 0.8); backdrop-filter: blur(20px); padding: 40px; border-radius: 20px; max-width: 450px; margin: auto; margin-top: 80px; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 15px 35px rgba(0,0,0,0.6); }}
    h1, h2, h3, p, label {{ color: #FFFFFF !important; font-weight: bold !important; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
    [data-testid="stChatMessage"] {{ background: rgba(32, 44, 51, 0.9) !important; border-radius: 15px !important; padding: 15px !important; margin-bottom: 10px !important; border: 1px solid rgba(255,255,255,0.05) !important; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
    [data-testid="stChatInput"] {{ background-color: rgba(42, 57, 66, 0.8) !important; border-radius: 25px !important; border: 1px solid rgba(255,255,255,0.1) !important; padding: 5px !important; }}
    [data-testid="stChatInput"] textarea {{ color: white !important; }}
    input, textarea, select {{ color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important; background-color: rgba(0, 0, 0, 0.5) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 8px !important; }}
    ::placeholder {{ color: #AAAAAA !important; }}
    </style>
""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth, st.session_state.user = False, ""
if 'custom_alert_text' not in st.session_state: st.session_state.custom_alert_text = "Low balance alert"
if 'low_limit' not in st.session_state: st.session_state.low_limit = 6000
if "last_processed_prompt" not in st.session_state: st.session_state.last_processed_prompt = None
if "pending_entry" not in st.session_state: st.session_state.pending_entry = None
if "entry_saved_flag" not in st.session_state: st.session_state.entry_saved_flag = False
if "user_sheet_url" not in st.session_state: st.session_state.user_sheet_url = ""
if "user_sheet_csv_url" not in st.session_state: st.session_state.user_sheet_csv_url = ""

# Restore login session automatically if URL token is valid
restore_session_from_url()

# --- HELPER FUNCTIONS ---
def sync_active_user_profile(username: str):
    prof = db_get_user(username)
    if prof:
        st.session_state.user_sheet_url = prof.get("sheet_url", "")
        st.session_state.user_sheet_csv_url = prof.get("csv_url", "")

def get_active_web_app_url():
    prof = db_get_user(st.session_state.get("user", ""))
    return (prof.get("sheet_url", "") if prof else st.session_state.get("user_sheet_url", "")).strip()

def get_active_csv_url():
    prof = db_get_user(st.session_state.get("user", ""))
    return (prof.get("csv_url", "") if prof else st.session_state.get("user_sheet_csv_url", "")).strip()

def send_whatsapp_auto(msg):
    try:
        account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
        auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
        if account_sid and auth_token and WA_PHONE:
            client = Client(account_sid, auth_token)
            client.messages.create(from_='whatsapp:+14155238886', body=msg, to=f'whatsapp:+{WA_PHONE}')
    except Exception:
        pass

def parse_mixed_dates(date_series):
    parsed = []
    for val in date_series:
        dt = pd.to_datetime(str(val).strip(), errors='coerce')
        if pd.isna(dt):
            dt = pd.to_datetime(str(val).strip(), dayfirst=True, errors='coerce')
        parsed.append(dt)
    return pd.Series(parsed)

@st.cache_data(ttl=5)
def load_data(active_csv_url="", cache_buster=0):
    try:
        target_csv = (active_csv_url or "").strip()
        if not target_csv:
            return pd.DataFrame(columns=['Date', 'Item', 'Debit', 'Credit'])
        sep = "&" if "?" in target_csv else "?"
        df = pd.read_csv(f"{target_csv}{sep}r={random.randint(1,999999)}_{cache_buster}")
        df.columns = df.columns.str.strip()
        df['Date'] = parse_mixed_dates(df['Date'])
        df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=['Date', 'Item', 'Debit', 'Credit'])

@st.cache_data(ttl=5)
def load_debts_data(active_csv_url="", cache_buster=0):
    try:
        target_csv = (active_csv_url or "").strip()
        if not target_csv:
            return pd.DataFrame(columns=['ID', 'Name', 'Type', 'Amount', 'Date', 'Status', 'Sender'])
        sep = "&" if "?" in target_csv else "?"
        df = pd.read_csv(f"{target_csv}{sep}r={random.randint(1,999999)}_{cache_buster}")
        df.columns = df.columns.str.strip()
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=['ID', 'Name', 'Type', 'Amount', 'Date', 'Status', 'Sender'])

def refresh_user_sheet_cache():
    st.cache_data.clear()

def create_pdf(df):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, txt="FINANCE REPORT", ln=True, align='C')
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
    except Exception:
        return None

def add_new_entry(item, amount, category="Others", type="Debit", entry_date=None):
    try:
        target_url = get_active_web_app_url()
        if not entry_date:
            entry_date = datetime.now(GST).strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "item": item,
            "amount": amount,
            "category": category,
            "type": type,
            "date": entry_date
        }
        if target_url:
            requests.post(target_url, json=payload, timeout=10)
            refresh_user_sheet_cache()
        send_whatsapp_auto(f"✅ *AI Entry Added*\n📝 Item: {item}\n💰 Amt: ₹{amount}")
        return f"Success: {item} - ₹{amount} ({type})"
    except Exception as e:
        return f"Error: {str(e)}"

def add_multiple_entries(entries_list):
    results = []
    try:
        target_url = get_active_web_app_url()
        for entry in entries_list:
            item = entry.get('item', 'Unknown')
            amount = entry.get('amount', 0)
            category = entry.get('category', 'Others')
            entry_type = entry.get('type', 'Debit')
            entry_date = entry.get('date', datetime.now(GST).strftime('%Y-%m-%d %H:%M:%S'))
            payload = {
                "item": item,
                "amount": amount,
                "category": category,
                "type": entry_type,
                "date": entry_date
            }
            if target_url:
                requests.post(target_url, json=payload, timeout=10)
            results.append(f'{item} - ₹{amount}')
        if target_url:
            refresh_user_sheet_cache()
        summary_text = '\n'.join([f'• {r}' for r in results])
        send_whatsapp_auto(f'✅ *AI Multi-Entries Added*\n{summary_text}')
        return f'Success: Added {len(results)} items.'
    except Exception as e:
        return f'Error: {str(e)}'

def add_debt_via_ai(name, type, amount, date=None):
    try:
        target_url = get_active_web_app_url()
        if not date:
            date = datetime.now(GST).strftime("%Y-%m-%d")
        payload = {
            "action": "add_debt",
            "name": name,
            "type": type,
            "amount": amount,
            "date": date
        }
        if target_url:
            requests.post(target_url, json=payload, timeout=10)
            refresh_user_sheet_cache()
        send_whatsapp_auto(f"🤝 *AI Debt Added*\n👤 Person: {name}\n📌 Type: {type}\n💰 Amt: ₹{amount}")
        return f"Success: {type} - {name} - ₹{amount}"
    except Exception as e:
        return f"Error: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "add_new_entry",
            "description": "Add a single expense or income",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "amount": {"type": "number"},
                    "category": {"type": "string", "description": "Food, Shop, Fish, Travel, Rent, Others"},
                    "type": {"type": "string", "enum": ["Debit", "Credit"]},
                    "date": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS"}
                },
                "required": ["item", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_multiple_entries",
            "description": "Add multiple expenses",
            "parameters": {
                "type": "object",
                "properties": {
                    "entries_list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item": {"type": "string"},
                                "amount": {"type": "number"},
                                "category": {"type": "string"},
                                "type": {"type": "string", "enum": ["Debit", "Credit"]},
                                "date": {"type": "string"}
                            },
                            "required": ["item", "amount"]
                        }
                    }
                },
                "required": ["entries_list"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_debt_entry",
            "description": "Add money lent or borrowed to Debt Tracker",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Person name"},
                    "type": {"type": "string", "enum": ["Lent (കൊടുത്തത്)", "Borrowed (വാങ്ങിയത്)"]},
                    "amount": {"type": "number"},
                    "date": {"type": "string"}
                },
                "required": ["name", "type", "amount"]
            }
        }
    }
]

# --- 🔒 PUBLIC SIGN UP, LOGIN & RESET PASSWORD SCREEN ---
if not st.session_state.auth:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.subheader("🔐 PAICHI EXPENSES")

        mode_tab1, mode_tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

        # --- TAB 1: LOGIN + PASSWORD RESET ---
        with mode_tab1:
            l_user = st.text_input("👤 Username / Email", key="login_user", placeholder="Enter your username or email").strip().lower()
            l_pass = st.text_input("🔑 Password", type="password", key="login_pass", placeholder="Enter your password")
            existing_prof = db_get_user(l_user) if l_user else None

            with st.expander("📄 My Google Sheet Links (Optional)"):
                l_web = st.text_input(
                    "Sheet Web App URL",
                    value=(existing_prof.get("sheet_url", "") if existing_prof else ""),
                    key="login_web_url",
                    placeholder="https://script.google.com/macros/s/.../exec"
                )
                l_csv = st.text_input(
                    "Sheet CSV URL",
                    value=(existing_prof.get("csv_url", "") if existing_prof else ""),
                    key="login_csv_url",
                    placeholder="https://docs.google.com/spreadsheets/d/.../pub?output=csv"
                )

            if st.button("LOGIN 🔓", key="btn_login"):
                user_rec = db_get_user(l_user)
                if not l_user:
                    st.error("❌ ദയവായി നിങ്ങളുടെ യൂസർനെയിം നൽകുക!")
                elif not l_pass:
                    st.error("❌ ദയവായി പാസ്‌വേഡ് നൽകുക!")
                elif not user_rec:
                    st.error("❌ അക്കൗണ്ട് കണ്ടെത്താനായില്ല! ആദ്യം Sign Up ടാബിൽ അക്കൗണ്ട് തുടങ്ങുക.")
                elif user_rec["password_hash"] == hash_password(l_pass):
                    final_web = l_web.strip() if l_web.strip() else user_rec.get("sheet_url", "")
                    final_csv = l_csv.strip() if l_csv.strip() else user_rec.get("csv_url", "")
                    db_update_links(l_user, final_web, final_csv)
                    refresh_user_sheet_cache()
                    set_persistent_login(l_user)
                    st.rerun()
                else:
                    st.error("❌ പാസ്‌വേഡ് തെറ്റാണ്!")

            with st.expander("🔄 Forgot / Reset Password"):
                r_user = st.text_input("👤 Existing Username / Email", key="reset_user", placeholder="Enter your registered username").strip().lower()
                r_new_pass = st.text_input("🔑 New Password", type="password", key="reset_new_pass", placeholder="Enter new password")
                r_confirm_pass = st.text_input("🔒 Confirm New Password", type="password", key="reset_confirm_pass", placeholder="Re-enter new password")

                if st.button("RESET PASSWORD 🔁", key="btn_reset_pass"):
                    if not r_user:
                        st.error("❌ ദയവായി യൂസർനെയിം നൽകുക!")
                    elif not db_get_user(r_user):
                        st.error("❌ ഈ യൂസർനെയിമിൽ അക്കൗണ്ട് ഇല്ല!")
                    elif not r_new_pass:
                        st.error("❌ പുതിയ പാസ്‌വേഡ് നൽകുക!")
                    elif r_new_pass != r_confirm_pass:
                        st.error("❌ രണ്ട് പാസ്‌വേഡുകളും ഒരുപോലെയല്ല!")
                    else:
                        db_update_password(r_user, r_new_pass)
                        st.success("✅ പാസ്‌വേഡ് വിജയകരമായി മാറ്റി! ഇനി ലോഗിൻ ചെയ്യാം.")

        # --- TAB 2: SIGN UP ---
        with mode_tab2:
            s_user = st.text_input("👤 Choose Username / Email", key="signup_user", placeholder="Create a username or email").strip().lower()
            s_pass = st.text_input("🔑 Create Password", type="password", key="signup_pass", placeholder="Create your own password")
            s_confirm = st.text_input("🔒 Confirm Password", type="password", key="signup_confirm", placeholder="Re-enter your password")

            with st.expander("📄 My Google Sheet Links (Optional)"):
                s_web = st.text_input(
                    "Sheet Web App URL",
                    value="",
                    key="signup_web_url",
                    placeholder="https://script.google.com/macros/s/.../exec"
                )
                s_csv = st.text_input(
                    "Sheet CSV URL",
                    value="",
                    key="signup_csv_url",
                    placeholder="https://docs.google.com/spreadsheets/d/.../pub?output=csv"
                )

            if st.button("CREATE ACCOUNT ✨", key="btn_signup"):
                if not s_user:
                    st.error("❌ ദയവായി ഒരു യൂസർനെയിം നൽകുക!")
                elif db_get_user(s_user):
                    st.error("❌ ഈ യൂസർനെയിം നിലവിലുണ്ട്! Login ടാബ് ഉപയോഗിക്കുക.")
                elif not s_pass:
                    st.error("❌ ദയവായി പാസ്‌വേഡ് നൽകുക!")
                elif s_pass != s_confirm:
                    st.error("❌ രണ്ട് പാസ്‌വേഡുകളും ഒരുപോലെയല്ല!")
                else:
                    db_create_user(s_user, s_pass, s_web, s_csv)
                    refresh_user_sheet_cache()
                    set_persistent_login(s_user)
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

else:
    sync_active_user_profile(st.session_state.user)
    active_csv = get_active_csv_url()
    active_web = get_active_web_app_url()
    df = load_data(active_csv)
    t_in, t_out = (df['Credit'].sum(), df['Debit'].sum()) if not df.empty else (0.0, 0.0)
    bal = t_in - t_out

    with st.sidebar.expander("⚙️ Settings"):
        updated_web = st.text_input(
            "📄 Target Sheet Web App URL",
            value=active_web,
            placeholder="https://script.google.com/macros/s/.../exec"
        ).strip()
        updated_csv = st.text_input(
            "📊 Target Sheet CSV URL",
            value=active_csv,
            placeholder="https://docs.google.com/spreadsheets/d/.../pub?output=csv"
        ).strip()
        if updated_web != active_web or updated_csv != active_csv:
            db_update_links(st.session_state.user, updated_web, updated_csv)
            refresh_user_sheet_cache()
            st.rerun()

        if st.button("🔄 Sync From My Sheet"):
            refresh_user_sheet_cache()
            st.rerun()

        st.session_state.custom_alert_text = st.text_area("Alert Message", value=st.session_state.custom_alert_text)
        st.session_state.low_limit = st.number_input("Low Balance Limit (₹)", value=st.session_state.low_limit)

    menu = ["🏠 Dashboard", "💰 Add Entry", "📅 Calendar", "📊 Report", "🔍 History", "🤝 Debt Tracker", "🤖 AI Chat", "🧠 My AI Buddy"]
    page = st.sidebar.radio("Menu", menu)
    if st.sidebar.button("Logout"):
        clear_persistent_login()
        st.rerun()

    # --- DASHBOARD ---
    if page == "🏠 Dashboard":
        if not active_csv:
            st.info("ℹ️ നിങ്ങളുടെ Google Sheet CSV URL ഇതുവരെ നൽകിയിട്ടില്ല. ഇടതുവശത്തെ **Settings**-ൽ Sheet CSV URL നൽകുമ്പോൾ നിങ്ങളുടെ ഷീറ്റിലെ ഡാറ്റ ഇവിടെ വരും.")
        if bal < st.session_state.low_limit:
            st.markdown(f'<div class="alert-banner">⚠️ ബാലൻസ് കുറവാണ്: {st.session_state.custom_alert_text} (₹{bal:,.2f})!</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="balance-banner"><span style="font-size:22px; color:#E0B0FF; letter-spacing: 2px;">AVAILABLE BALANCE</span><br><span style="font-size:50px; color:#FFD700; font-family: monospace;">₹{bal:,.2f}</span></div>', unsafe_allow_html=True)
        st.title("Financial Overview")
        st.markdown(f'<div class="glass-card"><h2 style="color:#00FF00;">Credit: ₹{t_in:,.2f}</h2><h2 style="color:#FF3131;">Debit: ₹{t_out:,.2f}</h2></div>', unsafe_allow_html=True)

        if not df.empty and 'Item' in df.columns:
            def extract_cat(x):
                item_text = str(x).lower()
                if any(w in item_text for w in ["food", "ഭക്ഷണം", "ചായ", "ഹോട്ടൽ", "ബിരിയാണി"]): return "Food"
                elif any(w in item_text for w in ["shop", "കട", "സാധനങ്ങൾ", "സൂപ്പർമാർക്കറ്റ്"]): return "Shop"
                elif any(w in item_text for w in ["fish", "മീൻ", "ഇറച്ചി", "ചിക്കൻ"]): return "Fish"
                elif any(w in item_text for w in ["travel", "യാത്ര", "പെട്രോൾ", "വണ്ടി", "ടാക്സി"]): return "Travel"
                elif any(w in item_text for w in ["rent", "വാടക", "റൂം"]): return "Rent"
                return "Others"
            df['Cat'] = df['Item'].apply(extract_cat)
            cats = df.groupby('Cat')['Debit'].sum().to_dict()
            cols = st.columns(3)
            for idx, (c_name, c_amt) in enumerate(cats.items()):
                if c_amt > 0:
                    with cols[idx % 3]:
                        st.markdown(f'<div class="category-box"><span style="color:#aaa;">Total {c_name}</span><br><span style="font-size:24px; color:#FFF;">₹{c_amt:,.2f}</span></div>', unsafe_allow_html=True)

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
            if any(x in raw for x in ["food", "ഭക്ഷണം", "ചായ", "ഹോട്ടൽ", "ബിരിയാണി"]): v_cat = "Food"
            elif any(x in raw for x in ["shop", "കട"]): v_cat = "Shop"
            elif any(x in raw for x in ["fish", "മീൻ", "ചിക്കൻ"]): v_cat = "Fish"
            elif any(x in raw for x in ["travel", "പെട്രോൾ", "വണ്ടി"]): v_cat = "Travel"
            if any(x in raw for x in ["കിട്ടി", "വന്നു", "തന്നു"]): v_type = "Credit"

        with st.form("entry_form", clear_on_submit=True):
            it = st.text_input("Description", value=v_desc)
            am_str = st.text_input("Amount", value=str(v_amt))
            cat = st.selectbox("Category", ["Food", "Shop", "Fish", "Travel", "Rent", "Others"], index=["Food", "Shop", "Fish", "Travel", "Rent", "Others"].index(v_cat))
            ty = st.radio("Type", ["Debit", "Credit"], horizontal=True, index=0 if v_type == "Debit" else 1)

            if st.form_submit_button("SAVE & NOTIFY"):
                try:
                    am = float(am_str.strip().replace(',', ''))
                    if not st.session_state.entry_saved_flag:
                        target_url = get_active_web_app_url()
                        payload = {
                            "item": it,
                            "amount": am,
                            "category": cat,
                            "type": ty,
                            "date": datetime.now(GST).strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if target_url:
                            requests.post(target_url, json=payload, timeout=10)
                            refresh_user_sheet_cache()
                        send_whatsapp_auto(f"✅ *Expense Entry*\n📝 {it}\n💰 ₹{am}")

                        st.session_state.entry_saved_flag = True
                        st.success("Saved! ✅")
                        time.sleep(1)
                        st.session_state.entry_saved_flag = False
                        st.rerun()
                except Exception as e:
                    st.error(f"Error! Valid amount required. {e}")

    # --- CALENDAR ---
    elif page == "📅 Calendar":
        st.title("P&L Calendar View 📅")
        if df.empty:
            st.info("No data available yet. Connect your Sheet CSV URL in Settings or add entries.")
        else:
            df_cal = df.dropna(subset=['Date'])
            summary = df_cal.groupby(df_cal['Date'].dt.strftime('%Y-%m-%d')).agg({'Debit': 'sum', 'Credit': 'sum'}).reset_index()
            events = []
            for _, row in summary.iterrows():
                if row['Credit'] > 0: events.append({"title": f" +₹{row['Credit']:,.0f}", "start": row['Date'], "backgroundColor": "#198754"})
                if row['Debit'] > 0: events.append({"title": f" -₹{row['Debit']:,.0f}", "start": row['Date'], "backgroundColor": "#dc3545"})

            cal_data = calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "initialView": "dayGridMonth"}, key="pnl_calendar")

            if cal_data and cal_data.get("callback") == "eventClick":
                event_data = cal_data.get("eventClick", {}).get("event", {})
                dt_click = event_data.get("start", "").split("T")[0]
                if dt_click:
                    st.markdown("---"); st.subheader(f"📋 Details for {pd.to_datetime(dt_click).strftime('%d %B %Y')}")
                    day_df = df_cal[df_cal['Date'].dt.strftime('%Y-%m-%d') == dt_click].copy()
                    if not day_df.empty:
                        day_df['Date'] = day_df['Date'].dt.strftime('%d/%m/%Y')
                        st.dataframe(day_df[['Date', 'Item', 'Debit', 'Credit']], use_container_width=True)

    # --- REPORT & HISTORY ---
    elif (page == "📊 Report" or page == "🔍 History"):
        if df.empty:
            st.info("No data available yet.")
        else:
            df_rep = df.dropna(subset=['Date']).copy()
            df_rep['Month'] = df_rep['Date'].dt.strftime('%B %Y')
            months = df_rep.dropna(subset=['Month']).sort_values(by='Date', ascending=False)['Month'].unique()

            if len(months) == 0:
                st.warning("No data found!")
            else:
                sel_m = st.selectbox("Select Month", months)
                m_df = df_rep[df_rep['Month'] == sel_m].copy()
                m_deb, m_crd = m_df['Debit'].sum(), m_df['Credit'].sum()

                if page == "📊 Report":
                    st.title("Monthly Expense Analysis")
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f'<div class="glass-card"><h3 style="color:#00FF00;">Credit</h3><h1 style="color:#00FF00;">₹{m_crd:,.2f}</h1></div>', unsafe_allow_html=True)
                    c2.markdown(f'<div class="glass-card"><h3 style="color:#FF3131;">Expense</h3><h1 style="color:#FF3131;">₹{m_deb:,.2f}</h1></div>', unsafe_allow_html=True)
                    c3.markdown(f'<div class="glass-card"><h3 style="color:#FFD700;">Savings</h3><h1 style="color:#FFD700;">₹{m_crd - m_deb:,.2f}</h1></div>', unsafe_allow_html=True)

                    m_df['Cat'] = m_df['Item'].apply(lambda x: x.split(':')[0] if ':' in str(x) else 'Others')
                    st.plotly_chart(px.pie(m_df[m_df['Debit'] > 0], values='Debit', names='Cat', hole=0.4), use_container_width=True)

                clean_df = m_df.drop(columns=['Month'], errors='ignore')
                clean_df['Date'] = clean_df['Date'].dt.strftime('%d/%m/%Y')
                st.dataframe(clean_df.iloc[::-1], use_container_width=True)

                if page == "📊 Report":
                    pdf_bytes = create_pdf(clean_df)
                    if pdf_bytes:
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"Expense_Report_{sel_m}.pdf",
                            mime="application/pdf"
                        )

    # --- DEBT TRACKER ---
    elif page == "🤝 Debt Tracker":
        st.title("🤝 Debt Tracker (കടം കണക്കുകൾ)")
        df_debts = load_debts_data(active_csv)

        tab1, tab2, tab3 = st.tabs(["📋 View All Debts", "➕ Add New Debt", "⚙️ Settlement History"])

        with tab1:
            st.subheader("Active Debts & Loans")
            if not df_debts.empty:
                pending_df = df_debts[df_debts['Status'] == "Pending"]
                total_lent = pending_df[pending_df['Type'].str.contains("Lent", na=False)]['Amount'].sum()
                total_borrowed = pending_df[pending_df['Type'].str.contains("Borrowed", na=False)]['Amount'].sum()
            else:
                total_lent, total_borrowed = 0.0, 0.0

            col_a, col_b = st.columns(2)
            col_a.markdown(f'<div class="glass-card"><h4 style="color:#00FF00;">Total Lent (കിട്ടാനുള്ളത്)</h4><h2 style="color:#00FF00;">₹{total_lent:,.2f}</h2></div>', unsafe_allow_html=True)
            col_b.markdown(f'<div class="glass-card"><h4 style="color:#FF3131;">Total Borrowed (കൊടുക്കാനുള്ളത്)</h4><h2 style="color:#FF3131;">₹{total_borrowed:,.2f}</h2></div>', unsafe_allow_html=True)

            st.markdown("---")

            if df_debts.empty or len(df_debts[df_debts['Status'] == "Pending"]) == 0:
                st.info("നിലവിൽ പെൻഡിംഗ് ആയ കടങ്ങൾ ഒന്നുമില്ല.")
            else:
                pending_items = df_debts[df_debts['Status'] == "Pending"].to_dict('records')
                for debt in pending_items:
                    with st.container():
                        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
                        c1.write(f"**{debt['Name']}**")
                        c2.write(f"{debt['Type']}")
                        c3.write(f"**₹{debt['Amount']:,.2f}**")
                        c4.write(f"{str(debt['Date']).split(' ')[0]}")

                        if c5.button("✅ Settle", key=f"settle_cloud_{debt['ID']}"):
                            try:
                                target_url = get_active_web_app_url()
                                payload = {"action": "settle_debt", "id": debt['ID']}
                                if target_url:
                                    requests.post(target_url, json=payload, timeout=10)
                                    refresh_user_sheet_cache()
                                st.success(f"{debt['Name']}-ന്റെ കണക്ക് തീർപ്പാക്കി!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        st.markdown("<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)

        with tab2:
            st.subheader("Add New Debt Entry")
            with st.form("cloud_debt_form", clear_on_submit=True):
                d_name = st.text_input("👤 Person Name (ആരുടെ പേര്)")
                d_type = st.selectbox("📌 Transaction Type", ["Lent (കൊടുത്തത്)", "Borrowed (വാങ്ങിയത്)"])
                d_amount = st.number_input("💰 Amount (₹)", min_value=1.0, step=10.0)
                d_date = st.date_input("📅 Date", value=datetime.now(GST).date())

                if st.form_submit_button("SAVE TO GOOGLE SHEET 💾"):
                    if not d_name.strip():
                        st.error("ദയവായി പേര് നൽകുക!")
                    else:
                        try:
                            target_url = get_active_web_app_url()
                            payload = {
                                "action": "add_debt",
                                "name": d_name.strip(),
                                "type": d_type,
                                "amount": d_amount,
                                "date": str(d_date)
                            }
                            if target_url:
                                requests.post(target_url, json=payload, timeout=10)
                                refresh_user_sheet_cache()
                            send_whatsapp_auto(f"🤝 *New Debt Saved*\n👤 Person: {d_name}\n📌 Type: {d_type}\n💰 Amt: ₹{d_amount}")

                            st.success("Debt saved successfully! ✅")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save: {e}")

        with tab3:
            st.subheader("Settled History")
            if df_debts.empty or len(df_debts[df_debts['Status'] == "Settled"]) == 0:
                st.info("തീർപ്പാക്കിയ കണക്കുകൾ ഒന്നുമില്ല.")
            else:
                settled_df = df_debts[df_debts['Status'] == "Settled"]
                for _, item in settled_df.iterrows():
                    st.write(f"✔️ **{item['Name']}** - {item['Type']} - ₹{item['Amount']:,.2f} (Date: {str(item['Date']).split(' ')[0]})")

    # --- MY AI BUDDY ---
    elif page == "🧠 My AI Buddy":
        st.title("🧠 Your Personal AI Buddy")
        if "buddy_messages" not in st.session_state: st.session_state.buddy_messages = []
        for msg in st.session_state.buddy_messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        user_input = st.chat_input("Ask me anything...", key="buddy_chat_box")
        if user_input:
            st.session_state.buddy_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"): st.markdown(user_input)
            with st.spinner("ആലോചിക്കുന്നു..."):
                try:
                    client = Groq(api_key=GROQ_API_KEY)
                    system_prompt = "You are a helpful personal AI assistant. Answer questions clearly and in a friendly way."
                    messages = [{"role": "system", "content": system_prompt}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.buddy_messages[-4:]]
                    response = client.chat.completions.create(model="openai/gpt-oss-120b", messages=messages, max_tokens=1024)
                    ai_reply = response.choices[0].message.content
                    st.session_state.buddy_messages.append({"role": "assistant", "content": ai_reply})
                    with st.chat_message("assistant"): st.markdown(ai_reply)
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- AI CHAT (AI Agent with Confirmation & Loop Fixed) ---
    elif page == "🤖 AI Chat":
        st.title("🤖 AI Agent & Assistant")

        if "messages" not in st.session_state: st.session_state.messages = []

        if st.session_state.pending_entry:
            st.warning(f"⏳ നിങ്ങൾ പറഞ്ഞത്: **{st.session_state.pending_entry['item']} - ₹{st.session_state.pending_entry['amount']}**. ഇത് എൻട്രി ചെയ്യണോ?")
            col1, col2 = st.columns(2)
            if col1.button("✅ Yes, Save it", key="save_entry_btn"):
                entry_data = st.session_state.pending_entry
                st.session_state.pending_entry = None

                result = add_new_entry(
                    item=entry_data['item'], amount=entry_data['amount'],
                    category=entry_data['category'], type=entry_data['type'], entry_date=entry_data['date']
                )
                ai_msg = f"✅ {entry_data['item']}-ന് ₹{entry_data['amount']} എൻട്രി ഇട്ടിട്ടുണ്ട്!" if "Success" in result else f"❌ {result}"
                st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                st.session_state.last_processed_prompt = None
                st.rerun()

            if col2.button("❌ No, Cancel", key="cancel_entry_btn"):
                st.session_state.pending_entry = None
                st.session_state.messages.append({"role": "assistant", "content": "ശരി, ഞാൻ എൻട്രി ഇട്ടിട്ടില്ല."})
                st.session_state.last_processed_prompt = None
                st.rerun()

        for message in st.session_state.messages:
            with st.chat_message(message["role"]): st.markdown(message["content"])

        v_raw = speech_to_text(language='ml', key='ai_voice_input')
        prompt = st.chat_input("Ask anything or add expense...", key="ai_chat_box")
        final_prompt = v_raw if v_raw else prompt

        if final_prompt:
            if st.session_state.get("last_processed_prompt") != final_prompt:
                st.session_state.last_processed_prompt = final_prompt

                if final_prompt.lower().strip() in ["yes", "y", "yep", "ya", "അതെ", "ശരി"] and st.session_state.pending_entry:
                    entry_data = st.session_state.pending_entry
                    st.session_state.messages.append({"role": "user", "content": final_prompt})
                    st.session_state.pending_entry = None

                    result = add_new_entry(
                        item=entry_data['item'], amount=entry_data['amount'],
                        category=entry_data['category'], type=entry_data['type'], entry_date=entry_data['date']
                    )
                    ai_msg = f"✅ {entry_data['item']}-ന് ₹{entry_data['amount']} എൻട്രി ഇട്ടിട്ടുണ്ട്!" if "Success" in result else f"❌ {result}"
                    st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                    st.session_state.last_processed_prompt = None
                    st.rerun()

                elif final_prompt.lower().strip() in ["no", "n", "nope", "അല്ല", "വേണ്ട"] and st.session_state.pending_entry:
                    st.session_state.messages.append({"role": "user", "content": final_prompt})
                    st.session_state.pending_entry = None
                    st.session_state.messages.append({"role": "assistant", "content": "ശരി, ഞാൻ എൻട്രി ഇട്ടിട്ടില്ല."})
                    st.session_state.last_processed_prompt = None
                    st.rerun()

                else:
                    st.session_state.messages.append({"role": "user", "content": final_prompt})
                    with st.chat_message("user"): st.markdown(final_prompt)

                    with st.spinner("AI ആലോചിക്കുന്നു..."):
                        try:
                            client = Groq(api_key=GROQ_API_KEY)
                            gst_now = datetime.now(GST).strftime("%Y-%m-%d %H:%M:%S")
                            system_instruction = f"നീ ഒരു ഫിനാൻസ് AI അസിസ്റ്റന്റാണ്. സമയം: {gst_now} (GST). ബാലൻസ്: {bal} Rs. പണം കൊടുത്തതോ വാങ്ങിയതോ ആണെങ്കിൽ 'add_debt_entry' ടൂൾ ഉപയോഗിക്കുക."

                            messages_for_api = [{"role": "system", "content": system_instruction}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-4:]]

                            response = client.chat.completions.create(
                                model="openai/gpt-oss-120b", messages=messages_for_api, tools=tools, tool_choice="auto", max_tokens=1024
                            )

                            response_message = response.choices[0].message

                            if response_message.tool_calls:
                                for tool_call in response_message.tool_calls:
                                    if tool_call.function.name == 'add_new_entry':
                                        args = json.loads(tool_call.function.arguments)
                                        st.session_state.pending_entry = {
                                            "item": args.get("item"), "amount": args.get("amount"),
                                            "category": args.get("category", "Others"), "type": args.get("type", "Debit"),
                                            "date": args.get("date") or datetime.now(GST).strftime("%Y-%m-%d %H:%M:%S")
                                        }
                                        ai_msg = f"ഞാൻ ഇത് എൻട്രി ചെയ്യാൻ പോകുന്നു: {st.session_state.pending_entry['item']} - ₹{st.session_state.pending_entry['amount']}. ശരിയാണോ? (Type 'yes' or 'no')"
                                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                                        st.rerun()

                                    elif tool_call.function.name == 'add_multiple_entries':
                                        args = json.loads(tool_call.function.arguments)
                                        entries = args.get("entries_list", [])
                                        result = add_multiple_entries(entries)
                                        ai_msg = f"✅ {len(entries)} എൻട്രികൾ ഒന്നിച്ച് സേവ് ചെയ്തിട്ടുണ്ട്!" if "Success" in result else f"❌ {result}"
                                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                                        st.rerun()

                                    elif tool_call.function.name == 'add_debt_entry':
                                        args = json.loads(tool_call.function.arguments)
                                        d_name = args.get("name")
                                        d_type = args.get("type")
                                        d_amount = args.get("amount")
                                        d_date = args.get("date") or datetime.now(GST).strftime("%Y-%m-%d")

                                        result = add_debt_via_ai(d_name, d_type, d_amount, d_date)
                                        ai_msg = f"✅ **{d_name}**-ന് ₹{d_amount} ({d_type}) Debt Tracker-ൽ സേവ് ചെയ്തിട്ടുണ്ട്!" if "Success" in result else f"❌ {result}"
                                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                                        st.session_state.last_processed_prompt = None
                                        st.rerun()

                            elif response_message.content:
                                ai_msg = response_message.content
                                st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                                st.rerun()

                        except Exception as e:
                            st.error(f"AI Error: {str(e)}")
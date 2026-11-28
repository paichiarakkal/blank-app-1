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
import smtplib
from email.message import EmailMessage
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
SMTP_EMAIL = st.secrets.get("SMTP_EMAIL", "")
SMTP_APP_PASSWORD = st.secrets.get("SMTP_APP_PASSWORD", "")
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "")
OTP_FROM_EMAIL = st.secrets.get("OTP_FROM_EMAIL", "onboarding@resend.dev")
BREVO_API_KEY = st.secrets.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = st.secrets.get("BREVO_SENDER_EMAIL", "")
MASTER_SHEET_SCRIPT_URL = st.secrets.get(
    "MASTER_SHEET_SCRIPT_URL",
    st.secrets.get("SHEET_WEB_APP_URL", st.secrets.get("GOOGLE_SHEET_WEB_APP_URL", ""))
)
DB_FILE = "paichi_users_v2.db"

# --- TIMEZONE SETUP (GST - Dubai Time) ---
GST = timezone(timedelta(hours=4))

st_autorefresh(interval=60000, key="auto_refresh")

# ============================================
# 🗄️ DATABASE + ST.SECRETS USER STORE
# ============================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            sheet_url TEXT DEFAULT '',
            csv_url TEXT DEFAULT '',
            debts_csv_url TEXT DEFAULT '',
            links_locked INTEGER DEFAULT 0,
            account_locked INTEGER DEFAULT 1
        )
    """)
    c.execute("PRAGMA table_info(users)")
    existing_cols = [col[1] for col in c.fetchall()]
    if "sheet_url" not in existing_cols:
        c.execute("ALTER TABLE users ADD COLUMN sheet_url TEXT DEFAULT ''")
    if "csv_url" not in existing_cols:
        c.execute("ALTER TABLE users ADD COLUMN csv_url TEXT DEFAULT ''")
    if "debts_csv_url" not in existing_cols:
        c.execute("ALTER TABLE users ADD COLUMN debts_csv_url TEXT DEFAULT ''")
    if "links_locked" not in existing_cols:
        c.execute("ALTER TABLE users ADD COLUMN links_locked INTEGER DEFAULT 0")
    if "account_locked" not in existing_cols:
        c.execute("ALTER TABLE users ADD COLUMN account_locked INTEGER DEFAULT 1")
    conn.commit()
    conn.close()

init_db()

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def load_secrets_users() -> dict:
    raw_users = st.secrets.get("USERS_DATA", {})
    if isinstance(raw_users, str):
        try:
            parsed = json.loads(raw_users)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    if isinstance(raw_users, dict):
        return dict(raw_users)
    return {}

def is_account_already_registered(username: str) -> bool:
    u = (username or "").strip().lower()
    if not u:
        return False
    if u in load_secrets_users():
        return True
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE username = ?", (u,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def db_get_user(username: str):
    init_db()
    u = (username or "").strip().lower()
    if not u:
        return None

    secrets_users = load_secrets_users()
    s_rec = secrets_users.get(u)
    if isinstance(s_rec, dict) and s_rec.get("password_hash"):
        sheet_val = (s_rec.get("sheet_url") or "").strip()
        csv_val = (s_rec.get("csv_url") or "").strip()
        debts_csv_val = (s_rec.get("debts_csv_url") or "").strip()
        locked_val = 1 if (sheet_val or csv_val or s_rec.get("links_locked")) else 0
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO users (username, password_hash, sheet_url, csv_url, debts_csv_url, links_locked, account_locked)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                sheet_url = CASE WHEN users.sheet_url != '' THEN users.sheet_url ELSE excluded.sheet_url END,
                csv_url = CASE WHEN users.csv_url != '' THEN users.csv_url ELSE excluded.csv_url END,
                debts_csv_url = CASE WHEN users.debts_csv_url != '' THEN users.debts_csv_url ELSE excluded.debts_csv_url END,
                links_locked = CASE WHEN users.links_locked = 1 OR excluded.links_locked = 1 THEN 1 ELSE 0 END,
                account_locked = 1
            """,
            (u, s_rec.get("password_hash", ""), sheet_val, csv_val, debts_csv_val, locked_val)
        )
        conn.commit()
        c.execute(
            "SELECT username, password_hash, sheet_url, csv_url, debts_csv_url, links_locked, account_locked FROM users WHERE username = ?",
            (u,)
        )
        row = c.fetchone()
        conn.close()
        if row:
            s_url_db = row[2] or ""
            c_url_db = row[3] or ""
            d_url_db = row[4] or ""
            is_locked = 1 if (s_url_db or c_url_db or int(row[5] or 0) == 1) else 0
            return {
                "username": row[0],
                "password_hash": row[1],
                "sheet_url": s_url_db,
                "csv_url": c_url_db,
                "debts_csv_url": d_url_db,
                "links_locked": is_locked,
                "account_locked": int(row[6] if row[6] is not None else 1)
            }

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT username, password_hash, sheet_url, csv_url, debts_csv_url, links_locked, account_locked FROM users WHERE username = ?",
        (u,)
    )
    row = c.fetchone()
    conn.close()
    if row:
        s_url_db = row[2] or ""
        c_url_db = row[3] or ""
        d_url_db = row[4] or ""
        is_locked = 1 if (s_url_db or c_url_db or int(row[5] or 0) == 1) else 0
        return {
            "username": row[0],
            "password_hash": row[1],
            "sheet_url": s_url_db,
            "csv_url": c_url_db,
            "debts_csv_url": d_url_db,
            "links_locked": is_locked,
            "account_locked": int(row[6] if row[6] is not None else 1)
        }
    return None

def provision_customer_sheet_auto(username: str):
    u = (username or "").strip().lower()
    master_url = (st.secrets.get("MASTER_SHEET_SCRIPT_URL", MASTER_SHEET_SCRIPT_URL) or "").strip()
    if not u or not master_url:
        return None
    try:
        resp = requests.post(
            master_url,
            json={"action": "provision_user", "user_email": u},
            timeout=20
        )
        if resp.status_code == 200:
            body = resp.json()
            if body.get("status") == "ok" and isinstance(body.get("data"), dict):
                data = body["data"]
                exp_csv = (data.get("expenses_csv_url") or "").strip()
                debts_csv = (data.get("debts_csv_url") or "").strip()
                ss_url = (data.get("spreadsheet_url") or "").strip()

                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute(
                    """
                    UPDATE users
                    SET sheet_url = ?, csv_url = ?, debts_csv_url = ?, links_locked = 1
                    WHERE username = ?
                    """,
                    (master_url, exp_csv, debts_csv, u)
                )
                conn.commit()
                conn.close()
                return {
                    "sheet_url": master_url,
                    "csv_url": exp_csv,
                    "debts_csv_url": debts_csv,
                    "spreadsheet_url": ss_url
                }
    except Exception:
        pass
    return None

def ensure_user_has_sheet(username: str):
    u = (username or "").strip().lower()
    prof = db_get_user(u)
    if not prof:
        return None
    if not (prof.get("csv_url") or "").strip():
        provision_customer_sheet_auto(u)
        prof = db_get_user(u)
    return prof

def db_create_user(username: str, password: str, sheet_url: str = "", csv_url: str = ""):
    init_db()
    u = username.strip().lower()
    if is_account_already_registered(u):
        raise ValueError("This Google/email account is already registered and locked.")
    pwd_hash = hash_password(password)
    s_url = (sheet_url or "").strip()
    c_url = (csv_url or "").strip()
    locked_flag = 1 if (s_url or c_url) else 0
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO users (username, password_hash, sheet_url, csv_url, debts_csv_url, links_locked, account_locked) VALUES (?, ?, ?, ?, '', ?, 1)",
        (u, pwd_hash, s_url, c_url, locked_flag)
    )
    conn.commit()
    conn.close()

    provision_customer_sheet_auto(u)

    return {
        u: {
            "password_hash": pwd_hash,
            "sheet_url": s_url,
            "csv_url": c_url,
            "links_locked": bool(locked_flag),
            "account_locked": True
        }
    }

def db_update_password(username: str, new_password: str):
    init_db()
    u = username.strip().lower()
    pwd_hash = hash_password(new_password)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pwd_hash, u))
    conn.commit()
    conn.close()
    return pwd_hash

# ============================================
# 📧 FREE EMAIL OTP HELPER (BREVO -> RESEND -> SMTP)
# ============================================
def get_secret_any(key_name: str, fallback: str = "") -> str:
    try:
        if key_name in st.secrets:
            val = st.secrets[key_name]
            if isinstance(val, str) and val.strip():
                return val.strip()
        for _, sec_val in st.secrets.items():
            if isinstance(sec_val, dict) and key_name in sec_val:
                val = sec_val[key_name]
                if isinstance(val, str) and val.strip():
                    return val.strip()
    except Exception:
        pass
    return (fallback or "").strip()

def send_otp_email(to_email: str, otp_code: str, purpose: str = "OTP Verification") -> bool:
    brevo_key = get_secret_any("BREVO_API_KEY", BREVO_API_KEY)
    brevo_sender = get_secret_any("BREVO_SENDER_EMAIL", BREVO_SENDER_EMAIL)
    resend_key = get_secret_any("RESEND_API_KEY", RESEND_API_KEY)
    from_email = get_secret_any("OTP_FROM_EMAIL", OTP_FROM_EMAIL) or "onboarding@resend.dev"

    body_text = (
        f"Hello,\n\n"
        f"Your 6-digit OTP code for PAICHI EXPENSES ({purpose}) is:\n\n"
        f"OTP: {otp_code}\n\n"
        f"Please do not share this code with anyone."
    )

    if brevo_key and brevo_sender:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": brevo_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            json={
                "sender": {"name": "PAICHI EXPENSES", "email": brevo_sender},
                "to": [{"email": to_email}],
                "subject": f"PAICHI EXPENSES - {purpose} OTP",
                "textContent": body_text
            },
            timeout=15
        )
        if resp.status_code in (200, 201, 202):
            return True
        raise RuntimeError(f"Brevo API Error ({resp.status_code}): {resp.text}")

    if resend_key:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": from_email,
                "to": [to_email],
                "subject": f"PAICHI EXPENSES - {purpose} OTP",
                "text": body_text
            },
            timeout=15
        )
        if resp.status_code in (200, 201):
            return True
        raise RuntimeError(f"Resend API Error ({resp.status_code}): {resp.text}")

    sender = get_secret_any("SMTP_EMAIL", SMTP_EMAIL)
    app_pwd = get_secret_any("SMTP_APP_PASSWORD", SMTP_APP_PASSWORD).replace(" ", "")

    if not sender or not app_pwd:
        raise ValueError("BREVO_API_KEY / BREVO_SENDER_EMAIL, RESEND_API_KEY, or SMTP_EMAIL / SMTP_APP_PASSWORD is not configured in Secrets.")

    msg = EmailMessage()
    msg["Subject"] = f"PAICHI EXPENSES - {purpose} OTP"
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender, app_pwd)
            server.send_message(msg)
        return True
    except Exception as ssl_err:
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(sender, app_pwd)
                server.send_message(msg)
            return True
        except Exception as tls_err:
            raise RuntimeError(f"SSL (465) Error: {ssl_err} | TLS (587) Error: {tls_err}")

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
    .category-box:hover {{ transform: scale(1.03); }}
    .alert-banner {{ background: linear-gradient(90deg, #ff4d4d, #cc0000); color: white; padding: 15px; border-radius: 10px; text-align: center; font-weight: bold; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(255, 77, 77, 0.4); }}
    .login-card {{ background: rgba(20, 20, 35, 0.8); backdrop-filter: blur(20px); padding: 40px; border-radius: 20px; max-width: 450px; margin: auto; margin-top: 80px; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 15px 35px rgba(0,0,0,0.6); }}
    h1, h2, h3, p, label {{ color: #FFFFFF !important; font-weight: bold !important; text-shadow: 0 2px 4px rgba(0,0,0,0.5); }}
    [data-testid="stChatMessage"] {{ background: rgba(32, 44, 51, 0.9) !important; border-radius: 15px !important; padding: 15px !important; margin-bottom: 10px !important; border: 1px solid rgba(255,255,255,0.05) !important; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
    [data-testid="stChatInput"] {{ background-color: rgba(42, 57, 66, 0.92) !important; border-radius: 28px !important; border: 1px solid rgba(255,255,255,0.18) !important; padding: 4px 8px !important; }}
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
if "ai_action_notice" not in st.session_state: st.session_state.ai_action_notice = None
if "entry_saved_flag" not in st.session_state: st.session_state.entry_saved_flag = False
if "ai_chat_key_id" not in st.session_state: st.session_state.ai_chat_key_id = 0
if "last_voice_text" not in st.session_state: st.session_state.last_voice_text = ""
if "last_heard_text" not in st.session_state: st.session_state.last_heard_text = ""
if "ai_chat_history" not in st.session_state: st.session_state.ai_chat_history = []

if "signup_otp" not in st.session_state: st.session_state.signup_otp = None
if "signup_otp_email" not in st.session_state: st.session_state.signup_otp_email = ""
if "signup_otp_verified" not in st.session_state: st.session_state.signup_otp_verified = False

if "reset_otp" not in st.session_state: st.session_state.reset_otp = None
if "reset_otp_email" not in st.session_state: st.session_state.reset_otp_email = ""
if "reset_otp_verified" not in st.session_state: st.session_state.reset_otp_verified = False

restore_session_from_url()

# --- HELPER FUNCTIONS ---
def format_display_name(username: str) -> str:
    u = (username or "").strip()
    if "@" in u:
        return u.split("@", 1)[0]
    return u

def format_english_datetime(dt_value=None) -> str:
    if dt_value is None:
        dt_obj = datetime.now(GST)
    elif isinstance(dt_value, datetime):
        dt_obj = dt_value
    else:
        parsed = pd.to_datetime(str(dt_value).strip(), errors="coerce")
        dt_obj = parsed.to_pydatetime() if not pd.isna(parsed) else datetime.now(GST)
    return dt_obj.strftime("%d %b %Y %H:%M:%S")

def translate_to_english_label(text: str, default_label: str = "Expense") -> str:
    raw = (text or "").strip()
    if not raw:
        return default_label
    low = raw.lower()
    mapping = {
        "ചായ": "Tea",
        "കാപ്പി": "Coffee",
        "ഭക്ഷണം": "Food",
        "ചിക്കൻ": "Chicken",
        "മീൻ": "Fish",
        "ബിരിയാണി": "Biryani",
        "കട": "Shop",
        "യാത്ര": "Travel",
        "പെട്രോൾ": "Petrol",
        "വാടക": "Rent",
        "ജയ": "Jaya",
        "شاي": "Tea",
        "قهوة": "Coffee",
        "طعام": "Food",
        "चाय": "Tea",
        "खाना": "Food"
    }
    for k, v in mapping.items():
        if k in low:
            return v
    if GROQ_API_KEY and re.search(r"[^\x00-\x7F]", raw):
        try:
            client = Groq(api_key=GROQ_API_KEY)
            resp = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "Translate the given expense/item/name text into clean concise English (1 to 2 words). Fix voice transcription mistakes. Return ONLY the English text."},
                    {"role": "user", "content": raw}
                ],
                max_tokens=30
            )
            translated = (resp.choices[0].message.content or "").strip().strip('"').strip("'")
            if translated:
                return translated
        except Exception:
            pass
    cleaned = re.sub(r"[^\x00-\x7F]+", "", raw).strip()
    return cleaned if cleaned else default_label

def get_current_user_email() -> str:
    return (st.session_state.get("user", "") or "").strip().lower()

def get_active_web_app_url() -> str:
    prof = ensure_user_has_sheet(get_current_user_email())
    if prof and (prof.get("sheet_url") or "").strip():
        return prof["sheet_url"].strip()
    return (st.secrets.get("MASTER_SHEET_SCRIPT_URL", MASTER_SHEET_SCRIPT_URL) or "").strip()

def get_active_csv_url() -> str:
    prof = ensure_user_has_sheet(get_current_user_email())
    if prof and (prof.get("csv_url") or "").strip():
        return prof["csv_url"].strip()
    return ""

def get_active_debts_csv_url() -> str:
    prof = ensure_user_has_sheet(get_current_user_email())
    if prof and (prof.get("debts_csv_url") or "").strip():
        return prof["debts_csv_url"].strip()
    return get_active_csv_url()

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
        user_email = get_current_user_email()
        target_url = get_active_web_app_url()
        eng_item = translate_to_english_label(item, "Expense")
        eng_cat = translate_to_english_label(category, "Others")
        eng_date = format_english_datetime(entry_date)
        payload = {
            "action": "add_entry",
            "user_email": user_email,
            "item": eng_item,
            "amount": amount,
            "category": eng_cat,
            "type": type,
            "date": eng_date
        }
        if target_url:
            requests.post(target_url, json=payload, timeout=15)
            refresh_user_sheet_cache()
        send_whatsapp_auto(f"✅ *AI Entry Added*\n👤 {user_email}\n📝 Item: {eng_item}\n💰 Amt: ₹{amount}\n📅 Date: {eng_date}")
        return True, f"Entry saved to your sheet: {eng_item} - ₹{amount} ({type})"
    except Exception as e:
        return False, f"Failed to save to sheet: {str(e)}"

def add_multiple_entries(entries_list):
    results = []
    try:
        user_email = get_current_user_email()
        target_url = get_active_web_app_url()
        for entry in entries_list:
            item = translate_to_english_label(entry.get('item', 'Expense'), 'Expense')
            amount = entry.get('amount', 0)
            category = translate_to_english_label(entry.get('category', 'Others'), 'Others')
            entry_type = entry.get('type', 'Debit')
            entry_date = format_english_datetime(entry.get('date'))
            payload = {
                "action": "add_entry",
                "user_email": user_email,
                "item": item,
                "amount": amount,
                "category": category,
                "type": entry_type,
                "date": entry_date
            }
            if target_url:
                requests.post(target_url, json=payload, timeout=15)
            results.append(f'{item} - ₹{amount}')
        if target_url:
            refresh_user_sheet_cache()
        summary_text = '\n'.join([f'• {r}' for r in results])
        send_whatsapp_auto(f'✅ *AI Multi-Entries Added*\n👤 {user_email}\n{summary_text}')
        return True, f"Saved {len(results)} entries to your sheet: " + ", ".join(results)
    except Exception as e:
        return False, f"Failed to save entries: {str(e)}"

def add_debt_via_ai(name, type, amount, date=None):
    try:
        user_email = get_current_user_email()
        target_url = get_active_web_app_url()
        eng_name = translate_to_english_label(name, "Person")
        eng_type = "Lent" if "Lent" in str(type) or "കൊടുത്ത" in str(type) else "Borrowed"
        eng_date_str = " ".join(format_english_datetime(date).split(" ")[0:3])
        payload = {
            "action": "add_debt",
            "user_email": user_email,
            "name": eng_name,
            "type": eng_type,
            "amount": amount,
            "date": eng_date_str
        }
        if target_url:
            requests.post(target_url, json=payload, timeout=15)
            refresh_user_sheet_cache()
        send_whatsapp_auto(f"🤝 *AI Debt Added*\n👤 {user_email}\n🤝 Person: {eng_name}\n📌 Type: {eng_type}\n💰 Amt: ₹{amount}")
        return True, f"Debt saved to your sheet: {eng_type} - {eng_name} - ₹{amount}"
    except Exception as e:
        return False, f"Failed to save debt: {str(e)}"

tools = [
    {
        "type": "function",
        "function": {
            "name": "add_new_entry",
            "description": "Add a single expense or income in English when item and amount are clear",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Item name translated to clean English"},
                    "amount": {"type": "number"},
                    "category": {"type": "string", "description": "Food, Shop, Fish, Travel, Rent, Others"},
                    "type": {"type": "string", "enum": ["Debit", "Credit"]},
                    "date": {"type": "string", "description": "English date format e.g. 21 Nov 2026 20:47:00"}
                },
                "required": ["item", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_multiple_entries",
            "description": "Add multiple expenses in English",
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
            "description": "Add money lent or borrowed to Debt Tracker in English",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Person name in English"},
                    "type": {"type": "string", "enum": ["Lent", "Borrowed"]},
                    "amount": {"type": "number"},
                    "date": {"type": "string"}
                },
                "required": ["name", "type", "amount"]
            }
        }
    }
]

# --- 🔒 LOGIN, PERMANENT SINGLE-REGISTRATION SIGN UP & FORGOT PASSWORD (OTP) ---
if not st.session_state.auth:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.subheader("🔐 PAICHI EXPENSES")

        mode_tab1, mode_tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])

        with mode_tab1:
            l_user = st.text_input("📧 Email / Username", key="login_user", placeholder="Enter your email or username").strip().lower()
            l_pass = st.text_input("🔑 Password", type="password", key="login_pass", placeholder="Enter your password")

            if st.button("LOGIN 🔓", key="btn_login"):
                user_rec = db_get_user(l_user)
                if not l_user:
                    st.error("❌ Please enter your email or username.")
                elif not l_pass:
                    st.error("❌ Please enter your password.")
                elif not user_rec:
                    st.error("❌ Account not found. Please sign up first.")
                elif user_rec["password_hash"] == hash_password(l_pass):
                    ensure_user_has_sheet(l_user)
                    refresh_user_sheet_cache()
                    set_persistent_login(l_user)
                    st.rerun()
                else:
                    st.error("❌ Incorrect password.")

            with st.expander("🔄 Forgot Password (Email OTP)"):
                r_user = st.text_input("📧 Registered Email", key="reset_user", placeholder="Enter your registered email").strip().lower()

                if st.button("📩 Send Reset OTP", key="btn_send_reset_otp"):
                    if not r_user:
                        st.error("❌ Please enter your registered email.")
                    elif not db_get_user(r_user):
                        st.error("❌ No account found for this email.")
                    elif "@" not in r_user:
                        st.error("❌ A valid email address is required for OTP.")
                    else:
                        code = f"{random.randint(100000, 999999)}"
                        st.session_state.reset_otp = code
                        st.session_state.reset_otp_email = r_user
                        st.session_state.reset_otp_verified = False
                        try:
                            send_otp_email(r_user, code, purpose="Reset Password")
                            st.success("✅ 6-digit OTP sent to your email. Check Inbox or Spam.")
                        except Exception as e:
                            st.error(f"❌ Failed to send OTP: {e}")

                if st.session_state.reset_otp and st.session_state.reset_otp_email == r_user:
                    r_otp_in = st.text_input("🔢 Enter Reset OTP", key="reset_otp_input", max_chars=6, placeholder="6-digit OTP")
                    if st.button("✅ Verify Reset OTP", key="btn_verify_reset_otp"):
                        if r_otp_in.strip() == st.session_state.reset_otp:
                            st.session_state.reset_otp_verified = True
                            st.success("✅ OTP verified. Enter your new password.")
                        else:
                            st.error("❌ Invalid OTP.")

                if st.session_state.reset_otp_verified and st.session_state.reset_otp_email == r_user:
                    r_new_pass = st.text_input("🔑 New Password", type="password", key="reset_new_pass", placeholder="Enter new password")
                    r_confirm_pass = st.text_input("🔒 Confirm New Password", type="password", key="reset_confirm_pass", placeholder="Re-enter new password")

                    if st.button("RESET PASSWORD 🔁", key="btn_reset_pass"):
                        if not r_new_pass:
                            st.error("❌ Please enter a new password.")
                        elif r_new_pass != r_confirm_pass:
                            st.error("❌ Passwords do not match.")
                        else:
                            new_hash = db_update_password(r_user, r_new_pass)
                            st.session_state.reset_otp = None
                            st.session_state.reset_otp_email = ""
                            st.session_state.reset_otp_verified = False
                            st.success("✅ Password updated.")
                            st.code(f'"{r_user}": {{"password_hash": "{new_hash}"}}', language="json")

        with mode_tab2:
            st.caption("Each Google/Email account can be registered only once.")
            s_user = st.text_input("📧 Google / Email ID", key="signup_user", placeholder="example@gmail.com").strip().lower()

            if is_account_already_registered(s_user):
                st.error("❌ This Google/Email account is already registered and cannot be submitted again.")
            else:
                if st.button("📩 Send Sign Up OTP", key="btn_send_signup_otp"):
                    if not s_user or "@" not in s_user:
                        st.error("❌ Please enter a valid email address.")
                    elif is_account_already_registered(s_user):
                        st.error("❌ This Google/Email account is already registered and cannot be submitted again.")
                    else:
                        code = f"{random.randint(100000, 999999)}"
                        st.session_state.signup_otp = code
                        st.session_state.signup_otp_email = s_user
                        st.session_state.signup_otp_verified = False
                        try:
                            send_otp_email(s_user, code, purpose="Sign Up")
                            st.success("✅ 6-digit OTP sent to your email. Check Inbox or Spam.")
                        except Exception as e:
                            st.error(f"❌ Failed to send OTP: {e}")

                if st.session_state.signup_otp and st.session_state.signup_otp_email == s_user:
                    s_otp_in = st.text_input("🔢 Enter OTP", key="signup_otp_input", max_chars=6, placeholder="6-digit OTP")
                    if st.button("✅ Verify OTP", key="btn_verify_signup_otp"):
                        if s_otp_in.strip() == st.session_state.signup_otp:
                            st.session_state.signup_otp_verified = True
                            st.success("✅ OTP verified. Set your password to complete registration.")
                        else:
                            st.error("❌ Invalid OTP.")

                if st.session_state.signup_otp_verified and st.session_state.signup_otp_email == s_user:
                    s_pass = st.text_input("🔑 Create Password", type="password", key="signup_pass", placeholder="Create your password")
                    s_confirm = st.text_input("🔒 Confirm Password", type="password", key="signup_confirm", placeholder="Re-enter your password")

                    if st.button("COMPLETE SIGN UP ✨", key="btn_signup"):
                        if is_account_already_registered(s_user):
                            st.error("❌ This Google/Email account is already registered and cannot be submitted again.")
                        elif not s_pass:
                            st.error("❌ Please enter a password.")
                        elif s_pass != s_confirm:
                            st.error("❌ Passwords do not match.")
                        else:
                            created_entry = db_create_user(s_user, s_pass, "", "")
                            st.session_state.signup_otp = None
                            st.session_state.signup_otp_email = ""
                            st.session_state.signup_otp_verified = False
                            refresh_user_sheet_cache()
                            st.info("📌 Add this entry to `USERS_DATA` in Secrets to keep the account across reboots:")
                            st.code(json.dumps(created_entry, indent=2), language="json")
                            set_persistent_login(s_user)
                            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

else:
    user_profile = ensure_user_has_sheet(st.session_state.user) or {}
    active_csv = get_active_csv_url()
    active_debts_csv = get_active_debts_csv_url()
    df = load_data(active_csv)
    t_in, t_out = (df['Credit'].sum(), df['Debit'].sum()) if not df.empty else (0.0, 0.0)
    bal = t_in - t_out

    st.sidebar.caption(f"👤 {format_display_name(st.session_state.user)}")

    with st.sidebar.expander("⚙️ Settings"):
        if st.button("🔄 Sync Data"):
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
        if bal < st.session_state.low_limit:
            st.markdown(f'<div class="alert-banner">⚠️ Low Balance Alert: {st.session_state.custom_alert_text} (₹{bal:,.2f})!</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="balance-banner"><span style="font-size:22px; color:#E0B0FF; letter-spacing: 2px;">AVAILABLE BALANCE</span><br><span style="font-size:50px; color:#FFD700; font-family: monospace;">₹{bal:,.2f}</span></div>', unsafe_allow_html=True)
        st.title("Financial Overview")
        st.markdown(f'<div class="glass-card"><h2 style="color:#00FF00;">Credit: ₹{t_in:,.2f}</h2><h2 style="color:#FF3131;">Debit: ₹{t_out:,.2f}</h2></div>', unsafe_allow_html=True)

        if not df.empty and 'Item' in df.columns:
            def extract_cat(x):
                item_text = str(x).lower()
                if any(w in item_text for w in ["food", "tea", "coffee", "biryani", "ഭക്ഷണം", "ചായ", "ഹോട്ടൽ", "ബിരിയാണി"]): return "Food"
                elif any(w in item_text for w in ["shop", "store", "supermarket", "കട", "സാധനങ്ങൾ", "സൂപ്പർമാർക്കറ്റ്"]): return "Shop"
                elif any(w in item_text for w in ["fish", "meat", "chicken", "മീൻ", "ഇറച്ചി", "ചിക്കൻ"]): return "Fish"
                elif any(w in item_text for w in ["travel", "petrol", "fuel", "taxi", "യാത്ര", "പെട്രോൾ", "വണ്ടി", "ടാക്സി"]): return "Travel"
                elif any(w in item_text for w in ["rent", "room", "വാടക", "റൂം"]): return "Rent"
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
        v_raw = speech_to_text(language='ml-IN', key='voice_v9')
        v_cat, v_amt, v_desc, v_type = "Others", "", "", "Debit"

        if v_raw:
            raw = v_raw.lower().replace('.', '').replace(',', '')
            nums = re.findall(r'\d+', raw)
            v_amt = nums[0] if nums else ""
            raw_desc = re.sub(r'\d+', '', raw).strip()
            v_desc = translate_to_english_label(raw_desc, "Expense")
            if any(x in raw for x in ["food", "tea", "coffee", "biryani", "ഭക്ഷണം", "ചായ", "ഹോട്ടൽ", "ബിരിയാണി"]): v_cat = "Food"
            elif any(x in raw for x in ["shop", "കട"]): v_cat = "Shop"
            elif any(x in raw for x in ["fish", "chicken", "മീൻ", "ചിക്കൻ"]): v_cat = "Fish"
            elif any(x in raw for x in ["travel", "petrol", "പെട്രോൾ", "വണ്ടി"]): v_cat = "Travel"
            if any(x in raw for x in ["credit", "received", "salary", "കിട്ടി", "വന്നു", "തന്നു"]): v_type = "Credit"

        with st.form("entry_form", clear_on_submit=True):
            it = st.text_input("Description", value=v_desc)
            am_str = st.text_input("Amount", value=str(v_amt))
            cat = st.selectbox("Category", ["Food", "Shop", "Fish", "Travel", "Rent", "Others"], index=["Food", "Shop", "Fish", "Travel", "Rent", "Others"].index(v_cat))
            ty = st.radio("Type", ["Debit", "Credit"], horizontal=True, index=0 if v_type == "Debit" else 1)

            if st.form_submit_button("SAVE & NOTIFY"):
                try:
                    am = float(am_str.strip().replace(',', ''))
                    if not st.session_state.entry_saved_flag:
                        eng_it = translate_to_english_label(it, "Expense")
                        eng_dt = format_english_datetime()
                        target_url = get_active_web_app_url()
                        user_email = get_current_user_email()
                        payload = {
                            "action": "add_entry",
                            "user_email": user_email,
                            "item": eng_it,
                            "amount": am,
                            "category": cat,
                            "type": ty,
                            "date": eng_dt
                        }
                        if target_url:
                            requests.post(target_url, json=payload, timeout=15)
                            refresh_user_sheet_cache()
                        send_whatsapp_auto(f"✅ *Expense Entry*\n👤 {user_email}\n📝 {eng_it}\n💰 ₹{am}\n📅 {eng_dt}")

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

        st.markdown("""
            <style>
            .fc {
                background-color: #ffffff !important;
                color: #111111 !important;
                padding: 12px;
                border-radius: 14px;
            }
            .fc a, .fc-col-header-cell-cushion, .fc-daygrid-day-number {
                color: #111111 !important;
                text-decoration: none !important;
                font-weight: 600 !important;
            }
            .fc-toolbar-title {
                color: #111111 !important;
                font-weight: 700 !important;
            }
            .fc-button-primary {
                background-color: #e55353 !important;
                border-color: #e55353 !important;
                color: #ffffff !important;
                font-weight: 700 !important;
            }
            .fc-event {
                border: none !important;
                border-radius: 3px !important;
                font-size: 11px !important;
                font-weight: 700 !important;
                padding: 1px 3px !important;
                margin-top: 2px !important;
            }
            </style>
        """, unsafe_allow_html=True)

        if df.empty:
            st.info("No data available yet.")
        else:
            df_cal = df.dropna(subset=['Date']).copy()
            df_cal['DayKey'] = df_cal['Date'].dt.strftime('%Y-%m-%d')

            summary = (
                df_cal.groupby('DayKey', as_index=False)
                .agg({'Debit': 'sum', 'Credit': 'sum'})
            )

            events = []
            for _, row in summary.iterrows():
                if row['Debit'] > 0:
                    events.append({
                        "title": f"-₹{row['Debit']:,.0f}",
                        "start": row['DayKey'],
                        "backgroundColor": "#d9383a",
                        "borderColor": "#d9383a",
                        "textColor": "#ffffff"
                    })
                if row['Credit'] > 0:
                    events.append({
                        "title": f"+₹{row['Credit']:,.0f}",
                        "start": row['DayKey'],
                        "backgroundColor": "#2e8b57",
                        "borderColor": "#2e8b57",
                        "textColor": "#ffffff"
                    })

            calendar_options = {
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth"
                },
                "initialView": "dayGridMonth",
                "height": "auto",
                "dayMaxEvents": True
            }

            cal_data = calendar(
                events=events,
                options=calendar_options,
                key="pnl_calendar_view"
            )

            selected_date = None
            if cal_data:
                if cal_data.get("callback") == "eventClick":
                    ev = cal_data.get("eventClick", {}).get("event", {})
                    selected_date = ev.get("start", "").split("T")[0]
                elif cal_data.get("callback") == "dateClick":
                    dt_obj = cal_data.get("dateClick", {}).get("date", "")
                    selected_date = dt_obj.split("T")[0]

            if selected_date:
                st.markdown("---")
                try:
                    pretty_dt = pd.to_datetime(selected_date).strftime('%d %b %Y')
                except Exception:
                    pretty_dt = selected_date

                st.subheader(f"📋 Details for {pretty_dt}")
                day_df = df_cal[df_cal['DayKey'] == selected_date].copy()
                if not day_df.empty:
                    day_df['Date'] = day_df['Date'].dt.strftime('%d %b %Y')
                    st.dataframe(day_df[['Date', 'Item', 'Debit', 'Credit']], use_container_width=True)
                else:
                    st.info("No entries found for this date.")

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
                clean_df['Date'] = clean_df['Date'].dt.strftime('%d %b %Y')
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
        st.title("🤝 Debt Tracker")
        df_debts = load_debts_data(active_debts_csv)

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
            col_a.markdown(f'<div class="glass-card"><h4 style="color:#00FF00;">Total Lent (Receivable)</h4><h2 style="color:#00FF00;">₹{total_lent:,.2f}</h2></div>', unsafe_allow_html=True)
            col_b.markdown(f'<div class="glass-card"><h4 style="color:#FF3131;">Total Borrowed (Payable)</h4><h2 style="color:#FF3131;">₹{total_borrowed:,.2f}</h2></div>', unsafe_allow_html=True)

            st.markdown("---")

            if df_debts.empty or len(df_debts[df_debts['Status'] == "Pending"]) == 0:
                st.info("No pending debts available.")
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
                                payload = {
                                    "action": "settle_debt",
                                    "user_email": get_current_user_email(),
                                    "id": debt['ID']
                                }
                                if target_url:
                                    requests.post(target_url, json=payload, timeout=15)
                                    refresh_user_sheet_cache()
                                st.success(f"Settled debt for {debt['Name']}.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        st.markdown("<hr style='margin: 5px 0; border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)

        with tab2:
            st.subheader("Add New Debt Entry")
            with st.form("cloud_debt_form", clear_on_submit=True):
                d_name = st.text_input("👤 Person Name")
                d_type = st.selectbox("📌 Transaction Type", ["Lent", "Borrowed"])
                d_amount = st.number_input("💰 Amount (₹)", min_value=1.0, step=10.0)
                d_date = st.date_input("📅 Date", value=datetime.now(GST).date())

                if st.form_submit_button("SAVE TO GOOGLE SHEET 💾"):
                    if not d_name.strip():
                        st.error("Please enter a person name.")
                    else:
                        try:
                            eng_d_name = translate_to_english_label(d_name.strip(), "Person")
                            eng_d_date = d_date.strftime("%d %b %Y")
                            target_url = get_active_web_app_url()
                            user_email = get_current_user_email()
                            payload = {
                                "action": "add_debt",
                                "user_email": user_email,
                                "name": eng_d_name,
                                "type": d_type,
                                "amount": d_amount,
                                "date": eng_d_date
                            }
                            if target_url:
                                requests.post(target_url, json=payload, timeout=15)
                                refresh_user_sheet_cache()
                            send_whatsapp_auto(f"🤝 *New Debt Saved*\n👤 {user_email}\n🤝 Person: {eng_d_name}\n📌 Type: {d_type}\n💰 Amt: ₹{d_amount}")

                            st.success("Debt saved successfully! ✅")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save: {e}")

        with tab3:
            st.subheader("Settled History")
            if df_debts.empty or len(df_debts[df_debts['Status'] == "Settled"]) == 0:
                st.info("No settled records available.")
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
        user_input = st.chat_input("Ask me anything in English, Malayalam, Arabic, or Hindi...", key="buddy_chat_box")
        if user_input:
            st.session_state.buddy_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"): st.markdown(user_input)
            with st.spinner("Thinking..."):
                try:
                    client = Groq(api_key=GROQ_API_KEY)
                    system_prompt = (
                        "You are a helpful personal AI assistant. Understand user messages in English, Malayalam, Arabic, or Hindi, "
                        "but ALWAYS reply clearly and politely in English."
                    )
                    messages = [{"role": "system", "content": system_prompt}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.buddy_messages[-4:]]
                    response = client.chat.completions.create(model="openai/gpt-oss-120b", messages=messages, max_tokens=1024)
                    ai_reply = response.choices[0].message.content
                    st.session_state.buddy_messages.append({"role": "assistant", "content": ai_reply})
                    with st.chat_message("assistant"): st.markdown(ai_reply)
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- AI CHAT (Clear Malayalam/Multilingual Voice + Transcript + Context + Single Confirmation Box) ---
    elif page == "🤖 AI Chat":
        st.title("🤖 AI Agent & Assistant")

        if st.session_state.ai_action_notice:
            st.success(st.session_state.ai_action_notice)

        if st.session_state.last_heard_text:
            st.caption(f"🎙️ Heard: {st.session_state.last_heard_text}")

        for h_msg in st.session_state.ai_chat_history[-6:]:
            with st.chat_message(h_msg["role"]):
                st.markdown(h_msg["content"])

        if st.session_state.pending_entry:
            p_item = st.session_state.pending_entry["item"]
            p_amt = st.session_state.pending_entry["amount"]
            p_date = st.session_state.pending_entry["date"]

            st.info(f"**Confirm Entry:** {p_item} - ₹{p_amt} ({p_date}). Save this entry to sheet?")
            col1, col2 = st.columns(2)

            if col1.button("Yes", key="save_entry_btn"):
                entry_data = st.session_state.pending_entry
                st.session_state.pending_entry = None
                st.session_state.last_processed_prompt = None
                st.session_state.last_voice_text = ""
                ok, status_msg = add_new_entry(
                    item=entry_data['item'],
                    amount=entry_data['amount'],
                    category=entry_data['category'],
                    type=entry_data['type'],
                    entry_date=entry_data['date']
                )
                st.session_state.ai_action_notice = status_msg if ok else f"Not saved: {status_msg}"
                st.session_state.ai_chat_history.append({"role": "assistant", "content": st.session_state.ai_action_notice})
                st.rerun()

            if col2.button("No", key="cancel_entry_btn"):
                cancelled_item = st.session_state.pending_entry["item"]
                cancelled_amt = st.session_state.pending_entry["amount"]
                st.session_state.pending_entry = None
                st.session_state.last_processed_prompt = None
                st.session_state.last_voice_text = ""
                st.session_state.ai_action_notice = f"Not saved to sheet: {cancelled_item} - ₹{cancelled_amt} (Cancelled)."
                st.session_state.ai_chat_history.append({"role": "assistant", "content": st.session_state.ai_action_notice})
                st.rerun()

        v_col, _ = st.columns([1.4, 2.6])
        with v_col:
            v_raw = speech_to_text(
                language='ml-IN',
                start_prompt="🎙️ Speak (ML / EN)",
                stop_prompt="⏹️ Stop",
                just_once=True,
                key=f'ai_voice_input_{st.session_state.ai_chat_key_id}'
            )

        prompt = st.chat_input("Type or speak in Malayalam, English, Arabic, or Hindi...", key="ai_chat_box")

        final_prompt = None
        if v_raw and v_raw.strip() and v_raw.strip() != st.session_state.last_voice_text:
            st.session_state.last_voice_text = v_raw.strip()
            st.session_state.last_heard_text = v_raw.strip()
            st.session_state.ai_chat_key_id += 1
            final_prompt = v_raw.strip()
        elif prompt and prompt.strip():
            st.session_state.last_heard_text = prompt.strip()
            final_prompt = prompt.strip()

        if final_prompt:
            clean_cmd = final_prompt.lower().strip()

            if clean_cmd in ["yes", "y", "yep", "ya", "ok", "okay", "അതെ", "ശരി", "نعم", "हां"] and st.session_state.pending_entry:
                entry_data = st.session_state.pending_entry
                st.session_state.pending_entry = None
                st.session_state.last_processed_prompt = None
                st.session_state.last_voice_text = ""
                ok, status_msg = add_new_entry(
                    item=entry_data['item'],
                    amount=entry_data['amount'],
                    category=entry_data['category'],
                    type=entry_data['type'],
                    entry_date=entry_data['date']
                )
                st.session_state.ai_action_notice = status_msg if ok else f"Not saved: {status_msg}"
                st.session_state.ai_chat_history.append({"role": "user", "content": final_prompt})
                st.session_state.ai_chat_history.append({"role": "assistant", "content": st.session_state.ai_action_notice})
                st.rerun()

            elif clean_cmd in ["no", "n", "nope", "cancel", "അല്ല", "വേണ്ട", "لا", "नहीं"] and st.session_state.pending_entry:
                cancelled_item = st.session_state.pending_entry["item"]
                cancelled_amt = st.session_state.pending_entry["amount"]
                st.session_state.pending_entry = None
                st.session_state.last_processed_prompt = None
                st.session_state.last_voice_text = ""
                st.session_state.ai_action_notice = f"Not saved to sheet: {cancelled_item} - ₹{cancelled_amt} (Cancelled)."
                st.session_state.ai_chat_history.append({"role": "user", "content": final_prompt})
                st.session_state.ai_chat_history.append({"role": "assistant", "content": st.session_state.ai_action_notice})
                st.rerun()

            else:
                st.session_state.ai_action_notice = None
                st.session_state.ai_chat_history.append({"role": "user", "content": final_prompt})
                with st.spinner("Processing..."):
                    try:
                        today_str = datetime.now(GST).strftime('%Y-%m-%d')
                        today_deb = 0.0
                        today_crd = 0.0
                        if not df.empty and 'Date' in df.columns:
                            d_valid = df.dropna(subset=['Date'])
                            t_rows = d_valid[d_valid['Date'].dt.strftime('%Y-%m-%d') == today_str]
                            if not t_rows.empty:
                                today_deb = float(t_rows['Debit'].sum())
                                today_crd = float(t_rows['Credit'].sum())

                        client = Groq(api_key=GROQ_API_KEY)
                        eng_now = format_english_datetime()
                        system_instruction = (
                            f"You are a sharp, accurate English finance AI assistant. Current time (GST): {eng_now}. "
                            f"Available balance: ₹{bal:,.2f}. Total Credit: ₹{t_in:,.2f}, Total Debit: ₹{t_out:,.2f}. "
                            f"Today's Credit: ₹{today_crd:,.2f}, Today's Debit: ₹{today_deb:,.2f}. "
                            f"Understand short or casual speech/text in Malayalam, English, Arabic, or Hindi, even if voice transcription has minor typos, "
                            f"and ALWAYS respond clearly and concisely in English. "
                            f"When the user asks for balance or today's balance, clearly state the Available Balance (₹{bal:,.2f}) and today's summary. "
                            f"Accurately interpret Malayalam/Arabic/Hindi/English expense words and numbers (for example 'ചായ മൂന്ന്' -> item 'Tea', amount 3; "
                            f"'ജയയ്ക്ക് 500 കൊടുത്തു' -> debt lent to 'Jaya', amount 500). "
                            f"Do NOT invent weird names or ask unnecessary follow-up questions when an expense item and amount are clear. "
                            f"When money is lent or borrowed, call 'add_debt_entry'."
                        )

                        recent_ctx = [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.ai_chat_history[-5:-1]
                        ]
                        messages_for_api = [
                            {"role": "system", "content": system_instruction},
                            *recent_ctx,
                            {"role": "user", "content": final_prompt},
                        ]

                        response = client.chat.completions.create(
                            model="openai/gpt-oss-120b",
                            messages=messages_for_api,
                            tools=tools,
                            tool_choice="auto",
                            max_tokens=1024
                        )

                        msg = response.choices[0].message

                        if msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                fn_name = tool_call.function.name
                                args = json.loads(tool_call.function.arguments or "{}")

                                if fn_name == "add_new_entry":
                                    st.session_state.pending_entry = {
                                        "item": translate_to_english_label(args.get("item", "Expense"), "Expense"),
                                        "amount": float(args.get("amount", 0)),
                                        "category": translate_to_english_label(args.get("category", "Others"), "Others"),
                                        "type": args.get("type", "Debit"),
                                        "date": format_english_datetime(args.get("date"))
                                    }
                                    st.rerun()

                                elif fn_name == "add_multiple_entries":
                                    ok, status_msg = add_multiple_entries(args.get("entries_list", []))
                                    st.session_state.ai_action_notice = status_msg if ok else f"Not saved: {status_msg}"
                                    st.session_state.ai_chat_history.append({"role": "assistant", "content": st.session_state.ai_action_notice})
                                    st.rerun()

                                elif fn_name == "add_debt_entry":
                                    ok, status_msg = add_debt_via_ai(
                                        name=args.get("name", "Person"),
                                        type=args.get("type", "Lent"),
                                        amount=float(args.get("amount", 0)),
                                        date=args.get("date")
                                    )
                                    st.session_state.ai_action_notice = status_msg if ok else f"Not saved: {status_msg}"
                                    st.session_state.ai_chat_history.append({"role": "assistant", "content": st.session_state.ai_action_notice})
                                    st.rerun()
                        else:
                            ai_reply = (msg.content or "").strip() or "How can I help you?"
                            st.session_state.ai_chat_history.append({"role": "assistant", "content": ai_reply})
                            st.rerun()

                    except Exception as e:
                        st.error(f"Error: {e}")
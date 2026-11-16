import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import random
import plotly.express as px
from streamlit_mic_recorder import speech_to_text
from streamlit_autorefresh import st_autorefresh
import json
from groq import Groq
from streamlit_calendar import calendar
from twilio.rest import Client

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="PAICHI EXPENSES v6.0", layout="wide")

# --- CONFIG & SETTINGS ---
CSV_URL = st.secrets.get("GOOGLE_SHEET_CSV", "")
WEB_APP_URL = st.secrets.get("APPS_SCRIPT_URL", "")

WA_PHONE = "971551347989"
USER_PINS = {
    "faisal": st.secrets.get("PIN_FAISAL", ""),
    "shabana": st.secrets.get("PIN_SHABANA", ""),
    "admin": st.secrets.get("PIN_ADMIN", "")
}
BG_IMAGE_URL = "https://raw.githubusercontent.com/paichiarakkal/paichiarakkal/main/profile.jpg"

st_autorefresh(interval=60000, key="auto_refresh")

st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: linear-gradient(rgba(0, 0, 0, 0.75), rgba(0, 0, 0, 0.75)), url("{BG_IMAGE_URL}");
        background-size: cover;
        background-attachment: fixed;
    }}
    [data-testid="stSidebar"] {{
        background: rgba(0, 0, 0, 0.85) !important;
    }}
    
    /* 3D Floating Cards & Glassmorphism */
    .purple-box {{
        background: linear-gradient(135deg, rgba(20, 20, 30, 0.8), rgba(40, 40, 60, 0.9));
        padding: 25px;
        border-radius: 20px;
        border: 2px solid rgba(255, 215, 0, 0.4);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5), inset 0 0 15px rgba(255, 215, 0, 0.1);
        transform: perspective(1000px) rotateX(2deg);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        text-align: center;
        margin-bottom: 25px;
    }}
    .purple-box:hover {{
        transform: perspective(1000px) rotateX(0deg) scale(1.02);
        box-shadow: 0 20px 40px rgba(255, 215, 0, 0.3);
    }}
    
    /* 3D Glowing Buttons */
    .stButton>button {{
        background: linear-gradient(135deg, #FFD700, #FFA500);
        color: #000;
        border-radius: 12px;
        font-weight: bold;
        padding: 10px 20px;
        box-shadow: 0 8px 20px rgba(255, 215, 0, 0.4);
        border: none;
        width: 100%;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 25px rgba(255, 215, 0, 0.6);
    }}
    
    .login-card {{
        background: rgba(0, 0, 0, 0.85);
        padding: 30px;
        border-radius: 20px;
        max-width: 450px;
        margin: auto;
        margin-top: 50px;
        border: 2px solid rgba(255, 215, 0, 0.3);
    }}
    h1, h2, h3, p, label {{
        color: white !important;
        font-weight: bold !important;
    }}
    
    [data-testid="stChatMessage"] {{
        background-color: #202c33 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        margin-bottom: 8px !important;
        border: none !important;
    }}
    [data-testid="stChatInput"] {{
        background-color: #2a3942 !important;
        border-radius: 24px !important;
        border: 1px solid #2a3942 !important;
        padding: 5px !important;
    }}
    [data-testid="stChatInput"] textarea {{
        color: white !important;
    }}
    input, textarea, select {{
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }}
    </style>
""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth, st.session_state.user = False, ""

# --- HELPER FUNCTIONS ---
def send_whatsapp_auto(msg):
    try:
        account_sid = st.secrets.get("TWILIO_ACCOUNT_SID", "")
        auth_token = st.secrets.get("TWILIO_AUTH_TOKEN", "")
        if account_sid and auth_token:
            client = Client(account_sid, auth_token)
            client.messages.create(from_='whatsapp:+14155238886', body=msg, to=f'whatsapp:+{WA_PHONE}')
    except: pass 

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
        if not CSV_URL: return pd.DataFrame()
        df = pd.read_csv(f"{CSV_URL}&r={random.randint(1,999)}")
        df.columns = df.columns.str.strip()
        df['Date'] = parse_mixed_dates(df['Date'])
        df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

def add_new_entry(item, amount, category="Others", type="Debit", entry_date=None):
    try:
        if not entry_date: entry_date = datetime.now().strftime("%Y-%m-%d")
        payload = {
            "item": item, "amount": amount, "category": category,
            "type": type, "date": entry_date, "sender": st.session_state.user.capitalize()
        }
        requests.post(WEB_APP_URL, json=payload, timeout=10)
        send_whatsapp_auto(f"✅ *AI Entry Added*\n📝 Item: {item}\n💰 Amt: ₹{amount}")
        load_data.clear()
        return f"Success: {item} - ₹{amount} ({type}) on {entry_date}"
    except Exception as e: return f"Error: {str(e)}"

def add_multiple_entries(entries_list):
    results = []
    try:
        for entry in entries_list:
            item = entry.get('item', 'Unknown')
            amount = entry.get('amount', 0)
            category = entry.get('category', 'Others')
            entry_type = entry.get('type', 'Debit')
            entry_date = entry.get('date', datetime.now().strftime('%Y-%m-%d'))
            payload = {
                "item": item, "amount": amount, "category": category,
                "type": entry_type, "date": entry_date, "sender": st.session_state.user.capitalize()
            }
            requests.post(WEB_APP_URL, json=payload, timeout=10)
            results.append(f'{item} - ₹{amount}')
        send_whatsapp_auto(f'✅ *AI Multi-Entries Added*\n' + '\n'.join([f'• {r}' for r in results]))
        load_data.clear()
        return f'Success: Added {len(results)} items.'
    except Exception as e: return f'Error: {str(e)}'

tools = [
    {
        "type": "function",
        "function": {
            "name": "add_new_entry",
            "description": "Add a single expense or income to Google Sheet ONLY after user confirms with Yes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "amount": {"type": "number"},
                    "category": {"type": "string", "description": "Food, Shop, Fish, Travel, Rent, Others"},
                    "type": {"type": "string", "enum": ["Debit", "Credit"]},
                    "date": {"type": "string"}
                },
                "required": ["item", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_multiple_entries",
            "description": "Add multiple expenses or incomes to Google Sheet ONLY after user confirms with Yes.",
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
    }
]

def run_ai_expense_agent(user_text, bal):
    client = Groq(api_key=GROQ_API_KEY)
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    system_instruction = f"""
You are PAICHI EXPENSES v6.0, a strict financial AI assistant for tracking expenses and income only. 
Current time: {utc_now}. Current Balance: ₹{bal:,.2f}. 

Strict Instructions:
1. Detect the user's language (Malayalam, English, Hindi, Arabic, etc.) and ALWAYS reply in the SAME language.
2. ONLY discuss expenses, income, budgets, and financial records. NEVER talk about lotteries, games, or unrelated topics.
3. If the user mentions an expense or income (e.g., 'tea 10', 'ബിരിയാണി 150'), do NOT call the tool immediately.
"""
    messages_for_api = [{"role": "system", "content": system_instruction}] + [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-6:]
    ] + [{"role": "user", "content": user_text}]

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages_for_api,
        tools=tools,
        tool_choice="auto",
        max_tokens=1024
    )

    response_message = response.choices[0].message
    entry_saved = False
    ai_reply = ""

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name == 'add_new_entry':
                args = json.loads(tool_call.function.arguments)
                result = add_new_entry(
                    item=args.get("item"), amount=args.get("amount"),
                    category=args.get("category", "Others"), type=args.get("type", "Debit"),
                    entry_date=args.get("date")
                )
                if "Success" in result:
                    ai_reply = f"✅ Added '{args.get('item')}' (₹{args.get('amount')}) to Google Sheet!"
                    entry_saved = True
                else: ai_reply = f"❌ {result}"

            elif tool_call.function.name == 'add_multiple_entries':
                args = json.loads(tool_call.function.arguments)
                result = add_multiple_entries(entries_list=args.get('entries_list', []))
                if 'Success' in result:
                    ai_reply = '✅ All entries successfully added to Google Sheet!'
                    entry_saved = True
                else: ai_reply = f'❌ {result}'
    elif response_message.content:
        ai_reply = response_message.content
    else:
        ai_reply = "Sorry, I couldn't understand."

    return ai_reply, entry_saved

# --- LOGIN SCREEN ---
if not st.session_state.auth:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.subheader("🔐 PAICHI EXPENSES LOGIN")
    u = st.selectbox("👤 Select User", ["faisal", "shabana", "admin"]).lower()
    pin = st.text_input("🔑 Enter 4-Digit PIN", type="password", max_chars=4)
    if st.button("UNLOCK APP 🔓"):
        if USER_PINS.get(u) == pin:
            st.session_state.auth, st.session_state.user = True, u
            st.rerun()
        else: st.error("❌ Incorrect PIN!")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    df = load_data()
    t_in, t_out = (df['Credit'].sum(), df['Debit'].sum()) if not df.empty else (0.0, 0.0)
    bal = t_in - t_out
    
    menu = ["🏠 Dashboard", "💰 Add Entry", "📅 Calendar", "📊 Report", "🔍 History", "🤝 Debt Tracker", "🤖 AI Chat", "🧠 My AI Buddy"]
    page = st.sidebar.radio("Menu", menu)
    if st.sidebar.button("Logout"): st.session_state.auth = False; st.rerun()

    # --- DASHBOARD ---
    if page == "🏠 Dashboard":
        st.title("Financial Overview")
        st.markdown(f'<div class="purple-box"><h2 style="color:#00FF00;">Credit: ₹{t_in:,.2f}</h2><h2 style="color:#FF3131;">Debit: ₹{t_out:,.2f}</h2><h3 style="color:#FFD700;">Balance: ₹{bal:,.2f}</h3></div>', unsafe_allow_html=True)

    # --- ADD ENTRY ---
    elif page == "💰 Add Entry":
        st.title("Smart Voice Entry 🎙️")
        st.write("Click the mic below to speak your expense:")
        voice_text = speech_to_text(language='ml', key='voice_add_entry')
        if voice_text: st.info(f"🎙️ Heard: {voice_text}")
        
        with st.form("entry_form", clear_on_submit=True):
            it = st.text_input("Description", value=voice_text if voice_text else "")
            am_str = st.text_input("Amount")
            cat = st.selectbox("Category", ["Food", "Shop", "Fish", "Travel", "Rent", "Others"])
            ty = st.radio("Type", ["Debit", "Credit"], horizontal=True)
            if st.form_submit_button("SAVE & NOTIFY"):
                try:
                    am = float(am_str.strip().replace(',', ''))
                    add_new_entry(it, am, cat, ty, datetime.now().strftime("%Y-%m-%d"))
                    st.success("Saved! ✅"); st.rerun()
                except Exception as e: st.error(f"Error! {e}")

    # --- CALENDAR ---
    elif page == "📅 Calendar":
        st.title("P&L Calendar View 📅")
        if not df.empty:
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
                    day_df = df_cal[df_cal['Date'].dt.strftime('%Y-%m-%d'] == dt_click].copy()
                    if not day_df.empty:
                        day_df['Date'] = day_df['Date'].dt.strftime('%d/%m/%Y')
                        st.dataframe(day_df[['Date', 'Item', 'Debit', 'Credit']], use_container_width=True)
        else:
            st.info("No data available for calendar.")

    # --- REPORT & HISTORY ---
    elif page == "📊 Report" or page == "🔍 History":
        st.title("Reports & History")
        if not df.empty:
            st.dataframe(df.iloc[::-1], use_container_width=True)
        else:
            st.info("No data found.")

    # --- DEBT TRACKER ---
    elif page == "🤝 Debt Tracker":
        st.title("🤝 Debt Tracker")
        st.info("Coming soon!")

    # --- MY AI BUDDY ---
    elif page == "🧠 My AI Buddy":
        st.title("🧠 Your Personal AI Buddy")
        st.write("Ask me anything in Malayalam or English.")
        if "buddy_messages" not in st.session_state: st.session_state.buddy_messages = []
        for msg in st.session_state.buddy_messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        user_input = st.chat_input("Ask me anything...", key="buddy_chat_box")
        if user_input:
            st.session_state.buddy_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"): st.markdown(user_input)
            client = Groq(api_key=GROQ_API_KEY)
            resp = client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": user_input}])
            ai_reply = resp.choices[0].message.content
            st.session_state.buddy_messages.append({"role": "assistant", "content": ai_reply})
            st.rerun()

    # --- AI CHAT (MULTILINGUAL WITH VOICE & YES/NO BUTTONS) ---
    elif page == "🤖 AI Chat":
        st.title("🤖 Multilingual AI Agent")
        st.write("You can chat or use voice in Malayalam, English, Arabic, or Hindi.")
        
        ai_voice_input = speech_to_text(language='ml', key='ai_chat_voice')

        if "messages" not in st.session_state: st.session_state.messages = []

        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()

        for message in st.session_state.messages:
            with st.chat_message(message["role"]): st.markdown(message["content"])

        # --- YES / NO QUICK ACTION BUTTONS ---
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
            col_y, col_n = st.columns(2)
            with col_y:
                if st.button("✅ YES", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": "Yes"})
                    with st.spinner("Saving..."):
                        try:
                            ai_reply, _ = run_ai_expense_agent("Yes", bal)
                            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                        except Exception as e: st.error(f"Error: {e}")
                    st.rerun()
            with col_n:
                if st.button("❌ NO", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": "No"})
                    st.session_state.messages.append({"role": "assistant", "content": "❌ Cancelled."})
                    st.rerun()

        prompt = st.chat_input("Type in any language or use voice above...")

        if ai_voice_input and not prompt:
            prompt = ai_voice_input

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.spinner("Thinking..."):
                try:
                    ai_reply, _ = run_ai_expense_agent(prompt, bal)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                except Exception as e: st.error(f"Error: {e}")
            st.rerun()
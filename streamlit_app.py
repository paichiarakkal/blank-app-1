import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import random
import plotly.express as px
from fpdf import FPDF
import json
from groq import Groq # 👈 പുതിയത്

# --- CONFIG ---
CSV_URL = "YOUR_FINANCE_SHEET_CSV_LINK"
FORM_API = "YOUR_FINANCE_FORM_API"
STOCK_CSV_URL = "YOUR_STOCK_SHEET_CSV_LINK"
STOCK_FORM_API = "YOUR_STOCK_FORM_API"

USER_PINS = {"admin": "1234", "shop1": "1111"}
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

# --- SAFE FORM SUBMIT (Demo-safe) ---
def submit_form(api_url, payload):
    if not api_url or "YOUR_" in api_url:
        return True  # 🎭 Demo mode: simulate success
    try:
        r = requests.post(api_url, data=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        st.error(f"❌ Submission failed: {e}")
        return False

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="PAICHI BUSINESS", layout="wide")

st.markdown("""
    <style>
    /* ബാക്ക്ഗ്രൗണ്ട് ഇളം നിറമാക്കി മാറ്റി */
    .stApp { background: #f4f6f9; color: #000000; }
    [data-testid="stSidebar"] { background: #e0e0e0 !important; }
    
    .stButton>button { background-color: #007BFF; color: #ffffff; border-radius: 10px; font-weight: bold; }
    .stDownloadButton>button { background-color: #28a745; color: #ffffff; border-radius: 10px; font-weight: bold; }
    
    /* ബാനർ ഡിസൈൻ */
    .banner { background: #ffffff; padding: 25px; border-radius: 15px; border-left: 10px solid #007BFF; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    
    /* എഴുത്തുകളുടെ നിറം കറുപ്പ് (Dark) ആക്കി മാറ്റി */
    h1, h2, h3, p, label, span { color: #000000 !important; font-weight: bold !important; }
    
    /* ചാറ്റ് ബോക്സ് ഡിസൈൻ */
    [data-testid="stChatMessage"] { background-color: #ffffff !important; border-radius: 10px; padding: 15px; border: 1px solid #ccc; color: #000; }
    
    /* ബാലൻസ് കാണിക്കുന്ന ബാനറിലെ എഴുത്തുകൾക്ക് നിറം */
    .banner span { color: #007BFF !important; }
    </style>
""", unsafe_allow_html=True)
if 'auth' not in st.session_state:
    st.session_state.auth, st.session_state.user = False, ""
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- HELPER: Safe CSV load ---
def _append_cache_buster(url):
    if not url or "YOUR_" in url:
        raise ValueError("placeholder")
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}r={random.randint(1,999)}"

@st.cache_data(ttl=5)
def load_finance_data():
    try:
        df = pd.read_csv(_append_cache_buster(CSV_URL))
        df.columns = df.columns.str.strip()
        df['Debit'] = pd.to_numeric(df['Debit'], errors='coerce').fillna(0)
        df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame({
            'Date': ['2026-11-01', '2026-11-02', '2026-11-03', '2026-11-04'],
            'Shop Name': ['Shop 1', 'Shop 2', 'Shop 1', 'Shop 2'],
            'Item': ['Sales', 'Sales', 'Salary: Rahim', 'Rent'],
            'Debit': [0, 0, 2500, 5000],
            'Credit': [4500, 6000, 0, 0]
        })

@st.cache_data(ttl=5)
def load_stock_data():
    try:
        df = pd.read_csv(_append_cache_buster(STOCK_CSV_URL))
        df.columns = df.columns.str.strip()
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame({
            'Date': ['2026-11-01', '2026-11-02', '2026-11-03'],
            'Item': ['Sugar', 'Sugar', 'Milk'],
            'Quantity': [100, 20, 50],
            'Type': ['Stock In', 'Stock Out', 'Stock In']
        })

def generate_pdf(df, title, columns):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, txt=title, ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    col_width = 190 / len(columns)
    for col in columns:
        pdf.cell(col_width, 10, txt=str(col), border=1, align='C')
    pdf.ln()
    pdf.set_font("Arial", size=9)
    for _, row in df.iterrows():
        for col in columns:
            val = str(row[col]).encode('ascii', 'ignore').decode('ascii')
            pdf.cell(col_width, 10, txt=val, border=1)
        pdf.ln()
    return bytes(pdf.output())

# ============================================
# 🤖 AI AGENT TOOLS
# ============================================
tools = [
    {
        "type": "function",
        "function": {
            "name": "add_finance",
            "description": "ഒരു പുതിയ സാമ്പത്തിക ഇടപാട് (Debit/Credit) ചേർക്കുക.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shop": {"type": "string", "enum": ["Shop 1", "Shop 2"]},
                    "item": {"type": "string", "description": "ഇടപാടിന്റെ വിവരണം"},
                    "amount": {"type": "number"},
                    "type": {"type": "string", "enum": ["Debit", "Credit"]}
                },
                "required": ["shop", "item", "amount", "type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_stock",
            "description": "സ്റ്റോക്കിൽ പുതിയ സാധനങ്ങൾ ചേർക്കുകയോ കുറയ്ക്കുകയോ ചെയ്യുക.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string"},
                    "qty": {"type": "number"},
                    "stock_type": {"type": "string", "enum": ["Stock In", "Stock Out"]}
                },
                "required": ["item_name", "qty", "stock_type"]
            }
        }
    }
]

def execute_add_finance(shop, item, amount, t_type):
    payload = {
        "entry.1044099436": datetime.now().strftime("%Y-%m-%d"),
        "entry.2013476337": f"[{shop}] {item}",
        "entry.1460982454": amount if t_type == "Debit" else 0,
        "entry.1221658767": 0 if t_type == "Debit" else amount
    }
    if submit_form(FORM_API, payload):
        st.cache_data.clear()
        return "Success"
    return "Failed"

def execute_add_stock(item_name, qty, stock_type):
    payload = {
        "entry.1044099436": datetime.now().strftime("%Y-%m-%d"),
        "entry.2013476337": item_name,
        "entry.1460982454": qty,
        "entry.1221658767": stock_type
    }
    if submit_form(STOCK_FORM_API, payload):
        st.cache_data.clear()
        return "Success"
    return "Failed"

# --- 🔒 LOGIN ---
if not st.session_state.auth:
    st.markdown('<div style="max-width:400px; margin:auto; margin-top:100px; background:rgba(0,0,0,0.8); padding:30px; border-radius:20px;">', unsafe_allow_html=True)
    st.subheader("🔐 PAICHI BUSINESS LOGIN")
    u = st.selectbox("👤 Select Role", ["admin", "shop1"]).lower()
    pin = st.text_input("🔑 Enter PIN (admin:1234, shop1:1111)", type="password", max_chars=4)
    if st.button("LOGIN"):
        if USER_PINS.get(u) == pin:
            st.session_state.auth, st.session_state.user = True, u
            st.rerun()
        else:
            st.error("❌ Incorrect PIN!")
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.sidebar.title(f"👋 Welcome, {st.session_state.user.capitalize()}")
    # 👈 മെനുവിൽ AI Agent ചേർത്തു
    menu = ["📊 Dashboard", "💰 Add Finance", "📦 Stock Management", "👨‍💼 Staff Salary", "🤖 AI Agent"]
    page = st.sidebar.radio("Menu", menu)

    if st.sidebar.button("Logout"):
        st.session_state.auth = False
        st.session_state.messages = []
        st.rerun()

    df_fin = load_finance_data()
    df_stk = load_stock_data()
    t_in, t_out = df_fin['Credit'].sum(), df_fin['Debit'].sum()
    bal = t_in - t_out

    # --- 1. DASHBOARD ---
    if page == "📊 Dashboard":
        st.markdown(f'<div class="banner"><span style="font-size:20px; color:#00BFFF;">Total Business Balance</span><br><span style="font-size:40px; color:#FFF;">₹{bal:,.2f}</span></div>', unsafe_allow_html=True)
        st.subheader("📈 Shop-wise Performance")
        if not df_fin.empty:
            shop_data = df_fin.groupby('Shop Name')[['Credit', 'Debit']].sum().reset_index()
            fig = px.bar(shop_data, x='Shop Name', y=['Credit', 'Debit'], barmode='group',
                         color_discrete_sequence=['#00FF00', '#FF3131'], title="Credit vs Debit")
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("📋 Recent Transactions")
            st.dataframe(df_fin.tail(10).iloc[::-1], use_container_width=True)

    # --- 2. ADD FINANCE ---
    elif page == "💰 Add Finance":
        st.title("💰 Finance Entry")
        with st.form("finance_form", clear_on_submit=True):
            shop = st.selectbox("Select Shop", ["Shop 1", "Shop 2"])
            it = st.text_input("Description")
            am_str = st.text_input("Amount")
            ty = st.radio("Type", ["Debit (Expense)", "Credit (Sales)"], horizontal=True)

            if st.form_submit_button("SAVE ENTRY"):
                clean = am_str.strip().replace(',', '')
                if not clean:
                    st.error("❗ Please enter an amount.")
                else:
                    try:
                        am = float(clean)
                        payload = {
                            "entry.1044099436": datetime.now().strftime("%Y-%m-%d"),
                            "entry.2013476337": f"[{shop}] {it}",
                            "entry.1460982454": am if "Debit" in ty else 0,
                            "entry.1221658767": 0 if "Debit" in ty else am
                        }
                        if submit_form(FORM_API, payload):
                            st.success("Saved! ✅")
                            st.cache_data.clear()
                    except ValueError:
                        st.error("❗ Invalid amount format.")

    # --- 3. STOCK MANAGEMENT ---
    elif page == "📦 Stock Management":
        st.title("📦 Stock & Inventory")
        tab1, tab2, tab3 = st.tabs(["📊 Current Stock", "➕ Add Entry", "📄 Item History & PDF"])

        with tab1:
            if not df_stk.empty:
                s = df_stk.copy()
                s['In'] = s.apply(lambda x: x['Quantity'] if x['Type'] == 'Stock In' else 0, axis=1)
                s['Out'] = s.apply(lambda x: x['Quantity'] if x['Type'] == 'Stock Out' else 0, axis=1)
                final_stk = s.groupby('Item')[['In', 'Out']].sum().reset_index()
                final_stk['Available Stock'] = final_stk['In'] - final_stk['Out']
                st.dataframe(final_stk[['Item', 'Available Stock']], use_container_width=True)
            else:
                st.info("No stock data.")

        with tab2:
            with st.form("stock_form", clear_on_submit=True):
                item_name = st.text_input("Item Name")
                qty = st.number_input("Quantity", min_value=1.0)
                stock_type = st.radio("Type", ["Stock In", "Stock Out"], horizontal=True)
                if st.form_submit_button("SAVE STOCK"):
                    payload = {
                        "entry.1044099436": datetime.now().strftime("%Y-%m-%d"),
                        "entry.2013476337": item_name,
                        "entry.1460982454": qty,
                        "entry.1221658767": stock_type
                    }
                    if submit_form(STOCK_FORM_API, payload):
                        st.success("Stock Updated! ✅")
                        st.cache_data.clear()

        with tab3:
            if not df_stk.empty:
                selected_item = st.selectbox("Select Item", df_stk['Item'].unique())
                item_history = df_stk[df_stk['Item'] == selected_item]
                st.dataframe(item_history[['Date', 'Type', 'Quantity']], use_container_width=True)
                pdf_b = generate_pdf(item_history, f"Stock History: {selected_item}", ['Date', 'Type', 'Quantity'])
                st.download_button(f"📥 Download {selected_item} PDF", pdf_b, f"{selected_item}_Stock.pdf", "application/pdf")

    # --- 4. STAFF SALARY ---
    elif page == "👨‍💼 Staff Salary":
        st.title("👨‍💼 Staff Salary Management")
        with st.expander("പുതിയ ശമ്പളം നൽകുക (Add New Salary)"):
            with st.form("salary_form", clear_on_submit=True):
                shop = st.selectbox("Select Shop", ["Shop 1", "Shop 2"])
                emp_name = st.text_input("Employee Name")
                sal_amt = st.number_input("Salary Amount", min_value=1.0)
                sal_month = st.selectbox("Month", ["November 2026", "October 2026"])
                if st.form_submit_button("PAY SALARY"):
                    payload = {
                        "entry.1044099436": datetime.now().strftime("%Y-%m-%d"),
                        "entry.2013476337": f"[{shop}] Salary: {emp_name} ({sal_month})",
                        "entry.1460982454": sal_amt,
                        "entry.1221658767": 0
                    }
                    if submit_form(FORM_API, payload):
                        st.success(f"✅ {emp_name}-ന്റെ ശമ്പളം വിജയകരമായി നൽകി!")
                        st.cache_data.clear()

        st.divider()
        st.subheader("📄 Salary History & PDF")
        if not df_fin.empty:
            sal_df = df_fin[df_fin['Item'].str.contains('Salary', case=False, na=False)].copy()
            if not sal_df.empty:
                sal_df['Employee'] = sal_df['Item'].apply(lambda x: x.split(':')[1].split('(')[0].strip() if ':' in x else "Unknown")
                selected_emp = st.selectbox("Select Staff Member", sal_df['Employee'].unique())
                emp_history = sal_df[sal_df['Employee'] == selected_emp]
                st.dataframe(emp_history[['Date', 'Shop Name', 'Item', 'Debit']], use_container_width=True)
                pdf_b = generate_pdf(emp_history, f"Salary Report: {selected_emp}", ['Date', 'Shop Name', 'Debit'])
                st.download_button(f"📥 Download {selected_emp}'s Salary PDF", pdf_b, f"{selected_emp}_Salary.pdf", "application/pdf")
            else:
                st.info("No salary records found.")

    # --- 5. AI AGENT (പുതിയത്) ---
    elif page == "🤖 AI Agent":
        st.title("🤖 PAICHI Business AI Agent")
        st.write("ബിസിനസ്സിലെ കാര്യങ്ങൾ ചാറ്റ് വഴി ചെയ്യാം. (ഉദാ: 'Shop 1-ൽ 5000 സെയിൽസ് ഉണ്ടായി')")

        if not GROQ_API_KEY:
            st.error("Groq API Key ലഭ്യമല്ല!")

        # ചാറ്റ് ഹിസ്റ്ററി കാണിക്കുക
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ask me to add finance, stock, or check balance..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.spinner("AI ആലോചിക്കുന്നു..."):
                try:
                    client = Groq(api_key=GROQ_API_KEY)
                    
                    # സമയം കണക്കാക്കുന്നു
                    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    
                    system_instruction = f"""
                    നീ ഒരു വളരെ മികച്ച ബിസിനസ്സ് മാനേജർ AI ഏജന്റ് ആണ്. 
                    നിലവിലെ മൊത്തം ബാലൻസ്: ₹{bal:,.2f}.
                    യൂസർ എന്തെങ്കിലും ഫിനാൻസ് എൻട്രി ചേർക്കാൻ പറഞ്ഞാൽ add_finance എന്ന ടൂൾ ഉപയോഗിക്കുക.
                    യൂസർ സ്റ്റോക്ക് കാര്യങ്ങൾ പറഞ്ഞാൽ add_stock എന്ന ടൂൾ ഉപയോഗിക്കുക.
                    ലോകത്തിലെ എല്ലാ കാര്യങ്ങളെക്കുറിച്ചും നിനക്ക് അറിയാം, എന്ത് ചോദിച്ചാലും മലയാളത്തിൽ മറുപടി നൽകുക.
                    """
                    
                    messages_for_api = [{"role": "system", "content": system_instruction}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]]

                    response = client.chat.completions.create(
                        model="openai/gpt-oss-120b", 
                        messages=messages_for_api,
                        tools=tools,
                        tool_choice="auto"
                    )

                    response_message = response.choices[0].message
                    
                    if response_message.tool_calls:
                        for tool_call in response_message.tool_calls:
                            if tool_call.function.name == "add_finance":
                                args = json.loads(tool_call.function.arguments)
                                res = execute_add_finance(args["shop"], args["item"], args["amount"], args["type"])
                                if res == "Success":
                                    ai_reply = f"✅ ചേട്ടാ, {args['shop']}-ൽ '{args['item']}' എന്നതിന് ₹{args['amount']} ({args['type']}) എൻട്രി ഇട്ടിട്ടുണ്ട്!"
                                else:
                                    ai_reply = "❌ എൻട്രി ഇടാൻ പറ്റിയില്ല."
                                    
                            elif tool_call.function.name == "add_stock":
                                args = json.loads(tool_call.function.arguments)
                                res = execute_add_stock(args["item_name"], args["qty"], args["stock_type"])
                                if res == "Success":
                                    ai_reply = f"✅ ചേട്ടാ, {args['item_name']}-ന്റെ {args['qty']} എണ്ണം ({args['stock_type']}) അപ്ഡേറ്റ് ചെയ്തിട്ടുണ്ട്!"
                                else:
                                    ai_reply = "❌ സ്റ്റോക്ക് അപ്ഡേറ്റ് ചെയ്യാൻ പറ്റിയില്ല."
                    else:
                        ai_reply = response_message.content

                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    with st.chat_message("assistant"):
                        st.markdown(ai_reply)
                        
                    # എൻട്രി വിജയിച്ചാൽ പേജ് റീഫ്രെഷ് ചെയ്യാൻ
                    if response_message.tool_calls:
                        st.rerun()

                except Exception as e:
                    st.error(f"AI Error: {str(e)}")
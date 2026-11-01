import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, date

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Paitan House Manager", page_icon="🍜", layout="wide")

DB = "paitan.db"
LOW_BALANCE_THRESHOLD = 2000

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        category TEXT,
        note TEXT,
        amount REAL NOT NULL,
        created_at TEXT
    )""")
    c.execute("SELECT COUNT(*) FROM entries")
    if c.fetchone()[0] == 0:
        today = date.today().isoformat()
        now = datetime.now().isoformat()
        c.execute("INSERT INTO entries (date,type,category,note,amount,created_at) VALUES (?,?,?,?,?,?)",
                  (today, 'income', 'Other', 'Opening Balance', 5000, now))
        c.execute("INSERT INTO entries (date,type,category,note,amount,created_at) VALUES (?,?,?,?,?,?)",
                  (today, 'expense', 'Food', 'ഇന്നത്തെ ചെലവ്', 3168, now))
    conn.commit()
    conn.close()

def get_entries():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM entries ORDER BY created_at DESC", conn)
    conn.close()
    return df

def add_entry(d, type_, cat, note, amount):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO entries (date,type,category,note,amount,created_at) VALUES (?,?,?,?,?,?)",
        (d, type_, cat, note, amount, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def delete_entry(eid):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM entries WHERE id=?", (eid,))
    conn.commit()
    conn.close()

def calc_balance(df):
    if df.empty:
        return 0.0
    return df.apply(lambda r: r['amount'] if r['type'] == 'income' else -r['amount'], axis=1).sum()

# ---------- AI PARSER ----------
def parse_and_add(text):
    m = re.search(r'(\d+(?:\.\d+)?)', text)
    if not m:
        return "തുക കണ്ടെത്തിയില്ല 😅 ദയവായി **'ബിരിയാണി 150'** എന്ന രീതിയിൽ എഴുതൂ."
    amount = float(m.group(1))
    if amount <= 0:
        return "തുക 0-ൽ കൂടുതലായിരിക്കണം."

    low = text.lower()
    is_income = any(w in low for w in
        ['income','salary','sale','sales','വരുമാനം','ശമ്പളം','വിൽപ്പന','received','credit'])
    type_ = 'income' if is_income else 'expense'

    note = text.replace(m.group(0), '').strip().lstrip('₹').strip() or ("Income" if is_income else "Expense")

    cat = 'Other'
    if is_income:
        if re.search(r'sale|വിൽപ്പന', text, re.I): cat = 'Sales'
        elif re.search(r'delivery|ഡെലിവറി', text, re.I): cat = 'Delivery'
        elif re.search(r'member', text, re.I): cat = 'Membership'
    else:
        if re.search(r'food|ഭക്ഷണം|ബിരിയാണി|ചായ|കാപ്പി|biriyani|tea|coffee|lunch|dinner', text, re.I): cat = 'Food'
        elif re.search(r'rent|വാടക', text, re.I): cat = 'Rent'
        elif re.search(r'salary|ശമ്പളം', text, re.I): cat = 'Salary'
        elif re.search(r'supply|supplies|സാധനം', text, re.I): cat = 'Supplies'
        elif re.search(r'bill|utility|കറന്റ്|current', text, re.I): cat = 'Utilities'
        elif re.search(r'market|promo|ad', text, re.I): cat = 'Marketing'

    add_entry(date.today().isoformat(), type_, cat, note, amount)
    bal = calc_balance(get_entries())
    sign = "💰 വരുമാനം" if is_income else "💸 ചെലവ്"
    return f"✅ {sign} ചേർത്തു:\n\n**{note}** – ₹{amount:,.2f} ({cat})\n\nഇപ്പോഴത്തെ ബാലൻസ്: **₹{bal:,.2f}**"

# ---------- INIT ----------
init_db()
df = get_entries()
balance = calc_balance(df)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.title("🍜 Paitan House")
    st.caption("Business Manager")
    page = st.radio("Navigation", [
        "🏠 Dashboard", "➕ Add Entry", "🔍 History",
        "📊 Report", "📅 Calendar", "🤖 AI Chat"
    ])
    st.divider()
    st.metric("💰 Balance", f"₹{balance:,.2f}")
    st.caption(f"📅 {date.today().strftime('%d %b %Y')}")

# ---------- LOW BALANCE WARNING ----------
if balance < LOW_BALANCE_THRESHOLD:
    st.warning(f"⚠️ ബാലൻസ് കുറവാണ്: ₹{balance:,.2f} (₹{LOW_BALANCE_THRESHOLD} ൽ കീഴിൽ)")

# ---------- DASHBOARD ----------
if page == "🏠 Dashboard":
    st.header("🏠 Dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Available Balance", f"₹{balance:,.2f}")

    if not df.empty:
        df2 = df.copy()
        df2['date_dt'] = pd.to_datetime(df2['date'])
        now = pd.Timestamp.now()
        m = df2[(df2['date_dt'].dt.month == now.month) & (df2['date_dt'].dt.year == now.year)]
        m_in = m[m['type'] == 'income']['amount'].sum()
        m_out = m[m['type'] == 'expense']['amount'].sum()
    else:
        m_in = m_out = 0

    c2.metric("📈 ഈ മാസം വരുമാനം", f"₹{m_in:,.2f}")
    c3.metric("📉 ഈ മാസം ചെലവ്", f"₹{m_out:,.2f}")

    st.divider()
    st.subheader("📋 സമീപകാല എൻട്രികൾ")
    if df.empty:
        st.info("ഇനിയും എൻട്രികൾ ഇല്ല")
    else:
        recent = df.head(10)[['date', 'type', 'category', 'note', 'amount']]
        st.dataframe(recent, use_container_width=True, hide_index=True)

# ---------- ADD ENTRY ----------
elif page == "➕ Add Entry":
    st.header("➕ പുതിയ എൻട്രി")
    with st.form("add_form", clear_on_submit=True):
        type_ = st.radio("തരം", ["expense", "income"], horizontal=True,
                         format_func=lambda x: "💸 ചെലവ്" if x == "expense" else "💰 വരുമാനം")
        cats = ['Food', 'Supplies', 'Rent', 'Salary', 'Utilities', 'Marketing', 'Other'] \
               if type_ == "expense" else ['Sales', 'Delivery', 'Membership', 'Other']
        cat = st.selectbox("വിഭാഗം", cats)
        amount = st.number_input("തുക (₹)", min_value=0.01, step=1.0, value=100.0)
        note = st.text_input("വിവരണം", placeholder="ബിരിയാണി / ചായ / വാടക")
        d = st.date_input("തീയതി", value=date.today())
        submit = st.form_submit_button("✅ സേവ് ചെയ്യുക", use_container_width=True)

        if submit:
            if not note.strip():
                st.error("വിവരണം ആവശ്യമാണ്")
            else:
                add_entry(d.isoformat(), type_, cat, note.strip(), amount)
                st.success(f"✅ ചേർത്തു: {note} – ₹{amount:,.2f}")
                st.rerun()

# ---------- HISTORY ----------
elif page == "🔍 History":
    st.header("🔍 എല്ലാ എൻട്രികളും")
    if df.empty:
        st.info("ഒന്നുമില്ല")
    else:
        f1, f2 = st.columns(2)
        tf = f1.selectbox("തരം", ["All", "income", "expense"])
        cf = f2.selectbox("വിഭാഗം", ["All"] + sorted(df['category'].dropna().unique().tolist()))

        filtered = df.copy()
        if tf != "All": filtered = filtered[filtered['type'] == tf]
        if cf != "All": filtered = filtered[filtered['category'] == cf]

        st.dataframe(filtered[['id', 'date', 'type', 'category', 'note', 'amount']],
                     use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🗑️ എൻട്രി ഒഴിവാക്കുക")
        c1, c2 = st.columns([2, 1])
        del_id = c1.number_input("Entry ID", min_value=1, step=1)
        if c2.button("ഒഴിവാക്കുക", type="primary", use_container_width=True):
            delete_entry(int(del_id))
            st.success(f"✅ ID {del_id} ഒഴിവാക്കി")
            st.rerun()

        csv = filtered[['date', 'type', 'category', 'note', 'amount']].to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ CSV ഡൗൺലോഡ്", csv, f"paitan_{date.today()}.csv", "text/csv")

# ---------- REPORT ----------
elif page == "📊 Report":
    st.header("📊 ബിസിനസ് റിപ്പോർട്ട്")
    if df.empty:
        st.info("ഡാറ്റ ഇല്ല")
    else:
        total_in = df[df['type'] == 'income']['amount'].sum()
        total_out = df[df['type'] == 'expense']['amount'].sum()
        profit = total_in - total_out

        c1, c2, c3 = st.columns(3)
        c1.metric("💰 ആകെ വരുമാനം", f"₹{total_in:,.2f}")
        c2.metric("💸 ആകെ ചെലവ്", f"₹{total_out:,.2f}")
        c3.metric("📈 മൊത്ത ലാഭം", f"₹{profit:,.2f}",
                  delta=f"{(profit/total_in*100 if total_in else 0):.1f}%")

        st.divider()
        st.subheader("📊 വിഭാഗം തിരിച്ചുള്ള ചെലവ്")
        exp_df = df[df['type'] == 'expense'].groupby('category')['amount'].sum().sort_values(ascending=False)
        if not exp_df.empty:
            st.bar_chart(exp_df)

        st.subheader("📈 ദൈനംദിന ബാലൻസ് (Cumulative)")
        df3 = df.copy()
        df3['date_dt'] = pd.to_datetime(df3['date'])
        df3['signed'] = df3.apply(lambda r: r['amount'] if r['type'] == 'income' else -r['amount'], axis=1)
        daily = df3.groupby('date_dt')['signed'].sum().cumsum().sort_index()
        if not daily.empty:
            st.line_chart(daily)

# ---------- CALENDAR ----------
elif page == "📅 Calendar":
    st.header("📅 കലണ്ടർ")
    if df.empty:
        st.info("ഡാറ്റ ഇല്ല")
    else:
        dfc = df.copy()
        dfc['date_dt'] = pd.to_datetime(dfc['date'])
        pivot = dfc.pivot_table(index='date_dt', columns='type',
                                values='amount', aggfunc='sum', fill_value=0)
        st.subheader("📆 ദിവസം തിരിച്ച്")
        st.dataframe(pivot, use_container_width=True)

        st.subheader("📊 മാസം തിരിച്ച്")
        dfc['month'] = dfc['date_dt'].dt.strftime('%Y-%m')
        monthly = dfc.groupby(['month', 'type'])['amount'].sum().unstack(fill_value=0)
        st.bar_chart(monthly)

# ---------- AI CHAT ----------
elif page == "🤖 AI Chat":
    st.header("🤖 Paitan Assistant")
    st.caption('ഉദാ: "ബിരിയാണി 150", "വാടക 8000", "income salary 5000"')

    if "messages" not in st.session_state:
        st.session_state.messages = [{
            "role": "assistant",
            "content": "നമസ്കാരം 👋 ഞാൻ **Paitan Assistant**. തുകയും വിവരണവും എഴുതൂ – ഞാൻ എൻട്രി ചേർക്കാം."
        }]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("ബിരിയാണി 150 ...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        reply = parse_and_add(user_input)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
        st.rerun()
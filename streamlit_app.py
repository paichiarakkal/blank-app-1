import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import os
import openai
from streamlit_autorefresh import st_autorefresh

# --- OpenAI API കോൺഫിഗറേഷൻ ---
openai.api_key = st.secrets["OPENAI_API_KEY"]

def call_openai_ai(prompt_text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_text}]
        )
        return response.choices[0].message['content']
    except Exception as e:
        return f"Error encountered: {e}"

# 1. പേജ് സെറ്റിംഗ്‌സ് & ഗോൾഡൻ തീം
st.set_page_config(page_title="Paichi AI Trader Pro", layout="wide")

st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #AA771C); color: #000; }
    section[data-testid="stSidebar"] { background: linear-gradient(180deg, #A9A9A9, #C0C0C0, #808080) !important; }
    .stButton>button { width: 100%; border-radius: 4px; height: 2.2em; background-color: #000 !important; color: #FFD700 !important; border: 1px solid #FFD700 !important; font-size: 14px !important; font-weight: bold; margin-bottom: 2px; }
    .main-title { color: #FFF; font-size: 26px; font-weight: 800; text-align: center; text-shadow: 2px 2px 4px #000; }
    .info-box { background-color: #f8f9fa; padding: 10px; border-radius: 8px; color: #333; font-weight: bold; text-align: center; border: 1px solid #ddd; font-size: 14px; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

st_autorefresh(interval=30000, key="faisal_original_app")
FILE_NAME = 'trade_history_v2.csv'

# --- ഫംഗ്ഷനുകൾ ---
def get_live_price(ticker):
    try:
        data = yf.Ticker(ticker).history(period='1d', interval='1m')
        return data['Close'].iloc[-1]
    except: return 0.0

def save_trade(symbol, action, entry_p, exit_p, qty, pnl, mood):
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    df_new = pd.DataFrame([[date, symbol, action, entry_p, exit_p, qty, pnl, mood]], 
                          columns=['Date', 'Item', 'Type', 'Entry', 'Exit', 'Qty', 'P&L', 'Mood'])
    if not os.path.isfile(FILE_NAME): df_new.to_csv(FILE_NAME, index=False)
    else: df_new.to_csv(FILE_NAME, mode='a', header=False, index=False)

# --- സെഷൻ സ്റ്റേറ്റ് ---
if 'sel_ticker' not in st.session_state:
    st.session_state.sel_ticker = ("^NSEI", "NIFTY 50")

# --- 2. സൈഡ് ബാർ ---
with st.sidebar:
    st.markdown("### 🚀 Paichi Pro")
    st.markdown("[💬 Contact on WhatsApp](https://wa.me/918714752210)")
    st.divider()
    
    # Currency Converter (AED to INR)
    st.write("💰 **AED to INR**")
    aed_val = st.number_input("Dirham Amount", min_value=0.0, value=1.0, step=1.0)
    ex_rate = get_live_price("AEDINR=X")
    if ex_rate > 0:
        st.markdown(f'<div class="info-box" style="color:green;">₹ {aed_val * ex_rate:,.2f} INR</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Gold Price
    st.write("🟡 **Gold Price (8g/1 Pawan)**")
    gold_price_per_gram = get_live_price("GC=F") 
    gold_8g_inr = (gold_price_per_gram / 31.1035) * 8 * ex_rate * 1.15 
    st.markdown(f'<div class="info-box" style="color:#B8860B;">₹ {gold_8g_inr:,.0f} (Approx)</div>', unsafe_allow_html=True)
    
    # Shop Rate
    st.write("🏪 **Shop Rate**")
    shop_rate = st.number_input("Today's Rate", value=gold_8g_inr, step=10.0)
    st.markdown(f'<div class="info-box">Shop: ₹ {shop_rate:,.0f}</div>', unsafe_allow_html=True)
    
    st.divider()
    mode = st.radio("മെനു:", ["MARKET", "JOURNAL", "DASHBOARD", "KEY MOMENTS"])
    st.divider()

    if mode == "MARKET":
        st.write("🎯 **Indices:**")
        if st.button("📈 NIFTY 50"): st.session_state.sel_ticker = ("^NSEI", "NIFTY 50"); st.rerun()
        if st.button("🏦 BANK NIFTY"): st.session_state.sel_ticker = ("^NSEBANK", "BANK NIFTY"); st.rerun()
        if st.button("💳 FIN NIFTY"): st.session_state.sel_ticker = ("NIFTY_FIN_SERVICE.NS", "FIN NIFTY"); st.rerun()
        if st.button("📊 SENSEX"): st.session_state.sel_ticker = ("^BSESN", "SENSEX"); st.rerun()
        if st.button("📉 MIDCAP"): st.session_state.sel_ticker = ("^NSEMDCP50", "MIDCAP 50"); st.rerun()
        if st.button("⛽ CRUDE OIL"): st.session_state.sel_ticker = ("CL=F", "CRUDE OIL"); st.rerun()

# --- 3. മെയിൻ കണ്ടന്റ് ---
if mode == "MARKET":
    st.markdown(f'<p class="main-title">🚀 {st.session_state.sel_ticker[1]}</p>', unsafe_allow_html=True)
    symbol, name = st.session_state.sel_ticker
    price = get_live_price(symbol)
    st.metric(label=name, value=f"₹ {price:,.2f}")

elif mode == "JOURNAL":
    st.markdown('<p class="main-title">📝 OPTION JOURNAL</p>', unsafe_allow_html=True)
    underlying = st.selectbox("Index", ["NIFTY", "BANKNIFTY", "FINNIFTY", "CRUDE OIL"])
    strike = st.text_input("Strike & Type", placeholder="Ex: 22400 CE")
    st.divider()
    col1, col2 = st.columns(2)
    entry_raw = col1.text_input("Entry Premium", value="", placeholder="0.00")
    exit_raw = col2.text_input("Exit Premium", value="", placeholder="0.00")
    qty_raw = col1.text_input("Total Qty", value="", placeholder="0")
    t_type = col2.selectbox("Order Type", ["BUY (Long)", "SELL (Short)"])
    mood = st.selectbox("Mood", ["Calm", "Disciplined", "Fear", "Greedy"])

    if st.button("SAVE OPTION TRADE"):
        try:
            entry = float(entry_raw) if entry_raw else 0.0
            exit_p = float(exit_raw) if exit_raw else 0.0
            qty = int(qty_raw) if qty_raw else 0
            pnl = (exit_p - entry) * qty if "BUY" in t_type else (entry - exit_p) * qty
            save_trade(f"{underlying} {strike}", t_type, entry, exit_p, qty, pnl, mood)
            st.success(f"സേവ് ചെയ്തു! P&L: ₹{pnl:,.2f}")
            st.rerun()
        except: st.error("Numbers only please!")

elif mode == "DASHBOARD":
    st.markdown('<p class="main-title">📊 DASHBOARD</p>', unsafe_allow_html=True)
    if os.path.isfile(FILE_NAME):
        df = pd.read_csv(FILE_NAME)
        st.write(f"### Net P&L: ₹ {df['P&L'].sum():,.2f}")
        st.dataframe(df.iloc[::-1], use_container_width=True)

# --- 4. KEY MOMENTS ---
elif mode == "KEY MOMENTS":
    st.markdown('<p class="main-title">📌 AI KEY MOMENTS</p>', unsafe_allow_html=True)
    km_ticker = st.text_input("സ്റ്റോക്ക് കോഡ് നൽകുക:", "^NSEI")
    
    if km_ticker:
        try:
            stock_obj = yf.Ticker(km_ticker)
            hist_df = stock_obj.history(period="5d")
            
            if not hist_df.empty:
                close_prices = hist_df['Close'].squeeze()
                latest_p = close_prices.iloc[-1]
                prev_p = close_prices.iloc[-2] if len(close_prices) > 1 else latest_p
                day_change = ((latest_p - prev_p) / prev_p) * 100
                
                stock_news = stock_obj.news
                news_text = ""
                if stock_news:
                    for n in stock_news[:5]:
                        news_text += f"- {n.get('title')}\n"
                
                c1, c2 = st.columns(2)
                c1.metric("നിലവിലെ വില", f"₹ {latest_p:,.2f}")
                c2.metric("Daily Change", f"{day_change:.2f}%")
                st.line_chart(close_prices)
                
                if st.button("AI KEY MOMENTS ജനറേറ്റ് ചെയ്യുക"):
                    with st.spinner("വിശകലനം ചെയ്യുന്നു..."):
                        ai_prompt = f"Analyze {km_ticker}. Price: {latest_p:.2f}, Change: {day_change:.2f}%. News: {news_text}. Give a brief Key Moments summary in Malayalam."
                        response_text = call_openai_ai(ai_prompt)
                        st.info(response_text)
            else:
                st.error("മാർക്കറ്റ് വിവരങ്ങൾ ലഭ്യമായില്ല.")
        except Exception as err:
            st.error(f"Error: {err}")

st.markdown(f'<p style="text-align: center; color: #FFF; margin-top: 50px;">Created by <b>Faisal Arakkal</b></p>', unsafe_allow_html=True)

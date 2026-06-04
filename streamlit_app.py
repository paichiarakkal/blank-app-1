import streamlit as st
import pandas as pd
import requests
import datetime

# ==========================================
# 1. PAGE SETUP
# ==========================================
st.set_page_config(page_title="Paichi Trading Bot", layout="wide")
st.title("📊 Paichi Live Trading Dashboard")

# ==========================================
# 2. YAHOO FINANCE DATA FUNCTION
# ==========================================
def get_yahoo_finance_price(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            return round(price, 2)
        return None
    except Exception as e:
        return None

# ==========================================
# 3. CALLMEBOT WHATSAPP FUNCTION
# ==========================================
def send_callmebot_whatsapp(message_text):
    # നിങ്ങൾ നൽകിയ കൃത്യമായ ഫോൺ നമ്പറും API കീയും
    phone_number = "971551347989"
    api_key = "7463030"
    
    # CallMeBot യുആർഎൽ ഉണ്ടാക്കുന്നു
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={message_text}&apikey={api_key}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
        else:
            st.error(f"CallMeBot Error Code: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# ==========================================
# 4. DASHBOARD UI & LOGIC
# ==========================================
st.subheader("Live Market Signals (Free Yahoo Finance Data)")

# നിഫ്റ്റിയും ക്രൂഡ് ഓയിലും ലൈവ് ആയി എടുക്കുന്നു
nifty_price = get_yahoo_finance_price("^NSEI")
crude_price = get_yahoo_finance_price("CL=F")

# വില കിട്ടിയില്ലെങ്കിൽ ബാക്ക്അപ്പ് വിലകൾ കാണിക്കും
if not nifty_price: nifty_price = 22450.50
if not crude_price: crude_price = 6580.00

live_data = [
    {"Instrument": "NIFTY 50", "Live Price (LTP)": nifty_price, "Supertrend Status": "BUY"},
    {"Instrument": "CRUDE OIL", "Live Price (LTY)": crude_price, "Supertrend Status": "SELL"}
]

df_signals = pd.DataFrame(live_data)
st.dataframe(df_signals, use_container_width=True)

st.write("---")
st.subheader("Manual Controls")

if st.button("🚀 Send Live Signal to WhatsApp via CallMeBot"):
    with st.spinner("CallMeBot വഴി മെസ്സേജ് അയക്കുന്നു..."):
        # വാട്സാപ്പിലേക്ക് അയക്കേണ്ട നല്ലൊരു മെസ്സേജ് ഫോർമാറ്റ്
        now_time = datetime.datetime.now().strftime('%Y-%m-%d+%H:%M:%S')
        msg = f"🔴+NEW+TRADING+SIGNAL+🔴%0A%0AAsset:+CRUDE+OIL%0ASignal:+SELL%0APrice:+{crude_price}%0ATime:+{now_time}"
        
        success = send_callmebot_whatsapp(msg)
        if success:
            st.success("CallMeBot വഴി നിങ്ങളുടെ വാട്സാപ്പിലേക്ക് സിഗ്നൽ മെസ്സേജ് പക്കാ ആയി പോയിട്ടുണ്ട് ഭായ്! ✅")

import streamlit as st
import yfinance as yf
import pandas as pd
import ta

# ഡാഷ്‌ബോർഡ് പേജ് കോൺഫിഗറേഷൻ
st.set_page_config(page_title="AI Trading Dashboard", layout="wide")
st.title("🤖 Zylostar മോഡൽ - AI Trading Assistant")
st.write("ലൈവ് മാർക്കറ്റ് ട്രെൻഡുകളും ടെക്നിക്കൽ ഇൻഡിക്കേറ്ററുകളും താഴെ കാണാം.")

# സൈഡ്‌ബാറിലുള്ള കൺട്രോളുകൾ
st.sidebar.header("⚙️ മാർക്കറ്റ് സെറ്റിംഗ്സ്")
ticker = st.sidebar.text_input("സ്റ്റോക്ക് / ക്രിപ്റ്റോ കോഡ് നൽകുക (eg: BTC-USD, AAPL)", "BTC-USD")
period = st.sidebar.selectbox("കാലയളവ് (Period)", ["1d", "5d", "1mo", "3mo", "1y"])
interval = st.sidebar.selectbox("ഇന്റർവൽ (Interval)", ["5m", "15m", "30m", "1h", "1d"])

# വൈഫിനാൻസിൽ നിന്ന് ഡാറ്റ ഫെച്ച് ചെയ്യാനുള്ള ഫങ്ഷൻ
@st.cache_data
def load_data(symbol, p, i):
    data = yf.download(tickers=symbol, period=p, interval=i)
    return data

# മെയിൻ ലോജിക്
try:
    df = load_data(ticker, period, interval)
    
    if not df.empty:
        # പുതിയ yfinance അപ്ഡേറ്റ് കാരണം വരുന്ന 2D അറേ പ്രശ്നം പരിഹരിക്കാൻ .squeeze() ഉപയോഗിക്കുന്നു
        close_prices = df['Close'].squeeze()
        
        # ടെക്നിക്കൽ ഇൻഡിക്കേറ്ററുകൾ കണക്കുകൂട്ടുന്നു (RSI)
        df['RSI'] = ta.momentum.rsi(close_prices)
        
        # ഏറ്റവും പുതിയ വില വിവരങ്ങൾ (1D സീരീസിൽ നിന്ന് എടുക്കുന്നു)
        latest_price = close_prices.iloc[-1]
        latest_rsi = df['RSI'].iloc[-1]
        
        # സ്ക്രീനിൽ വില വിവരങ്ങൾ കാണിക്കാനുള്ള ഡിസ്‌പ്ലേ കാർഡുകൾ
        col1, col2, col3 = st.columns(3)
        col1.metric("നിലവിലെ വില", f"${latest_price:,.2f}")
        
        # RSI മൂല്യം കൃത്യമായി കാണിക്കുന്നു
        if pd.isna(latest_rsi):
            col2.metric("RSI (14)", "ഡാറ്റ അപര്യാപ്തമാണ്")
            status = "🟡 HOLD (No Data)"
        else:
            col2.metric("RSI (14)", f"{latest_rsi:.2f}")
            
            # ലളിതമായ ഒരു AI/അൽഗോരിതമിക് സിഗ്നൽ ലോജിക്
            if latest_rsi < 30:
                status = "🟢 BUY SIGNAL (Oversold)"
            elif latest_rsi > 70:
                status = "🔴 SELL SIGNAL (Overbought)"
            else:
                status = "🟡 HOLD (Neutral)"
            
        col3.metric("AI ട്രേഡിംഗ് സിഗ്നൽ", status)
        
        # ലൈവ് പ്രൈസ് കാണിക്കുന്ന ലൈൻ ചാർട്ട്
        st.subheader(f"📈 {ticker} ലൈവ് പ്രൈസ് ചാർട്ട്")
        st.line_chart(close_prices)
        
        # ബാക്ക്എൻഡ് ഡാറ്റ ടേബിൾ
        st.subheader("📊 അവസാനത്തെ 5 റെക്കോർഡുകൾ")
        st.dataframe(df.tail(5))
        
    else:
        st.error("ഡാറ്റ ലഭ്യമല്ല. ദയവായി ടിക്കർ സിംബൽ പരിശോധിക്കുക.")
        
except Exception as e:
    st.error(f"Error encountered: {e}")

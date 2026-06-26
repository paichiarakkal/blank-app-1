import streamlit as st
import yfinance as yf
import pandas as pd
import ta

# ഡാഷ്‌ബോർഡ് ടൈറ്റിൽ
st.set_page_config(page_title="AI Trading Dashboard", layout="wide")
st.title("🤖 Zylostar മോഡൽ - AI Trading Assistant")
st.write("ലൈവ് മാർക്കറ്റ് ട്രെൻഡുകളും ടെക്നിക്കൽ ഇൻഡിക്കേറ്ററുകളും താഴെ കാണാം.")

# സൈഡ്‌ബാറിലുള്ള ഓപ്ഷനുകൾ
ticker = st.sidebar.text_input("സ്റ്റോക്ക് / ക്രിപ്റ്റോ കോഡ് നൽകുക (eg: BTC-USD, AAPL)", "BTC-USD")
period = st.sidebar.selectbox("കാലയളവ്", ["1d", "5d", "1mo", "3mo", "1y"])
interval = st.sidebar.selectbox("ഇന്റർവൽ", ["5m", "15m", "30m", "1h", "1d"])

# ഡാറ്റ ഫെച്ച് ചെയ്യൽ
@st.cache_data
def load_data(symbol, p, i):
    data = yf.download(tickers=symbol, period=p, interval=i)
    return data

try:
    df = load_data(ticker, period, interval)
    
    if not df.empty:
        # ടെക്നിക്കൽ ഇൻഡിക്കേറ്ററുകൾ കണക്കുകൂട്ടുന്നു (RSI)
        df['RSI'] = ta.momentum.rsi(df['Close'])
        
        # ഏറ്റവും പുതിയ വില വിവരങ്ങൾ
        latest_price = df['Close'].iloc[-1]
        latest_rsi = df['RSI'].iloc[-1]
        
        # ഡിസ്‌പ്ലേ കാർഡുകൾ
        col1, col2, col3 = st.columns(3)
        col1.metric("നിലവിലെ വില", f"${latest_price:,.2f}")
        col2.metric("RSI (14)", f"{latest_rsi:.2f}")
        
        # ലളിതമായ ഒരു AI/അൽഗോരിതമിക് സിഗ്നൽ
        if latest_rsi < 30:
            status = "🟢 BUY SIGNAL (Oversold)"
        elif latest_rsi > 70:
            status = "🔴 SELL SIGNAL (Overbought)"
        else:
            status = "🟡 HOLD (Neutral)"
            
        col3.metric("AI ട്രേഡിംഗ് സിഗ്നൽ", status)
        
        # ചാർട്ട് കാണിക്കാൻ
        st.subheader(f"{ticker} ലൈവ് പ്രൈസ് ചാർട്ട്")
        st.line_chart(df['Close'])
        
        # ഡാറ്റ ടേബിൾ
        st.subheader("അവസാനത്തെ 5 റെക്കോർഡുകൾ")
        st.dataframe(df.tail(5))
        
    else:
        st.error("ഡാറ്റ ലഭ്യമല്ല. ദയവായി ടിക്കർ സിംബൽ പരിശോധിക്കുക.")
except Exception as e:
    st.error(f"Error: {e}")

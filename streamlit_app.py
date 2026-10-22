# --- DEBT TRACKER ---
elif page == "🤝 Debt Tracker":
    st.title("🤝 Debt Tracker & Summary")
    st.info("ഇവിടെ നിങ്ങളുടെ കടം വാങ്ങിയതും നൽകിയതുമായ വിവരങ്ങൾ കാണാം.")

# ============================================
# 🤖 SMART AI AGENT (Secrets API Key ഉപയോഗിച്ച്)
# ============================================
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Ask AI Agent")

# Streamlit Secrets-ൽ നിന്ന് API Key എടുക്കുന്നു
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except KeyError:
    st.sidebar.error("⚠️ GEMINI_API_KEY സീക്രട്ട്സിൽ കണ്ടെത്തിയില്ല.")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 1. AI-ക്ക് നൽകാനുള്ള ടൂളുകൾ (Tools)
def ai_add_entry(amount: float, category: str, description: str, type: str = "Debit"):
    try:
        payload = {
            "entry.1044099436": datetime.now().strftime("%Y-%m-%d"), 
            "entry.2013476337": f"[{st.session_state.user.capitalize()}] {category}: {description}", 
            "entry.1460982454": amount if type == "Debit" else 0, 
            "entry.1221658767": 0 if type == "Debit" else amount
        }
        requests.post(FORM_API, data=payload, timeout=10)
        send_whatsapp_auto(f"✅ *Auto Entry Added via AI*\n📝 {description}\n💰 ₹{amount}\n🗂️ {category}")
        return "Success"
    except: return "Error"

def ai_send_whatsapp(message: str):
    try:
        send_whatsapp_auto(message)
        return "Success"
    except: return "Error"

tools = [
    Tool(
        function_declarations=[
            FunctionDeclaration(
                name="ai_add_entry",
                description="Add a new expense or income to the database.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "amount": {"type": "NUMBER", "description": "Amount spent."},
                        "category": {"type": "STRING", "description": "Food, Shop, Travel, etc."},
                        "description": {"type": "STRING", "description": "Item details."},
                        "type": {"type": "STRING", "description": "Debit or Credit."}
                    },
                    "required": ["amount", "category", "description"]
                }
            ),
            FunctionDeclaration(
                name="ai_send_whatsapp",
                description="Send a WhatsApp message to the user.",
                parameters={
                    "type": "OBJECT",
                    "properties": {"message": {"type": "STRING", "description": "Message content."}},
                    "required": ["message"]
                }
            )
        ]
    )
]

# 2. മോഡൽ ലോഡ് ചെയ്യുന്നു
if 'GEMINI_API_KEY' in locals() and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools=tools,
        system_instruction="നീയാണ് PAICHI EXPENSES എന്ന ആപ്പിന്റെ AI മാനേജർ. യൂസർ എന്തെങ്കിലും ചെലവ് ചേർക്കാൻ പറഞ്ഞാൽ 'ai_add_entry' ടൂൾ ഉപയോഗിച്ച് അത് സ്വയം ചെയ്യണം. വാട്സാപ്പിൽ മെസ്സേജ് അയക്കാൻ പറഞ്ഞാൽ 'ai_send_whatsapp' ഉപയോഗിക്കണം. യൂസർ മലയാളത്തിൽ ചോദിച്ചാൽ മലയാളത്തിൽ തന്നെ മറുപടി നൽകുക."
    )

# 3. ചാറ്റ് ഇന്റർഫേസ്
for message in st.session_state.messages:
    with st.sidebar.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.sidebar.chat_input("Ask about your expenses..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.sidebar.chat_message("user"):
        st.markdown(prompt)

    if 'GEMINI_API_KEY' in locals() and GEMINI_API_KEY:
        with st.sidebar.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = model.generate_content(prompt)
                    
                    # AI ടൂൾ വിളിക്കാൻ തീരുമാനിച്ചോ എന്ന് നോക്കുന്നു
                    if response.candidates[0].content.parts[0].function_call:
                        func_call = response.candidates[0].content.parts[0].function_call
                        args = func_call.args
                        
                        st.write(f"⚙️ *Working on: {func_call.name}*")
                        
                        if func_call.name == "ai_add_entry":
                            ai_add_entry(args["amount"], args["category"], args["description"], args.get("type", "Debit"))
                            reply = f"ശരി, {args['description']} ന് {args['amount']} ചേർത്തിട്ടുണ്ട്! ✅"
                        elif func_call.name == "ai_send_whatsapp":
                            ai_send_whatsapp(args["message"])
                            reply = "വാട്സാപ്പിൽ മെസ്സേജ് അയച്ചു! 📱"
                        else:
                            reply = "എനിക്ക് അത് ചെയ്യാൻ സാധിക്കില്ല."
                            
                        st.markdown(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    
                    else:
                        st.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                        
                except Exception as e:
                    st.error(f"Error: {e}")
import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64

# ── YOUR GEMINI API KEY (paste it here) ──────────────────────────────────────
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]   # 👈 Replace this with your actual key
# ─────────────────────────────────────────────────────────────────────────────

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3-flash-preview")
# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MediScan AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&family=Playfair+Display:wght@600&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

/* Main background */
.stApp {
    background: linear-gradient(160deg, #f0f7ff 0%, #84B6E2 50%, #5E99CD 100%);
    color: #1f2937;
}

/* Hide sidebar */
section[data-testid="stSidebar"] { display: none; }

/* Title */
h1 {
    font-family: 'Playfair Display', serif !important;
    color: #1a56db !important;
}

/* Subheadings */
h2, h3 { color: #3b82f6 !important; }

/* Chat bubbles */
.stChatMessage {
    background: white !important;
    border: 1px solid #e0e7ff !important;
    border-radius: 16px !important;
    box-shadow: 0 1px 8px rgba(59,130,246,0.08) !important;
    margin-bottom: 10px !important;
}

/* File uploader */
.stFileUploader {
    background: white !important;
    border: 2px dashed #93c5fd !important;
    border-radius: 16px !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
    color: white !important;
    border: none !important;
    border-radius: 50px !important;
    font-weight: 600 !important;
    padding: 0.4rem 1.2rem !important;
}

/* Success / info boxes */
.stAlert {
    border-radius: 12px !important;
    border: none !important;
}

/* Chat input bar */
.stChatInputContainer {
    background: white !important;
    border: 1.5px solid #bfdbfe !important;
    border-radius: 50px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helper: extract text from PDF ─────────────────────────────────────────────
def extract_text_from_pdf(uploaded_file) -> str:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()


# ── Helper: extract text from image ──────────────────────────────────────────
def extract_text_from_image(uploaded_file) -> str:
    image = Image.open(uploaded_file)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    img_part = {"mime_type": "image/png", "data": base64.b64encode(img_bytes).decode()}
    response = model.generate_content([
        "Extract ALL text from this medical report image. Return only the raw text, no commentary.",
        img_part
    ])
    return response.text.strip()


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are MediScan AI, a helpful and empathetic medical report analyst.
When given a medical report, you:
1. Summarise key findings in plain English
2. Highlight values that are outside normal ranges clearly
3. Explain what those findings might indicate in simple language
4. Suggest follow-up questions the patient should ask their doctor
5. ALWAYS remind the user that your analysis is for informational purposes only and is NOT a substitute for professional medical advice.

When answering follow-up questions, be thorough, empathetic, and clear.
"""

# ── Analyse report ────────────────────────────────────────────────────────────
def analyse_report(report_text: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nHere is the medical report to analyse:\n\n{report_text}"
    response = model.generate_content(prompt)
    return response.text


# ── Answer follow-up question ─────────────────────────────────────────────────
def answer_question(report_text: str, question: str, history: list) -> str:
    history_text = "\n".join(
        [f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}" for m in history[-6:]]
    )
    prompt = f"""{SYSTEM_PROMPT}

Medical Report (for context):
{report_text}

Conversation so far:
{history_text}

User question: {question}

Answer clearly and helpfully."""
    response = model.generate_content(prompt)
    return response.text


# ── Session state init ────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "report_text" not in st.session_state:
    st.session_state.report_text = ""
if "report_analysed" not in st.session_state:
    st.session_state.report_analysed = False

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🩺 MediScan AI")
st.markdown("Upload your medical report and get an instant AI-powered analysis — then ask questions in plain English.")

col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🗑️ Clear & Start Over"):
        st.session_state.messages = []
        st.session_state.report_text = ""
        st.session_state.report_analysed = False
        st.rerun()

# ── Upload section ────────────────────────────────────────────────────────────
if not st.session_state.report_analysed:
    uploaded_file = st.file_uploader(
        "📂 Upload your medical report (PDF or Image)",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Supported formats: PDF, PNG, JPG"
    )

    if uploaded_file:
        with st.spinner("🔍 Reading and analysing your report... please wait"):
            try:
                # Extract text based on file type
                if uploaded_file.type == "application/pdf":
                    report_text = extract_text_from_pdf(uploaded_file)
                else:
                    report_text = extract_text_from_image(uploaded_file)

                if not report_text:
                    st.error("❌ Could not extract text. Please try a clearer scan.")
                    st.stop()

                st.session_state.report_text = report_text

                # Analyse the report
                analysis = analyse_report(report_text)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"📋 **Report Analysis Complete!**\n\n{analysis}"
                })
                st.session_state.report_analysed = True
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ── Chat section ──────────────────────────────────────────────────────────────
if st.session_state.report_analysed:
    st.success("✅ Report analysed! Ask me anything about your report below.")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🩺"):
        st.markdown(msg["content"])

# Chat input
if st.session_state.report_analysed:
    if prompt := st.chat_input("Ask a question about your report..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🩺"):
            with st.spinner("Thinking..."):
                try:
                    answer = answer_question(
                        st.session_state.report_text,
                        prompt,
                        st.session_state.messages
                    )
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ── Footer disclaimer ─────────────────────────────────────────────────────────
st.divider()
st.caption("⚠️ MediScan AI is for informational purposes only. Always consult a qualified healthcare professional for medical advice.")

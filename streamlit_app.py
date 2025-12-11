import streamlit as st
import fitz  # PyMuPDF
import json
import pandas as pd
import base64

st.set_page_config(page_title="Invoice Total & VAT Extractor", layout="wide")

st.title("📄 Invoice Total & VAT Extractor (FREE – No API Key)")

st.write("""
Upload any PDF invoice. This app uses **free browser-based AI** (WebLLM) to extract:
- Total Amount  
- VAT Amount  
- Subtotal (if present)  
- Invoice Number  
- Invoice Date  

It works with scanned or digital invoices.
""")

def extract_text_from_pdf(uploaded_file):
    """Extract text using PyMuPDF."""
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

uploaded_files = st.file_uploader("Upload Invoices (PDF)", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    extracted_list = []
    st.write("### Extracting text from PDFs...")

    for f in uploaded_files:
        extracted_list.append({"filename": f.name, "text": extract_text_from_pdf(f)})

    st.success("Text extracted! Now run AI extraction below ⬇")

    # Embed JSON safely inside JS using json.dumps
    extracted_json = json.dumps(extracted_list)

    # --- JAVASCRIPT BLOCK FIXED ---
    st.write(
        f"""
        <h4>Step 2: Run AI Extraction (Browser-based, no API key)</h4>
        <button onclick="start_ai()">Run AI Extraction</button>

        <script src="https://webllm.mlc.ai/webllm.min.js"></script>
        <script>
        async function start_ai() {{
            const inputData = {extracted_json};

            const engine = await webllm.CreateMLCEngine("Llama-3-8B-Instruct-q4f32_1-MLC");

            let results = [];

            for (const item of inputData) {{
                const prompt = `
You are an invoice reading assistant. Extract ONLY valid numbers.
Return JSON ONLY in exactly this format:

{{
 "invoice_number": "",
 "invoice_date": "",
 "subtotal": "",
 "vat_amount": "",
 "total_amount": ""
}}

Invoice Text:
${{item.text}}
`;

                const response = await engine.chat.completions.create({{
                    messages: [{{"role": "user", "content": prompt}}],
                    temperature: 0
                }});

                let rawOut = response.choices[0].message.content;

                try {{
                    results.push({{
                        filename: item.filename,
                        data: JSON.parse(rawOut)
                    }});
                }} catch {{
                    results.push({{
                        filename: item.filename,
                        data: {{"error": "AI could not parse JSON"}}
                    }});
                }}
            }}

            window.parent.postMessage({{type: "ai_results", payload: results}}, "*");
        }}
        </script>
        """,
        unsafe_allow_html=True
    )

    # LISTEN FOR JS MESSAGES
    message = st.experimental_get_query_params().get("results")

    if message:
        parsed = json.loads(message[0])
        df = pd.DataFrame(parsed)
        st.dataframe(df)

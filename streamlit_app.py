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

# --------------------------
# OCR / TEXT Extraction
# --------------------------
def extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    return full_text


# --------------------------
# Excel download helper
# --------------------------
def download_excel(df):
    output = df.to_excel(index=False)
    b64 = base64.b64encode(output).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="invoice_results.xlsx">⬇ Download Excel File</a>'


# -------------------------------------
# FRONT-END
# -------------------------------------
uploaded_files = st.file_uploader("Upload Invoices (PDF)", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    st.write("### Step 1: Extracting Text from PDFs...")
    extracted_texts = []

    for file in uploaded_files:
        text = extract_text_from_pdf(file)
        extracted_texts.append({"filename": file.name, "text": text})

    st.success("Text extracted! Now run AI extraction below.")

    st.write("### Step 2: AI Extraction (Runs in Browser, No API Key Required)")

    # JavaScript to perform in-browser LLM extraction
    st.write("""
    <h4>Click the button below to extract totals using free AI (no API key)</h4>
    <button onclick="run_ai()">Run AI Extraction</button>

    <script src="https://webllm.mlc.ai/webllm.min.js"></script>
    <script>
    async function run_ai() {
        const results = [];
        const engine = await webllm.CreateMLCEngine("Llama-3-8B-Instruct-q4f32_1-MLC");

        const data = %s;

        for (const item of data) {
            const prompt = `
You are an invoice reading assistant. Extract ONLY valid numbers.
Return JSON ONLY in this exact format:

{
 "invoice_number": "",
 "invoice_date": "",
 "subtotal": "",
 "vat_amount": "",
 "total_amount": ""
}

Now extract from this invoice text:

""" + item.text + `"
`;

            const out = await engine.chat.completions.create({
                messages: [{"role": "user", "content": prompt}],
                temperature: 0
            });

            let jsonText = out.choices[0].message.content;

            try {
                results.push({
                    filename: item.filename,
                    data: JSON.parse(jsonText)
                });
            } catch (e) {
                results.push({
                    filename: item.filename,
                    data: {"error": "AI could not parse JSON"}
                });
            }
        }

        window.parent.postMessage({type: "invoice_results", results: results}, "*");
    }
    </script>
    """ % json.dumps(extracted_texts), unsafe_allow_html=True)

    # Listen for browser results
    js_results = st.experimental_get_query_params().get("js_results")

    if js_results:
        final_data = json.loads(js_results[0])
        st.write("## Extracted Data")

        rows = []
        for invoice in final_data:
            row = {"filename": invoice["filename"]}
            row.update(invoice["data"])
            rows.append(row)

        df = pd.DataFrame(rows)

        st.dataframe(df)

        st.markdown(download_excel(df), unsafe_allow_html=True)

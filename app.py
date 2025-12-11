import streamlit as st
import PyPDF2
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import io
import requests
import pandas as pd
import json

# Function to extract text from PDF (tries direct text, falls back to OCR if needed)
def extract_text_from_pdf(pdf_bytes):
    text = ""
    try:
        # Try extracting text directly (for digital PDFs)
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
        
        # If little text extracted, assume scanned and use OCR
        if len(text.strip()) < 100:  # Arbitrary threshold for "little text"
            text = ""
            images = convert_from_bytes(pdf_bytes)
            for img in images:
                text += pytesseract.image_to_string(img) + "\n"
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
    return text

# Function to call free AI (Hugging Face Mistral model, no API key needed)
def extract_amounts_with_ai(invoice_text):
    url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
    prompt = f"""
    You are an expert at extracting amounts from invoice text. Analyze the following invoice text carefully.
    Identify the final total amount (the grand total or amount due) and the VAT amount (tax or value-added tax).
    Be accurate—do not guess. If VAT is not mentioned, set it to 0.
    Output only JSON in this exact format: {{"total": "exact amount as string", "vat": "exact amount as string"}}
    Invoice text: {invoice_text}
    """
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 100, "return_full_text": False}
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()[0]['generated_text'].strip()
        # Parse the JSON output
        data = json.loads(result)
        return data.get('total', 'Not found'), data.get('vat', 'Not found')
    except Exception as e:
        st.error(f"Error with AI extraction: {str(e)}")
        return "Error", "Error"

# Streamlit app
st.title("Invoice Extractor App")
st.write("Upload one or more PDF invoices. The app will extract the total and VAT amounts using a free AI and output an Excel file.")

uploaded_files = st.file_uploader("Upload PDF invoices", type="pdf", accept_multiple_files=True)

if uploaded_files:
    data = []
    for uploaded_file in uploaded_files:
        pdf_bytes = uploaded_file.read()
        invoice_text = extract_text_from_pdf(pdf_bytes)
        if invoice_text:
            total, vat = extract_amounts_with_ai(invoice_text)
            data.append({"Invoice": uploaded_file.name, "Total": total, "VAT": vat})
    
    if data:
        df = pd.DataFrame(data)
        # Create Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        
        st.download_button(
            label="Download Excel",
            data=output,
            file_name="extracted_invoices.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

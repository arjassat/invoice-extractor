# streamlit_app.py
import streamlit as st
import fitz            # PyMuPDF
import re
import pandas as pd
import io
from decimal import Decimal, InvalidOperation

st.set_page_config(page_title="Invoice Total & VAT Extractor", layout="wide")
st.title("📄 Invoice Total & VAT Extractor")
st.write("Upload invoices (PDF). The app extracts invoice number, date, subtotal, VAT and total. Review and download Excel.")

# --------------------------
# Helpers: parsing and cleaning
# --------------------------
CURRENCY_RE = r"(?:(?:R|\$|€|£)\s*)?[-+]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?"

def normalize_amount_text(s: str):
    """Return normalized numeric string or None."""
    if s is None: return None
    s = s.strip()
    # remove currency letters before/after
    s = re.sub(r"[^\d\.,\-]", "", s)
    # unify comma thousands vs decimal
    # heuristic: if comma exists and there is a dot -> comma thousands
    if s.count(",") and s.count("."):
        s = s.replace(",", "")
    else:
        # if comma present and no dot, assume comma = decimal separator -> replace comma with dot
        if s.count(",") and not s.count("."):
            s = s.replace(",", ".")
    # remove spaces
    s = s.replace(" ", "")
    # ensure only one minus
    s = s.replace("--", "-")
    return s

def to_decimal(s: str):
    if not s: return None
    try:
        return Decimal(normalize_amount_text(s))
    except (InvalidOperation, TypeError):
        return None

def find_amounts_in_text(text):
    # find all currency-like amounts
    found = re.findall(CURRENCY_RE, text)
    cleaned = []
    for f in found:
        f_norm = normalize_amount_text(f)
        val = to_decimal(f_norm)
        if val is not None:
            cleaned.append((f.strip(), val))
    return cleaned

def search_label_value_pairs(text):
    # common labels and patterns to look for
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    results = {
        "invoice_number": None,
        "invoice_date": None,
        "subtotal": None,
        "vat_amount": None,
        "total_amount": None
    }

    # invoice number patterns
    for ln in lines:
        m = re.search(r"(invoice\s*no[:\s]*|inv(?:\.|o)?\s*#[:\s]*|invoice\s*#[:\s]*)([A-Z0-9\-\/]+)", ln, re.I)
        if m:
            results["invoice_number"] = m.group(2).strip()
            break

    # fallback invoice number: look for "Invoice" + short token
    if not results["invoice_number"]:
        for ln in lines[:30]:
            m = re.search(r"Invoice[:\s]*([A-Z0-9\-\/]+)", ln, re.I)
            if m:
                results["invoice_number"] = m.group(1).strip()
                break

    # invoice date patterns (many formats)
    date_re = r"(\b\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4}\b|\b\d{4}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{1,2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{4})"
    for ln in lines[:40]:
        m = re.search(r"(date[:\s]*|issue date[:\s]*|invoice date[:\s]*)" + date_re, ln, re.I)
        if m:
            results["invoice_date"] = m.group(2).strip() if m.lastindex and m.lastindex>=2 else m.group(1)
            break
    if not results["invoice_date"]:
        for ln in lines[:40]:
            m = re.search(date_re, ln)
            if m:
                results["invoice_date"] = m.group(0).strip()
                break

    # search for labelled monetary fields
    for ln in lines[::-1]:  # scan from bottom where totals usually are
        low = ln.lower()
        # total
        if any(k in low for k in ("total due", "amount due", "invoice total", "grand total", "\ttotal", "total:")):
            m = re.search(CURRENCY_RE, ln)
            if m:
                val = to_decimal(normalize_amount_text(m.group(0)))
                if val is not None and results["total_amount"] is None:
                    results["total_amount"] = str(val)
        # vat
        if any(k in low for k in ("vat", "tax", "vat amount", "tax amt", "vat:")):
            m = re.search(CURRENCY_RE, ln)
            if m:
                val = to_decimal(normalize_amount_text(m.group(0)))
                if val is not None and results["vat_amount"] is None:
                    results["vat_amount"] = str(val)
        # subtotal
        if any(k in low for k in ("subtotal", "sub total", "net total", "net amount")):
            m = re.search(CURRENCY_RE, ln)
            if m:
                val = to_decimal(normalize_amount_text(m.group(0)))
                if val is not None and results["subtotal"] is None:
                    results["subtotal"] = str(val)

    # Fallbacks: if total not found, pick the largest amount near bottom
    if not results["total_amount"]:
        amounts = find_amounts_in_text(text)
        if amounts:
            # choose largest numeric value
            largest = max(amounts, key=lambda x: x[1])[1]
            results["total_amount"] = str(largest)

    # convert decimals to strings for JSON-friendly export
    for k in ["subtotal","vat_amount","total_amount"]:
        if isinstance(results[k], Decimal):
            results[k] = str(results[k])

    return results

# --------------------------
# PDF text extraction
# --------------------------
def extract_text_from_pdf_bytes(pdf_bytes: bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            # get_text() works for digital PDFs; if not, will be empty
            page_text = page.get_text("text")
            text += page_text + "\n"
        return text
    except Exception as e:
        return ""

# --------------------------
# Streamlit UI
# --------------------------
uploaded = st.file_uploader("Upload one or more PDF invoices", type=["pdf"], accept_multiple_files=True)

if uploaded:
    st.info("Extracting text and parsing invoices...")
    rows = []
    for f in uploaded:
        pdf_bytes = f.read()
        text = extract_text_from_pdf_bytes(pdf_bytes)
        parsed = search_label_value_pairs(text)
        rows.append({
            "filename": f.name,
            "invoice_number": parsed.get("invoice_number") or "",
            "invoice_date": parsed.get("invoice_date") or "",
            "subtotal": parsed.get("subtotal") or "",
            "vat_amount": parsed.get("vat_amount") or "",
            "total_amount": parsed.get("total_amount") or ""
        })

    df = pd.DataFrame(rows)

    st.write("### Preview extracted values (edit if any are wrong)")
    edited = st.experimental_data_editor(df, num_rows="dynamic")

    st.write("### Final results")
    st.dataframe(edited)

    # Export to Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        edited.to_excel(writer, index=False, sheet_name="invoices")
    buffer.seek(0)

    st.download_button(
        label="⬇ Download results as Excel (.xlsx)",
        data=buffer,
        file_name="invoice_extraction_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("Done — verify values above and download the Excel file.")
    st.markdown("If some invoices are scanned images and the fields are empty, see the OCR notes below.")

# --------------------------
# OCR NOTES / Optional
# --------------------------
st.markdown("---")
st.markdown("### Notes on scanned PDFs / OCR")
st.markdown("""
- This app **extracts text directly** from PDFs using PyMuPDF. That is fast and accurate for digital invoices (text embedded in PDF).
- If a PDF is a pure image (scanned), the server needs OCR (e.g., pytesseract) to convert images to text. That **improves extraction** but sometimes requires system packages (Tesseract binary) that may not be preinstalled on free hosting.
- If you need robust OCR for many scanned invoices, we can add an OCR option that uses `pytesseract` and instructions to deploy on a host that supports installing Tesseract (I will provide the steps).
""")

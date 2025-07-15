import streamlit as st
import os
import json
import re
from datetime import datetime

from utils.parser_docx import parse_docx_status
from utils.parser_pdf import parse_pdf_status
from utils.parser_pptx import parse_pptx_status
from utils.parser_vtt import parse_vtt_status
from utils.parser_email import parse_email_status
from pipeline.compare import compare_kpis
from pipeline.risk_detect import detect_risks
from pipeline.insight_extractor import extract_insights

# ---------- UI ----------
st.set_page_config(page_title="📋 Executive Insights Parser", layout="wide")
st.title("📁 Upload a Project Document")

uploaded_file = st.file_uploader("Upload a project update", type=["docx", "pdf", "pptx", "vtt", "eml", "msg"])
if not uploaded_file:
    st.stop()

# ---------- METADATA INPUT ----------
st.subheader("🏷️ Project Metadata")

state = st.selectbox("State", ["FL", "TX", "CA", "Other"])
agency = st.text_input("Agency Name")
division = st.text_input("Division (optional)")
project_title = st.text_input("Project Title")
report_date = st.date_input("Report Date", value=datetime.today()).strftime("%Y-%m-%d")

if not project_title or not agency:
    st.warning("Please enter both a Project Title and Agency to continue.")
    st.stop()

# ---------- SAVE RAW FILE ----------
os.makedirs("data/raw/", exist_ok=True)
raw_path = f"data/raw/{uploaded_file.name}"
with open(raw_path, "wb") as f:
    f.write(uploaded_file.getbuffer())

# ---------- PARSE BASED ON FILE TYPE ----------
file_type = uploaded_file.name.split(".")[-1].lower()
result = {}
try:
    if file_type == "docx":
        result = parse_docx_status(raw_path)
    elif file_type == "pdf":
        result = parse_pdf_status(raw_path)
    elif file_type == "pptx":
        result = parse_pptx_status(raw_path)
    elif file_type == "vtt":
        result = parse_vtt_status(raw_path)
    elif file_type in ["eml", "msg"]:
        result = parse_email_status(raw_path)
    else:
        st.error("Unsupported file type.")
        st.stop()
except Exception as e:
    st.error(f"❌ Parsing failed: {e}")
    st.stop()

raw_text = result.get("raw_text", "")
summary_data = result.get("parsed", {})

# ---------- ADD METADATA ----------
summary_data.update({
    "state": state,
    "agency": agency,
    "division": division,
    "project_title": project_title,
    "report_date": report_date,
    "source_file": uploaded_file.name,
})

# ---------- KPI & RISK DETECTION ----------
if "kpis" not in summary_data and raw_text:
    summary_data["kpis"] = compare_kpis(raw_text)

if raw_text:
    summary_data["risks"] = detect_risks(raw_text)
    summary_data["insights"] = extract_insights(raw_text)

# ---------- DISPLAY PREVIEW ----------
st.subheader("📌 Parsed Summary")
st.json(summary_data)

with st.expander("🧾 Raw Text Preview", expanded=False):
    st.text(raw_text[:5000] if raw_text else "No raw text found.")

# ---------- SAVE SNAPSHOT ----------
project_id = re.sub(r'[^a-zA-Z0-9_]', '_', project_title.strip().lower())
folder = f"data/processed/{state}/{agency}/{project_id}/"
os.makedirs(folder, exist_ok=True)
filename = f"{report_date}.json"
save_path = os.path.join(folder, filename)

if st.button("💾 Save this snapshot"):
    with open(save_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    st.success(f"📁 Snapshot saved: {save_path}")
    st.write("📁 Full path:", os.path.abspath(save_path))

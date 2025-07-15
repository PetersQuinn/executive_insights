import streamlit as st
import os
import json
import re
from datetime import datetime

from utils.parser_docx import parse_docx_status
from pipeline.compare import compare_kpis
from pipeline.risk_detect import detect_risks

st.set_page_config(page_title="📋 Executive Insights Parser", layout="wide")
st.title("📄 Upload Weekly Project Update (.docx)")

uploaded_file = st.file_uploader("Upload a project document", type=["docx", "pdf", "pptx", "eml", "msg", "vtt"])

if uploaded_file:
    # Save raw file
    os.makedirs("data/raw/", exist_ok=True)
    raw_path = f"data/raw/{uploaded_file.name}"
    with open(raw_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Parse file
    try:
        result = parse_docx_status(raw_path)
        current_kpis = result.get("parsed", {})
        raw_text = result.get("raw_text", "")
    except Exception as e:
        st.error(f"❌ Parsing failed: {e}")
        st.stop()

    # Validate required keys
    if not current_kpis or "kpis" not in current_kpis:
        st.error("❌ Parsed data is missing required 'kpis' field.")
        st.stop()

    # Sanitize project name and generate filename
    project_name_raw = current_kpis.get("project_name", "unnamed_project")
    project_name_clean = re.sub(r'[^a-zA-Z0-9_]', '_', project_name_raw.strip().lower())
    report_date = current_kpis.get("report_date")
    if not report_date:
        report_date = datetime.now().strftime("%Y-%m-%d")  # fallback
    processed_path = f"data/processed/{project_name_clean}_{report_date}.json"

    # Show parsed content
    st.subheader("📌 Parsed Summary")
    st.json(current_kpis)

    with st.expander("🧾 Raw Text", expanded=False):
        st.text(raw_text)

    # Save new snapshot
    if st.button("💾 Save this snapshot"):
        os.makedirs("data/processed/", exist_ok=True)
        with open(processed_path, "w") as f:
            json.dump(current_kpis, f, indent=2)
        st.success(f"📁 Snapshot saved: {processed_path}")
        st.write("📁 Full save path:", os.path.abspath(processed_path))

import streamlit as st
from utils.parser_docx import parse_docx_status

st.set_page_config(page_title="📋 Executive Insights Parser", layout="wide")
st.title("📄 Upload Weekly Project Update (.docx)")

uploaded_file = st.file_uploader("Upload a project update DOCX file", type=["docx"])

if uploaded_file:
    with open("temp_upload.docx", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    result = parse_docx_status("temp_upload.docx")

    st.subheader("📌 Parsed Summary")
    st.json(result["parsed"])

    with st.expander("🧾 Raw Text", expanded=False):
        st.text(result["raw_text"])

import streamlit as st
import os
import re
import json
import sqlite3
from datetime import datetime
from utils.parser_docx import parse_docx_status
from utils.parser_pdf import parse_pdf_status
from utils.parser_pptx import parse_pptx_status
from utils.parser_vtt import parse_vtt_status
from utils.parser_email import parse_email_status
from pipeline.compare import compare_kpis
from pipeline.risk_detect import detect_risks
import hashlib

# ---------- INIT DB ----------
DB_PATH = "data/project_data.db"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    issuer TEXT,
    start_date TEXT,
    summary TEXT,
    contacts TEXT,
    tags TEXT,
    rfp_file TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    filename TEXT,
    file_type TEXT,
    report_date TEXT,
    uploaded_at TEXT,
    raw_text TEXT,
    metadata TEXT,
    llm_output TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
)
''')

# Create the risk_cache table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS risk_cache (
    project_id TEXT,
    current_date TEXT,
    previous_date TEXT,
    snapshot_pair_hash TEXT PRIMARY KEY,
    risk_json TEXT,
    generated_at TEXT
)
""")

conn.commit()

# ---------- PAGE UI ----------
st.set_page_config(page_title="🗂️ Project Manager Hub", layout="wide")
st.title("🧩 Project Manager")
tabs = st.tabs(["➕ Initialize Project", "📁 Upload File", "📂 View Uploaded Files"])

# ---------- TAB 1: Project Initialization ----------
with tabs[0]:
    st.subheader("➕ Create New Project")
    with st.form("create_project_form"):
        name = st.text_input("Project Name")
        issuer = st.text_input("Issuer / Client")
        start_date = st.date_input("Start Date").strftime("%Y-%m-%d")
        summary = st.text_area("Project Summary")
        contacts = st.text_area("Key Contacts (Name, Role, Email)")
        tags = st.text_input("Tags (comma-separated)")
        status = st.selectbox("Project Status", ["active", "completed", "archived"])
        submitted = st.form_submit_button("✅ Create Project")

        if submitted:
            project_id = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip().lower())
            cursor.execute("""
                INSERT OR REPLACE INTO projects
                (id, name, issuer, start_date, summary, contacts, tags, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, name, issuer, start_date, summary,
                contacts, tags, status, datetime.now().isoformat()
            ))
            conn.commit()
            st.success(f"✅ Project '{name}' initialized.")

# ---------- TAB 2: Upload and Parse File ----------
with tabs[1]:
    
    st.subheader("📄 Upload Project File")

    # --- Project Selector ---
    project_options = cursor.execute("SELECT id, name FROM projects").fetchall()

    if not project_options:
        st.warning("No projects found. Please create a project first.")
        st.stop()

    project_map = {f"{name} ({pid})": pid for pid, name in project_options}
    selected_label = st.selectbox("Select Project", list(project_map.keys()))
    selected_project = project_map.get(selected_label)

    if not selected_project:
        st.warning("Please select a project to proceed.")
        st.stop()

    # --- Upload File ---
    uploaded_file = st.file_uploader("Upload a document", type=["docx", "pdf", "pptx", "vtt", "eml", "msg"])

    if uploaded_file:
        file_type = uploaded_file.name.split(".")[-1].lower()

        try:
            if file_type == "docx":
                result = parse_docx_status(uploaded_file)
            elif file_type == "pdf":
                result = parse_pdf_status(uploaded_file)
            elif file_type == "pptx":
                result = parse_pptx_status(uploaded_file)
            elif file_type == "vtt":
                result = parse_vtt_status(uploaded_file)
            elif file_type in ["eml", "msg"]:
                result = parse_email_status(uploaded_file)
            else:
                st.error("Unsupported file type.")
                st.stop()
        except Exception as e:
            st.error(f"❌ Parsing failed: {e}")
            st.stop()

        raw_text = result.get("raw_text", "")
        parsed = result.get("parsed", {})
        report_date = parsed.get("report_date")

        # --- Look up most recent prior report for comparison ---
        previous_kpis = {}
        if report_date:
            cursor.execute("""
                SELECT metadata FROM files
                WHERE project_id = ? AND report_date < ?
                ORDER BY report_date DESC
                LIMIT 1
            """, (selected_project, report_date))
            row = cursor.fetchone()
            if row:
                try:
                    previous_metadata = json.loads(row[0])
                    previous_kpis = previous_metadata.get("kpis", {})
                except:
                    previous_kpis = {}

        # --- Compare KPIs + Detect Risks ---
            kpis_now = parsed.get("kpis", {})
            parsed["kpis"] = kpis_now
            # Predefine llm_output structure before risk detection
            llm_output = {
                "project_name": parsed.get("project_name"),
                "report_date": report_date,
                "summary": parsed.get("summary"),
                "kpis": parsed.get("kpis", {}),
                "risks": {},  # will be filled below
                "issues": parsed.get("issues", ""),
                "next_steps": parsed.get("next_steps", "")
            }
            # ---------- Risk Cache Handling ----------
            # Generate a unique hash for this snapshot comparison
            hash_input = json.dumps(previous_kpis, sort_keys=True) + json.dumps(kpis_now, sort_keys=True)
            snapshot_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            # Check if this comparison already exists
            cursor.execute("""
                SELECT risk_json FROM risk_cache WHERE snapshot_pair_hash = ?
            """, (snapshot_hash,))
            existing = cursor.fetchone()

            if existing:
                risks = json.loads(existing[0])
                st.info("✅ Risks loaded from cache.")
            else:
                try:
                    risks = detect_risks(kpis_now, previous_kpis)
                    cursor.execute("""
                        INSERT INTO risk_cache (project_id, current_date, previous_date, snapshot_pair_hash, risk_json, generated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        selected_project,
                        report_date,
                        parsed.get("previous_report_date", "N/A"),  # Optional tracking
                        snapshot_hash,
                        json.dumps(risks),
                        datetime.now().isoformat()
                    ))
                    conn.commit()
                    st.success("🧠 Risks detected and cached.")
                except Exception as e:
                    risks = {}
                    st.error(f"❌ Risk detection failed: {e}")

            # Store risks into the parsed dict
            parsed["risks"] = risks
            llm_output["risks"] = risks


        # --- Fallback for missing date ---
        if not report_date:
            st.warning("⚠️ Report date not found in the document. Using today's date as fallback.")
            report_date = datetime.today().strftime("%Y-%m-%d")

        # --- Display Results ---
        st.subheader("📌 Parsed Preview")
        st.json(parsed)

        with st.expander("🧾 Raw Text Preview", expanded=False):
            st.text(raw_text[:5000] if raw_text else "No raw text found.")

        # --- Save ---
        if st.button("💾 Save to Project"):
            file_id = f"{selected_project}_{report_date}"
            
            # Save both: parsed metadata AND llm_output (for summary view)
            llm_output = {
                "project_name": parsed.get("project_name"),
                "report_date": report_date,
                "summary": parsed.get("summary"),
                "kpis": parsed.get("kpis", {}),
                "risks": parsed.get("risks", {}),
                "issues": parsed.get("issues", ""),
                "next_steps": parsed.get("next_steps", "")
            }

            cursor.execute("""
                INSERT OR REPLACE INTO files
                (id, project_id, filename, file_type, report_date, uploaded_at, raw_text, metadata, llm_output)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id, selected_project, uploaded_file.name, file_type,
                report_date, datetime.now().isoformat(),
                raw_text, json.dumps(parsed), json.dumps(llm_output)
            ))
            conn.commit()
            st.success("✅ File saved and linked to project.")


# ---------- TAB 3: View Uploaded Files ----------
with tabs[2]:
    st.subheader("📂 Files Uploaded for Project")

    if not project_options:
        st.warning("No projects found. Please create a project first.")
        st.stop()

    selected_label_view = st.selectbox("Select Project to View Files", list(project_map.keys()), key="view_project_select")
    selected_project_view = project_map.get(selected_label_view)

    if not selected_project_view:
        st.warning("Please select a project to proceed.")
        st.stop()

    files = cursor.execute("""
        SELECT filename, report_date, uploaded_at, metadata
        FROM files
        WHERE project_id = ?
        ORDER BY report_date DESC
    """, (selected_project_view,)).fetchall()

    if not files:
        st.info("No files uploaded for this project yet.")
    else:
        for filename, report_date, uploaded_at, metadata_json in files:
            st.markdown(f"### 📁 `{filename}`")
            st.markdown(f"- 🗓️ Report Date: **{report_date}**")
            st.markdown(f"- ⏱️ Uploaded At: `{uploaded_at}`")

            try:
                metadata = json.loads(metadata_json)
                with st.expander("📌 Parsed Metadata", expanded=False):
                    st.json(metadata)
            except Exception as e:
                st.error(f"Error reading metadata: {e}")

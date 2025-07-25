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
import pandas as pd

# ---------- INIT DB ----------
DB_PATH = "data/project_data.db"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)

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
tabs = st.tabs([
    "➕ Initialize Project",
    "📁 Upload File",
    "📂 View Uploaded Files",
    "📊 Upload Excel Snapshot"
])


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
    uploaded_files = st.file_uploader(
    "Upload project files (folder or multiple)", 
    type=["docx", "pdf", "pptx", "vtt", "eml", "msg"], 
    accept_multiple_files=True
)


    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_type = uploaded_file.name.split(".")[-1].lower()
            st.markdown(f"---\n### 📄 Processing: `{uploaded_file.name}`")

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
                    continue
            except Exception as e:
                st.error(f"❌ Parsing failed: {e}")
                continue

            raw_text = result.get("raw_text", "")
            parsed = result.get("parsed", {})
            report_date = parsed.get("report_date") or datetime.today().strftime("%Y-%m-%d")

            # Get previous KPIs
            previous_kpis = {}
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

            # Generate hash
            kpis_now = parsed.get("kpis", {})
            hash_input = json.dumps(previous_kpis, sort_keys=True) + json.dumps(kpis_now, sort_keys=True)
            snapshot_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            # Risk detection
            cursor.execute("SELECT risk_json FROM risk_cache WHERE snapshot_pair_hash = ?", (snapshot_hash,))
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
                        parsed.get("previous_report_date", "N/A"),
                        snapshot_hash,
                        json.dumps(risks),
                        datetime.now().isoformat()
                    ))
                    conn.commit()
                    st.success("🧠 Risks detected and cached.")
                except Exception as e:
                    risks = {}
                    st.error(f"❌ Risk detection failed: {e}")

            parsed["risks"] = risks

            # Preview
            st.subheader("📌 Parsed Preview")
            st.json(parsed)
            with st.expander("🧾 Raw Text Preview", expanded=False):
                st.text(raw_text[:5000] if raw_text else "No raw text found.")

            # Save button per file
            if st.button(f"💾 Save {uploaded_file.name}", key=f"save_{uploaded_file.name}"):
                file_id = f"{selected_project}_{report_date}"
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
                st.success(f"✅ `{uploaded_file.name}` saved to project.")



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

# ---------- TAB 4: Upload Excel Snapshot ----------
with tabs[3]:
    st.subheader("📊 Upload Excel-Based Project Snapshot")

    with st.form("upload_excel_form"):
        uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])
        submitted = st.form_submit_button("📅 Upload Snapshot")

    if submitted and uploaded_file:
        try:
            xl = pd.ExcelFile(uploaded_file)

            # --- Title Page: Basic Project Info ---
            title_df = xl.parse("Contents", header=None)

            name = title_df.iloc[2, 1]       # B3
            issuer = title_df.iloc[3, 1]     # B4
            start_date = title_df.iloc[4, 1] # B5
            summary = title_df.iloc[5, 1]    # B6
            tags = title_df.iloc[9, 1]       # B10
            status = title_df.iloc[1, 1]     # B2
            created_at = datetime.now().isoformat()

            if not name:
                st.error("❌ 'Project Name' is required in the Title Page.")
                st.stop()

            project_id = name.strip().lower().replace(" ", "_")

            # --- Contacts Sheet: Flexible Multi-Row Contacts ---
            df_contacts = xl.parse("Contents", header=None)
            df_clean = df_contacts.iloc[20:, 0:4]  # From row 21 down, columns A–D
            df_clean = df_clean.dropna(how="all")
            df_clean = df_clean.dropna(subset=[1])  # Require Name
            df_clean.columns = ["Role", "Name", "Organization", "Email"]
            contacts_list = df_clean.to_dict(orient="records")
            contacts_json = json.dumps(contacts_list)

           # --- Check if Project Already Exists ---
            cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
            existing = cursor.fetchone()

            if existing:
                selected_project_id = project_id
                st.success(f"✅ Snapshot will be added to existing project '{name}'.")
            else:
                cursor.execute("""
                    INSERT INTO projects
                    (id, name, issuer, start_date, summary, contacts, tags, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    project_id, name, issuer, start_date, summary,
                    contacts_json, tags, status, created_at
                ))
                conn.commit()
                selected_project_id = project_id
                st.success(f"🆕 Project '{name}' created and initialized.")



            # --- Budget Sheet: Optional Extraction ---
            try:
                budget_df = xl.parse("Budget")
                budget_row = budget_df.dropna().iloc[0]
                allotted = float(budget_row["Allotted Budget"])
                spent = float(budget_row["Spent Budget"])
                remaining = allotted - spent
                percent_spent = (spent / allotted) * 100
            except:
                allotted = spent = remaining = percent_spent = None

            # --- Schedule Sheet: Extract Task Data ---
            try:
                schedule_df = xl.parse("Schedule")
                schedule_df = schedule_df.dropna(how="all")

                expected_columns = [
                    "Task ID", "Task Name", "Description", "Assigned To",
                    "Start Date", "End Date", "Duration (Days)", "Status", "Dependencies"
                ]

                if all(col in schedule_df.columns for col in expected_columns):
                    # Convert datetime columns to ISO string format
                    schedule_df["Start Date"] = pd.to_datetime(schedule_df["Start Date"], errors="coerce").dt.strftime("%Y-%m-%d")
                    schedule_df["End Date"] = pd.to_datetime(schedule_df["End Date"], errors="coerce").dt.strftime("%Y-%m-%d")

                    # Extract only the expected columns, as list of dicts
                    schedule = schedule_df[expected_columns].to_dict(orient="records")
                    st.success(f"✅ Parsed {len(schedule)} tasks from the Schedule sheet.")
                else:
                    st.warning("⚠️ Schedule sheet missing expected columns. Skipping task parsing.")
                    schedule = []
            except Exception as e:
                st.warning(f"⚠️ Failed to parse Schedule sheet: {e}")
                schedule = []
            
            # --- Issue Log Sheet: Extract Issue Data ---
            try:
                issue_df = xl.parse("Issue Log")
                issue_df = issue_df.dropna(how="all")

                expected_issue_columns = [
                    "Issue #", "Issue Creation Date", "Issue Category", "Issue Detail",
                    "Recommended Action", "Owner", "Status", "Due Date", "Resolution"
                ]

                if all(col in issue_df.columns for col in expected_issue_columns):
                    # Convert Timestamp objects to string for JSON serialization
                    issue_df["Issue Creation Date"] = issue_df["Issue Creation Date"].astype(str)
                    issue_df["Due Date"] = issue_df["Due Date"].astype(str)

                    issues = issue_df[expected_issue_columns].to_dict(orient="records")
                    st.success(f"✅ Parsed {len(issues)} issues from the Issue Log.")
                else:
                    st.warning("⚠️ Issue Log sheet missing expected columns. Skipping issue parsing.")
                    issues = []
            except Exception as e:
                st.warning(f"⚠️ Failed to parse Issue Log sheet: {e}")
                issues = []


            # --- Construct llm_output Snapshot JSON ---
            llm_output = {
                "report_date": datetime.now().strftime("%Y-%m-%d"),
                "source": "excel",
                "summary": None,
                "kpis": {
                    "budget": f"${allotted:,.0f} ({percent_spent:.0f}% used)" if allotted else None,
                    "timeline": "On Track",
                    "scope": "Unchanged",
                    "client_sentiment": "Positive",
                    "allotted_budget": allotted,
                    "spent_budget": spent,
                    "remaining_budget": remaining,
                    "percent_spent": percent_spent
                },
                "schedule": schedule,
                "issues": issues,
                "risks": [],
                "deliverables": [],
                "extra_notes": {
                    "client_feedback": "Positive"
                }
            }

            file_id = f"{selected_project_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute("""
                INSERT INTO files (id, project_id, filename, file_type, report_date, uploaded_at, raw_text, metadata, llm_output)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_id, selected_project_id, uploaded_file.name, "excel",
                llm_output["report_date"], datetime.now().isoformat(),
                "", "", json.dumps(llm_output)
            ))
            conn.commit()
            st.success("✅ Snapshot saved and Excel data parsed.")

        except Exception as e:
            st.error(f"❌ Failed to process Excel file: {e}")




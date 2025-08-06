import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import sqlite3
import os
from utils.openai_client import ask_gpt
from pipeline.risk_detect import detect_risks
from pipeline.compare import compare_kpis

st.set_page_config(page_title="📘 Project Overview", layout="wide")
st.title("🧠 Project Overview Dashboard")

# Ensure DB path exists
os.makedirs("data", exist_ok=True)

# Connect to SQLite DB
conn = sqlite3.connect("data/project_data.db", check_same_thread=False)
cursor = conn.cursor()

# Load snapshot data from DB
cursor.execute("""
    SELECT project_id, report_date, uploaded_at, llm_output
    FROM files
    WHERE report_date IS NOT NULL AND llm_output IS NOT NULL
    ORDER BY project_id, uploaded_at DESC
""")
rows = cursor.fetchall()

# Map snapshots by project_id
project_map = {}
for project_id, report_date, uploaded_at, llm_output in rows:
    if project_id not in project_map:
        project_map[project_id] = []
    project_map[project_id].append({
        "report_date": report_date,
        "uploaded_at": uploaded_at,
        "data": llm_output  # Still needs to be parsed later
    })

# List of unique project names
project_names = sorted(project_map.keys())

# Define the tabs for this page
tabs = st.tabs(["📝 Executive Summary", "🚨 Risk Dashboard", "🔍 AI Insights Feed"])

# === Executive Summary Tab ===
with tabs[0]:
    st.subheader("📝 AI-Generated Project Summary")
    selected_project = st.selectbox("Select a project", project_names, key="summary_project")
    tone = st.radio("Choose summary tone", ["Formal", "Friendly", "Technical"], horizontal=True)

    # Fix: Properly access report_date for display
    snapshot_options = [
        f"{snap['report_date']} — index {i}"
        for i, snap in enumerate(project_map[selected_project])
    ]
    selected_snapshots = st.multiselect("Select snapshot(s)", snapshot_options, key="summary_snapshots")

    if st.button("▶️ Generate Summary"):
        combined_entries = []

        for option in selected_snapshots:
            index = int(option.split("index ")[-1])
            raw_data = project_map[selected_project][index].get("data")

            if not raw_data:
                st.warning(f"⚠️ Snapshot {index} missing data.")
                continue

            try:
                combined_entries.append(raw_data)
            except Exception as e:
                st.warning(f"⚠️ Skipped malformed snapshot at index {index}: {e}")

        if not combined_entries:
            st.info("Please select at least one valid snapshot.")
        else:
            st.subheader("📂 Combined Snapshot Preview")
            st.json(combined_entries)

            with st.spinner("Generating executive summary..."):
                prompt = f"""
You are a senior analyst assistant. Use a **{tone}** tone to summarize the following project snapshot(s) into a brief executive summary (2–4 sentences), followed by a bullet list of key updates.

Snapshots:
{json.dumps(combined_entries, indent=2)}

Format your response in Markdown with:
- One short paragraph at the top (executive summary)
- Then 3–6 bullet points highlighting notable changes, risks, or progress
"""
                try:
                    response = ask_gpt(prompt)
                    st.subheader("🧠 Executive Summary")
                    st.markdown(response)
                except Exception as e:
                    st.error(f"❌ Failed to generate summary: {e}")


# === Risk Dashboard Tab ===
with tabs[1]:
    st.subheader("🚨 Project Risk Overview")
    selected_project = st.selectbox("Select a project", project_names, key="risk_project")

    snapshot_options = [f"{snap['report_date']} — index {i}" for i, snap in enumerate(project_map[selected_project])]
    selected_snapshots = st.multiselect("Select snapshot(s)", snapshot_options, key="risk_snapshots")

    if selected_snapshots:
        all_risks = []
        snapshot_risk_counts = []
        risk_category_counts = {}

        for option in selected_snapshots:
            index = int(option.split("index ")[-1])
            snap = project_map[selected_project][index]

            try:
                # Parse the 'data' field, which contains the LLM output as a JSON string
                parsed = json.loads(snap["data"])  # 👈 fixed this
                risks = parsed.get("risks", [])
                report_date = snap["report_date"]

                snapshot_risk_counts.append({"date": report_date, "count": len(risks)})

                for r in risks:
                    entry = r.copy()
                    entry["Snapshot Date"] = report_date
                    all_risks.append(entry)

                    category = r.get("Risk Category", "Unknown")
                    risk_category_counts[category] = risk_category_counts.get(category, 0) + 1

            except Exception as e:
                st.warning(f"❌ Failed to load snapshot {snap.get('report_date', 'Unknown')}: {e}")

        if not all_risks:
            st.info("No risks found in selected snapshots.")
            st.stop()

        # --- Snapshot Risk Count Bar Chart ---
        st.subheader("📊 Risk Count by Snapshot")
        snap_df = pd.DataFrame(snapshot_risk_counts)
        snap_df["date"] = pd.to_datetime(snap_df["date"])
        snap_df = snap_df.sort_values("date")

        fig, ax = plt.subplots()
        ax.bar(snap_df["date"].dt.strftime('%b %d'), snap_df["count"], color="red")
        ax.set_xlabel("Snapshot Date")
        ax.set_ylabel("Number of Risks")
        ax.set_title("Risk Volume per Snapshot")
        st.pyplot(fig)

        # --- Risk Category Pie Chart ---
        st.subheader("📈 Risk Distribution by Category")
        cat_labels = list(risk_category_counts.keys())
        cat_values = list(risk_category_counts.values())
        fig, ax = plt.subplots()
        ax.pie(cat_values, labels=cat_labels, autopct="%1.1f%%", startangle=140)
        ax.axis("equal")
        st.pyplot(fig)

# === AI Insights Feed Tab ===
with tabs[2]:
    st.subheader("🔍 Cross-Snapshot AI Insights")
    selected_project = st.selectbox("Select a project", project_names, key="insight_project")

    if selected_project:
        sorted_snapshots = list(reversed(project_map[selected_project]))
        snapshot_labels = [f"{snap['report_date']} — index {i}" for i, snap in enumerate(sorted_snapshots)]
        selected_options = st.multiselect("Select snapshots to include", snapshot_labels, key="insight_snapshots")

        selected_snapshots = []
        for option in selected_options:
            index = int(option.split("index ")[-1])
            snap = sorted_snapshots[index]
            try:
                parsed_data = json.loads(snap["data"])  # 👈 parse the JSON inside the "data" field
                selected_snapshots.append(parsed_data)
            except Exception as e:
                st.warning(f"⚠️ Skipped malformed snapshot: {e}")

        if selected_snapshots and st.button("🔍 Generate Insights"):
            st.subheader("📌 GPT Summary Across Selected Snapshots")
            with st.spinner("Generating insights..."):
                prompt = f"""
You are a cross-project insights generator.
Given the following snapshots, identify key trends, risks, and changes across the selected project timeline.
Highlight patterns in budget, scope, sentiment, and risk.

Summarize findings in 5–7 bullet points.

Snapshots:
{json.dumps(selected_snapshots, indent=2)}
"""
                try:
                    response = ask_gpt(prompt)
                    st.markdown(response)
                except Exception as e:
                    st.error(f"Failed to generate insights: {e}")

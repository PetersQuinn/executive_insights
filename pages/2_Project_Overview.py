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
conn = sqlite3.connect("data/project_data.db")
cursor = conn.cursor()

# Load snapshot data from DB
cursor.execute("""
    SELECT project_id, report_date, llm_output
    FROM files
    WHERE report_date IS NOT NULL AND llm_output IS NOT NULL
    ORDER BY project_id, report_date ASC
""")
rows = cursor.fetchall()

project_map = {}
for project_id, report_date, llm_output in rows:
    if project_id not in project_map:
        project_map[project_id] = []
    project_map[project_id].append((report_date, llm_output))

project_names = sorted(project_map.keys())

tabs = st.tabs(["📝 Executive Summary", "🚨 Risk Dashboard", "🔍 AI Insights Feed"])

# === Executive Summary Tab ===
with tabs[0]:
    st.subheader("📝 AI-Generated Project Summary")
    selected_project = st.selectbox("Select a project", project_names, key="summary_project")
    tone = st.radio("Choose summary tone", ["Formal", "Friendly", "Technical"], horizontal=True)

    snapshot_options = [f"{date} — index {i}" for i, (date, _) in enumerate(project_map[selected_project])]
    selected_snapshots = st.multiselect("Select snapshot(s)", snapshot_options, key="summary_snapshots")

    if st.button("▶️ Generate Summary"):
        combined_entries = []
        for option in selected_snapshots:
            index = int(option.split("index ")[-1])
            _, raw_json = project_map[selected_project][index]
            try:
                combined_entries.append(json.loads(raw_json))
            except Exception as e:
                st.warning(f"⚠️ Skipped malformed snapshot: {e}")

        if not combined_entries:
            st.info("Please select at least one snapshot.")
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
                    st.error(f"Failed to generate summary: {e}")

# === Risk Dashboard Tab ===
with tabs[1]:
    st.subheader("🚨 Project Risk Overview")
    selected_project = st.selectbox("Select a project", project_names, key="risk_project")
    if st.button("🔄 Refresh Risks"):
        snapshots = cursor.execute("""
            SELECT report_date, metadata
            FROM files
            WHERE project_id = ?
            ORDER BY report_date ASC
        """, (selected_project,)).fetchall()

        for i in range(1, len(snapshots)):
            prev_date, prev_meta = snapshots[i - 1]
            curr_date, curr_meta = snapshots[i]

            pair_hash = f"{selected_project}_{prev_date}_{curr_date}"
            exists = cursor.execute("SELECT 1 FROM risk_cache WHERE snapshot_pair_hash = ?", (pair_hash,)).fetchone()
            if exists:
                continue  # Already cached

            try:
                prev_kpis = json.loads(prev_meta).get("kpis", {})
                curr_kpis = json.loads(curr_meta).get("kpis", {})
                delta = compare_kpis(prev_kpis, curr_kpis)
                risks = detect_risks(curr_kpis, delta)

                cursor.execute("""
                    INSERT OR REPLACE INTO risk_cache (project_id, current_date, previous_date, snapshot_pair_hash, risk_json, generated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    selected_project, curr_date, prev_date, pair_hash,
                    json.dumps(risks), datetime.now().isoformat()
                ))
            except Exception as e:
                st.warning(f"❌ Failed risk calc for {curr_date}: {e}")

        conn.commit()
        st.success("✅ Risk cache refreshed.")

    snapshot_options = [f"{date} — index {i}" for i, (date, _) in enumerate(reversed(project_map[selected_project]))]
    selected_snapshots = st.multiselect("Select snapshot(s)", snapshot_options, key="risk_snapshots")

    if selected_snapshots:
        risk_summary = []
        category_counts = {"cost": 0, "timeline": 0, "scope": 0, "client_sentiment": 0}

        for option in selected_snapshots:
            index = int(option.split("index ")[-1])
            date, raw_json = project_map[selected_project][index]

            # Get previous snapshot's date (for pair hash)
            if index == 0:
                continue  # Can't evaluate risk without previous snapshot
            prev_date = project_map[selected_project][index - 1][0]
            pair_hash = f"{selected_project}_{prev_date}_{date}"

            # Fetch cached risk
            cursor.execute("SELECT risk_json FROM risk_cache WHERE snapshot_pair_hash = ?", (pair_hash,))
            row = cursor.fetchone()
            if not row:
                st.warning(f"⚠️ No cached risk found for {date}. Please refresh risks.")
                continue

            try:
                risks = json.loads(row[0])
                entry = {"snapshot": date, "date": date}
                total_highs = 0

                for category in category_counts:
                    alerts = risks.get(category, [])
                    alert_levels = [r["alert_level"] for r in alerts]
                    level = max(alert_levels, key=lambda x: ["LOW", "MEDIUM", "HIGH"].index(x)) if alert_levels else "NONE"
                    entry[category] = level
                    if level == "HIGH":
                        total_highs += 1
                        category_counts[category] += 1

                entry["total_high"] = total_highs
                risk_summary.append(entry)
            except Exception as e:
                st.warning(f"❌ Error reading cached risks for {date}: {e}")


        df = pd.DataFrame(risk_summary)
        st.subheader(f"📋 Risk Table for '{selected_project.replace('_', ' ').title()}'")

        def color_risk(val):
            colors = {"HIGH": "#ff4d4d", "MEDIUM": "#ffa500", "LOW": "#90ee90", "NONE": "#e0e0e0"}
            return f"background-color: {colors.get(val, 'white')}; color: black"

        styled_df = df.style.applymap(color_risk, subset=list(category_counts.keys()))
        st.dataframe(styled_df, use_container_width=True)

        st.subheader("📊 Risk Category Breakdown")
        fig, ax = plt.subplots()
        ax.bar(category_counts.keys(), category_counts.values(), color=["red", "orange", "blue", "purple"])
        ax.set_ylabel("# of HIGH Risk Snapshots")
        ax.set_title("High Risk Alerts by Category")
        st.pyplot(fig)

# === AI Insights Feed Tab ===
with tabs[2]:
    st.subheader("🔍 Cross-Snapshot AI Insights")
    selected_project = st.selectbox("Select a project", project_names, key="insight_project")

    if selected_project:
        sorted_snapshots = list(reversed(project_map[selected_project]))
        snapshot_labels = [f"{date} — index {i}" for i, (date, _) in enumerate(sorted_snapshots)]
        selected_options = st.multiselect("Select snapshots to include", snapshot_labels, key="insight_snapshots")

        selected_snapshots = []
        for option in selected_options:
            index = int(option.split("index ")[-1])
            selected_snapshots.append(sorted_snapshots[index][1])

        if selected_snapshots and st.button("🔍 Generate Insights"):
            all_snapshots = []
            for raw_json in selected_snapshots:
                try:
                    all_snapshots.append(json.loads(raw_json))
                except Exception as e:
                    st.warning(f"⚠️ Skipped malformed snapshot: {e}")

            st.subheader("📌 GPT Summary Across Selected Snapshots")
            with st.spinner("Generating insights..."):
                prompt = f"""
You are a cross-project insights generator.
Given the following snapshots, identify key trends, risks, and changes across the selected project timeline.
Highlight patterns in budget, scope, sentiment, and risk.

Summarize findings in 5–7 bullet points.

Snapshots:
{json.dumps(all_snapshots, indent=2)}
"""
                try:
                    response = ask_gpt(prompt)
                    st.markdown(response)
                except Exception as e:
                    st.error(f"Failed to generate insights: {e}")

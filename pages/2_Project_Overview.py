import streamlit as st
import os
import json
import re
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from utils.openai_client import ask_gpt
from pipeline.risk_detect import detect_risks

st.set_page_config(page_title="📘 Project Overview", layout="wide")
st.title("🧠 Project Overview Dashboard")

# --- Load processed snapshot data ---
processed_dir = "data/processed/"
summaries_dir = "data/summaries/"
os.makedirs(summaries_dir, exist_ok=True)

if not os.path.exists(processed_dir):
    st.warning("No processed files found.")
    st.stop()

project_files = [f for f in os.listdir(processed_dir) if f.endswith(".json")]
project_map = {}

# Group by project name
for filename in project_files:
    match = re.match(r"(.+)_((?:\d{4}-\d{2}-\d{2}))\.json", filename)
    if match:
        name = match.group(1)
        date = match.group(2)
        if name not in project_map:
            project_map[name] = []
        project_map[name].append((date, filename))

project_names = sorted(project_map.keys())

# --- Tabs ---
tabs = st.tabs(["📝 Executive Summary", "🚨 Risk Dashboard", "🔍 AI Insights Feed"])

# === TAB 1: Executive Summary ===
with tabs[0]:
    st.subheader("📝 AI-Generated Project Summary")
    selected_project = st.selectbox("Select a project", project_names, key="summary_project")
    tone = st.radio("Choose summary tone", ["Formal", "Friendly", "Technical"], horizontal=True)

    snapshot_options = [f"{date} — {fname}" for date, fname in sorted(project_map[selected_project])]
    selected_snapshots = st.multiselect("Select snapshot(s) to include in summary", snapshot_options, key="summary_snapshots")

    if st.button("▶️ Generate Summary"):
        combined_entries = []
        for option in selected_snapshots:
            _, filename = option.split(" — ", 1)
            with open(os.path.join(processed_dir, filename)) as f:
                combined_entries.append(json.load(f))

        if not combined_entries:
            st.info("Please select at least one snapshot.")
        else:
            st.subheader("📂 Combined Snapshot Preview")
            st.json(combined_entries)

            with st.spinner("Generating executive summary with GPT..."):
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

                    summary_record = {
                        "generated_at": datetime.now().isoformat(),
                        "project": selected_project,
                        "tone": tone,
                        "snapshots_used": selected_snapshots,
                        "summary": response
                    }
                    audit_path = os.path.join(summaries_dir, f"{selected_project}_summaries.json")
                    if os.path.exists(audit_path):
                        with open(audit_path, "r") as f:
                            past_summaries = json.load(f)
                    else:
                        past_summaries = []
                    past_summaries.append(summary_record)
                    with open(audit_path, "w") as f:
                        json.dump(past_summaries, f, indent=2)
                    st.success("Summary saved to audit trail.")
                except Exception as e:
                    st.error(f"Failed to generate summary: {e}")

# === TAB 2: Risk Dashboard ===
with tabs[1]:
    st.subheader("🚨 Project Risk Overview")
    selected_project = st.selectbox("Select a project to view risk details", project_names, key="risk_project")

    snapshot_options = [f"{date} — {fname}" for date, fname in sorted(project_map[selected_project], reverse=True)]
    selected_snapshots = st.multiselect("Select snapshot(s) to analyze risk", snapshot_options, key="risk_snapshots")

    if selected_snapshots:
        risk_summary = []
        category_counts = {"cost": 0, "timeline": 0, "scope": 0, "client_sentiment": 0}

        for option in selected_snapshots:
            _, filename = option.split(" — ", 1)
            path = os.path.join(processed_dir, filename)
            date_match = re.search(r"_(\d{4}-\d{2}-\d{2})\.json$", filename)
            date = date_match.group(1) if date_match else "Unknown"

            with open(path) as f:
                snapshot = json.load(f)
                kpis = snapshot.get("kpis", {})
                delta = {}
                risks = detect_risks(kpis, delta)

            entry = {"snapshot": filename, "date": date}
            total_highs = 0

            for category in ["cost", "timeline", "scope", "client_sentiment"]:
                alerts = risks.get(category, [])
                alert_levels = [r["alert_level"] for r in alerts]
                if alert_levels:
                    level = max(alert_levels, key=lambda x: ["LOW", "MEDIUM", "HIGH"].index(x))
                else:
                    level = "NONE"
                entry[category] = level
                if level == "HIGH":
                    total_highs += 1
                    category_counts[category] += 1

            entry["total_high"] = total_highs
            risk_summary.append(entry)

        df = pd.DataFrame(risk_summary)
        st.subheader(f"📋 Risk Table for '{selected_project.replace('_', ' ').title()}'")

        def color_risk(val):
            colors = {"HIGH": "#ff4d4d", "MEDIUM": "#ffa500", "LOW": "#90ee90", "NONE": "#e0e0e0"}
            return f"background-color: {colors.get(val, 'white')}; color: black"

        styled_df = df.style.applymap(color_risk, subset=["cost", "timeline", "scope", "client_sentiment"])
        st.dataframe(styled_df, use_container_width=True)

        st.subheader("📊 Risk Category Breakdown")
        fig, ax = plt.subplots()
        labels = list(category_counts.keys())
        values = list(category_counts.values())
        ax.bar(labels, values, color=["red", "orange", "blue", "purple"])
        ax.set_ylabel("# of HIGH Risk Snapshots")
        ax.set_title("High Risk Alerts by Category")
        st.pyplot(fig)

# === TAB 3: AI Insights Feed ===
with tabs[2]:
    st.subheader("🔍 Cross-Snapshot AI Insights")
    selected_project = st.selectbox("Select a project", project_names, key="insight_project")

    if selected_project:
        sorted_snapshots = sorted(project_map[selected_project], reverse=True)
        snapshot_labels = [f"{date}" for date, _ in sorted_snapshots]
        selected_labels = st.multiselect("Select snapshots to include in insights feed", snapshot_labels, key="insight_snapshots")
        selected_snapshots = [filename for date, filename in sorted_snapshots if date in selected_labels]

        if selected_snapshots:
            if st.button("🔍 Generate Insights"):
                all_snapshots = []
                for file in selected_snapshots:
                    with open(os.path.join(processed_dir, file)) as f:
                        all_snapshots.append(json.load(f))

                st.subheader("📌 GPT Summary Across Selected Snapshots")
                with st.spinner("Generating insights with GPT..."):
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
        else:
            st.info("Please select at least one snapshot to generate insights.")
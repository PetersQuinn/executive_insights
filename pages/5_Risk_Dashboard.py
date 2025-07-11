import streamlit as st
import os
import json
import re
import pandas as pd
import matplotlib.pyplot as plt
from pipeline.risk_detect import detect_risks

st.set_page_config(page_title="🚨 Risk Dashboard", layout="wide")
st.title("🔥 Project Risk Overview")

# --- Load and group snapshots ---
processed_dir = "data/processed/"
if not os.path.exists(processed_dir):
    st.warning("No processed snapshots found.")
    st.stop()

project_files = [f for f in os.listdir(processed_dir) if f.endswith(".json")]
project_map = {}

for filename in project_files:
    match = re.match(r"(.+)_((?:\d{4}-\d{2}-\d{2}))\.json", filename)
    if match:
        name = match.group(1)
        date = match.group(2)
        if name not in project_map:
            project_map[name] = []
        project_map[name].append((date, filename))

project_names = sorted(project_map.keys())
selected_project = st.selectbox("Select a project to view risk details", project_names)

# --- Show snapshot list for selected project ---
snapshot_options = [f"{date} — {fname}" for date, fname in sorted(project_map[selected_project], reverse=True)]
selected_snapshots = st.multiselect("Select snapshot(s) to analyze risk", snapshot_options)

if not selected_snapshots:
    st.info("Select one or more snapshots to continue.")
    st.stop()

# --- Analyze selected snapshots ---
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
        delta = {}  # Optional: use real delta if available
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

# --- Convert to DataFrame ---
df = pd.DataFrame(risk_summary)
if df.empty:
    st.info("No risk data found.")
    st.stop()

# --- Show Risk Table ---
st.subheader(f"📋 Risk Table for '{selected_project.replace('_', ' ').title()}'")
def color_risk(val):
    colors = {"HIGH": "#ff4d4d", "MEDIUM": "#ffa500", "LOW": "#90ee90", "NONE": "#e0e0e0"}
    return f"background-color: {colors.get(val, 'white')}; color: black"

styled_df = df.style.applymap(color_risk, subset=["cost", "timeline", "scope", "client_sentiment"])
st.dataframe(styled_df, use_container_width=True)

# --- Risk Category Breakdown ---
st.subheader("📊 Risk Category Breakdown")
fig, ax = plt.subplots()
labels = list(category_counts.keys())
values = list(category_counts.values())
ax.bar(labels, values, color=["red", "orange", "blue", "purple"])
ax.set_ylabel("# of HIGH Risk Snapshots")
ax.set_title("High Risk Alerts by Category")
st.pyplot(fig)

import streamlit as st
import os
import json
import re
from utils.openai_client import ask_gpt

st.set_page_config(page_title="🧠 AI Insights Feed", layout="wide")
st.title("🧠 AI Insights Feed")

# --- Load available processed files ---
processed_dir = "data/processed/"
if not os.path.exists(processed_dir):
    st.warning("No processed project files found.")
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

# --- Project selection hierarchy ---
project_names = sorted(project_map.keys())
selected_project = st.selectbox("Select a project", project_names)

selected_snapshots = []
if selected_project:
    sorted_snapshots = sorted(project_map[selected_project], reverse=True)
    snapshot_labels = [f"{date}" for date, _ in sorted_snapshots]
    selected_labels = st.multiselect("Select snapshots to include in the insights feed", snapshot_labels)

    selected_snapshots = [filename for date, filename in sorted_snapshots if date in selected_labels]

# --- Button-triggered generation ---
if selected_snapshots:
    if st.button("🔍 Generate Insights"):
        all_snapshots = []
        for file in selected_snapshots:
            with open(os.path.join(processed_dir, file)) as f:
                snapshot = json.load(f)
                all_snapshots.append(snapshot)

        # --- GPT cross-snapshot insights ---
        st.subheader("🔍 GPT Summary Across Selected Snapshots")
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

import streamlit as st
import os
import json
import re
from utils.openai_client import ask_gpt
from datetime import datetime

st.set_page_config(page_title="🧠 Executive Summary", layout="wide")
st.title("📝 AI-Generated Project Summary & Insights")

# --- Load available processed files ---
processed_dir = "data/processed/"
summaries_dir = "data/summaries/"
os.makedirs(summaries_dir, exist_ok=True)

if not os.path.exists(processed_dir):
    st.warning("No processed files found.")
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

# --- UI: Choose project and tone ---
project_names = sorted(project_map.keys())
selected_project = st.selectbox("Select a project", project_names)
tone = st.radio("Choose summary tone", ["Formal", "Friendly", "Technical"], horizontal=True)

# --- UI: Choose one or more snapshots ---
snapshot_options = [f"{date} — {fname}" for date, fname in sorted(project_map[selected_project])]
selected_snapshots = st.multiselect("Select snapshot(s) to include in summary", snapshot_options)

# --- Trigger Summary Generation ---
generate_summary = st.button("▶️ Generate Summary")

if generate_summary:
    # --- Combine selected snapshot data ---
    combined_entries = []
    for option in selected_snapshots:
        _, filename = option.split(" — ", 1)
        with open(os.path.join(processed_dir, filename)) as f:
            parsed = json.load(f)
            combined_entries.append(parsed)

    if not combined_entries:
        st.info("Please select at least one snapshot to summarize.")
        st.stop()

    # --- Show preview of combined data ---
    st.subheader("📂 Combined Snapshot Preview")
    st.json(combined_entries)

    # --- Generate Executive Summary ---
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
        except Exception as e:
            st.error(f"Failed to generate summary: {e}")
            response = None

    # --- Display and Save Summary ---
    if response:
        st.subheader("🧠 Executive Summary")
        st.markdown(response)

        # Save to audit trail
        summary_record = {
            "generated_at": datetime.now().isoformat(),
            "project": selected_project,
            "tone": tone,
            "snapshots_used": selected_snapshots,
            "summary": response
        }
        audit_path = os.path.join(summaries_dir, f"{selected_project}_summaries.json")
        try:
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
            st.warning(f"Could not save summary: {e}")

        if st.button("📋 Copy Summary to Clipboard"):
            st.code(response, language="markdown")

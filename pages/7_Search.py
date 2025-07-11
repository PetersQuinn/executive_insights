import streamlit as st
import os
import json
import re
from utils.openai_client import ask_gpt

st.set_page_config(page_title="🔎 Search Across Projects", layout="wide")
st.title("🔎 GPT Search Across Project Snapshots")

# --- Load processed files ---
processed_dir = "data/processed/"
if not os.path.exists(processed_dir):
    st.warning("No processed project files found.")
    st.stop()

project_files = [f for f in os.listdir(processed_dir) if f.endswith(".json")]
snapshot_data = []

for filename in project_files:
    match = re.match(r"(.+)_((?:\d{4}-\d{2}-\d{2}))\.json", filename)
    if match:
        name = match.group(1).replace("_", " ").title()
        date = match.group(2)
        with open(os.path.join(processed_dir, filename)) as f:
            parsed = json.load(f)
            snapshot_data.append({
                "project": name,
                "date": date,
                "filename": filename,
                "content": parsed
            })

# --- Input: Search query ---
query = st.text_input("Enter your question or search phrase")

if query and st.button("🔍 Run GPT Search"):
    st.subheader("📄 Matched Snapshots")

    chunks = [
        {
            "project": s["project"],
            "date": s["date"],
            "kpis": s["content"].get("kpis", {}),
            "summary": s["content"].get("summary", ""),
            "issues": s["content"].get("issues", ""),
            "next_steps": s["content"].get("next_steps", "")
        }
        for s in snapshot_data
    ]

    prompt = f"""
You are an expert assistant searching through project summaries.

A user asked:
"{query}"

Your job is to return the 3–5 most relevant snapshot entries from the list below. For each one, return:
- Project name
- Report date
- A short 1-sentence explanation of why it matched
- Any key content (summary, issues, next steps, or KPIs) relevant to the question

Entries:
{json.dumps(chunks, indent=2)}
"""

    with st.spinner("Searching with GPT..."):
        try:
            response = ask_gpt(prompt)
            st.markdown(response)
        except Exception as e:
            st.error(f"❌ GPT search failed: {e}")
else:
    st.info("Enter a search phrase and press the button to begin.")

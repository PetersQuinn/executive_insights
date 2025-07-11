import streamlit as st
import os
import json
import re
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="📈 Project KPI History", layout="wide")
st.title("📊 KPI Trends Over Time")

# --- Load snapshot data ---
processed_dir = "data/processed/"
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

# --- Select project to view history ---
project_names = sorted(project_map.keys())
selected_project = st.selectbox("Select a project to view KPI trends", project_names)

# --- Load snapshots into a DataFrame ---
snapshots = sorted(project_map[selected_project])
data = []

for date, filename in snapshots:
    with open(os.path.join(processed_dir, filename)) as f:
        parsed = json.load(f)
        kpis = parsed.get("kpis", {})
        row = {
            "date": date,
            "budget": kpis.get("budget", None),
            "timeline": kpis.get("timeline", None),
            "scope": kpis.get("scope", None),
            "sentiment": kpis.get("client sentiment", None)
        }
        data.append(row)

if not data:
    st.info("No KPI snapshots found for this project.")
    st.stop()

# --- Convert to DataFrame ---
df = pd.DataFrame(data)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

# --- Parse budget values if numeric ---
def extract_budget_amount(text):
    if not isinstance(text, str):
        return None
    match = re.search(r"\$?([\d,.]+)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None

df["budget_numeric"] = df["budget"].apply(extract_budget_amount)

# --- Plot budget trend ---
st.subheader("💰 Budget Utilization Over Time")
fig, ax = plt.subplots()
ax.plot(df["date"], df["budget_numeric"], marker="o")
ax.set_ylabel("Budget ($)")
ax.set_xlabel("Date")
ax.set_title("Budget Trend")
fig.autofmt_xdate(rotation=45)
ax.tick_params(axis='x', labelsize=9)
st.pyplot(fig)

# --- Timeline as categorical line trend ---
def plot_categorical_trend(column, title):
    st.subheader(title)
    fig, ax = plt.subplots()
    ax.plot(df["date"], df[column], marker="o", linestyle="--")
    ax.set_xlabel("Date")
    ax.set_ylabel(column.title())
    ax.set_title(f"{column.title()} Over Time")
    fig.autofmt_xdate(rotation=45)
    ax.tick_params(axis='x', labelsize=9)
    st.pyplot(fig)

plot_categorical_trend("timeline", "📅 Timeline Status Over Time")

# --- Scope and Sentiment as annotated lists ---
def display_text_trend(column, title, emoji=""):
    st.subheader(f"{emoji} {title}")
    simplified = df[["date", column]].dropna()
    simplified[column] = simplified[column].astype(str).str.strip()

    for _, row in simplified.iterrows():
        st.markdown(f"- **{row['date'].strftime('%b %d')}**: {row[column]}")

display_text_trend("scope", "Scope Updates", "📦")
display_text_trend("sentiment", "Client Sentiment Changes", "💬")

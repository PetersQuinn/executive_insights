import streamlit as st
import os
import json
import re
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pipeline.compare import compare_kpis
from pipeline.risk_detect import detect_risks

st.set_page_config(page_title="📈 Project History Dashboard", layout="wide")
st.title("📚 Project History Overview")

# --- Load processed snapshot data ---
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

project_names = sorted(project_map.keys())

# --- Tabs for History + Trends ---
tabs = st.tabs(["🔁 Recent Trends", "📊 KPI History"])

# === TAB 1: Recent Trends ===
with tabs[0]:
    st.subheader("🔍 Compare Latest KPI Snapshots")
    selected_projects = st.multiselect("Select projects to compare", project_names)

    def format_arrow(before_after):
        try:
            before, after = before_after.split(" → ")
            return f"{before} → {after}"
        except:
            return before_after

    emoji_map = {
        "HIGH": "🔴",
        "MEDIUM": "🟠",
        "LOW": "🟢"
    }

    for project in selected_projects:
        st.markdown(f"### 🧹 {project.replace('_', ' ').title()}")
        sorted_files = sorted(project_map[project], reverse=True)

        if len(sorted_files) < 2:
            st.warning("Not enough snapshots to compare.")
            continue

        date_latest, file_latest = sorted_files[0]
        date_prev, file_prev = sorted_files[1]

        with open(os.path.join(processed_dir, file_latest)) as f:
            latest_data = json.load(f)
        with open(os.path.join(processed_dir, file_prev)) as f:
            prev_data = json.load(f)

        latest_kpis = latest_data.get("kpis", {})
        prev_kpis = prev_data.get("kpis", {})

        delta = compare_kpis(latest_kpis, prev_kpis)
        risks = detect_risks(latest_kpis, delta)

        st.write(f"**Latest:** {date_latest} | **Previous:** {date_prev}")

        st.subheader("📉 KPI Changes")
        kpi_table = []

        if "budget_change" in delta:
            budget_delta = delta["budget_change"]
            percent = delta.get("budget_percent_change", 0)
            kpi_table.append(("Budget", f"${budget_delta:,.0f}", f"{percent:+.1f}%"))

        if "timeline_change" in delta:
            kpi_table.append(("Timeline", format_arrow(delta["timeline_change"]), ""))

        if "scope_change" in delta:
            kpi_table.append(("Scope", format_arrow(delta["scope_change"]), ""))

        if "sentiment_change" in delta:
            kpi_table.append(("Client Sentiment", format_arrow(delta["sentiment_change"]), ""))

        if kpi_table:
            st.table(kpi_table)
        else:
            st.info("No KPI differences found.")

        st.subheader("⚠️ Detected Risks")
        for category, items in risks.items():
            if not items:
                continue
            with st.expander(f"📌 {category.title()} Risks ({len(items)})", expanded=True):
                for risk in items:
                    emoji = emoji_map.get(risk["alert_level"], "⚪")
                    st.markdown(
                        f"{emoji} **{risk['risk']}**  \n"
                        f"Confidence: `{risk['confidence']}` | Impact: `{risk['impact']}` | Alert: `{risk['alert_level']}`"
                    )
        # ⚠️ RISK DETECTION

    with st.expander("ℹ️ How Risk Levels Are Determined"):
        st.markdown("""
    We evaluate risks based on explicit **rule-based triggers** in four categories: **Cost, Timeline, Scope, and Client Sentiment**. Each trigger produces a risk alert only if it meets strict criteria.

    #### 💰 Cost
    - Budget increase > **10%** → `Budget overrun likely`
    - Budget increase 5–10% → `Possible budget pressure`

    #### 📅 Timeline
    - Timeline changed from **On Track → anything else** → `Schedule deviation reported`

    #### 📦 Scope
    - Scope contains keywords like **expanded, added, increased, enhanced** → `Scope creep risk due to new work`

    #### 💬 Client Sentiment
    - Sentiment **drops** (e.g., `Positive → Neutral`) → `Client dissatisfaction trend`

    ---

    ### 🔢 Confidence Scoring (1–10)
    - Budget >15% → `9`
    - Budget 10–15% → `8`
    - Budget 5–10% → `6`
    - Timeline changed → `7`
    - Scope keyword matched → `6`
    - Sentiment dropped → `7`

    ---

    ### 📊 Impact Level
    - Budget >10% → `HIGH`
    - Timeline issues → `HIGH`
    - Scope expanded → `MEDIUM`
    - Sentiment drop → `MEDIUM`

    ---

    ### 🚨 Final Alert Level Matrix

    | Confidence ↓ / Impact → | LOW | MEDIUM | HIGH |
    |-------------------------|-----|--------|------|
    | 1–2                     | LOW | LOW    | MEDIUM |
    | 3–4                     | LOW | MEDIUM | MEDIUM |
    | 5–6                     | LOW | MEDIUM | HIGH |
    | 7–8                     | MEDIUM | HIGH | HIGH |
    | 9–10                    | HIGH | HIGH | HIGH |
    """)
        st.divider()

# === TAB 2: KPI History ===
with tabs[1]:
    st.subheader("📊 KPI Trends Over Time")
    selected_project = st.selectbox("Select a project to view KPI trends", project_names)

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

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    def extract_budget_amount(text):
        if not isinstance(text, str):
            return None
        match = re.search(r"\$?([\d,.]+)", text)
        if match:
            return float(match.group(1).replace(",", ""))
        return None

    df["budget_numeric"] = df["budget"].apply(extract_budget_amount)

    st.subheader("💰 Budget Utilization Over Time")
    fig, ax = plt.subplots()
    ax.plot(df["date"], df["budget_numeric"], marker="o")
    ax.set_ylabel("Budget ($)")
    ax.set_xlabel("Date")
    ax.set_title("Budget Trend")
    fig.autofmt_xdate(rotation=45)
    ax.tick_params(axis='x', labelsize=9)
    st.pyplot(fig)

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

    plot_categorical_trend("timeline", "🗓️ Timeline Status Over Time")

    def display_text_trend(column, title, emoji=""):
        st.subheader(f"{emoji} {title}")
        simplified = df[["date", column]].dropna()
        simplified[column] = simplified[column].astype(str).str.strip()

        for _, row in simplified.iterrows():
            st.markdown(f"- **{row['date'].strftime('%b %d')}**: {row[column]}")

    display_text_trend("scope", "Scope Updates", "📦")
    display_text_trend("sentiment", "Client Sentiment Changes", "💬")

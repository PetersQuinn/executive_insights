import streamlit as st
import sqlite3
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pipeline.compare import compare_kpis
from pipeline.risk_detect import detect_risks
from pipeline.risk_detect import detect_risks_safe
import re
from collections import defaultdict
from utils.openai_client import ask_gpt

st.set_page_config(page_title="📈 Project History Dashboard", layout="wide")
st.title("📚 Project History Overview")

# === Connect to DB ===
conn = sqlite3.connect("data/project_data.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT project_id, report_date, llm_output
    FROM files
    WHERE report_date IS NOT NULL AND llm_output IS NOT NULL
    ORDER BY project_id, report_date DESC
""")
rows = cursor.fetchall()

st.header("🧪 Deep DB Check: Count total rows and nulls")

# Total rows
cursor.execute("SELECT COUNT(*) FROM files")
total = cursor.fetchone()[0]
st.markdown(f"**📦 Total rows in `files`:** {total}")

# Rows with missing report_date
cursor.execute("SELECT COUNT(*) FROM files WHERE report_date IS NULL")
null_dates = cursor.fetchone()[0]
st.markdown(f"**⚠️ Rows with NULL `report_date`:** {null_dates}")

# Show a few raw rows, regardless of report_date
cursor.execute("SELECT project_id, report_date, llm_output FROM files LIMIT 5")
rows_any = cursor.fetchall()
if rows_any:
    st.markdown("**🔍 First 5 raw entries (ignoring filters):**")
    for row in rows_any:
        st.text(row)
else:
    st.error("🚫 `files` table is completely empty.")


# === Build project_map with parsed JSON ===
project_map = defaultdict(list)

for project_id, report_date, llm_output in rows:
    try:
        parsed = json.loads(llm_output)
        project_map[project_id].append((report_date, parsed))
    except Exception as e:
        st.warning(f"Skipping {project_id} on {report_date}: {e}")
        continue

project_names = sorted(project_map.keys())
st.write("Available projects:", project_names)

# === TABS ===
tabs = st.tabs(["🔁 Recent Trends", "📊 KPI History"])

# === TAB 1: RECENT TRENDS ===
with tabs[0]:
    st.subheader("🔍 Compare Latest KPI Snapshots")

    # === Build project_map safely with debugging ===
    project_map = defaultdict(list)

    for project_id, report_date, llm_output in rows:
        if not llm_output or llm_output.strip() == "":
            st.warning(f"⛔ Skipping {project_id} on {report_date}: Empty `llm_output`")
            continue

        try:
            parsed = json.loads(llm_output)
        except Exception as e:
            st.error(f"❌ Skipping {project_id} on {report_date}: Invalid JSON — {e}")
            continue

        # Optionally warn, but include even if 'kpis' is missing
        if "kpis" not in parsed:
            st.warning(f"⚠️ {project_id} on {report_date} has no 'kpis' key.")

        project_map[project_id].append((report_date, parsed))

    project_names = sorted(project_map.keys())
    st.write("✅ Final parsed projects:", project_names)

    if not project_names:
        st.error("🚫 No valid project data found. Please check your database.")
        st.stop()

    # === UI selection ===
    selected_projects = st.multiselect("Select projects to compare", project_names)

    def format_arrow(before_after):
        try:
            before, after = before_after.split(" → ")
            return f"{before} → {after}"
        except:
            return before_after

    emoji_map = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢"}

    for project in selected_projects:
        st.markdown(f"### 🧹 {project.replace('_', ' ').title()}")
        snapshots = sorted(project_map[project], reverse=True)

        if len(snapshots) < 2:
            st.warning("Not enough snapshots to compare.")
            continue

        (date_latest, latest_data), (date_prev, prev_data) = snapshots[:2]

        latest_kpis = latest_data.get("kpis", {})
        prev_kpis = prev_data.get("kpis", {})

        delta = compare_kpis(latest_kpis, prev_kpis)
        risks_raw = detect_risks(latest_kpis, delta)
        risks = detect_risks_safe(risks_raw)
        st.write("🔍 Raw risk output:", risks_raw)
        st.write("✅ Cleaned risk output:", risks)



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
        expected_categories = ["cost", "timeline", "scope", "client_sentiment"]
        for category in expected_categories:
            items = risks.get(category, [])
            with st.expander(f"📌 {category.title()} Risks ({len(items)})", expanded=True):
                if not items:
                    st.markdown("_✅ No risks detected in this category._")
                else:
                    for risk in items:
                        emoji = emoji_map.get(risk["alert_level"], "⚪")
                        st.markdown(
                            f"{emoji} **{risk['risk']}**  \n"
                            f"Confidence: `{risk['confidence']}` | Impact: `{risk['impact']}` | Alert: `{risk['alert_level']}`"
                        )


    with st.expander("ℹ️ How Risk Levels Are Determined"):
        st.markdown("...")  # Keep your risk explanation here


# === TAB 2: KPI HISTORY ===
with tabs[1]:
    st.subheader("📊 KPI Trends Over Time")
    selected_project = st.selectbox("Select a project to view KPI trends", project_names)

    snapshots = sorted(project_map[selected_project])
    data = []

    for date, parsed in snapshots:
        kpis = parsed.get("kpis", {})
        row = {
            "date": date,
            "budget": kpis.get("budget", None),
            "timeline": kpis.get("timeline", None),
            "scope": kpis.get("scope", None),
            "sentiment": kpis.get("client_sentiment", None)
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

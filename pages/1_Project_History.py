import streamlit as st
import sqlite3
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from pipeline.compare import compare_kpis
from pipeline.risk_detect import detect_risks
from pipeline.risk_detect import detect_risks_save
import re
from collections import defaultdict
from utils.openai_client import ask_gpt
from datetime import datetime
import plotly.express as px

# === Streamlit Page Setup ===
st.set_page_config(page_title="📈 Project History Dashboard", layout="wide")
st.title("📚 Project History Overview")

# === Connect to SQLite DB ===
conn = sqlite3.connect("data/project_data.db")
cursor = conn.cursor()

# === Pull relevant fields ===
# Includes uploaded_at to sort snapshots precisely
cursor.execute("""
    SELECT project_id, report_date, uploaded_at, llm_output
    FROM files
    WHERE report_date IS NOT NULL AND llm_output IS NOT NULL
    ORDER BY project_id, uploaded_at DESC
""")
rows = cursor.fetchall()

# === Build project_map with parsed JSON and full metadata ===
# Each entry: project_id -> list of dicts with report_date, uploaded_at, parsed JSON
project_map = defaultdict(list)

for project_id, report_date, uploaded_at, llm_output in rows:
    try:
        parsed = json.loads(llm_output)
        project_map[project_id].append({
            "report_date": report_date,
            "uploaded_at": uploaded_at,
            "data": parsed
        })
    except Exception as e:
        st.warning(f"⚠️ Skipping {project_id} on {report_date}: Invalid JSON — {e}")
        continue

# === TABS ===
tabs = st.tabs(["🔁 Recent Trends", "📊 KPI History"])

# === TAB 1: RECENT TRENDS ===
with tabs[0]:
    st.subheader("🔍 Compare Latest KPI Snapshots")

    # Dictionary to group all parsed snapshots by project
    project_map = defaultdict(list)

    # Parse rows and populate project_map
    for project_id, report_date, uploaded_at, llm_output in rows:
        if not llm_output or llm_output.strip() == "":
            st.warning(f"⛔ Skipping {project_id} on {report_date}: Empty `llm_output`")
            continue

        try:
            parsed = json.loads(llm_output)
        except Exception as e:
            st.error(f"❌ Skipping {project_id} on {report_date}: Invalid JSON — {e}")
            continue

        if "kpis" not in parsed:
            st.warning(f"⚠️ {project_id} on {report_date} has no 'kpis' key.")

        project_map[project_id].append({
            "report_date": report_date,
            "uploaded_at": uploaded_at,
            "data": parsed
        })

    project_names = sorted(project_map.keys())

    if not project_names:
        st.error("🚫 No valid project data found. Please check your database.")
        st.stop()

    # === UI Selection ===
    selected_project = st.selectbox("Select project to compare", project_names)

    def format_kpi_change(key, prev, latest):
        if prev == latest:
            return prev, latest, "🟢 No change"
        return prev, latest, "🔁 Changed"

    if selected_project:
        st.markdown(f"### 🧹 {selected_project.replace('_', ' ').title()}")

        # Sort using uploaded_at timestamp (ensures accuracy even with same report_date)
        snapshots = sorted(
            project_map[selected_project],
            key=lambda x: datetime.strptime(x["uploaded_at"], "%Y-%m-%dT%H:%M:%S.%f"),
            reverse=True
        )

        if len(snapshots) < 2:
            st.warning("Not enough snapshots to compare.")
        else:
            latest = snapshots[0]
            previous = snapshots[1]

            latest_data = latest["data"]
            prev_data = previous["data"]
            date_latest = latest["report_date"]
            date_prev = previous["report_date"]

            st.subheader("📉 KPI Changes")

            kpi_fields = ["allotted_budget", "percent_spent", "client_sentiment", "scope", "timeline"]
            kpi_table_data = []

            latest_kpis = latest_data.get("kpis", {})
            prev_kpis = prev_data.get("kpis", {})

            for kpi in kpi_fields:
                prev_val = prev_kpis.get(kpi, "❓ Missing")
                latest_val = latest_kpis.get(kpi, "❓ Missing")

                prev_val_str = f"{prev_val:,}" if isinstance(prev_val, (int, float)) else str(prev_val)
                latest_val_str = f"{latest_val:,}" if isinstance(latest_val, (int, float)) else str(latest_val)

                before, after, status = format_kpi_change(kpi, prev_val_str, latest_val_str)
                kpi_table_data.append((kpi.replace("_", " ").title(), before, after, status))

            st.table(pd.DataFrame(kpi_table_data, columns=["KPI", "Previous", "Latest", "Change"]))

            # =========================
            # 💰 Budget Details Section
            # =========================
            st.subheader("💰 Budget Details")

            def map_budget_by_category(budget_list):
                return {item["Category"]: item for item in budget_list}

            prev_budget_map = map_budget_by_category(prev_data.get("budget_details", []))
            latest_budget_map = map_budget_by_category(latest_data.get("budget_details", []))
            all_categories = set(prev_budget_map) | set(latest_budget_map)

            for category in sorted(all_categories):
                prev = prev_budget_map.get(category)
                latest = latest_budget_map.get(category)

                with st.expander(f"🧾 Category: {category}", expanded=False):
                    def compare_values(label, prev_val, latest_val, percent=False):
                        if prev_val == latest_val:
                            st.markdown(f"**{label}**: {prev_val if not percent else f'{prev_val*100:.1f}%'} 🟢 No Change")
                        else:
                            old = f"{prev_val:,}" if isinstance(prev_val, (int, float)) and not percent else f"{prev_val*100:.1f}%"
                            new = f"{latest_val:,}" if isinstance(latest_val, (int, float)) and not percent else f"{latest_val*100:.1f}%"
                            st.markdown(f"**{label}**: {old} → {new} 🔁 Changed")

                    if not prev:
                        st.warning("🆕 This category is new in the latest snapshot.")
                        compare_values("Allotted Budget", "-", latest["Allotted Budget"])
                        compare_values("Spent Budget", "-", latest["Spent Budget"])
                        compare_values("Remaining Budget", "-", latest["Remaining Budget"])
                        compare_values("Percent Spent", 0, latest["Percent Spent"], percent=True)
                        st.markdown(f"**Notes**: {latest.get('Notes', '-')}")
                    elif not latest:
                        st.error("❌ This category was removed in the latest snapshot.")
                        compare_values("Allotted Budget", prev["Allotted Budget"], "-")
                        compare_values("Spent Budget", prev["Spent Budget"], "-")
                        compare_values("Remaining Budget", prev["Remaining Budget"], "-")
                        compare_values("Percent Spent", prev["Percent Spent"], 0, percent=True)
                        st.markdown(f"**Notes**: {prev.get('Notes', '-')}")
                    else:
                        compare_values("Allotted Budget", prev["Allotted Budget"], latest["Allotted Budget"])
                        compare_values("Spent Budget", prev["Spent Budget"], latest["Spent Budget"])
                        compare_values("Remaining Budget", prev["Remaining Budget"], latest["Remaining Budget"])
                        compare_values("Percent Spent", prev["Percent Spent"], latest["Percent Spent"], percent=True)
                        prev_notes = prev.get("Notes") or "-"
                        latest_notes = latest.get("Notes") or "-"
                        if prev_notes == latest_notes:
                            st.markdown(f"**Notes**: {latest_notes} 🟢 No Change")
                        else:
                            st.markdown(f"**Notes**: `{prev_notes}` → `{latest_notes}` 🔁 Changed")

            # ==============================
            # 📦 Deliverables Comparison
            # ==============================
            st.subheader("📦 Deliverables")

            prev_delivs = {d["Deliverable"]: d for d in prev_data.get("deliverables", [])}
            latest_delivs = {d["Deliverable"]: d for d in latest_data.get("deliverables", [])}
            all_deliv_keys = set(prev_delivs) | set(latest_delivs)

            for deliverable in sorted(all_deliv_keys):
                prev = prev_delivs.get(deliverable)
                latest = latest_delivs.get(deliverable)

                with st.expander(f"📦 Deliverable: {deliverable}", expanded=False):
                    def field_change(label, prev_val, latest_val):
                        if prev_val == latest_val:
                            st.markdown(f"**{label}**: {prev_val} 🟢 No Change")
                        else:
                            st.markdown(f"**{label}**: `{prev_val}` → `{latest_val}` 🔁 Changed")

                    if not prev:
                        st.success("🆕 New deliverable added in latest snapshot.")
                        st.markdown(f"**Start Date**: {latest['Start Date']}")
                        st.markdown(f"**Due Date**: {latest['Date Due']}")
                        st.markdown(f"**Status**: {latest['Status']}")
                    elif not latest:
                        st.error("❌ Deliverable removed in latest snapshot.")
                        st.markdown(f"**Start Date**: {prev['Start Date']}")
                        st.markdown(f"**Due Date**: {prev['Date Due']}")
                        st.markdown(f"**Status**: {prev['Status']}")
                    else:
                        field_change("Start Date", prev["Start Date"], latest["Start Date"])
                        field_change("Due Date", prev["Date Due"], latest["Date Due"])
                        field_change("Status", prev["Status"], latest["Status"])
            # ==============================
            # 📋 Issues Comparison
            # ==============================
            st.subheader("📋 Issues")

            # Index issues by Issue # if available, else by (Issue Detail + Creation Date) fallback
            def get_issue_key(issue):
                if "Issue #" in issue:
                    return f"ID-{issue['Issue #']}"
                else:
                    return f"{issue.get('Issue Detail', '')}__{issue.get('Issue Creation Date', '')}"

            prev_issues_raw = prev_data.get("issues", [])
            latest_issues_raw = latest_data.get("issues", [])

            prev_issues = {get_issue_key(i): i for i in prev_issues_raw}
            latest_issues = {get_issue_key(i): i for i in latest_issues_raw}
            all_issue_keys = set(prev_issues) | set(latest_issues)

            for key in sorted(all_issue_keys):
                prev = prev_issues.get(key)
                latest = latest_issues.get(key)

                issue_title = latest.get("Issue Detail") if latest else prev.get("Issue Detail")
                with st.expander(f"📋 Issue: {issue_title}", expanded=False):
                    def field_change(label, prev_val, latest_val):
                        if prev_val == latest_val:
                            st.markdown(f"**{label}**: {prev_val} 🟢 No Change")
                        else:
                            st.markdown(f"**{label}**: `{prev_val}` → `{latest_val}` 🔁 Changed")

                    if not prev:
                        st.success("🆕 New issue added in latest snapshot.")
                        for field in ["Issue Category", "Status", "Owner", "Due Date", "Recommended Action"]:
                            st.markdown(f"**{field}**: {latest.get(field, '-')}")
                    elif not latest:
                        st.error("❌ Issue removed in latest snapshot.")
                        for field in ["Issue Category", "Status", "Owner", "Due Date", "Recommended Action"]:
                            st.markdown(f"**{field}**: {prev.get(field, '-')}")
                    else:
                        field_change("Issue Category", prev.get("Issue Category", "-"), latest.get("Issue Category", "-"))
                        field_change("Status", prev.get("Status", "-"), latest.get("Status", "-"))
                        field_change("Owner", prev.get("Owner", "-"), latest.get("Owner", "-"))
                        field_change("Due Date", prev.get("Due Date", "-"), latest.get("Due Date", "-"))
                        field_change("Recommended Action", prev.get("Recommended Action", "-"), latest.get("Recommended Action", "-"))

            # ==============================
            # 🗓️ Schedule Comparison (Gantt Chart)
            # ==============================


            st.subheader("🗓️ Schedule Comparison")

            prev_schedule = prev_data.get("schedule", [])
            latest_schedule = latest_data.get("schedule", [])

            def build_gantt_df(schedule, snapshot_label, color, opacity):
                data = []
                for task in schedule:
                    data.append({
                        "Task": task["Task Name"],
                        "Start": task["Start Date"],
                        "Finish": task["End Date"],
                        "Status": task.get("Status", "Unknown"),
                        "Snapshot": snapshot_label,
                        "Color": color,
                        "Opacity": opacity
                    })
                return data

            # Build both snapshots
            prev_df = build_gantt_df(prev_schedule, "Previous", "lightblue", 0.3)
            latest_df = build_gantt_df(latest_schedule, "Latest", "blue", 1.0)

            # Merge datasets
            combined_df = prev_df + latest_df
            combined_df = pd.DataFrame(combined_df)

            # Convert to datetime
            combined_df["Start"] = pd.to_datetime(combined_df["Start"])
            combined_df["Finish"] = pd.to_datetime(combined_df["Finish"])

            # Plotly Gantt-style chart
            fig = px.timeline(
                combined_df,
                x_start="Start",
                x_end="Finish",
                y="Task",
                color="Snapshot",
                opacity=combined_df["Opacity"],
                title="Schedule Comparison: Latest vs Previous"
            )

            fig.update_traces(marker=dict(line_color="black"))
            fig.update_yaxes(autorange="reversed")  # So top-down matches schedule order
            st.plotly_chart(fig, use_container_width=True)

with st.expander("ℹ️ How Risk Levels Are Determined"):
    st.markdown("""
### 🧠 Risk Classification Engine Rules

These are the **strict rules** used to classify risks from KPI snapshots. No speculation or interpretation is applied.

---

#### 🏷️ STEP 1 — Identify Risks by Category

Each KPI category is evaluated using the exact triggers below:

**COST TRIGGERS**
- Budget increased >10% → Risk: _"Budget overrun likely"_
- Budget increased 5–10% → Risk: _"Possible budget pressure"_

**TIMELINE TRIGGERS**
- Changed from "on track" → anything else → Risk: _"Schedule deviation reported"_
- Changed from "delayed" → "on track" → _No risk_

**SCOPE TRIGGERS**
- Scope contains: _"expanded", "added", "increased", "enhanced"_ → Risk: _"Scope creep risk due to new work"_
- Reduced/removed → _No risk_

**CLIENT SENTIMENT TRIGGERS**
- Sentiment worsened (e.g., _Positive → Neutral_) → Risk: _"Client dissatisfaction trend"_
- Sentiment improved → _No risk_

---

#### 📏 STEP 2 — Assign Confidence Score (1–10)

Confidence reflects how strongly the KPI indicates a real risk:

- Budget increased >15% → `confidence = 9`
- Budget increased 10–15% → `confidence = 8`
- Budget increased 5–10% → `confidence = 6`
- Timeline changed → `confidence = 7`
- Scope expanded → `confidence = 6`
- Sentiment dropped → `confidence = 7`

> Return the **highest** score triggered.

---

#### 💥 STEP 3 — Assign Impact Level

Impact shows how severe the change is:

- Budget increase >10% → `impact = HIGH`
- Timeline slipped → `impact = HIGH`
- Scope expanded → `impact = MEDIUM`
- Sentiment dropped → `impact = MEDIUM`

---

#### 🚨 STEP 4 — Alert Level Matrix

Alert level is calculated from the confidence + impact:

| Confidence ↓ / Impact → | LOW | MEDIUM | HIGH |
|-------------------------|-----|--------|------|
| 1–2                     | LOW | LOW    | MEDIUM |
| 3–4                     | LOW | MEDIUM | MEDIUM |
| 5–6                     | LOW | MEDIUM | HIGH |
| 7–8                     | MEDIUM | HIGH | HIGH |
| 9–10                    | HIGH | HIGH | HIGH |

""")



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

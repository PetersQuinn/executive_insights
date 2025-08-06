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
        

        # ==============================
        # 📍 Detected Risks (LLM-Generated)
        # ==============================
        
        # Extract KPIs from snapshots
        latest_kpis = latest_data.get("kpis", {})
        prev_kpis = prev_data.get("kpis", {})

        # Compute KPI delta
        kpi_delta = compare_kpis(latest_kpis, prev_kpis)

        
        # Run LLM risk detection before rendering UI
        risks = detect_risks(
            current_snapshot=latest_data,
            delta_summary=kpi_delta
        )

        st.subheader("📍 Detected Risks from Snapshot Changes")

        # Ensure risks is a list of dictionaries before proceeding
        if isinstance(risks, list) and risks:
            for idx, risk in enumerate(risks, start=1):
                # Extract relevant fields with fallbacks
                risk_name = risk.get("Risk Name", f"Unnamed Risk {idx}")
                risk_description = risk.get("Risk Description", "No description provided.")
                impact_rating = risk.get("Impact Rating", "N/A")
                date_identified = risk.get("Date Identified", "N/A")

                # Display each risk in a collapsible section
                with st.expander(f"⚠️ {risk_name}", expanded=False):
                    st.markdown(f"**📅 Date Identified:** `{date_identified}`")
                    st.markdown(f"**🎯 Impact Rating:** `{impact_rating}` (Scale: 0–10)")
                    st.markdown("**📝 Description:**")
                    st.markdown(f"{risk_description}")
        else:
            st.info("✅ No new risks detected from snapshot differences.")

    with st.expander("ℹ️ How to Use AI-Powered Risk Detection Effectively"):
        st.markdown("""
    ### 🧠 AI-Powered Risk Detection: How It Works & How to Use It

    This system provides **suggested project risks** using AI, based on KPI data, changes from prior snapshots, and the risks already being tracked.

    These suggestions are **not final**. You, as the project lead, should review them and decide which risks to formally log.

    ---

    ### 🔄 What Goes Into AI Risk Detection?

    The LLM is fed three things:

    1. **Current KPI data** (budget, timeline, scope, sentiment, etc.)
    2. **Snapshot changes** (e.g., budget increased, timeline slipped)
    3. **Existing tracked risks** (to avoid duplicates)

    It then uses logic to suggest new risks that are:
    - Justified by the actual data
    - Not already tracked
    - Realistic and proportional to the situation

    ---

    ### 🧾 What to Do With These Risks

    - Review each suggestion and determine whether it's valid
    - Add accepted risks to your **official risk log** (typically in Excel)
    - Add any other risks you know of that weren’t detected
    - Mark and update mitigations in your usual workflow

    > 💡 These risks are **meant to accelerate awareness**, not replace judgment.

    ---

    ### 📏 Impact Rating Scale

    The `Impact Rating` is a value from **0.0 to 10.0**, estimating how severely the risk could affect project outcomes:

    - **0.0 – 3.9** → Minor impact (isolated noise, local issue)
    - **4.0 – 6.9** → Moderate impact (some disruption or delay)
    - **7.0 – 10.0** → Major impact (broad risk, serious consequence)

    We instruct the model to **stay grounded** and not assign exaggerated impact scores unless clearly warranted.

    ---

    ### 📂 Example Use Case in Workflow

    1. Upload latest project update
    2. Navigate to the **Project History** or **Recent Trends** tab
    3. View detected risks under **AI-Suggested Risks**
    4. Decide what to keep and what to ignore
    5. Input chosen risks into your formal Excel document or risk tracker

    > This approach keeps risk monitoring consistent and informed without requiring constant manual analysis.

    """)



# === TAB 2: KPI HISTORY ===
with tabs[1]:
    st.subheader("📊 KPI Trends Over Time")

    selected_project = st.selectbox("Select a project to view KPI trends", project_names)

    # Retrieve and sort snapshots by date
    raw_snapshots = project_map[selected_project]
    snapshots = sorted(raw_snapshots, key=lambda x: x["report_date"])


    if not snapshots:
        st.info("No KPI snapshots found for this project.")
        st.stop()

    # ----------------- Build DataFrame -----------------
    data = []
    category_trends = {}  # For tracking category-level budget trends

    for snap in snapshots:
        kpis = snap["data"].get("kpis", {})
        budget_details = snap["data"].get("budget_details", [])
        report_date = snap["report_date"]

        # Top-level KPI row
        row = {
            "date": report_date,
            "budget": kpis.get("budget"),
            "timeline": kpis.get("timeline"),
            "scope": kpis.get("scope"),
            "sentiment": kpis.get("client_sentiment"),
            "percent_spent": kpis.get("percent_spent", None)
        }
        data.append(row)

        # Track category-level budget percent spent
        for bd in budget_details:
            category = bd.get("Category")
            if not category or category.lower() == "total":
                continue  # Skip total row

            if category not in category_trends:
                category_trends[category] = []

            category_trends[category].append({
                "date": report_date,
                "percent_spent": bd.get("Percent Spent", None)
            })

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # ----------------- Line Graph: Overall Percent Spent -----------------
    st.subheader("📈 Overall Budget Utilization")

    # Convert decimal to actual percent
    df["percent_spent_display"] = df["percent_spent"] * 100

    fig, ax = plt.subplots()
    ax.plot(df["date"], df["percent_spent_display"], marker="o")
    ax.set_ylabel("Percent Spent (%)")
    ax.set_xlabel("Date")
    ax.set_title("Total Budget % Spent Over Time")
    fig.autofmt_xdate(rotation=45)
    ax.tick_params(axis='x', labelsize=9)
    st.pyplot(fig)

    # ----------------- Pie Charts for Timeline, Scope, Sentiment -----------------
    def pie_chart(col, title):
        st.subheader(f"🥧 {title}")
        counts = df[col].value_counts(dropna=True)
        fig, ax = plt.subplots()
        ax.pie(counts, labels=counts.index, autopct="%1.1f%%", startangle=140)
        ax.axis("equal")
        st.pyplot(fig)

    pie_chart("timeline", "Timeline Distribution")
    pie_chart("scope", "Scope Distribution")
    pie_chart("sentiment", "Client Sentiment Distribution")

    # ----------------- Per-Category Budget Trend Lines -----------------
    st.subheader("💡 Budget Category Utilization Over Time")
    for category, entries in category_trends.items():
        cat_df = pd.DataFrame(entries)
        cat_df["date"] = pd.to_datetime(cat_df["date"])
        cat_df = cat_df.sort_values("date")

        # Convert to percent
        cat_df["percent_spent_display"] = cat_df["percent_spent"] * 100

        fig, ax = plt.subplots()
        ax.plot(cat_df["date"], cat_df["percent_spent_display"], marker="o")
        ax.set_ylabel("Percent Spent (%)")
        ax.set_xlabel("Date")
        ax.set_title(f"{category} Budget Utilization")
        fig.autofmt_xdate(rotation=45)
        ax.tick_params(axis='x', labelsize=9)
        st.pyplot(fig)


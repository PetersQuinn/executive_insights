# 🧠 Project Performance Insights (PPI)

PPI is a Streamlit-based dashboard for extracting insights, detecting risks, and tracking KPIs across complex project lifecycles. It ingests documents like status reports, Excel trackers, and meeting transcripts, then summarizes and analyzes them using Azure OpenAI.

---

## 🚀 Features

- Upload and analyze project update files (.docx, .xlsx, .vtt, etc.)
- Generate executive summaries and cross-snapshot insights via GPT
- Visualize risks and KPI trends over time
- Compare snapshots to detect scope, budget, sentiment, or timeline changes
- Supports DOCX, PDF, Email, PowerPoint, VTT (transcripts), and Excel

---

## 📁 Directory Structure

```
.
├── pages/
│   ├── 1_project_history.py       # Streamlit tab-based UI for viewing historical KPI trends
│   ├── 2_project_overview.py       # Streamlit tab-based UI for active AI-powered PM insights
├── utils/
│   ├── openai_client.py        # Azure GPT interface
│   ├── parser_docx.py          # DOCX parsing logic
│   ├── parser_pdf.py           # PDF parsing logic (early stage)
│   ├── parser_email.py         # Email parser (early stage)
│   ├── parser_pptx.py          # PowerPoint parser (early stage)
│   ├── parser_vtt.py           # VTT transcript parser (early stage)
├── pipeline/
│   └── compare.py              # Snapshot comparison logic
│   └── risk_detect.py          # Risk suggestion via GPT
├── data/
│   └── project_data.db             # SQLite database (auto-generated)
├── logs/
│   └── execution.log             
├── README.md
├── .env
├── .gitignore
├── requirements.txt
```

---

## 🧠 LLM-Powered Capabilities

All GPT calls use Azure OpenAI via the `ask_gpt()` function, with project-specific prompts to:

- Generate executive summaries
- Detect emerging risks (based on snapshot delta + KPIs)
- Summarize cross-snapshot trends

### ⚠️ Known Caveat
`parser_docx.py` contains a legacy LLM function (`extract_sections_via_llm`) that **does not work with the current JSON schema**. However, this is handled elsewhere using a newer ingestion pipeline.

---

## 📄 File Parsers

| Format   | Parser File          | Status         | Notes |
|----------|----------------------|----------------|-------|
| `.docx`  | `parser_docx.py`     | ✅ Working      | LLM extraction may be skipped in favor of new pipeline |
| `.xlsx`  | *(not shown here)*   | ✅ Ingested     | Used for structured KPIs, risks, budget, etc. |
| `.vtt`   | `parser_vtt.py`      | ⚠️ Early-stage | Useful for meeting transcripts (e.g., from Fireflies) |
| `.eml`   | `parser_email.py`    | ⚠️ Early-stage | Extracts plain text only |
| `.pdf`   | `parser_pdf.py`      | ⚠️ Early-stage | Text extraction only, no structure |
| `.pptx`  | `parser_pptx.py`     | ⚠️ Early-stage | Extracts visible slide text |

---

## 🗄️ Database Schema

SQLite database at `data/project_data.db` contains three tables:

### `projects`

| Column       | Type   | Description                      |
|--------------|--------|----------------------------------|
| id           | TEXT   | Primary Key (UUID or slug)       |
| name         | TEXT   | Project name                     |
| issuer       | TEXT   | Issuing agency or client         |
| start_date   | TEXT   | `YYYY-MM-DD` start date          |
| summary      | TEXT   | Project summary                  |
| contacts     | TEXT   | JSON-encoded contact details     |
| tags         | TEXT   | Optional keywords/tags           |
| rfp_file     | TEXT   | Reference to uploaded RFP        |
| status       | TEXT   | Default `active`                 |
| created_at   | TEXT   | Timestamp                        |

### `files`

| Column        | Type   | Description                                |
|---------------|--------|--------------------------------------------|
| id            | TEXT   | Primary Key                                |
| project_id    | TEXT   | Foreign Key to `projects.id`               |
| filename      | TEXT   | Uploaded filename                          |
| file_type     | TEXT   | Extension: docx, xlsx, etc.                |
| snapshot_date | TEXT   | Reserved (currently unused)                |
| report_date   | TEXT   | Detected date from file                    |
| uploaded_at   | TEXT   | Upload timestamp                           |
| llm_output    | TEXT   | JSON string of structured project snapshot |

### `risk_cache` *(deprecated)*

| Column              | Type   | Description                          |
|---------------------|--------|--------------------------------------|
| project_id          | TEXT   | Related project                      |
| current_date        | TEXT   | Newer snapshot date                  |
| previous_date       | TEXT   | Older snapshot date                  |
| snapshot_pair_hash  | TEXT   | Primary Key (hash of pair)           |
| risk_json           | TEXT   | Cached JSON output of risks          |
| generated_at        | TEXT   | When comparison was made             |

> 💡 This table is not used in the current implementation.

---

## ⚙️ Setup Instructions

1. **Clone repo**  
   ```bash
   git clone https://github.com/PetersQuinn/executive_insights
   cd executive_insights
   ```

2. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API**  
   Create a `.env` file:
   ```env
   ENDPOINT_URL=https://<your-azure-openai-endpoint>
   DEPLOYMENT_NAME=o4-mini
   AZURE_OPENAI_API_KEY=your-key-here
   AZURE_API_VERSION=2025-01-01-preview
   ```

4. **Run app**  
   ```bash
   streamlit run project_manager.py
   ```

---

## 🧪 Testing

- Most core LLM flows and Excel parsers are working and tested.
- Parsers for `.vtt`, `.eml`, `.pptx`, and `.pdf` are early-stage and require refinement.

---

## 🛣️ Roadmap

- [ ] Risk cache integration for faster comparisons
- [ ] Parser improvements (emails, PDFs, presentations)
- [ ] Add Fireflies or Teams API integration
- [ ] Embed visual trend tracking across snapshots
- [ ] Robust snapshot history + rollback

---

## 🧑‍💻 Author

Made by Quinton Peters  
Risk, Data, and Financial Engineering @ Duke University  
OpenAI GPT-4o + Python enthusiast
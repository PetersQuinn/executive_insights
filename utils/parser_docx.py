from docx import Document
import re

def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    return "\n".join(full_text)

def extract_kpis_and_sections(text: str) -> dict:
    sections = {
        "project_name": None,
        "report_date": None,
        "summary": None,
        "kpis": {},
        "issues": None,
        "next_steps": None,
    }

    # Basic regex patterns (tweak these based on your templates)
    patterns = {
        "project_name": r"Project Name[:\-]?\s*(.+)",
        "report_date": r"Report Date[:\-]?\s*(.+)",
        "summary": r"Summary[:\-]?\s*(.+)",
        "issues": r"Issues[:\-]?\s*(.+)",
        "next_steps": r"Next Steps[:\-]?\s*(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            sections[key] = match.group(1).strip()

    # Extract KPI blocks (example: "Budget: $X", "Timeline: On Track")
    kpi_matches = re.findall(r"(?i)(Budget|Timeline|Scope|Client Sentiment)\s*[:\-]?\s*(.+)", text)
    for label, value in kpi_matches:
        sections["kpis"][label.strip().lower()] = value.strip()

    return sections

def parse_docx_status(file_path: str) -> dict:
    raw_text = extract_text_from_docx(file_path)
    parsed = extract_kpis_and_sections(raw_text)
    return {
        "file": file_path,
        "raw_text": raw_text,
        "parsed": parsed
    }

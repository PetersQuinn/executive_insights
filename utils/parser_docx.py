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
        "summary": "",
        "kpis": {},
        "issues": "",
        "next_steps": "",
    }

    current_section = None
    section_headers = {
        "summary": "summary",
        "issues": "issues",
        "next steps": "next_steps",
    }

    for line in text.splitlines():
        line_clean = line.strip()

        if not line_clean:
            continue

        # Project name
        if not sections["project_name"]:
            match = re.match(r"Project Name[:\-]?\s*(.+)", line_clean, re.IGNORECASE)
            if match:
                sections["project_name"] = match.group(1).strip()
                continue

        # Date
        if not sections["report_date"]:
            match = re.match(r"(?:Report Date|Date)[:\-]?\s*(\d{4}-\d{2}-\d{2})", line_clean)
            if match:
                sections["report_date"] = match.group(1).strip()
                continue

        # KPIs
        kpi_patterns = {
            "budget": r"(?i)^Budget[:\-]?\s*(.+)",
            "timeline": r"(?i)^Timeline[:\-]?\s*(.+)",
            "scope": r"(?i)^Scope[:\-]?\s*(.+)",
            "client sentiment": r"(?i)^Client Sentiment[:\-]?\s*(.+)",
        }

        kpi_matched = False
        for kpi_label, pattern in kpi_patterns.items():
            match = re.match(pattern, line_clean)
            if match:
                sections["kpis"][kpi_label] = match.group(1).strip()
                kpi_matched = True
                break
        if kpi_matched:
            continue

        # Inline or block section headers
        section_header_match = re.match(r"^(Summary|Issues|Next Steps)[:\-]?\s*(.*)", line_clean, re.IGNORECASE)
        if section_header_match:
            label = section_header_match.group(1).strip().lower()
            content = section_header_match.group(2).strip()
            key = section_headers[label]
            current_section = key
            if content:
                sections[key] += content + "\n"
            continue

        # Add line to current section
        if current_section:
            sections[current_section] += line_clean + "\n"

    # Cleanup
    for key in ["summary", "issues", "next_steps"]:
        content = sections[key].strip()
        sections[key] = content if content else None

    return sections




def parse_docx_status(file_path: str) -> dict:
    raw_text = extract_text_from_docx(file_path)
    parsed = extract_kpis_and_sections(raw_text)
    return {
        "file": file_path,
        "raw_text": raw_text,
        "parsed": parsed
    }

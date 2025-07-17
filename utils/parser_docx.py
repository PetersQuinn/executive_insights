from docx import Document
from utils.openai_client import ask_gpt
import json


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            flat = para.text.replace("\n", " ").replace("  ", " ").strip()
            full_text.append(flat)
    return "\n".join(full_text)

def extract_sections_via_llm(text: str) -> dict:
    prompt = f"""
You are an AI assistant that extracts structured project status data from text.

Text:
{text[:6000]}  # Truncated for token limits.

Please extract and return a JSON object with the following fields:
- project_name: str
- report_date: str (YYYY-MM-DD if possible)
- summary: str
- kpis: object with keys like budget, timeline, scope, client sentiment
- issues: str
- next_steps: str

Respond with only the JSON.
    """
    response = ask_gpt(prompt)
    try:
        parsed = json.loads(response)
        return parsed
    except Exception as e:
        return {
            "error": str(e),
            "raw_response": response
        }

def parse_docx_status(file_path: str) -> dict:
    raw_text = extract_text_from_docx(file_path)
    parsed = extract_sections_via_llm(raw_text)
    return {
        "file": file_path,
        "raw_text": raw_text,
        "parsed": parsed
    }

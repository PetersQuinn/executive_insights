# === Risk Detection via GPT ===
# This version generates a flat list of full risk records (not grouped).
# Each entry matches the expected structure in llm_output["risks"].
# All fields are returned and ready for user review or system ingestion.

from datetime import date
import json
from utils.openai_client import ask_gpt

def detect_risks(current_snapshot: dict, delta_summary: dict) -> list | dict:
    """
    Detects newly emerging project risks using GPT.
    Only returns risks not already tracked in the current snapshot.

    Expected output:
    [
      {
        "Date Identified": "YYYY-MM-DD",
        "Impact Rating": float (0.0 to 10.0),
        "Risk Name and Description": "string"
      },
      ...
    ]
    """

    try:
        # Prepare prompt inputs
        current_kpis = current_snapshot.get("kpis", {})
        current_risks = current_snapshot.get("risks", [])
        current_kpis_json = json.dumps(current_kpis, indent=2)
        delta_summary_json = json.dumps(delta_summary, indent=2)
        current_risks_json = json.dumps([
            r.get("Risk Name and Description", "")
            for r in current_risks
        ], indent=2)

        today_str = date.today().isoformat()

        # GPT prompt
        prompt = f"""
You are a structured risk suggestion assistant for project performance snapshots.

Your task is to suggest **new and realistic risks** based on:
- KPI values
- Changes between the current and previous snapshot
- Risks already being tracked

⚠️ GUIDELINES:
- DO NOT duplicate risks already tracked (see existing list).
- DO NOT invent extreme risks — stay grounded in the input.
- Suggest **only risks justified by the data**.
- You may skip categories with no clear risk.
- Do NOT fabricate metrics, budgets, timelines, or events.

📏 IMPACT RATING GUIDANCE (0.0 to 10.0 scale):
- 0–3 → Very low impact (minor noise, isolated concern)
- 4–6 → Medium impact (moderate project or delivery disruption)
- 7–10 → High impact (broad consequences, major delay or cost)

🚨 ONLY return valid risk suggestions in this exact JSON format:
[
  {{
    "Date Identified": "{today_str}",
    "Impact Rating": float (0.0 to 10.0),
    "Risk Name": "short and specific"
    "Risk Description": "detailed explanation of the risk (1-2 sentences)"
  }},
  ...
]

---

📊 Current KPIs:
{current_kpis_json}

📈 Snapshot Delta Summary:
{delta_summary_json}

🗂️ Risks Already Tracked:
{current_risks_json}

Return only a clean JSON list (no Markdown, no comments).
"""

        # GPT response
        response = ask_gpt(prompt)

        if not response or "Azure GPT ERROR" in response:
            raise ValueError(f"No response returned from GPT: {response or 'empty'}")

        # Strip markdown formatting if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        return json.loads(cleaned)

    except Exception as e:
        return {
            "error": str(e),
            "raw_response": response if 'response' in locals() else "No response"
        }



def detect_risks_save(risks_raw):
    """
    Attempts to repair invalid risk suggestion output.
    Ensures the result is a list of valid risk dicts with minimal required fields.
    """
    if isinstance(risks_raw, list):
        return risks_raw

    prompt = f"""
Fix the broken JSON input below. Your job is to:

- ONLY fix syntax issues
- DO NOT invent or rewrite content
- DO NOT add any surrounding language or formatting. You must respond with ONLY valid JSON.
- Ensure output is a clean list of objects, each with:
  - "Date Identified"
  - "Impact Rating" (float)
  - "Risk Name"
  - "Risk Description"

Broken Input:
{risks_raw}
"""

    try:
        response = ask_gpt(prompt)

        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").split("\n", 1)[-1]

        cleaned = cleaned.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")
        return json.loads(cleaned)

    except Exception as e:
        return {
            "error": f"Failed to fix risk JSON: {e}",
            "raw_input": risks_raw
        }

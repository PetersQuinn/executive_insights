from utils.openai_client import ask_gpt
import json

def detect_risks(current_kpis: dict, delta_summary: dict) -> dict:
    import json
    from utils.openai_client import ask_gpt

    try:
        # Only include relevant KPI changes to keep the prompt shorter
        changed_kpis = {k: v for k, v in current_kpis.items() if k in delta_summary}

        current_kpis_json = json.dumps(changed_kpis, indent=2)
        delta_summary_json = json.dumps(delta_summary, indent=2)

        # Build prompt
        prompt = f"""
You are a risk classification engine. Do not speculate, interpret loosely, or write summaries. Your job is to apply the following **exact rules** to classify project risks from current KPIs and delta metrics.

### STEP 1 — Identify Risks by Category

For each category (cost, timeline, scope, client sentiment), use the **exact triggers** below. If no trigger is present, return an empty list.

#### COST TRIGGERS
- Budget increased >10% → risk = "Budget overrun likely"
- Budget increased 5–10% → risk = "Possible budget pressure"

#### TIMELINE TRIGGERS
- Timeline changed from "on track" to anything else → risk = "Schedule deviation reported"
- Timeline changed from "delayed" to "on track" → no risk

#### SCOPE TRIGGERS
- Scope change includes keywords: ["expanded", "added", "increased", "enhanced"] → risk = "Scope creep risk due to new work"
- Scope removed/reduced → no risk

#### CLIENT SENTIMENT TRIGGERS
- Sentiment worsened (e.g., Positive → Neutral or Neutral → Negative) → risk = "Client dissatisfaction trend"
- Sentiment improved → no risk

---

### STEP 2 — Assign Confidence Score (1–10)

Use **this exact logic**:
- Budget change >15% → confidence = 9
- Budget change 10–15% → confidence = 8
- Budget change 5–10% → confidence = 6
- Timeline changed → confidence = 7
- Scope changed using matching keywords → confidence = 6
- Sentiment dropped → confidence = 7

Use the highest matching rule. If multiple apply, return the max.

---

### STEP 3 — Assign Impact Level (LOW, MEDIUM, HIGH)

Use this logic:
- Budget change >10% → HIGH
- Timeline slippage → HIGH
- Scope expansion → MEDIUM
- Sentiment drop → MEDIUM

---

### STEP 4 — Assign Alert Level Using Matrix

| Confidence ↓ / Impact → | LOW | MEDIUM | HIGH |
|-------------------------|-----|--------|------|
| 1–2                     | LOW | LOW    | MEDIUM |
| 3–4                     | LOW | MEDIUM | MEDIUM |
| 5–6                     | LOW | MEDIUM | HIGH |
| 7–8                     | MEDIUM | HIGH | HIGH |
| 9–10                    | HIGH | HIGH | HIGH |

---

### FORMAT (MANDATORY)

Return your result **exactly like this**:

{{
  "cost": [{{"risk": "...", "confidence": X, "impact": "MEDIUM", "alert_level": "HIGH"}}],
  "timeline": [...],
  "scope": [...],
  "client_sentiment": [...]
}}

---

### INPUTS

Current KPIs:
{current_kpis_json}

Delta Summary:
{delta_summary_json}

Only output valid risks based on the rules above. Do not generate extra explanation.
"""

        # Get GPT response
        response = ask_gpt(prompt)


        if not response or response.strip() == "" or "Azure GPT ERROR" in response:
            raise ValueError(f"No response returned from GPT: {response or 'empty'}")

        # Strip code fences if GPT wraps it in Markdown
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()

        # Attempt to parse clean JSON
        return json.loads(cleaned)

    except Exception as e:
        return {
            "error": str(e),
            "raw_response": response if 'response' in locals() else "No response returned."
        }


def detect_risks_save(risks_raw):
    import json
    from utils.openai_client import ask_gpt

    # If it's already parsed as a dictionary, return it directly
    if isinstance(risks_raw, dict):
        return risks_raw

    # If it's a string or malformed, fix it using GPT without changing the structure
    prompt = f"""
The following is a broken or malformed JSON string representing structured risk categories.

Your job is ONLY to clean and return valid JSON — do not change the structure, rewrite text, or invent data.

Fix this exactly and return valid JSON in this format:
{{
  "cost": [{{"risk": "...", "confidence": X, "impact": "MEDIUM", "alert_level": "HIGH"}}],
  "timeline": [...],
  "scope": [...],
  "client_sentiment": [...]
}}

Broken input:
{risks_raw}
"""

    try:
        response = ask_gpt(prompt)

        # Clean markdown code block if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").split("\n", 1)[-1]

        # Replace smart quotes just in case
        cleaned = cleaned.replace("“", "\"").replace("”", "\"").replace("‘", "'").replace("’", "'")

        # Attempt to parse and return
        return json.loads(cleaned)

    except Exception as e:
        return {
            "error": f"Failed to fix risk JSON: {e}",
            "raw_input": risks_raw
        }

from utils.openai_client import ask_gpt
import json

def detect_risks(current_kpis: dict, delta_summary: dict) -> dict:
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
{json.dumps(current_kpis, indent=2)}

Delta Summary:
{json.dumps(delta_summary, indent=2)}

Only output valid risks based on the rules above. Do not generate extra explanation.
"""

    response = None  # ✅ Initialize here to prevent UnboundLocalError

    try:
        response = ask_gpt(prompt)

        # Optional: print prompt for debugging
        # print("===== PROMPT =====")
        # print(prompt)

        # Strip Markdown code blocks if needed
        if response.strip().startswith("```"):
            response = response.strip().strip("```").split("\n", 1)[-1]

        return json.loads(response)

    except Exception as e:
        return {
            "error": str(e),
            "raw_response": response or "No response returned."
        }

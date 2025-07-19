import re

def extract_budget_number(budget_str):
    # Pull numeric value from string like "$2.3M (80% utilized)"
    match = re.search(r"\$([\d\.]+)([MK]?)", budget_str)
    if not match:
        return None
    num, suffix = match.groups()
    multiplier = {"M": 1_000_000, "K": 1_000}.get(suffix.upper(), 1)
    return float(num) * multiplier

def compare_kpis(current, previous):
    delta = {}

    # --- Budget ---
    budget_now = extract_budget_number(current.get("budget", ""))
    budget_prev = extract_budget_number(previous.get("budget", ""))
    if budget_now is not None and budget_prev is not None:
        delta["budget_change"] = budget_now - budget_prev
        if budget_prev != 0:
            delta["budget_percent_change"] = ((budget_now - budget_prev) / budget_prev) * 100
        else:
            delta["budget_percent_change"] = 0

    # --- Timeline ---
    timeline_now = str(current.get("timeline", "")).strip().lower()
    timeline_prev = str(previous.get("timeline", "")).strip().lower()
    if timeline_now and timeline_prev and timeline_now != timeline_prev:
        delta["timeline_change"] = f"{timeline_prev} → {timeline_now}"

    # --- Scope ---
    scope_now = str(current.get("scope", "")).strip()
    scope_prev = str(previous.get("scope", "")).strip()
    if scope_now and scope_prev and scope_now != scope_prev:
        delta["scope_change"] = f"{scope_prev} → {scope_now}"

    # --- Client Sentiment ---
    sent_now = str(current.get("client sentiment", "")).strip().capitalize()
    sent_prev = str(previous.get("client sentiment", "")).strip().capitalize()
    if sent_now and sent_prev and sent_now != sent_prev:
        delta["sentiment_change"] = f"{sent_prev} → {sent_now}"

    return delta


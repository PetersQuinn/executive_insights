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

    # --- Allotted Budget ---
    ab_now = current.get("allotted_budget")
    ab_prev = previous.get("allotted_budget")
    if ab_now is not None and ab_prev is not None and ab_now != ab_prev:
        delta["allotted_budget_change"] = ab_prev, ab_now

    # --- Percent Spent ---
    ps_now = current.get("percent_spent")
    ps_prev = previous.get("percent_spent")
    if ps_now is not None and ps_prev is not None and ps_now != ps_prev:
        delta["percent_spent_change"] = f"{ps_prev:.2%} → {ps_now:.2%}"

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
    sent_now = str(current.get("client_sentiment", "")).strip().capitalize()
    sent_prev = str(previous.get("client_sentiment", "")).strip().capitalize()
    if sent_now and sent_prev and sent_now != sent_prev:
        delta["client_sentiment_change"] = f"{sent_prev} → {sent_now}"

    return delta

def compare_budget(current, previous):
    """
    Compares budget_details between snapshots.
    Returns dictionary with:
    - added categories
    - removed categories
    - changed fields per matching category
    """
    def by_category(lst):
        return {item["Category"]: item for item in lst}

    curr_map = by_category(current)
    prev_map = by_category(previous)

    all_keys = set(curr_map) | set(prev_map)
    result = {"added": [], "removed": [], "changed": []}

    for cat in all_keys:
        curr = curr_map.get(cat)
        prev = prev_map.get(cat)

        if not prev:
            result["added"].append(curr)
        elif not curr:
            result["removed"].append(prev)
        else:
            changed = {}
            for field in ["Allotted Budget", "Spent Budget", "Remaining Budget", "Percent Spent", "Notes"]:
                if curr.get(field) != prev.get(field):
                    changed[field] = (prev.get(field), curr.get(field))
            if changed:
                result["changed"].append({"Category": cat, "diff": changed})

    return result

def compare_deliverables(current, previous):
    """
    Compares deliverables by name.
    Returns added, removed, and changed deliverables.
    """
    curr_map = {d["Deliverable"]: d for d in current}
    prev_map = {d["Deliverable"]: d for d in previous}

    all_keys = set(curr_map) | set(prev_map)
    result = {"added": [], "removed": [], "changed": []}

    for key in all_keys:
        curr = curr_map.get(key)
        prev = prev_map.get(key)

        if not prev:
            result["added"].append(curr)
        elif not curr:
            result["removed"].append(prev)
        else:
            diff = {}
            for field in ["Start Date", "Date Due", "Status"]:
                if curr.get(field) != prev.get(field):
                    diff[field] = (prev.get(field), curr.get(field))
            if diff:
                result["changed"].append({"Deliverable": key, "diff": diff})

    return result

def compare_issues(current, previous):
    """
    Compares issues using Issue # if available, otherwise uses Issue Detail + Date.
    Returns added, removed, and changed issues.
    """
    def issue_key(issue):
        return f"#{issue.get('Issue #')}" if issue.get("Issue #") else (
            f"{issue.get('Issue Detail', '')}__{issue.get('Issue Creation Date', '')}"
        )

    curr_map = {issue_key(i): i for i in current}
    prev_map = {issue_key(i): i for i in previous}

    all_keys = set(curr_map) | set(prev_map)
    result = {"added": [], "removed": [], "changed": []}

    for key in all_keys:
        curr = curr_map.get(key)
        prev = prev_map.get(key)

        if not prev:
            result["added"].append(curr)
        elif not curr:
            result["removed"].append(prev)
        else:
            diff = {}
            for field in ["Status", "Owner", "Due Date", "Recommended Action", "Issue Category"]:
                if curr.get(field) != prev.get(field):
                    diff[field] = (prev.get(field), curr.get(field))
            if diff:
                result["changed"].append({"Issue Key": key, "diff": diff})

    return result

def compare_schedule(current, previous):
    """
    Compares scheduled tasks using Task ID or Task Name.
    Returns added, removed, and changed tasks.
    """
    def task_key(task):
        return task.get("Task ID") or task.get("Task Name")

    curr_map = {task_key(t): t for t in current}
    prev_map = {task_key(t): t for t in previous}

    all_keys = set(curr_map) | set(prev_map)
    result = {"added": [], "removed": [], "changed": []}

    for key in all_keys:
        curr = curr_map.get(key)
        prev = prev_map.get(key)

        if not prev:
            result["added"].append(curr)
        elif not curr:
            result["removed"].append(prev)
        else:
            diff = {}
            for field in ["Start Date", "End Date", "Status", "Assigned To"]:
                if curr.get(field) != prev.get(field):
                    diff[field] = (prev.get(field), curr.get(field))
            if diff:
                result["changed"].append({"Task": key, "diff": diff})

    return result

def compare_risks(current, previous):
    """
    Compares risks structurally (for now — detailed risk comparison can evolve later).
    Matches on Risk Name + Date Identified.
    """
    def risk_key(risk):
        return f"{risk.get('Risk Name and Description', '')}__{risk.get('Date Identified', '')}"

    curr_map = {risk_key(r): r for r in current}
    prev_map = {risk_key(r): r for r in previous}

    all_keys = set(curr_map) | set(prev_map)
    result = {"added": [], "removed": [], "changed": []}

    for key in all_keys:
        curr = curr_map.get(key)
        prev = prev_map.get(key)

        if not prev:
            result["added"].append(curr)
        elif not curr:
            result["removed"].append(prev)
        else:
            diff = {}
            for field in ["Impact Rating", "Probability Rating", "Risk Category", "Task Area"]:
                if curr.get(field) != prev.get(field):
                    diff[field] = (prev.get(field), curr.get(field))
            if diff:
                result["changed"].append({"Risk": key, "diff": diff})

    return result

def compare_snapshots(current, previous):
    """
    Compares two full snapshot JSON objects (from llm_output) and returns structured differences.
    These can be used to detect emerging risks or generate summaries.
    """
    return {
        "kpi_changes": compare_kpis(current.get("kpis", {}), previous.get("kpis", {})),
        "budget_changes": compare_budget(current.get("budget_details", []), previous.get("budget_details", [])),
        "deliverable_changes": compare_deliverables(current.get("deliverables", []), previous.get("deliverables", [])),
        "issue_changes": compare_issues(current.get("issues", []), previous.get("issues", [])),
        "schedule_changes": compare_schedule(current.get("schedule", []), previous.get("schedule", [])),
        "risk_changes": compare_risks(current.get("risks", []), previous.get("risks", [])),
    }



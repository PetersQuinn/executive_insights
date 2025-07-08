from pipeline.compare import compare_kpis

prev = {
    "budget": "$2.0M (70% utilized)",
    "timeline": "On Track",
    "scope": "Standard MVP features",
    "client sentiment": "Neutral"
}

curr = {
    "budget": "$2.3M (80% utilized)",
    "timeline": "Delayed",
    "scope": "Slightly expanded due to client add-ons",
    "client sentiment": "Positive"
}

print(compare_kpis(curr, prev))

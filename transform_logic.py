"""
transform_logic.py

Data transformation logic for the TfL pipeline, kept separate from
any database code so it can be tested directly.
Given a line dictionary as input, without needing a real database connection.
"""

def extract_line_fields(line):
    """
    Takes one line's dictionary from a TfL raw snapshot and returns
    just the fields needed for clean_line_status, as a dictionary.
    """
    status = line["lineStatuses"][0]

    return {
        "line_id": line["id"],
        "line_name": line["name"],
        "status_severity": status["statusSeverity"],
        "status_severity_description": status["statusSeverityDescription"],
        "reason": status.get("reason"),
        "category": status.get("disruption", {}).get("category"),
    }
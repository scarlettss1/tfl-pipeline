import pytest
from transform_logic import extract_line_fields


def test_extract_line_fields_good_service():
    # A line with "Good Service" (no disruption) so reason and category
    # should come back as None.
    line = {
        "id": "circle",
        "name": "Circle",
        "lineStatuses": [
            {
                "statusSeverity": 10,
                "statusSeverityDescription": "Good Service"
            }
        ]
    }

    result = extract_line_fields(line)

    assert result["line_id"] == "circle"
    assert result["line_name"] == "Circle"
    assert result["status_severity"] == 10
    assert result["status_severity_description"] == "Good Service"
    assert result["reason"] is None
    assert result["category"] is None


def test_extract_line_fields_with_disruption():
    line = {
        "id": "bakerloo",
        "name": "Bakerloo",
        "lineStatuses": [
            {
                "statusSeverity": 9,
                "statusSeverityDescription": "Minor Delays",
                "reason": "Bakerloo Line: Minor delays due to train cancellations. ",
                "disruption": {
                    "category": "RealTime"
                }
            }
        ]
    }

    result = extract_line_fields(line)

    assert result["line_id"] == "bakerloo"
    assert result["status_severity"] == 9
    assert result["reason"] == "Bakerloo Line: Minor delays due to train cancellations. "
    assert result["category"] == "RealTime"


def test_extract_line_fields_missing_line_statuses():
    # If lineStatuses is missing, this raises an error.
    line = {
        "id": "central",
        "name": "Central"
    }

    with pytest.raises(KeyError):
        extract_line_fields(line)


def test_extract_line_fields_empty_line_statuses():
    # If lineStatuses exists but is an empty list, this raises an error.
    line = {
        "id": "central",
        "name": "Central",
        "lineStatuses": []
    }

    with pytest.raises(IndexError):
        extract_line_fields(line)
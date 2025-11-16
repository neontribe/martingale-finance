import json
from pathlib import Path
import pytest

# 👇 Update this import to match where your function lives
# e.g. from app.beacon import parse_beacon_data
from  app.libs.beacon_strategy import (
        parse_beacon_data
    )

@pytest.fixture
def sample_data():
    data_path = Path(__file__).parent / "digest" / "response1.json"
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_parse_beacon_data_structure_and_values(sample_data):
    # Call with target_id=None to return all results in the expected projected shape
    result = parse_beacon_data(sample_data, target_id=None)

    # Should be a list with one projected entity
    assert isinstance(result, list)
    assert len(result) == 1

    item = result[0]

    # Keys expected from the JMESPath projection
    assert set(item.keys()) == {
        "application_id",
        "applicant_id",
        "applicant_name",
        "application_cycle",
        "attachments",
        "student_finance_letter",
        "identified_value",
    }

    # Values from the provided JSON
    assert item["application_id"] == 4772
    assert item["application_cycle"] == ["2025 entry"]

    # Attachments: only id, url, type should be projected
    assert isinstance(item["attachments"], list)
    assert item["attachments"] == [
        {
            "id": "ffd56441-3e4f-4393-a29a-ced51d4c821a",
            "url": "https://example.com/PYas.pdf",
            "type": "application/pdf",
        }
    ]

    # Student finance letter: same projection
    assert isinstance(item["student_finance_letter"], list)
    assert item["student_finance_letter"] == [
        {
            "id": "54d0a853-6b9d-4323-b571-d30e1c7cc703",
            "url": "https://example.com/BYnry.pdf",
            "type": "application/pdf",
        }
    ]

    # Identified value should be the numeric value from the entity
    assert item["identified_value"] == 10000

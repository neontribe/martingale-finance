import json

import jmespath
import jsonschema
from jsonschema import validate
from typing import Optional

import config
from libs.http_strategy_selector import get_http, patch_http

PROJECT_ROOT = config.get_project_root()

HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.API_BEARER_TOKEN}",
        "Beacon-Application": "developer_api",
        "Accept": "application/json"
    }

def make_beacon_data(data: dict):
    # Extract values
    maintenance_grant = data.get("maintenance_grant")
    maintenance_loan = data.get("maintenance_loan")
    authority = data.get("authority")
    # Determine which value to use and set estimate status
    if maintenance_grant is not None:
        value = maintenance_grant
        estimate_status = ["Accurate"]
    elif maintenance_loan is not None:
        value = maintenance_loan
        estimate_status = ["Estimate"]
    else:
        value = None
        estimate_status = None
    # Determine if there's an error
    error_condition = (
        data.get("document_valid") is True and (
            (not maintenance_grant and not maintenance_loan) or
            (authority is None or str(authority).strip() == "")
        )
    )
    processed_data = {
        "c_what_type_of_financial_evidence_is_this": authority or None,
        "c_identified_value": {
            "currency": "GBP",
            "value": value,
            "base_value": value
        } if value is not None else None,
        "c_is_this_value_an_estimate_or_accurate": estimate_status,
        "c_error_report_martingale_team_to_review": "Error in Document" if error_condition else None,
    }
    print(processed_data)
    return processed_data


def get_beacon_data(uri: Optional[str]):

    url = uri or config.API_URL

    try:
        response = get_http(url, HEADERS)
        response.raise_for_status()
    except Exception as e:
        config.LOGGER.error(f"HTTP request failed: {e}")
        return None

    try:
        data = response.json()
        config.LOGGER.info(f"API response received and parsed: {data}")

    except Exception as e:
        config.LOGGER.error(f"Response is not valid JSON: {e}")
        return None

    with open( PROJECT_ROOT / "app/libs/schemas/beacon-schema-short.json") as f:
        schema = json.load(f)

    try:
        validate(instance=data, schema=schema)
        config.LOGGER.info("JSON is valid")
    except jsonschema.exceptions.ValidationError as e:
        config.LOGGER.error("JSON is invalid")
        config.LOGGER.error(f"Error: {e.message}")

    return data


def parse_beacon_data(data, target_id: Optional[str]):

    if target_id is None:
        mode = "results[*]"
    else:
        mode = f"results[?entity.id == `{target_id}`]"

    search = mode + ".entity.{id: id, c_application_cycle: c_application_cycle[*]c_attachments: c_attachments[*].{id: id, url:url, type: type}, c_student_finance_letter: c_student_finance_letter[*].{id: id, url:url, type: type}, c_identified_value: c_identified_value}"

    return jmespath.search(search, data)

def patch_beacon_data(data, uri: Optional[str]):

    url = uri or config.API_URL

    try:
        response = patch_http(url, HEADERS, data)
        response.raise_for_status()
    except Exception as e:
        config.LOGGER.error(f"HTTP request failed: {e}")
        return None

    try:
        data = response.json()
        config.LOGGER.info(f"API response received and parsed: {data}")
    except Exception as e:
        config.LOGGER.error(f"Response is not valid JSON: {e}")
        return None

    print(data)
    status = response.status_code
    return status

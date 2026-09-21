import json

import jmespath
import jsonschema
from jsonschema import validate
from typing import Optional, Union, Any

import config
from libs.http_strategy_selector import get_http, patch_http

PROJECT_ROOT = config.get_project_root()

HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.API_BEARER_TOKEN}",
        "Beacon-Application": "developer_api",
        "Accept": "application/json"
    }

def validate_candidate(digest, value, applicant_estimate):

    if not digest["document_valid"]:
        return "No valid documents"

    if not digest["authority"]:
        return "Could not extract authority type"

    if not value:
        return "Could not extract grant/loan data"

    if float(applicant_estimate or 0) > float(value or 0):
        return f"Student reported value {applicant_estimate} is more than grant/loan {value}"

    return None

def make_beacon_data(digest, item):
    # Extract values
    maintenance_grant = digest.get("maintenance_grant")
    maintenance_loan = digest.get("maintenance_loan")
    authority = digest.get("authority")
    applicant_estimate = item.get("applicant_estimate")

    # Determine which value to use and set estimate status
    if maintenance_grant is not None:
        value = maintenance_grant
        estimate_status = "Accurate"
    elif maintenance_loan is not None:
        value = maintenance_loan
        estimate_status = "Estimate"
    else:
        value = None
        estimate_status = None

    # Determine if there's an error
    error_condition = validate_candidate(digest, value, applicant_estimate)

    processed_data = {
        "application_id": item.get("application_id") or None,
        "applicant_id": item.get("applicant_id") or None,
        "applicant_name": item.get("applicant_name") or None,
        "authority": authority or None,
        "identified_value": value if value is not None else None,
        "estimate_or_accurate": estimate_status,
        "error": "Y" if error_condition else "N",
        "error_reason": error_condition,
    }
    return processed_data

def get_beacon_data(uri=None):

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


def parse_beacon_data(data, target_id: Optional[str] = None):

    if target_id is None:
        mode = "results[*]"
    else:
        mode = f"results[?entity.id == `{target_id}`]"

    search = mode + (
            ".{"
                "application_id: entity.id,"
                "applicant_id: references[0].entity.id,"
                "applicant_name: references[0].entity.name.full,"
                "applicant_estimate: entity.c_if_yes_please_state_the_total_amount_of_maintenance_loan_and_or_grant_you_received_in_your_most_recent_academic_year.value,"
                "application_cycle: entity.c_application_cycle[*],"
                "attachments: entity.c_attachments[*].{"
                    "id: id,"
                    "url:url,"
                    "type: type},"
                "student_finance_letter: entity.c_student_finance_letter[*].{"
                    "id: id,"
                    "url:url,"
                    "type: type},"
                "identified_value: entity.c_identified_value}"
    )
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

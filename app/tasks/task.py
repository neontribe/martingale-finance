import csv
import json
from functools import lru_cache
from typing import Any, Optional, Dict

from app import config
from app.libs.document_strategy_selector import document_get
from app.libs.ai_strategy import upload_gcs_file_part, analyze_document_with_gemini
from libs.ai_strategy import delete_gcs_file
from libs.beacon_strategy import get_beacon_data, parse_beacon_data, patch_beacon_data, make_beacon_data

REGION = "europe-west2"

def scheduled_task():
    config.LOGGER.info("Scheduled task started.")

    # get beacon data
    data = get_beacon_data()

    # parse it
    if data is not None:
        parsed = parse_beacon_data(data)
        # process it
        if parsed is not None:
            process(parsed)
        else:
            config.LOGGER.error("Bad data from beacon")
    else:
        config.LOGGER.error("No Data from Beacon")

def process(data):
    # iterate over the applications
    for item in data:
        application_id = item.get("application_id")
        application_cycle = item.get("application_cycle", [])
        applicant_id = item.get("applicant_id")
        applicant_name = item.get("applicant_name")
        student_finance_letters = item.get("student_finance_letter", [])
        attachments = item.get("attachments", [])

        config.LOGGER.info(f"\nProcessing item ID: {application_id}")

        # digest the documents and find ones that match
        parsed_docs = []
        for err_msg, source in [
            ("No student finance letters.", student_finance_letters),
            ("No student finance letters in attachments.", attachments),
        ]:
            if not source:
                config.LOGGER.error(err_msg)
                continue

            parsed_docs = list(filter(None, map(get_document_digest, source, application_cycle)))
            if parsed_docs:  # stop at the first source that yields docs
                break

        print(parsed_docs)
'''
        if not parsed_docs:
            config.LOGGER.error("No student finance letters.")
            # write a null line to the csv
        else:
            # process the list of candidates.
            # write a good line to the csv
'''

@lru_cache(maxsize=8)
def _load_prompt(uri: str) -> bytes:
    # Cache prompt files so repeated calls don't hit I/O every time
    return document_get(uri)

def get_document_digest(docref: Dict[str, Any], intake: Optional[str]) -> Optional[Dict[str, Any]]:
    att_id = docref.get("id")
    att_url = docref.get("url")
    att_type = docref.get("type")

    try:
        document_content = document_get(att_url)
        gcs_part = upload_gcs_file_part(att_id, document_content, att_type)

        categorisation_prompt = _load_prompt("file://app/libs/data/categorising_prompt.txt")
        categorisation = validate_response(
            analyze_document_with_gemini(REGION, gcs_part, categorisation_prompt),
            att_id,
        ) or {}

        if not categorisation.get("document_valid"):
            return None

        extraction_prompt = _load_prompt("file://app/libs/data/extracting_prompt.txt")
        extraction = validate_response(
            analyze_document_with_gemini(REGION, gcs_part, extraction_prompt),
            att_id,
        ) or {}

        # glue the two together and return
        return categorisation | extraction

    finally:
        # Always clean up, even if anything above raises
        delete_gcs_file(att_id)

def validate_response(response, att_id):
    parsed_response = None
    try:
        parsed_response = json.loads(response)
        config.LOGGER.info(f"  Valid JSON response received for docref ID: {att_id}")
    except json.JSONDecodeError:
        config.LOGGER.error(f"  Invalid JSON response for docref ID: {att_id}")
    return parsed_response


'''
beacon_data = get_beacon_data(config.API_URL)
with open("../../tests/data/sample.json", "w") as f:
    json.dump(beacon_data, f)
'''


document_data= document_get("file://app/libs/data/Student_Finance_Letter_3.pdf")
instruction_data= document_get("file://app/libs/data/extraction_prompt.txt")
part = upload_gcs_file_part("SFL3.pdf", document_data, "application/pdf")
extracted_data = analyze_document_with_gemini("europe-west2", part, instruction_data)

'''
if extracted_data is not None:
    patch_data = make_beacon_data(extracted_data)
    patch_url = "https://api.beaconcrm.org/v1/account/24909/entity/c_application/113554"
    patch_beacon_data(patch_data, patch_url)
'''

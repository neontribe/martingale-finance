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


def write_csv(output, filename):
    # Mapping of CSV headers to dict keys
    field_map = {
        "Record ID (person)": "applicant_id",
        "Record ID (Application)": "application_id",
        "Type of Financial Evidence": "authority",
        "Identified Value": "identified_value",
        "Estimate / Accurate?": "estimate_or_accurate",
        "Error Report (Y/N)": "error",
        "Notes": "error_reason",
    }

    # open a file handler
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header row
        writer.writerow(field_map.keys())

        # Write data rows
        for item in output:
            row = []
            for header, key in field_map.items():
                value = item.get(key)

                # Convert list values to comma-separated string
                if isinstance(value, list):
                    value = "; ".join(value)

                row.append(value)
            writer.writerow(row)


def scheduled_task():
    config.LOGGER.info("Scheduled task started.")

    # get beacon digest
    data = get_beacon_data()

    # parse it
    if data is not None:
        parsed = parse_beacon_data(data)
        # process it
        if parsed is not None:
            output = process(parsed)
            write_csv(output, "output.csv")
        else:
            config.LOGGER.error("Bad digest from beacon")
    else:
        config.LOGGER.error("No Data from Beacon")

def process(data):
    # iterate over the applications
    output = []
    for item in data:
        application_id = item.get("application_id")
        config.LOGGER.info(f"\nProcessing item ID: {application_id}")

        application_cycle = item.get("application_cycle", [])
        student_finance_letters = item.get("student_finance_letter", [])
        attachments = item.get("attachments", [])

        documents = student_finance_letters + attachments
        if documents:
            # get compact list of possible documents
            digests = list(filter(None, map(get_document_digest, documents, application_cycle)))
            best_doc = find_best(digests)
            if best_doc:
                output.append(make_beacon_data(best_doc, item))
        else:
            config.LOGGER.info("No Documents")
    return output

# finds the best item in a list.
def find_best(digests):
    return sorted(
        digests,
        key=lambda x: (
            not x["document_valid"],
            x["maintenance_grant"] in (None, ""),
            x["maintenance_loan"] in (None, ""),
        )
    )[0]

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
        categorisation = analyze_document_with_gemini(REGION, gcs_part, categorisation_prompt) or {}

        null_extraction = {"institutional_money": None, "maintenance_loan": None, "maintenance_grant": None}

        if not categorisation.get("document_valid"):
            return { **categorisation, **null_extraction }

        extraction_prompt = _load_prompt("file://app/libs/data/extraction_prompt.txt")
        extraction = analyze_document_with_gemini(REGION, gcs_part, extraction_prompt) or null_extraction

        result = { **categorisation, **extraction }
        print(result)
        # glue the two together and return
        return result

    finally:
        # Always clean up, even if anything above raises
        delete_gcs_file(att_id)

'''
beacon_data = get_beacon_data(config.API_URL)
with open("../../tests/data/sample.json", "w") as f:
    json.dump(beacon_data, f)
'''

'''
data = { "id": "document", "url": "file://app/libs/data/Student_Finance_Letter_3.pdf", "type": "application/pdf"}
details = get_document_digest(data, " ")
print(details)
'''

'''
document_data= document_get("file://app/libs/data/Student_Finance_Letter_3.pdf")
instruction_data= document_get("file://app/libs/data/extraction_prompt.txt")
part = upload_gcs_file_part("SFL3.pdf", document_data, "application/pdf")
extracted_data = analyze_document_with_gemini("europe-west2", part, instruction_data)
'''

'''
if extracted_data is not None:
    patch_data = make_beacon_data(extracted_data)
    patch_url = "https://api.beaconcrm.org/v1/account/24909/entity/c_application/113554"
    patch_beacon_data(patch_data, patch_url)
'''

scheduled_task()

import json
from typing import Any

from app import config
from app.libs.document_strategy_selector import document_get
from app.libs.ai_strategy import upload_gcs_file_part, analyze_document_with_gemini
from libs.ai_strategy import delete_gcs_file
from libs.beacon_strategy import get_beacon_data, parse_beacon_data, patch_beacon_data, make_beacon_data


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
    for item in data:
        item_id = item.get("id")
        application_cycle = item.get("c_application_cycle", [])
        student_finance_letters = item.get("c_student_finance_letter", [])
        attachments = item.get("c_attachments", [])

        config.LOGGER.info(f"\nProcessing item ID: {item_id}")


        if student_finance_letters:
            parsed_letters = list(map(process_document,student_finance_letters))
        else:
            parsed_letters = []
            config.LOGGER.error("No student finance letters.")

        if attachments:
            parsed_attachments = list(map(process_document,attachments))
        else:
            parsed_attachments = []
            config.LOGGER.error("No student finance letters.")


def process_document(docref) -> Any:
        att_id = docref.get("id")
        att_url = docref.get("url")
        att_type = docref.get("type")

        # fetch the document content from where it's stored
        document_content = document_get(att_url)

        # upload to gcs and get a document "part" reference
        part = upload_gcs_file_part(att_id, document_content, att_type)

        # process the data
        instructions = document_get("file://app/libs/data/instructions.txt")

        response = analyze_document_with_gemini("europe-west2", part, instructions)

        parsed_response = None

        try:
            parsed_response = json.loads(response)
            config.LOGGER.info(f"  Valid JSON response received for docref ID: {att_id}")
        except json.JSONDecodeError:
            config.LOGGER.error(f"  Invalid JSON response for docref ID: {att_id}")
        else:
            # check the response
            if not parsed_response.get('document_valid'):
                config.LOGGER.error(f"Invalid Document: {att_id}")
        finally:
            # delete the document
            delete_gcs_file(att_id)

        return parsed_response

'''
beacon_data = get_beacon_data(config.API_URL)
with open("../../tests/data/sample.json", "w") as f:
    json.dump(beacon_data, f)
'''

'''
document_data= document_get("file://app/libs/data/Student_Finance_Letter_3.pdf")
instruction_data= document_get("file://app/libs/data/instructions.txt")
part = upload_gcs_file_part("SFL3.pdf", document_data, "application/pdf")
extracted_data = analyze_document_with_gemini("europe-west2", part, instruction_data)

if extracted_data is not None:
    patch_data = make_beacon_data(extracted_data)
    patch_url = "https://api.beaconcrm.org/v1/account/24909/entity/c_application/113554"
    patch_beacon_data(patch_data, patch_url)
'''

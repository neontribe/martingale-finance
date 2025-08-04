import json

import jmespath
import jsonschema
from jsonschema import validate

from app import config
from app.libs.document_strategy_selector import document_get
from app.libs.http_strategy_selector import get_http
from app.libs.ai_strategy import upload_gcs_file_part, analyze_document_with_gemini


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


def get_beacon_data():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.API_BEARER_TOKEN}",
        "Beacon-Application": "developer_api",
        "Accept": "application/json"
    }

    try:
        response = get_http(config.API_URL, headers)
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

    with open("./app/libs/schemas/beacon-schema-short.json") as f:
        schema = json.load(f)

    try:
        validate(instance=data, schema=schema)
        config.LOGGER.info("JSON is valid")
    except jsonschema.exceptions.ValidationError as e:
        config.LOGGER.error("JSON is invalid")
        config.LOGGER.error(f"Error: {e.message}")

    return data


def parse_beacon_data(data):
    search = "results[*].entity.{id: id, attachments: attachments[*].{id: id, url:url, type: type}}"
    parsed = jmespath.search(search, data)
    return parsed


def process(data):
    for item in data:
        item_id = item.get("id")
        attachments = item.get("attachments", [])

        config.LOGGER.info(f"\nProcessing item ID: {item_id}")

        if not attachments:
            config.LOGGER.error("  No attachments.")
        else:
            for attachment in attachments:
                att_id = attachment.get("id")
                att_url = attachment.get("url")
                att_type = attachment.get("type")

                # Do your processing here
                config.LOGGER.info(f"  Attachment ID: {att_id}")
                config.LOGGER.info(f"  Type: {att_type}")
                config.LOGGER.info(f"  URL: {att_url}")

                document_data = document_get(att_url)

                part = upload_gcs_file_part(att_id, document_data, att_type)
                query = "This is a multipart query with a document part. Enumerate the properties of the document part."
                analyze_document_with_gemini("europe-west2", part, query)


part = upload_gcs_file_part("chips.txt", "fish n chips!", "text/plain")
query = "This is a multipart query with a document part. Enumerate the properties of the document part."
analyze_document_with_gemini("europe-west2", part, query);

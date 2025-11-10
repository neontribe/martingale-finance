import logging
from app import config
from app.libs.httpStrategySelector import get_http
import jmespath
import json
import jsonschema
from jsonschema import validate

logger = logging.getLogger(__name__)

def scheduled_task():
    logger.info("Scheduled task started.")

    # get beacon data
    data = getBeaconData()

    # parse it
    if data is not None:
        parsed = parseBeaconData(data)
        # process it
        if parsed is not None:
            process(parsed)
        else:
            logger.error("Bad data from beacon")
    else:
        logger.error("No Data from Beacon")

def getBeaconData():
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
        logger.error(f"HTTP request failed: {e}")
        return None

    try:
        data = response.json()
        logger.info(f"API response received and parsed: {data}")

    except Exception as e:
        logger.error(f"Response is not valid JSON: {e}")
        return None

    with open("./app/libs/schemas/beacon-schema-short.json") as f:
        schema = json.load(f)

    try:
        validate(instance=data, schema=schema)
        logger.info("JSON is valid")
    except jsonschema.exceptions.ValidationError as e:
        logger.error("JSON is invalid")
        logger.error(f"Error: {e.message}")

    return data


def parseBeaconData(data):
    search = "results[*].entity.{id: id, attachments: attachments[*].{id: id, url:url, type: type}}"
    parsed = jmespath.search(search, data)
    return parsed

def process(data):
    for item in data:
        item_id = item.get("id")
        attachments = item.get("attachments", [])

        print(f"\nProcessing item ID: {item_id}")

        if not attachments:
            print("  No attachments.")
        else:
            for attachment in attachments:
                att_id = attachment.get("id")
                att_url = attachment.get("url")
                att_type = attachment.get("type")

                # Do your processing here
                print(f"  Attachment ID: {att_id}")
                print(f"  Type: {att_type}")
                print(f"  URL: {att_url}")
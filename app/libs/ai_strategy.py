from vertexai.generative_models import Part
from google.cloud import storage
from google.oauth2 import service_account
from config import LOGGER, GCS_BUCKET_NAME, GOOGLE_APPLICATION_CREDENTIALS_JSON, get_project_root
import json

def upload_gcs_file_part(target_filename: str, contents: bytes = None, mime_type: str = 'text/plain') -> Part:
    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{target_filename}"

    storage_client = set_storage_with_credentials()

    # Upload to GCS
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(target_filename)

    LOGGER.info(f"Uploading '{target_filename}' to '{gcs_uri}'...")
    blob.upload_from_string(contents, mime_type)
    LOGGER.info("Upload complete.")

    # Create and return the Part object
    document_part = Part.from_uri(gcs_uri, mime_type=mime_type)

    return document_part

def delete_gcs_file(file_name: str, client: storage.Client = None):
    if client is None:
        client = set_storage_with_credentials()

    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(file_name)

    blob.delete()

    LOGGER.info(f"Deleted gs://{GCS_BUCKET_NAME}/{file_name}")


def set_storage_with_credentials():
    try:
        credentials_dict = json.loads(GOOGLE_APPLICATION_CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        storage_client = storage.Client(credentials=credentials)
        LOGGER.info("Authentication successful using raw JSON from environment variable.")
    except json.JSONDecodeError:
        storage_client = storage.Client.from_service_account_json(get_project_root() / GOOGLE_APPLICATION_CREDENTIALS_JSON)
        LOGGER.info("Authentication successful using a file path from environment variable.")
    if storage_client:
        LOGGER.info("\nListing all buckets in the project:")
        for bucket in storage_client.list_buckets():
            LOGGER.info(f"- {bucket.name}")
    return storage_client
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import storage
from google.oauth2 import service_account
from config import LOGGER, GCS_BUCKET_NAME, PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON, get_project_root
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


def analyze_document_with_gemini(
    location: str,
    document_part: Part,
    query_text: str
):
    # 1. Initialize Vertex AI client with project and location.
    # This is critical for specifying the geographic jurisdiction.
    vertexai.init(project=PROJECT_ID, location=location)

    # 2. Load the GenerativeModel
    model = GenerativeModel("gemini-2.5-flash")

    # 3. Create the multimodal prompt using Part objects.
    # The prompt is a list of "parts" that can be text, images, files, etc.
    multimodal_prompt = [
        # Part 1:
        document_part,
        # Part 2: The text query to perform on the document.
        Part.from_text(query_text)
    ]

    LOGGER.info("Sending prompt to the model\n")
    LOGGER.info(f"Query: {query_text}\n")

    # 4. Call the model to generate content.
    response = model.generate_content(multimodal_prompt)

    # 5. Print the model's response.
    LOGGER.info("Model's determination:")
    LOGGER.info(response.text)

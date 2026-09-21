import json
from pathlib import Path
import pytest

import app.libs.ai_strategy as ai_strategy
from google.cloud import storage
from google.oauth2 import service_account
from google.auth.credentials import Credentials
from vertexai.generative_models import Part
from google.cloud import aiplatform


class FakeBlob:
    def __init__(self):
        self.upload_args = None
        self.deleted = False

    def upload_from_string(self, contents, mime_type):
        self.upload_args = (contents, mime_type)

    def delete(self):
        self.deleted = True


class FakeBucket:
    def __init__(self, blob):
        self._blob = blob

    def blob(self, name):
        # Return our fake blob regardless of name for simplicity
        return self._blob


class FakeClient:
    def __init__(self, bucket):
        self._bucket = bucket
        self.list_buckets = lambda: []

    def bucket(self, name):
        return self._bucket


@pytest.fixture(autouse=True)
def env_constants(monkeypatch, tmp_path):
    """
    Override constants so tests don't depend on real config.
    """
    monkeypatch.setattr(ai_strategy, 'GCS_BUCKET_NAME', 'test-bucket')
    monkeypatch.setattr(ai_strategy, 'PROJECT_ID', 'test-project')
    # Point credentials JSON env var to a dummy string or filename
    monkeypatch.setattr(ai_strategy, 'GOOGLE_APPLICATION_CREDENTIALS_JSON', 'dummy-creds.json')
    # Override get_project_root to tmp_path
    monkeypatch.setattr(ai_strategy, 'get_project_root', lambda: tmp_path)
    return tmp_path


def test_upload_gcs_file_part(monkeypatch, env_constants):
    # Prepare fake storage client
    fake_blob = FakeBlob()
    fake_bucket = FakeBucket(fake_blob)
    fake_client = FakeClient(fake_bucket)
    # Patch storage client creation
    monkeypatch.setattr(ai_strategy, 'set_storage_with_credentials', lambda: fake_client)
    # Patch Part.from_uri
    expected_part = object()
    monkeypatch.setattr(Part, 'from_uri', classmethod(lambda cls, uri, mime_type=None: expected_part))

    # Call function
    result = ai_strategy.upload_gcs_file_part('file.txt', b'digest', 'text/plain')

    # Assertions
    assert result is expected_part
    assert fake_blob.upload_args == (b'digest', 'text/plain')


def test_delete_gcs_file_with_provided_client(monkeypatch, env_constants):
    fake_blob = FakeBlob()
    fake_bucket = FakeBucket(fake_blob)
    fake_client = FakeClient(fake_bucket)

    # Call delete with explicit client
    ai_strategy.delete_gcs_file('to_delete.txt', client=fake_client)

    assert fake_blob.deleted is True


def test_delete_gcs_file_without_client(monkeypatch, env_constants):
    fake_blob = FakeBlob()
    fake_bucket = FakeBucket(fake_blob)
    fake_client = FakeClient(fake_bucket)
    # Patch default client creation
    monkeypatch.setattr(ai_strategy, 'set_storage_with_credentials', lambda: fake_client)

    ai_strategy.delete_gcs_file('to_delete2.txt')
    assert fake_blob.deleted is True


def test_set_storage_with_credentials_json_parsing(monkeypatch, env_constants):
    # Provide valid JSON
    creds_dict = {'hello': 'world'}
    monkeypatch.setattr(ai_strategy, 'GOOGLE_APPLICATION_CREDENTIALS_JSON', json.dumps(creds_dict))

    # Record calls
    called = {}
    def fake_from_info(info):
        called['info'] = info
        return 'creds-object'
    monkeypatch.setattr(service_account.Credentials, 'from_service_account_info', staticmethod(fake_from_info))

    def fake_storage_client(credentials):
        called['credentials'] = credentials
        return FakeClient(FakeBucket(FakeBlob()))
    monkeypatch.setattr(storage, 'Client', fake_storage_client)

    # Execute
    client = ai_strategy.set_storage_with_credentials()
    assert called['info'] == creds_dict
    assert called['credentials'] == 'creds-object'
    assert isinstance(client, FakeClient)


def test_set_storage_with_credentials_file_fallback(monkeypatch, env_constants):
    # JSON parsing fails
    monkeypatch.setattr(ai_strategy, 'GOOGLE_APPLICATION_CREDENTIALS_JSON', 'not a json')
    monkeypatch.setattr(json, 'loads', lambda x: (_ for _ in ()).throw(json.JSONDecodeError("err", "doc", 0)))

    # Patch from_service_account_json
    called = {}
    def fake_from_json(path):
        called['path'] = path
        return FakeClient(FakeBucket(FakeBlob()))
    monkeypatch.setattr(storage.Client, 'from_service_account_json', classmethod(lambda cls, path: fake_from_json(path)))

    # Execute
    client = ai_strategy.set_storage_with_credentials()
    assert isinstance(client, FakeClient)
    # Expect fallback to use the monkeypatched JSON name ('not a json')
    assert called['path'] == env_constants / ai_strategy.GOOGLE_APPLICATION_CREDENTIALS_JSON


def test_initialize_vertex_ai_with_json(monkeypatch, env_constants):
    # Valid JSON branch
    creds_dict = {'a': 1}
    monkeypatch.setattr(ai_strategy, 'GOOGLE_APPLICATION_CREDENTIALS_JSON', json.dumps(creds_dict))
    monkeypatch.setattr(json, 'loads', lambda x: creds_dict)

    called = {}
    def fake_from_info(info):
        called['info'] = info
        return 'cred-info'
    monkeypatch.setattr(service_account.Credentials, 'from_service_account_info', staticmethod(fake_from_info))

    def fake_aiplatform_init(project, location, credentials):
        called['project'] = project
        called['location'] = location
        called['credentials'] = credentials
    monkeypatch.setattr(aiplatform, 'init', fake_aiplatform_init)

    # Execute
    ai_strategy.initialize_vertex_ai('us-central1')
    assert called['info'] == creds_dict
    assert called['project'] == 'test-project'
    assert called['location'] == 'us-central1'
    assert called['credentials'] == 'cred-info'


def test_initialize_vertex_ai_file_fallback(monkeypatch, env_constants):
    # JSON decode error branch
    monkeypatch.setattr(ai_strategy, 'GOOGLE_APPLICATION_CREDENTIALS_JSON', 'path.json')
    monkeypatch.setattr(json, 'loads', lambda x: (_ for _ in ()).throw(json.JSONDecodeError("err", "doc", 0)))

    monkeypatch.setattr(ai_strategy, 'get_project_root', lambda: Path("/root"))
    called = {}
    def fake_from_file(path):
        called['path'] = path
        return 'cred-file'
    monkeypatch.setattr(service_account.Credentials, 'from_service_account_file', staticmethod(fake_from_file))

    def fake_aiplatform_init(project, location, credentials):
        called['project'] = project
        called['location'] = location
        called['credentials'] = credentials
    monkeypatch.setattr(aiplatform, 'init', fake_aiplatform_init)

    # Execute
    ai_strategy.initialize_vertex_ai('europe-west1')
    assert called['path'] == Path("/root") / 'path.json'
    assert called['project'] == 'test-project'
    assert called['location'] == 'europe-west1'
    assert called['credentials'] == 'cred-file'


def test_analyze_document_with_gemini(monkeypatch, env_constants):
    # Patch initialize
    called = {}
    monkeypatch.setattr(ai_strategy, 'initialize_vertex_ai', lambda location: called.update({'init_loc': location}))

    # Fake model
    class FakeModel:
        def __init__(self, name):
            called['model_name'] = name

        def generate_content(self, prompt):
            called['prompt'] = prompt
            return type('R', (), {'text': 'fake-response'})()

    monkeypatch.setattr(ai_strategy, 'GenerativeModel', FakeModel)
    monkeypatch.setattr(Part, 'from_text', classmethod(lambda cls, text: f'text-part:{text}'))

    # Execute
    result = ai_strategy.analyze_document_with_gemini('loc1', 'doc-part', 'my query')
    assert called['init_loc'] == 'loc1'
    assert called['model_name'] == 'gemini-2.5-flash'
    assert called['prompt'] == ['doc-part', 'text-part:my query']
    assert result == 'fake-response'

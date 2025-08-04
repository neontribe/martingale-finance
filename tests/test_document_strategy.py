import http.server
import os
import socketserver
import threading
from pathlib import Path

import pytest

from app.libs.document_strategy_selector import (
    document_get,
    is_file_uri,
    local_document_get,
    remote_document_get
)

# Constants
TEST_FILE_DIR = Path(__file__).parent / "data"
TEST_FILE_NAME = "testfile.txt"
TEST_FILE_PATH = TEST_FILE_DIR / TEST_FILE_NAME
TEST_FILE_CONTENT = b"Hello, world!\n"  # Adjust this to match the actual file content


def test_is_file_uri_true():
    assert is_file_uri("file://tests/data/testfile.txt") is True


def test_is_file_uri_false():
    assert is_file_uri("https://example.com/file.txt") is False


def test_local_document_get_reads_file():
    uri = "file://tests/data/testfile.txt"
    content = local_document_get(uri)
    assert content == TEST_FILE_CONTENT


def test_document_get_local_file():
    uri = "file://tests/data/testfile.txt"
    content = document_get(uri)
    assert content == TEST_FILE_CONTENT


def test_local_document_get_file_not_found():
    uri = "file://tests/data/nonexistent.txt"
    with pytest.raises(FileNotFoundError):
        local_document_get(uri)


def test_local_document_get_is_directory():
    uri = "file://tests/data"
    with pytest.raises(IsADirectoryError):
        local_document_get(uri)


# ---------- Remote Tests with Real HTTP Server ----------

@pytest.fixture(scope="module")
def test_http_server():
    """
    Spin up a local HTTP server serving the test file.
    """
    os.chdir(TEST_FILE_DIR)  # serve from data directory
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("localhost", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}/{TEST_FILE_NAME}"
    httpd.shutdown()


def test_remote_document_get(test_http_server):
    uri = test_http_server
    content = remote_document_get(uri)
    assert content == TEST_FILE_CONTENT


def test_document_get_remote(test_http_server):
    uri = test_http_server
    content = document_get(uri)
    assert content == TEST_FILE_CONTENT

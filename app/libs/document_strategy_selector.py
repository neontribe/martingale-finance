from urllib.parse import urlparse
from pathlib import Path
import requests
from app.config import get_project_root, LOGGER

PROJECT_ROOT = get_project_root()

def remote_document_get(uri: str) -> bytes:
    resp = requests.get(uri)
    # may cause an exception
    resp.raise_for_status()
    return resp.content

def local_document_get(uri: str) -> bytes:
    parsed = urlparse(uri)
    parts = []
    if parsed.netloc and parsed.netloc.lower() != "localhost":
        parts.append(parsed.netloc)
    parts.append(parsed.path.lstrip("/"))
    rel_path = Path().joinpath(*parts)
    file_path = PROJECT_ROOT / rel_path

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise IsADirectoryError(f"Expected a file but found a directory: {file_path}")

    return file_path.read_bytes()

def document_get(uri: str) -> bytes:
    if is_file_uri(uri):
        return local_document_get(uri)
    else:
        return remote_document_get(uri)

def is_file_uri(uri: str) -> bool:
    return urlparse(uri).scheme == "file"

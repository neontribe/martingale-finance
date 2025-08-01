from typing import Callable
import requests
from requests import Response
from app.config import ENV, get_project_root

import json

PROJECT_ROOT = get_project_root()

HttpGetter = Callable[[str, dict], requests.Response]

def real_http_get(url: str, headers: dict) -> requests.Response:
    return requests.get(url, headers=headers, timeout=10)

def mock_http_get(url: str, headers: dict) -> requests.Response:
    with open(PROJECT_ROOT / "app/libs/data/beacon-data.json") as f:
        mock_data = json.load(f)

    mock_response = Response()
    mock_response.status_code = 200
    mock_response._content = json.dumps(mock_data).encode("utf-8")
    mock_response.headers["Content-Type"] = "application/json"
    mock_response.url = url

    return mock_response

# Decide which function to use based on ENV
get_http = mock_http_get if ENV in {"testing", "development"} else real_http_get
# Configuration

All configuration is supplied through environment variables. `app/config.py` loads environment variables from a `.env` file at the project root on module import via `load_dotenv()`.

```bash
cp .env.example .env
```

---

## 1. How Configuration is Loaded

`app/config.py` implements a helper function:

```python
get_env(name: str, default=None, required=False, cast=str)
```

- Reads `os.getenv(name)`.
- Falls back to `default` if the variable is not set.
- Raises a `ValueError` if a `required` variable is missing or cannot be cast to the specified type.
- Evaluates configuration at module import time so misconfigured environments fail fast immediately upon application launch.

---

## 2. Environment Variables Reference

### `ENV`

- **Type:** String
- **Required:** No
- **Default:** `development`
- **Options:** `development`, `testing`, `production`

Controls external HTTP behaviour for Beacon CRM via `app/libs/http_strategy_selector.py`:
- `development` / `testing`: Routes API requests through `mock_http_get` and `mock_http_patch`. No actual HTTP requests are made to Beacon CRM; requests return local fixture data.
- Any other value (e.g. `production`): Dispatches real HTTP requests to Beacon CRM.

### `SCHEDULE_CRON`

- **Type:** String (5-field cron expression: `minute hour day-of-month month day-of-week`)
- **Required:** No
- **Default:** `*/1 * * * *` (every minute, for local testing)

Defines the cron interval when running via `start_scheduler()` in `app/runner.py`.

Examples:

| Expression | Schedule |
| --- | --- |
| `*/1 * * * *` | Every minute (development/testing only) |
| `*/15 * * * *` | Every 15 minutes |
| `0 3 * * *` | Daily at 03:00 UTC |
| `0 2 * * 1` | Weekly on Mondays at 02:00 UTC |

### `API_BEARER_TOKEN`

- **Type:** String
- **Required:** Yes

Bearer authentication token for accessing the Beacon CRM developer API. Interpolated into the `Authorization: Bearer <token>` header in `app/libs/beacon_strategy.py`.

### `API_URL`

- **Type:** String
- **Required:** Yes

The Beacon CRM REST API endpoint URL used to query applicant entity records (e.g. `https://api.beaconcrm.org/v1/account/<ACCOUNT_ID>/entity/c_application`).

### `PROJECT_ID`

- **Type:** String
- **Required:** Yes

The Google Cloud Project ID used to initialize Google Cloud Vertex AI (`aiplatform.init()`).

### `GCS_BUCKET_NAME`

- **Type:** String
- **Required:** Yes

The Google Cloud Storage bucket used as a transient staging area for documents during Vertex AI multimodal analysis.

> **Important:** The bucket should be located in `europe-west2` (London) to match the Vertex AI analysis region and keep applicant data within the UK jurisdiction.

### `GOOGLE_APPLICATION_CREDENTIALS_JSON`

- **Type:** String (File path or raw JSON string)
- **Required:** Yes
- **Default:** `.vertexai.json`

Credentials for Google Cloud Storage and Vertex AI service account authentication. Supports two formats:
1. **Relative File Path:** Path relative to the project root (e.g. `.vertexai.json`).
2. **Inline JSON String:** The raw service account credentials JSON string (useful in containerized/cloud environments like Cloud Run or Kubernetes where injecting files is undesirable).

The authentication loader in `app/libs/ai_strategy.py` attempts `json.loads()` first; if decoding fails, it falls back to loading the file from disk.

---

## 3. Mock Mode & Isolation

In `development` and `testing` modes:
- Beacon CRM calls return local mock fixture data (`app/libs/data/beacon-data.json`), ensuring no data in Beacon CRM is inadvertently read or modified.
- Document retrieval supports `file://` URIs (e.g., `file://app/libs/data/Student_Finance_Letter_3.pdf`) for offline testing.
- Google Cloud Storage and Vertex AI calls connect to the configured Google Cloud project (or use unit test mocks).

---

## 4. Pre-Flight Checklist for Production

Before running against live Beacon CRM data:

- [ ] `ENV` set to `production` (disabling mock responses).
- [ ] `API_BEARER_TOKEN` verified and active with appropriate Beacon permissions.
- [ ] `API_URL` points to the correct production Beacon account and entity endpoint.
- [ ] `PROJECT_ID` configured to the production GCP project.
- [ ] `GCS_BUCKET_NAME` created in `europe-west2` with appropriate bucket lifecycle rules (auto-deletion after 1 day to catch orphaned staging objects).
- [ ] Service account credentials provided with `Vertex AI User` and `Storage Object Admin` roles.
- [ ] `SCHEDULE_CRON` set to an appropriate batch schedule.

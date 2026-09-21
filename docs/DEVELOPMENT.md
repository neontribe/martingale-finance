# Development Guide

This guide covers developer onboarding, local environment setup, testing strategies, prompt engineering, and codebase conventions for `martingale-finance`.

---

## 1. Local Environment Setup

### 1.1 Python Environment

Create an isolated virtual environment using Python 3.9+ (Python 3.10–3.12 recommended):

```bash
git clone <repository-url>
cd martingale-finance

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 1.2 Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

For offline local development without connecting to live Beacon CRM instances, leave `ENV=development`.

---

## 2. Codebase Organisation

The repository follows a clean, modular structure:

| Path | Purpose |
| --- | --- |
| `main.py` | Top-level execution entrypoint. |
| `app/config.py` | Environment variable parsing, validation, and type casting. |
| `app/runner.py` | Task execution controllers (`do_task_now`, `start_scheduler`). |
| `app/tasks/task.py` | Pipeline coordinator: application loop, document digestion, ranking, and CSV export. |
| `app/libs/ai_strategy.py` | Vertex AI client initialisation, Gemini multimodal prompting, and GCS staging. |
| `app/libs/beacon_strategy.py` | Beacon API payload transformation (JMESPath) and business candidate validation. |
| `app/libs/document_strategy_selector.py` | Universal document retrieval (handling `file://` local files and `http://`/`https://` URLs). |
| `app/libs/http_strategy_selector.py` | Environment-aware HTTP dispatch (routing to local JSON fixtures in `development`/`testing`). |
| `app/libs/data/` | Prompt text templates, mock Beacon fixtures, and reference PDFs. |
| `app/libs/schemas/` | JSON Schema definitions for external payload verification. |
| `tests/` | Automated test suite covering parsing, HTTP abstraction, document loading, and AI mocks. |

---

## 3. Working with AI Prompts

The pipeline uses two independent prompts located in `app/libs/data/`:

### 3.1 Categorisation Prompt (`categorising_prompt.txt`)
- **Purpose:** Verifies that an attachment is an authentic UK student finance notification letter.
- **Criteria for Qualifying Documents:**
  - Issued by recognised UK funding bodies: Student Finance England (SFE), SUSI (Ireland), SAAS (Scotland), Student Finance Wales (SFW), Student Finance NI (SFNI).
  - Business correspondence format outlining financial support, tuition fee loans, or maintenance funding.
- **Output:** Returns JSON with `document_valid` (boolean), `issue_date` (`YYYY-MM-DD` or `null`), and `authority` (string or `null`).

### 3.2 Extraction Prompt (`extraction_prompt.txt`)
- **Purpose:** Extracts numeric breakdown of awarded financial figures.
- **Values Extracted:**
  - `institutional_money`: Money paid directly to the university/institution.
  - `maintenance_loan`: Maintenance loan amount for the full academic year.
  - `maintenance_grant`: Maintenance grant amount for the full academic year.
- **Output:** Returns clean JSON formatted as floats to 2 decimal places (or `null` if not present).

> **Prompt Hygiene:**
> - Prompts enforce strict instructions never to guess or approximate values.
> - When modifying prompt files, verify that Gemini returns raw JSON adhering to the expected keys.
> - Prompt files are cached via `@lru_cache(maxsize=8)` in `app/tasks/task.py`.

---

## 4. Testing & Verification

The project uses `pytest` with `pytest-mock`. Test configuration is maintained in `pytest.ini`.

### 4.1 Running Tests

Run the full test suite from the project root:

```bash
pytest
```

Run a specific test module:

```bash
pytest tests/test_beacon_strategy.py
```

### 4.2 Test Suite Architecture

- **`tests/test_ai_strategy.py`:** Mocks `google.cloud.storage.Client` and `vertexai.generative_models.GenerativeModel` to verify GCS upload/deletion and prompt execution without making live cloud API calls.
- **`tests/test_beacon_strategy.py`:** Validates JMESPath search query projections against sample Beacon application records.
- **`tests/test_document_strategy.py`:** Tests local file reading (`file://`) and spins up a local ephemeral HTTP server to verify remote document retrieval over HTTP.
- **`tests/test_http_strategy.py`:** Verifies that `ENV=development`/`ENV=testing` correctly binds to fixture-backed mock HTTP handlers.

---

## 5. Development Notes & Branch Considerations

When developing on this branch (`feature/update-instructions`), keep the following details in mind:

1. **Python Search Path (`PYTHONPATH`):**
   Some modules in `app/tasks` and `app/libs` import from `app.libs` while others import from `libs`. To ensure imports resolve consistently when executing scripts or tests directly:
   ```bash
   export PYTHONPATH=.
   ```
   *(Standardizing all internal imports to absolute `app.libs...` package paths is recommended for future refactoring).*

2. **Fixture Path Naming:**
   The repository stores mock test data in `app/libs/data/beacon-data.json` and `tests/data/response1.json`. Ensure any new test fixtures or mock loaders align with these locations.

3. **CSV Output vs Direct CRM Write-Back (Safety Rationale):**
   The current pipeline intentionally exports reconciled results to `output.csv` via `write_csv()`. Direct CRM write-back was deferred to protect data integrity and ensure human-in-the-loop validation of scholarship awards. Full technical steps, schema mapping, and safety requirements to implement automated patching are documented in [`docs/BEACON_INTEGRATION.md`](BEACON_INTEGRATION.md).

4. **Applicant Privacy & Data Handling:**
   - Financial documents contain personal data. Never commit real applicant documents or un-anonymized Beacon responses to git.
   - All staged files in GCS are automatically deleted in the `finally` block of `get_document_digest()`.

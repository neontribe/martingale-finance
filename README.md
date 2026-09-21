# martingale-finance

A tool for extracting pertinent finance information from documents held by Martingale.

The service reads scholarship application records from Beacon CRM, retrieves the student
finance documents attached to each application, analyzes them using Google Gemini (via Vertex AI)
in a two-stage verification and extraction pipeline, validates the extracted figures against
applicant estimates, and generates a structured CSV output for the Martingale team.

---

## What it does

Applicants to Martingale scholarships upload official funding letters (such as Student
Finance England, SUSI, or SAAS notifications) to support means-tested grant applications.
Verifying these documents manually requires checking that each file is an authentic, official
entitlement letter, extracting maintenance grant and maintenance loan figures, and checking
for discrepancies against self-reported estimates.

This service automates that evaluation pipeline:

1. **Ingestion:** Fetches candidate application records from Beacon CRM (or mock fixtures in local development).
2. **Document Retrieval:** Downloads attached financial evidence letters (or reads local test fixtures).
3. **Staging:** Temporarily uploads documents to a Google Cloud Storage bucket in `europe-west2`.
4. **Two-Stage Gemini AI Analysis:**
   - **Stage 1 (Categorisation):** Confirms whether the document is an authentic funding letter from a recognised authority (e.g. Student Finance England, SUSI, SAAS, Student Finance Wales, Student Finance NI), extracting the issuing authority and issue date.
   - **Stage 2 (Extraction):** If valid, extracts the financial breakdown: maintenance grant, maintenance loan, and institutional funding.
5. **Multi-Document Selection:** When multiple documents or attachments exist for an application, selects the highest-fidelity evidence (prioritising valid documents with explicit grant figures).
6. **Validation & Reconciliation:** Compares extracted figures against applicant estimates. Flags discrepancies, missing authorities, or missing financial values.
7. **CSV Export:** Compiles all processed records into a clean, human-readable CSV report (`output.csv`).
8. **Cleanup:** Reliably deletes staged files from Cloud Storage in a `finally` block.

---

## Quickstart

### 1. Prerequisites

- Python 3.9+ (Python 3.10–3.12 recommended)
- A Google Cloud Project with Vertex AI and Google Cloud Storage enabled
- A service account with permissions for Vertex AI Generative Models and GCS Object Admin
- A Beacon CRM API account and bearer token (for live runs)

### 2. Setup

Clone the repository, create a virtual environment, and install dependencies:

```bash
git clone <repository-url>
cd martingale-finance

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and supply your credentials:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `ENV` | `development` / `testing` (uses mock Beacon HTTP calls) or `production` (real calls) | `development` |
| `SCHEDULE_CRON` | Five-field cron expression for scheduled execution | `*/1 * * * *` |
| `API_BEARER_TOKEN` | Bearer token for Beacon CRM developer API | *Required* |
| `API_URL` | Beacon CRM application endpoint | *Required* |
| `PROJECT_ID` | Google Cloud project ID for Vertex AI | *Required* |
| `GCS_BUCKET_NAME` | Cloud Storage bucket in `europe-west2` for transient file staging | *Required* |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | Service account JSON string or path to `.vertexai.json` | `.vertexai.json` |

See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for full configuration details.

### 4. Run

To execute a single batch run:

```bash
python main.py
```

By default, `main.py` invokes `do_task_now()`, processing available records and writing results to `output.csv`.

To run on a continuous schedule using the configured cron expression, switch `main.py` to `start_scheduler()`.

---

## Repository Structure

```
martingale-finance/
├── .env.example                # Example environment variables template
├── Dockerfile                  # Container build definition
├── Procfile                    # PaaS / Heroku worker process definition
├── README.md                   # Project overview and quickstart
├── pytest.ini                  # Pytest runner configuration
├── requirements.txt            # Python package dependencies
├── main.py                     # Application entrypoint
├── app/
│   ├── __init__.py
│   ├── config.py               # Environment parsing and validation
│   ├── runner.py               # One-shot task and APScheduler runner
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── task.py             # Pipeline orchestration, multi-document selection, CSV export
│   └── libs/
│       ├── __init__.py
│       ├── ai_strategy.py      # Vertex AI (Gemini 2.5 Flash) and GCS staging logic
│       ├── beacon_strategy.py  # Beacon API ingestion, JMESPath extraction, validation
│       ├── document_strategy_selector.py # Local (file://) and remote (http/https) document fetcher
│       ├── http_strategy_selector.py     # Environment-based HTTP routing (mock vs live)
│       ├── data/               # Prompt templates, schemas, and test data
│       │   ├── categorising_prompt.txt   # Stage 1 qualification prompt
│       │   ├── extraction_prompt.txt     # Stage 2 financial extraction prompt
│       │   ├── beacon-data.json          # Mock Beacon response fixture
│       │   └── Student_Finance_Letter_3.pdf # Sample student finance letter
│       └── schemas/
│           └── beacon-schema-short.json  # JSON schema for validating Beacon API responses
├── docs/                       # Comprehensive documentation
│   ├── ARCHITECTURE.md         # Detailed pipeline architecture and design patterns
│   ├── BEACON_INTEGRATION.md   # CRM safety rationale & automated patching roadmap
│   ├── CONFIGURATION.md        # Environment variables and credential management
│   ├── DEVELOPMENT.md          # Developer guide, prompt tuning, testing, and troubleshooting
│   └── DEPLOYMENT.md           # Production deployment, containerization, and operations
└── tests/                      # Automated test suite
    ├── __init__.py
    ├── data/                   # Test fixtures (response1.json, testfile.txt)
    ├── test_ai_strategy.py     # Vertex AI and GCS upload/delete tests
    ├── test_beacon_strategy.py # JMESPath parsing and record transformation tests
    ├── test_document_strategy.py # Local and HTTP document fetching tests
    └── test_http_strategy.py   # Mock and live HTTP routing tests
```

---

## Documentation

Comprehensive documentation is available in the `docs/` folder:

- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md):** Deep dive into the pipeline architecture, two-stage AI prompting, candidate validation, document ranking, and data schemas.
- **[`docs/BEACON_INTEGRATION.md`](docs/BEACON_INTEGRATION.md):** Human safety rationale for aborting direct CRM write-back, risk analysis, and full technical roadmap for automated Beacon patching.
- **[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md):** Detailed guide to every configuration variable, mock modes, credential formats, and security practices.
- **[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md):** Developer setup, test workflows, prompt engineering, code conventions, and known branch considerations.
- **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md):** Deployment patterns (Cloud Run Jobs, Docker containers, background workers), data privacy, and operational monitoring.

---

## Current Status & Known Considerations

The codebase on this branch implements the complete two-stage AI extraction, candidate validation, and CSV export pipeline. Developers working on this branch should keep the following points in mind:

- **Package Import Consistency:** Several modules contain a mix of `from app.libs...` and `from libs...` imports. Ensure `PYTHONPATH=.` or project root is on the module search path when running scripts directly.
- **Test Fixture Paths:** Certain unit tests and mock loaders reference fixture directories (`data/` vs `digest/`). See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for details on aligning test fixture paths.
- **Output Destination & Safety Rationale:** The pipeline currently outputs reconciled results to `output.csv`. Direct Beacon CRM patching was intentionally deferred for safety to allow human-in-the-loop auditability before committing financial awards to the CRM. See [`docs/BEACON_INTEGRATION.md`](docs/BEACON_INTEGRATION.md) for the complete roadmap to enable automated CRM updates.
- **Model and Region Defaults:** Google Vertex AI uses `gemini-2.5-flash` in `europe-west2` (London) to keep document processing in the UK jurisdiction.

---

## License

Internal proprietary software. All rights reserved.

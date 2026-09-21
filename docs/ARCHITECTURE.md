# Architecture

This document details the software architecture, data processing pipeline, and design decisions of `martingale-finance`. It serves as a technical reference for developers maintaining or extending the system.

---

## 1. Executive Summary

`martingale-finance` automates the extraction and validation of means-tested student finance awards from applicant-submitted documents for the Martingale scholarship programme.

Applicants upload official entitlement letters (e.g., from Student Finance England, SAAS, SUSI, Student Finance Wales, or Student Finance NI) to Beacon CRM. This service ingests application records, retrieves the uploaded documents, runs a two-stage analysis using Google Gemini (via Vertex AI), validates the extracted figures against applicant estimates, and generates a structured CSV output (`output.csv`) for the Martingale assessment team.

---

## 2. End-to-End Pipeline

The processing pipeline runs either as a one-shot batch process (`do_task_now()`) or on an automated schedule (`start_scheduler()`).

```
+---------------------------------------------------------------------------------+
|                                 Beacon CRM                                      |
|            (GET Applications with Attachments & Estimates)                     |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                           1. Ingestion & Parsing                                |
|   - get_beacon_data() queries Beacon API (or mock fixture)                      |
|   - Validates JSON against beacon-schema-short.json                             |
|   - parse_beacon_data() extracts records via JMESPath                           |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                     2. Document Retrieval & Staging                             |
|   - Merges student finance letters and general attachments                      |
|   - document_get() fetches content via HTTP(S) or local file:// URI             |
|   - upload_gcs_file_part() stages file in GCS bucket (europe-west2)             |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                    3. Two-Stage Gemini AI Analysis                              |
|   - Stage 1 (Categorisation):                                                   |
|       * Prompts Gemini 2.5 Flash with categorising_prompt.txt                   |
|       * Checks if document is an authentic funding letter                       |
|       * Extracts document_valid, issue_date, authority                          |
|   - Stage 2 (Extraction):                                                       |
|       * If document_valid is True, prompts Gemini with extraction_prompt.txt    |
|       * Extracts maintenance_grant, maintenance_loan, institutional_money       |
|   - delete_gcs_file() ensures staging file is deleted in a finally block        |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                    4. Ranking & Candidate Selection                             |
|   - find_best() evaluates all document digests per applicant                    |
|   - Ranks by: (1) validity, (2) grant presence, (3) loan presence               |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                   5. Validation & Business Rule Checks                          |
|   - make_beacon_data() maps values:                                             |
|       * Maintenance grant -> Value with "Accurate" status                       |
|       * Maintenance loan  -> Value with "Estimate" status                       |
|   - validate_candidate() checks:                                                |
|       * Valid document present?                                                 |
|       * Authority recognised?                                                   |
|       * Financial value extracted?                                              |
|       * Applicant estimate <= extracted award?                                  |
|   - Sets error ("Y"/"N") and error_reason                                       |
+---------------------------------------------------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                       6. CSV Export / Reporting                                 |
|   - write_csv() formats records and outputs to output.csv                       |
+---------------------------------------------------------------------------------+
```

---

## 3. Core Architectural Components

### 3.1 Orchestration (`app/runner.py` and `app/tasks/task.py`)

- **`app/runner.py`:** Provides `do_task_now()` for immediate batch execution and `start_scheduler()` using APScheduler's `BackgroundScheduler` configured with `SCHEDULE_CRON`.
- **`app/tasks/task.py`:** Manages the pipeline lifecycle:
  - Invokes `get_beacon_data()`.
  - Parses application records via `parse_beacon_data()`.
  - Coordinates multi-document analysis for each applicant (`process()`).
  - Calls `find_best()` to pick the most reliable evidence.
  - Generates the final output via `write_csv()`.

### 3.2 Two-Stage AI Strategy (`app/libs/ai_strategy.py`)

Rather than attempting classification and data extraction in a single prompt, the system decouples the task into two sequential operations. This separation improves model reliability, prevents hallucination on irrelevant attachments, and avoids wasted extraction calls.

#### Stage 1: Document Categorisation
- **Prompt:** `app/libs/data/categorising_prompt.txt`
- **Objective:** Verify whether the document is an official student funding letter issued by a recognised government body (e.g. Student Finance England, SUSI, SAAS, Student Finance Wales, Student Finance NI).
- **Output Schema:**
```json
{
  "document_valid": true,
  "issue_date": "YYYY-MM-DD",
  "authority": "AUTHORITY_NAME"
}
```
If the document is invalid (e.g. bank statement, student self-assessment, CV, or general correspondence), the model returns `document_valid: false`, and Stage 2 is skipped.

#### Stage 2: Financial Extraction
- **Prompt:** `app/libs/data/extraction_prompt.txt`
- **Objective:** Extract the specific financial awards for the academic year.
- **Output Schema:**
```json
{
  "institutional_money": 0.00,
  "maintenance_loan": 0.00,
  "maintenance_grant": 0.00
}
```

The model (`gemini-2.5-flash`) is executed via Google Cloud Vertex AI in `europe-west2` (London). Prompt files are cached in memory using `@lru_cache(maxsize=8)` to eliminate redundant filesystem I/O.

### 3.3 Multi-Document Ranking (`find_best`)

Applicants frequently upload multiple attachments (e.g. cover letters, multi-page scans, or revised entitlement letters). The service runs all candidate attachments through the digest pipeline and ranks them using a tuple sort key:

```python
def find_best(digests):
    return sorted(
        digests,
        key=lambda x: (
            not x["document_valid"],
            x["maintenance_grant"] in (None, ""),
            x["maintenance_loan"] in (None, ""),
        )
    )[0]
```

This ranking prioritises:
1. Valid student finance documents over invalid ones.
2. Documents containing an explicit **Maintenance Grant** (the strongest indicator of low household income).
3. Documents containing a **Maintenance Loan**.

### 3.4 Candidate Validation & Business Logic (`app/libs/beacon_strategy.py`)

The `make_beacon_data()` and `validate_candidate()` functions convert raw extraction digests into business-ready records and apply strict validation rules:

1. **Value Mapping:**
   - If a `maintenance_grant` is found, `identified_value` is set to the grant amount and marked as `"Accurate"`.
   - If only a `maintenance_loan` is found, `identified_value` is set to the loan amount and marked as `"Estimate"`.
   - If neither is found, `identified_value` is `None`.

2. **Validation Rules (`validate_candidate`):**
   - **Invalid Document:** If `document_valid` is False $\rightarrow$ Error: `"No valid documents"`
   - **Missing Authority:** If `authority` is missing $\rightarrow$ Error: `"Could not extract authority type"`
   - **Missing Value:** If `value` is None $\rightarrow$ Error: `"Could not extract grant/loan data"`
   - **Over-Reported Estimate:** If `applicant_estimate > identified_value` $\rightarrow$ Error: `"Student reported value {estimate} is more than grant/loan {value}"`

Records failing any check have their `error` flag set to `"Y"` and `error_reason` populated with the specific failure description.

### 3.5 Output Format (`write_csv`)

The reconciled results are written to `output.csv` with the following column structure:

| CSV Header | Dict Key | Description |
| --- | --- | --- |
| `Record ID (person)` | `applicant_id` | Beacon CRM person record ID |
| `Record ID (Application)` | `application_id` | Beacon CRM application record ID |
| `Type of Financial Evidence` | `authority` | Issuing body (e.g., Student Finance England) |
| `Identified Value` | `identified_value` | Extracted grant/loan numeric value |
| `Estimate / Accurate?` | `estimate_or_accurate` | `"Accurate"` (grant) or `"Estimate"` (loan) |
| `Error Report (Y/N)` | `error` | `"Y"` if validation failed, `"N"` otherwise |
| `Notes` | `error_reason` | Diagnostic error message or blank |

---

## 4. Key Design Patterns & Principles

### 4.1 Strategy Selector Pattern
The codebase abstracts external dependencies behind strategy selectors:
- **`document_strategy_selector.py`:** Inspects URI schemes (`file://` vs `http://` / `https://`) to route requests seamlessly between local files and remote endpoints.
- **`http_strategy_selector.py`:** Binds `get_http` and `patch_http` to mock or real implementations based on `ENV`. In `development` and `testing`, calls return local JSON fixtures without accessing external networks.

### 4.2 Transient Cloud Staging
Document files are uploaded to Google Cloud Storage solely to allow Vertex AI multimodal ingestion via `Part.from_uri()`. Every upload is paired with an immediate deletion in a `finally` block:

```python
try:
    gcs_part = upload_gcs_file_part(att_id, document_content, att_type)
    ...
finally:
    delete_gcs_file(att_id)
```

No applicant documents remain stored in the GCS bucket post-analysis.

### 4.3 Deterministic Cautiousness
Because means-tested scholarship allocation depends on accurate financial numbers, the Gemini prompts explicitly forbid guessing or hallucinating values. Ambiguous or incomplete records are flagged with clear error reasons for human review rather than silently approximated.

### 4.4 Safety-First Output Routing (CSV vs Direct CRM Write-Back)
The service writes output to `output.csv` rather than writing directly to Beacon CRM. This design decision was made specifically for safety:
- **Risk Mitigation:** Means testing directly determines scholarship funding. Unchecked automated overwrites could corrupt applicant records or misallocate awards.
- **Human-in-the-Loop Verification:** Exporting to CSV provides an audit boundary where reviewers inspect validation errors (`error: "Y"` / `error_reason`), verify low-confidence extractions, and reconcile applicant estimates prior to modifying the system of record.
- **Future Integration:** For the technical blueprint to enable automated CRM patching with safe execution gates (dry-run mode, schema transformation, per-record endpoints), see [`docs/BEACON_INTEGRATION.md`](BEACON_INTEGRATION.md).

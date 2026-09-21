# Beacon CRM Integration & Automated Patching Roadmap

This document provides a comprehensive analysis of the decision to defer direct CRM write-back in favor of CSV export, outlines the human safety rationale behind that decision, and provides a step-by-step technical blueprint for enabling automated Beacon CRM patching safely.

---

## 1. Context & Background

The `martingale-finance` service is designed to assess means-tested financial evidence submitted by applicants to the Martingale scholarship programme. 

During initial development, the pipeline was intended to directly update Beacon CRM records (`c_application` entities) via `PATCH` requests once Google Gemini extracted and validated student finance details. However, direct CRM patching was deliberately aborted, and the pipeline was re-routed to generate a structured audit file (`output.csv`) instead.

---

## 2. Safety Rationale: Why Direct Patching Was Aborted

The human justification for stopping direct CRM updates and piping results to CSV is rooted in **data safety, risk mitigation, and the necessity for human oversight in high-stakes financial award workflows**:

### 2.1 High Stakes of Scholarship Allocation
Martingale scholarships provide substantial financial support based on means testing. An automated error that under-reports or mischaracterises an applicant's entitlement could unjustly disqualify an eligible student or misallocate limited scholarship funds.

### 2.2 LLM Extraction Risk & Non-Determinism
Although Google Gemini 2.5 Flash demonstrates strong extraction capabilities, multimodal LLMs are subject to edge-case anomalies:
- Document quality issues (low-resolution scans, multi-page variations, non-standard layout templates across devolved UK administrations).
- Ambiguous or revised entitlement letters (e.g., provisional calculations vs final schedules, reassessments).
- Edge-case misinterpretations between tuition fee loans, maintenance loans, grants, and institutional bursaries.

### 2.3 Irreversibility and Lack of Direct Rollback
Beacon CRM does not provide an automated "undo" or point-in-time snapshot rollback for batched API updates. Overwriting existing application fields directly via automated scripts risks corrupting or overwriting historic CRM records without a straightforward recovery mechanism.

### 2.4 Human-in-the-Loop Auditability
Exporting results to `output.csv` establishes a transparent, reviewable intermediate boundary:
- Assessors can inspect extracted figures (`Identified Value`) against applicant self-reported figures (`applicant_estimate`).
- Reviewers can evaluate validation failures (`error: "Y"`) and read explicit diagnostic notes (`error_reason`) across the applicant cohort.
- Assessors can verify borderline cases and confirm evidence authenticity before committing changes to the primary CRM system of record.

---

## 3. Current State vs Target CRM Schema

### 3.1 Current Pipeline Output
Currently, `app/tasks/task.py` and `app/libs/beacon_strategy.py` construct an internal dictionary tailored for CSV export:

```python
{
    "application_id": 96593,
    "applicant_id": 12345,
    "applicant_name": "Jane Doe",
    "authority": "Student Finance England",
    "identified_value": 4500.00,
    "estimate_or_accurate": "Accurate",
    "error": "N",
    "error_reason": None
}
```

### 3.2 Required Beacon CRM Entity Schema
To update Beacon CRM via `PATCH /v1/account/<ACCOUNT_ID>/entity/c_application/<APPLICATION_ID>`, the payload must match Beacon's custom entity schema (defined in `app/libs/schemas/beacon-schema-short.json`):

| CRM Field Name | Type | Expected Format / Values | Description |
| --- | --- | --- | --- |
| `c_what_type_of_financial_evidence_is_this` | `string` / `null` | String (e.g. `"Student Finance England"`) | Extracted issuing authority |
| `c_identified_value` | `object` / `null` | `{"currency": "GBP", "value": 4500.0, "base_value": 4500.0}` | Extracted financial award |
| `c_is_this_value_an_estimate_or_accurate` | `array[string]` | `["Accurate"]` or `["Estimate"]` | Classification level |
| `c_error_report_martingale_team_to_review` | `string` / `null` | String explanation or `null` | Validation error message |

---

## 4. Technical Blueprint: Work Required to Automatically Update Beacon

To transition `martingale-finance` from CSV export to safe, reliable, and automated Beacon CRM updates, the following technical tasks must be completed:

```
+-------------------------------------------------------------------------------+
|                       AUTOMATED PATCHING IMPLEMENTATION                       |
+-------------------------------------------------------------------------------+
|  1. Payload Transformation     -->  Map internal dict to Beacon CRM schema   |
|  2. URL Target Resolution      -->  Target specific record: API_URL/{id}      |
|  3. Safe Execution Gates       -->  Error guards, dry-run mode, rate limits   |
|  4. Pipeline Integration       -->  Call patch_beacon_data() in task loop     |
|  5. Audit & Error Tracking     -->  Log API status codes, track audit history |
|  6. Verification & Sandbox     -->  End-to-end sandbox validation before prod|
+-------------------------------------------------------------------------------+
```

---

### Step 1: Implement Schema-Compliant Payload Transformation

Create a dedicated payload transformer in `app/libs/beacon_strategy.py` that formats extracted figures into Beacon CRM's structure:

```python
def make_beacon_patch_payload(item_data: dict) -> dict:
    """
    Transforms internal processed data into Beacon CRM c_application entity schema.
    """
    value = item_data.get("identified_value")
    identified_value_payload = None
    if value is not None:
        identified_value_payload = {
            "currency": "GBP",
            "value": float(value),
            "base_value": float(value)
        }

    estimate_status = item_data.get("estimate_or_accurate")
    estimate_array = [estimate_status] if estimate_status else []

    error_reason = item_data.get("error_reason")

    return {
        "c_what_type_of_financial_evidence_is_this": item_data.get("authority"),
        "c_identified_value": identified_value_payload,
        "c_is_this_value_an_estimate_or_accurate": estimate_array,
        "c_error_report_martingale_team_to_review": error_reason if item_data.get("error") == "Y" else None,
    }
```

---

### Step 2: Per-Record Resource URL Construction

Beacon CRM REST conventions require `PATCH` requests to target the specific entity record URL:

- **Collection URL (Current `config.API_URL`):** `https://api.beaconcrm.org/v1/account/<ACCOUNT_ID>/entity/c_application`
- **Specific Record URL:** `f"{config.API_URL}/{application_id}"`

Update `patch_beacon_data` in `app/libs/beacon_strategy.py`:

```python
def patch_beacon_record(application_id: Union[int, str], payload: dict) -> bool:
    """
    Sends a PATCH request to update a single Beacon application record.
    """
    target_url = f"{config.API_URL}/{application_id}"
    try:
        response = patch_http(target_url, HEADERS, payload)
        response.raise_for_status()
        config.LOGGER.info(f"Successfully patched application {application_id}")
        return True
    except Exception as e:
        config.LOGGER.error(f"Failed to patch application {application_id}: {e}")
        return False
```

---

### Step 3: Implement Safety Gates & Operational Controls

To prevent unintended overwrites and protect production data integrity, implement the following safety mechanisms:

1. **Dry-Run Mode (`DRY_RUN=true`):**
   - Add a `DRY_RUN` boolean environment variable in `app/config.py`.
   - When enabled, the application builds and logs the exact `PATCH` payloads and target URIs without dispatching the HTTP requests.

2. **Conditional Patching (Error Shielding):**
   - When `error == "Y"`, decide whether to:
     - *Option A (Recommended):* Update only `c_error_report_martingale_team_to_review` while leaving financial fields intact for human assessment.
     - *Option B:* Skip updating the record entirely and log a review alert.

3. **Rate Limiting & Throttling:**
   - Beacon CRM API enforces rate limits. Introduce a small back-off delay (e.g. `time.sleep(0.2)`) or a token bucket rate limiter between sequential `PATCH` calls.

4. **Batch Summary & Audit Log:**
   - Maintain a runtime ledger recording `{application_id, status_code, timestamp, payload}` and write an execution audit log.

---

### Step 4: Integrate CRM Patching into the Task Pipeline

Update `process()` and `scheduled_task()` in `app/tasks/task.py`:

```python
def process(items):
    output = []
    for item in items:
        # 1. Document analysis & selection
        digests = []
        # ... process attachments ...
        best_doc = find_best(digests)
        processed_data = make_beacon_data(best_doc, item)
        output.append(processed_data)

        # 2. Automated CRM Patching (if enabled)
        if config.ENABLE_CRM_PATCHING:
            if config.DRY_RUN:
                config.LOGGER.info(f"[DRY RUN] Would patch {item['application_id']} with: {processed_data}")
            else:
                patch_payload = make_beacon_patch_payload(processed_data)
                patch_beacon_record(item['application_id'], patch_payload)

    # 3. Retain CSV export for auditing
    write_csv(output, "output.csv")
    return output
```

---

### Step 5: Configuration & Environment Setup

Add configuration flags in `app/config.py` and `.env.example`:

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `ENABLE_CRM_PATCHING` | `bool` | `False` | Global toggle to enable automated Beacon CRM patching |
| `DRY_RUN` | `bool` | `True` | Logs planned updates without sending network requests |
| `CRM_RATE_LIMIT_DELAY` | `float` | `0.2` | Delay in seconds between successive API calls |

---

### Step 6: Testing & Validation Strategy

Before enabling CRM patching in production, execute the following test plan:

1. **Unit Tests:**
   - Test `make_beacon_patch_payload()` against all permutations (valid grant, valid loan, missing authority, estimate mismatch, null values).
   - Test payload conformity against `app/libs/schemas/beacon-schema-short.json`.

2. **Mock HTTP Tests:**
   - Test `patch_beacon_record()` with simulated 200 OK, 400 Bad Request, 401 Unauthorized, 404 Not Found, 429 Too Many Requests, and 500 Internal Server Error responses.

3. **Staging / Sandbox Verification:**
   - Connect to a non-production Beacon CRM test account.
   - Run a batch of sample applications and verify in the Beacon UI that custom fields populate accurately.

4. **Production Phased Rollout:**
   - Step 1: Run with `ENABLE_CRM_PATCHING=False` to verify CSV report output.
   - Step 2: Run with `ENABLE_CRM_PATCHING=True` and `DRY_RUN=True` to audit generated payloads in log streams.
   - Step 3: Enable live patching for a restricted batch of test application records.
   - Step 4: Enable full automated synchronization.

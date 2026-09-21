# Deployment Guide

This guide outlines deployment options, containerisation, operational considerations, and infrastructure requirements for running `martingale-finance`.

---

## 1. Execution Models

The application supports two primary operational modes:

### 1.1 Scheduled One-Shot Execution (`do_task_now()`)
- **How it runs:** Executes a single pass over Beacon CRM applications, processes documents, writes the reconciled `output.csv`, and exits immediately.
- **Recommended for:** Cloud Run Jobs, Kubernetes `CronJob`, AWS ECS Scheduled Tasks, or GitHub Actions.
- **Advantages:** Cost-efficient (zero idle compute costs), serverless scaling, and avoids process memory leaks or deadlocks.

```bash
# Executing one-shot in main.py
python main.py
```

### 1.2 Persistent Background Worker (`start_scheduler()`)
- **How it runs:** Long-running daemon powered by APScheduler's `BackgroundScheduler`. Wakes up periodically based on the `SCHEDULE_CRON` expression.
- **Recommended for:** Heroku worker dynos, persistent VMs, or dedicated Docker worker containers.

```bash
# In main.py:
from app.runner import start_scheduler

if __name__ == "__main__":
    start_scheduler()
```

---

## 2. Containerisation

The repository includes a `Dockerfile` for containerised environments:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### 2.1 Building and Running Locally

```bash
# Build the Docker image
docker build -t martingale-finance:latest .

# Run with environment variables from .env
docker run --rm --env-file .env martingale-finance:latest
```

### 2.2 Container Best Practices
- **Base Image:** While `python:3.9-slim` is defined, updating to `python:3.11-slim` or `python:3.12-slim` is recommended for performance and security maintenance.
- **Dockerignore:** Ensure `.dockerignore` excludes `.venv`, `.git`, `.env`, `.vertexai.json`, and temporary test artifacts from image builds.
- **Non-Root Execution:** For production security, configure a non-root user in the Dockerfile.

---

## 3. Cloud Deployment Patterns

### 3.1 Recommended Architecture: Google Cloud Run Job + Cloud Scheduler

Because `martingale-finance` integrates with Google Cloud Storage and Vertex AI in `europe-west2`, deploying as a **Google Cloud Run Job** triggered by **Google Cloud Scheduler** provides the best operational efficiency:

```
+--------------------------+
|  Google Cloud Scheduler  |  (Triggers on Cron Schedule e.g. Daily 03:00)
+--------------------------+
             |
             v
+--------------------------+
|   Google Cloud Run Job   |  (Executes python main.py -> do_task_now())
+--------------------------+
      |               |
      v               v
+------------+  +-------------------+
| Beacon CRM |  | Vertex AI / GCS   |
| (API Ingest|  | (Gemini Analysis, |
| & Records) |  | europe-west2)     |
+------------+  +-------------------+
```

#### Key Benefits:
- **Same Region (`europe-west2`):** Keeps document uploads, AI model queries, and compute within the London region for data sovereignty and lower latency.
- **Application Default Credentials (ADC):** In Cloud Run, attaching a Service Account directly eliminates the need to manage `.vertexai.json` key files.

---

## 4. PaaS / Worker Deployment (`Procfile`)

For Heroku-like platforms, the repository includes a `Procfile`:

```
worker: python main.py
```

When deployed to a PaaS:
1. Configure `main.py` to invoke `start_scheduler()`.
2. Configure all environment variables in the platform's configuration dashboard (supplying `GOOGLE_APPLICATION_CREDENTIALS_JSON` as an inline JSON string).
3. Scale the `worker` process to 1 instance.

---

## 5. Security & Data Protection

### 5.1 Secrets Management
- Never store `API_BEARER_TOKEN` or service account keys in version control.
- In production, inject secrets using Secret Manager (e.g. GCP Secret Manager, HashiCorp Vault, or AWS Secrets Manager).
- Pass `GOOGLE_APPLICATION_CREDENTIALS_JSON` as a raw JSON string to eliminate secret files on disk.

### 5.2 Storage Bucket Lifecycle
- The Cloud Storage bucket is used strictly for transient staging.
- Set a **GCS Bucket Lifecycle Rule** to delete objects older than 1–2 days. This provides automated cleanup in the event of an unhandled process termination or network failure before `delete_gcs_file()` executes.

---

## 6. Observability & Logging

- Logs are emitted to standard output at `INFO` level using Python's `logging` module.
- In cloud environments, standard output logs are ingested automatically by Cloud Logging / Datadog.
- Monitor for `"Bad digest from beacon"` or `"No Data from Beacon"` error entries, and alert on non-zero exit codes.

---

## 7. Pre-Deployment Verification Checklist

- [ ] Target environment variables configured (`ENV=production`, `API_BEARER_TOKEN`, `API_URL`, `PROJECT_ID`, `GCS_BUCKET_NAME`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`).
- [ ] GCS bucket created in `europe-west2` with auto-expiration lifecycle rules.
- [ ] Vertex AI API enabled in the Google Cloud Project.
- [ ] Service Account assigned `roles/aiplatform.user` and `roles/storage.objectAdmin`.
- [ ] Schedule configured to avoid overlapping runs.
- [ ] Output destination (`output.csv` or Cloud Storage sink) confirmed for the Martingale review team.

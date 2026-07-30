# Production GCP deployment and ingestion

This deployment uses one immutable container image for the API and Cloud Run
Jobs. Data artifacts are versioned in Cloud Storage; product state and
embeddings remain authoritative in Cloud SQL.

## Architecture

1. Secret Manager supplies database URLs and the Gemini API key.
2. `asanclip-api-migrate` applies Alembic migrations to Cloud SQL.
3. `asanclip-api-ingest` idempotently upserts a mounted CSV.
4. `asanclip-api-embed` claims and embeds only pending/changed products.
5. `asanclip-api-faiss` builds an immutable, verified FAISS release in GCS.
6. Cloud Build rolls Cloud Run to the new FAISS release path.
7. Cloud Logging and Cloud Monitoring observe the API and all job executions.

The automatic path uses `asanclip-api-pipeline`, which calls the three data
scripts in order while holding a PostgreSQL advisory lock. The individual
ingest/embed/FAISS jobs remain available for controlled manual maintenance.

The API service is private by default. Do not make it public until application
authentication is implemented.

## Prerequisites

- A billed GCP project and the `gcloud` CLI.
- A Cloud SQL for PostgreSQL 16 instance.
- A Cloud Build repository connection for this Git repository.
- A globally unique GCS bucket name.

Use the same region for Cloud Run, Cloud SQL, Artifact Registry, and GCS.

## 1. Create the GCP foundation

From PowerShell:

```powershell
.\deploy\gcp\bootstrap.ps1 `
  -ProjectId "YOUR_PROJECT_ID" `
  -Region "europe-west1" `
  -FaissBucket "YOUR_PROJECT_ID-asanclip-data"
```

The script enables APIs, creates Artifact Registry, enables bucket versioning,
creates separate API/pipeline service accounts, creates empty secrets, and
applies least-privilege IAM for GCS and secret access.

Grant the human or automation principal that submits builds
`roles/iam.serviceAccountUser` on the dedicated `asanclip-cloud-build` service
account. Do not run production builds as the default Compute Engine or legacy
Cloud Build service account.

Create Cloud SQL with automated backups, point-in-time recovery, deletion
protection, high availability, and storage auto-growth. Create an `asanclip`
database and a strong pipeline database user. For the initial deployment, both
database secrets may contain the pipeline URL; split the API user afterward.
The pipeline user must be allowed to create the supported `vector` and
`pg_trgm` extensions during the first migration. Verify Cloud SQL provides a
pgvector release with `halfvec`/HNSW support before deployment.

Cloud Run connects through `/cloudsql`:

```text
postgresql+psycopg2://USER:URL_ENCODED_PASSWORD@/asanclip?host=/cloudsql/PROJECT:REGION:INSTANCE
```

The supplied YAML uses the Cloud SQL integration (`--set-cloudsql-instances`).
If the instance is private-IP-only, add the same `--network` and `--subnet`
Direct VPC egress settings to the API and every job definition before deploy.
Public-IP Cloud SQL still uses the authenticated/encrypted Cloud SQL connector;
do not add broad authorized networks.

Add secret versions using temporary files or the Secret Manager console. Never
put secret values in YAML, Git, command arguments, or `.env` committed to Git.

Required secrets:

- `asanclip-database-url` — API database URL
- `asanclip-pipeline-database-url` — migration/ingestion database URL
- `asanclip-gemini-api-key` — Gemini API key

## 2. Deploy image, jobs, schema, and API

Replace the placeholder substitutions in `cloudbuild.deploy.yaml`, especially:

- `_REGION`
- `_CLOUD_SQL_INSTANCE` (`PROJECT:REGION:INSTANCE`)
- `_FAISS_BUCKET`
- `_CORS_ORIGINS` (semicolon-separated HTTPS origins)

Then submit:

```powershell
gcloud builds submit `
  --project "YOUR_PROJECT_ID" `
  --region "europe-west1" `
  --service-account "projects/YOUR_PROJECT_ID/serviceAccounts/asanclip-cloud-build@YOUR_PROJECT_ID.iam.gserviceaccount.com" `
  --config "deploy/gcp/cloudbuild.deploy.yaml" `
  .
```

This build is intentionally fail-fast: the API is not deployed if the image,
job configuration, or Alembic migration fails.

After the first migration, create a separate API database user and grant only:

```sql
GRANT CONNECT ON DATABASE asanclip TO asanclip_api;
GRANT USAGE ON SCHEMA public TO asanclip_api;
GRANT SELECT ON asanclipproducts, product_captions TO asanclip_api;
GRANT SELECT, INSERT ON retrieval_logs TO asanclip_api;
GRANT SELECT, INSERT, UPDATE ON firewall_daily_usage TO asanclip_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO asanclip_api;
```

Put that user's URL in `asanclip-database-url`. Keep schema ownership and
ingestion privileges only in `asanclip-pipeline-database-url`.

## 3. Upload and ingest data

CSV requirements:

- Required: `id`, `name`
- Optional: `short_description`, `description`, `product_type`, `occasion`,
  `platform`, `url`
- IDs must be unique within the file.
- Upload a complete current snapshot or a delta file; both are safe because the
  ingestion is an upsert. Products absent from a snapshot are not deleted;
  deletion/deactivation must be an explicit, separately reviewed operation.

```powershell
gcloud storage cp ".\products.csv" `
  "gs://YOUR_PROJECT_ID-asanclip-data/incoming/products-2026-07-30.csv"

gcloud builds submit `
  --no-source `
  --project "YOUR_PROJECT_ID" `
  --region "europe-west1" `
  --service-account "projects/YOUR_PROJECT_ID/serviceAccounts/asanclip-cloud-build@YOUR_PROJECT_ID.iam.gserviceaccount.com" `
  --config "deploy/gcp/cloudbuild.ingest.yaml" `
  --substitutions "_CSV_OBJECT=incoming/products-2026-07-30.csv,_REGION=europe-west1,_SERVICE_NAME=asanclip-api"
```

The pipeline stops if any stage fails. The old Cloud Run revision and old FAISS
release remain active until every data stage succeeds.

The first production embedding run intentionally re-embeds legacy rows whose
`embedding_model` is empty. Estimate Gemini quota/cost for the full catalog
before that run. Later runs process only new rows, semantic changes, failures
within the retry limit, or rows created by an embedding-model change.

## 4. Automate new CSV uploads

Create a Pub/Sub topic and a GCS `OBJECT_FINALIZE` notification restricted to
the `incoming/` prefix. Then create a regional Cloud Build Pub/Sub trigger for
`deploy/gcp/cloudbuild.ingest.yaml` with these payload bindings:

```powershell
gcloud storage buckets notifications create `
  "gs://YOUR_PROJECT_ID-asanclip-data" `
  --topic "asanclip-ingest" `
  --event-types "OBJECT_FINALIZE" `
  --object-prefix "incoming/" `
  --payload-format "json"
```

```text
_EVENT_TYPE = $(body.message.attributes.eventType)
_BUCKET_ID  = $(body.message.attributes.bucketId)
_CSV_OBJECT = $(body.message.attributes.objectId)
```

Use this subscription filter:

```text
_EVENT_TYPE == "OBJECT_FINALIZE" &&
_BUCKET_ID == "YOUR_PROJECT_ID-asanclip-data" &&
_CSV_OBJECT.matches("incoming/[A-Za-z0-9_./-]+[.]csv")
```

Also set `_REGION` and `_SERVICE_NAME` as fixed trigger substitutions. Filtering
to `incoming/` is important: FAISS releases are written to the same bucket and
must not trigger another ingestion build.

Configure the trigger to execute as the dedicated
`asanclip-cloud-build@PROJECT_ID.iam.gserviceaccount.com` account created by
`bootstrap.ps1`.

For production, enable trigger approval until several manual pipeline runs have
completed successfully; then disable approval for fully automatic ingestion.

If another system writes products directly to Cloud SQL, the Alembic migration
installs a trigger that invalidates embeddings after semantic field changes.
Trigger `cloudbuild.refresh.yaml` after the external writer completes its batch
(or on a conservative schedule matching the source update window) to embed
those pending rows, rebuild FAISS, and activate a release without a CSV.

## 5. Test

Get the private service URL and an identity token:

```powershell
gcloud run services add-iam-policy-binding asanclip-api `
  --region europe-west1 `
  --member "user:YOUR_EMAIL" `
  --role "roles/run.invoker"

$Url = gcloud run services describe asanclip-api `
  --region europe-west1 `
  --format "value(status.url)"
$Token = gcloud auth print-identity-token

Invoke-RestMethod "$Url/api/v1/health" `
  -Headers @{ Authorization = "Bearer $Token" }
Invoke-RestMethod "$Url/api/v1/ready" `
  -Headers @{ Authorization = "Bearer $Token" }
```

Test search with a UTF-8 JSON body and verify that a `retrieval_logs` row is
created. Keep the service private and grant callers `roles/run.invoker`.

## 6. Monitor and operate

Create Cloud Monitoring alerts for:

- Cloud Run 5xx rate and p95 request latency.
- Cloud Run Job failed executions for migration, pipeline, and maintenance jobs.
- Cloud SQL CPU, connections, disk utilization, and replication/PITR health.
- No successful ingestion build within the expected update interval.

Logs are structured by Cloud Run resource and execution. Every ingestion run
uses the Cloud Build ID as `ingestion_run_id`. Every FAISS release contains:

- `faiss.index`
- `faiss.pkl`
- `faiss.manifest.json` with count, dimension, source timestamp, and checksums

To roll back only the index, point `FAISS_INDEX_PATH` at an older release:

```powershell
gcloud run services update asanclip-api `
  --region europe-west1 `
  --update-env-vars "FAISS_INDEX_PATH=/mnt/faiss/releases/PREVIOUS_BUILD_ID/faiss.index"
```

Use a GCS lifecycle policy to retain enough previous releases for rollback.
Schedule Cloud SQL backups and test restoration regularly.

## Important production rules

- Never run Alembic automatically in every API instance startup.
- Never overwrite the active FAISS files in place; publish versioned releases.
- Never retain an embedding after semantic product text changes.
- Never expose database URLs or exception details from health endpoints.
- Do not run multiple ingestion builds for the same dataset concurrently.
- Deploy immutable image tags (`$BUILD_ID`), not `latest`.

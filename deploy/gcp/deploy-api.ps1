# Deploy asanclip-api to Cloud Run (production).
param(
    [string]$Project = "asanclip-rag-prod",
    [string]$Region = "europe-west4",
    [string]$Service = "asanclip-api",
    [string]$Image = "europe-west4-docker.pkg.dev/asanclip-rag-prod/asanclip/asanclip-api:latest",
    [string]$CloudSqlInstance = "asanclip-rag-prod:europe-west1:asanclip-db-prod",
    [string]$VpcConnector = "asanclip-vpc-connector",
    [string]$ServiceAccount = "sa-cloudrun-asanclip@asanclip-rag-prod.iam.gserviceaccount.com",
    [string]$FaissBucket = "sale1404"
)

$ErrorActionPreference = "Stop"

Write-Host "Deploying $Service to $Region ..."

gcloud run deploy $Service `
  --project=$Project `
  --region=$Region `
  --image=$Image `
  --service-account=$ServiceAccount `
  --ingress=internal `
  --no-allow-unauthenticated `
  --set-cloudsql-instances=$CloudSqlInstance `
  --vpc-connector=$VpcConnector `
  --vpc-egress=private-ranges-only `
  --set-secrets="DATABASE_URL=database-url:latest,REDIS_URL=redis-url:latest,GEMINI_API_KEY=gemini-api-key:latest" `
  --set-env-vars="ENVIRONMENT=production,ENABLE_CACHE=true,ENABLE_PII_DETECTION=true,EMBEDDING_DIMENSION=3072,EMBEDDING_MODEL=gemini-embedding-001,LOG_TO_FILE=false,DB_POOL_SIZE=5,DB_MAX_OVERFLOW=2,FAISS_INDEX_PATH=/mnt/faiss/current/faiss.index" `
  --add-volume='name=faiss,type=cloud-storage,bucket=sale1404,readonly=true' `
  --add-volume-mount='volume=faiss,mount-path=/mnt/faiss' `
  --execution-environment=gen2 `
  --cpu=2 `
  --memory=2Gi `
  --concurrency=20 `
  --min-instances=1 `
  --max-instances=10 `
  --timeout=60 `
  --port=8080 `
  --startup-probe='httpGet.path=/health,initialDelaySeconds=0,timeoutSeconds=5,periodSeconds=5,failureThreshold=24' `
  --liveness-probe='httpGet.path=/health,initialDelaySeconds=10,timeoutSeconds=5,periodSeconds=30,failureThreshold=3'

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Deployment complete."

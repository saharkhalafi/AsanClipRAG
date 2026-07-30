param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$Region = "europe-west1",
    [string]$ArtifactRepository = "asanclip",

    [Parameter(Mandatory = $true)]
    [string]$FaissBucket,

    [string]$ApiServiceAccount = "asanclip-api",
    [string]$PipelineServiceAccount = "asanclip-pipeline",
    [string]$CloudBuildServiceAccount = "asanclip-cloud-build",
    [string]$IngestTopic = "asanclip-ingest"
)

$ErrorActionPreference = "Stop"

function Invoke-Gcloud {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud failed: gcloud $($Arguments -join ' ')"
    }
}

function Ensure-ServiceAccount {
    param([string]$Name, [string]$DisplayName)
    & gcloud iam service-accounts describe "$Name@$ProjectId.iam.gserviceaccount.com" `
        --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Gcloud iam service-accounts create $Name `
            --display-name $DisplayName `
            --project $ProjectId
    }
}

function Ensure-Secret {
    param([string]$Name)
    & gcloud secrets describe $Name --project $ProjectId *> $null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Gcloud secrets create $Name `
            --replication-policy automatic `
            --project $ProjectId
    }
}

Invoke-Gcloud config set project $ProjectId
Invoke-Gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    secretmanager.googleapis.com `
    sqladmin.googleapis.com `
    storage.googleapis.com `
    pubsub.googleapis.com `
    iamcredentials.googleapis.com `
    --project $ProjectId

& gcloud artifacts repositories describe $ArtifactRepository `
    --location $Region --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Gcloud artifacts repositories create $ArtifactRepository `
        --repository-format docker `
        --location $Region `
        --description "AsanClip production images" `
        --project $ProjectId
}

& gcloud storage buckets describe "gs://$FaissBucket" --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Gcloud storage buckets create "gs://$FaissBucket" `
        --location $Region `
        --uniform-bucket-level-access `
        --project $ProjectId
}
Invoke-Gcloud storage buckets update "gs://$FaissBucket" `
    --versioning `
    --uniform-bucket-level-access `
    --public-access-prevention

& gcloud pubsub topics describe $IngestTopic --project $ProjectId *> $null
if ($LASTEXITCODE -ne 0) {
    Invoke-Gcloud pubsub topics create $IngestTopic --project $ProjectId
}

$projectNumber = (& gcloud projects describe $ProjectId --format "value(projectNumber)").Trim()
if (-not $projectNumber) {
    throw "Could not determine the GCP project number"
}
$storageServiceAgent = "service-$projectNumber@gs-project-accounts.iam.gserviceaccount.com"
Invoke-Gcloud pubsub topics add-iam-policy-binding $IngestTopic `
    --member "serviceAccount:$storageServiceAgent" `
    --role roles/pubsub.publisher `
    --project $ProjectId

Ensure-ServiceAccount $ApiServiceAccount "AsanClip Cloud Run API"
Ensure-ServiceAccount $PipelineServiceAccount "AsanClip ingestion pipeline"
Ensure-ServiceAccount $CloudBuildServiceAccount "AsanClip Cloud Build deployer"
Ensure-Secret "asanclip-database-url"
Ensure-Secret "asanclip-pipeline-database-url"
Ensure-Secret "asanclip-gemini-api-key"

$apiPrincipal = "serviceAccount:$ApiServiceAccount@$ProjectId.iam.gserviceaccount.com"
$pipelinePrincipal = "serviceAccount:$PipelineServiceAccount@$ProjectId.iam.gserviceaccount.com"

foreach ($principal in @($apiPrincipal, $pipelinePrincipal)) {
    Invoke-Gcloud projects add-iam-policy-binding $ProjectId `
        --member $principal `
        --role roles/cloudsql.client `
        --condition None
}

foreach ($secret in @("asanclip-database-url", "asanclip-gemini-api-key")) {
    Invoke-Gcloud secrets add-iam-policy-binding $secret `
        --member $apiPrincipal `
        --role roles/secretmanager.secretAccessor `
        --project $ProjectId
}
foreach ($secret in @("asanclip-pipeline-database-url", "asanclip-gemini-api-key")) {
    Invoke-Gcloud secrets add-iam-policy-binding $secret `
        --member $pipelinePrincipal `
        --role roles/secretmanager.secretAccessor `
        --project $ProjectId
}

Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$FaissBucket" `
    --member $apiPrincipal `
    --role roles/storage.objectViewer
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$FaissBucket" `
    --member $pipelinePrincipal `
    --role roles/storage.objectUser

$cloudBuildSa = "$CloudBuildServiceAccount@$ProjectId.iam.gserviceaccount.com"
$cloudBuildPrincipal = "serviceAccount:$cloudBuildSa"

foreach ($role in @(
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/storage.objectViewer",
    "roles/serviceusage.serviceUsageConsumer"
)) {
    Invoke-Gcloud projects add-iam-policy-binding $ProjectId `
        --member $cloudBuildPrincipal `
        --role $role `
        --condition None
}

foreach ($serviceAccount in @($ApiServiceAccount, $PipelineServiceAccount)) {
    Invoke-Gcloud iam service-accounts add-iam-policy-binding `
        "$serviceAccount@$ProjectId.iam.gserviceaccount.com" `
        --member $cloudBuildPrincipal `
        --role roles/iam.serviceAccountUser `
        --project $ProjectId
}

Write-Host ""
Write-Host "GCP foundation is ready."
Write-Host "Add secret values before deployment:"
Write-Host "  API database URL:      asanclip-database-url"
Write-Host "  Pipeline database URL: asanclip-pipeline-database-url"
Write-Host "  Gemini key:            asanclip-gemini-api-key"
Write-Host "Bucket: gs://$FaissBucket"
Write-Host "Ingestion Pub/Sub topic: $IngestTopic"
Write-Host "Cloud Build service account: $cloudBuildSa"

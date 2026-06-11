#!/bin/bash

# ==========================================
# MCP Bakery Demo - Complete Cleanup Script
# ==========================================

# 1. Configuration & Project Detection
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ENV_FILE="$SCRIPT_DIR/../adk_agent/mcp_bakery_app/.env"
DATASET_NAME="mcp_bakery"

# Attempt to load Project ID from local .env if available (supports multi-session/cloud shell)
if [ -f "$ENV_FILE" ]; then
    PROJECT_ID=$(grep -E "^GOOGLE_CLOUD_PROJECT=" "$ENV_FILE" | cut -d'=' -f2)
fi

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi

if [ -z "$PROJECT_ID" ]; then
    echo "Error: Could not determine Google Cloud Project ID."
    exit 1
fi

# Determine bucket name (Default or Argument)
if [ -z "$1" ]; then
    BUCKET_NAME="gs://mcp-bakery-data-$PROJECT_ID"
else
    BUCKET_NAME=$1
fi

echo "----------------------------------------------------------------"
echo "CLEANUP TARGETS"
echo "----------------------------------------------------------------"
echo "Project:   $PROJECT_ID"
echo "Dataset:   $DATASET_NAME"
echo "Bucket:    $BUCKET_NAME"
echo "Local Env: $ENV_FILE"
echo "API Keys:  Keys named 'bakery-demo-key-*'"
echo "Cloud Run: Service 'launchmybakery' in us-west1"
echo "Secrets:   Secret named 'MAPS_API_KEY'"
echo "IAM SA:    Service Account 'bakery-app-runner'"
echo "----------------------------------------------------------------"
echo "WARNING: This will permanently delete the dataset, bucket, and API keys."
read -p "Are you sure you want to proceed? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled."
    exit 1
fi
echo "----------------------------------------------------------------"

# ------------------------------------------
# Phase 1: BigQuery & Storage
# ------------------------------------------
echo "[1/5] Removing BigQuery Dataset..."
if bq show "$PROJECT_ID:$DATASET_NAME" >/dev/null 2>&1; then
    # -r = Recursive, -f = Force
    bq rm -r -f --dataset "$PROJECT_ID:$DATASET_NAME"
    echo "      Dataset '$DATASET_NAME' removed."
else
    echo "      Dataset not found. Skipping."
fi

echo "[2/5] Removing Storage Bucket..."
if gcloud storage buckets describe "$BUCKET_NAME" >/dev/null 2>&1; then
    gcloud storage rm --recursive "$BUCKET_NAME"
    echo "      Bucket '$BUCKET_NAME' deleted."
else
    echo "      Bucket not found. Skipping."
fi

# ------------------------------------------
# Phase 2: API Keys
# ------------------------------------------
echo "[3/5] Cleaning up API Keys..."
# Find keys matching the demo pattern
KEYS_TO_DELETE=$(gcloud alpha services api-keys list \
    --filter="displayName:bakery-demo-key-*" \
    --format="value(name)" 2>/dev/null)

if [ -z "$KEYS_TO_DELETE" ]; then
    echo "      No matching API keys found."
else
    for KEY_NAME in $KEYS_TO_DELETE; do
        echo "      Deleting API Key: $KEY_NAME"
        gcloud alpha services api-keys delete "$KEY_NAME" --quiet
    done
    echo "      Keys deleted."
fi

# ------------------------------------------
# Phase 3: Cloud Run & IAM (Optional)
# ------------------------------------------
echo "[4/7] Cleaning up Cloud Run and IAM resources..."

# 1. Delete Cloud Run service
if gcloud run services describe launchmybakery --region=us-west1 --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "      Deleting Cloud Run service: launchmybakery..."
    gcloud run services delete launchmybakery --region=us-west1 --project="$PROJECT_ID" --quiet
    echo "      Cloud Run service deleted."
else
    echo "      Cloud Run service 'launchmybakery' not found in us-west1. Skipping."
fi

# 2. Delete Secret Manager secret
if gcloud secrets describe MAPS_API_KEY --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "      Deleting secret: MAPS_API_KEY..."
    gcloud secrets delete MAPS_API_KEY --project="$PROJECT_ID" --quiet
    echo "      Secret deleted."
else
    echo "      Secret 'MAPS_API_KEY' not found. Skipping."
fi

# 3. Delete Service Account
SA_EMAIL="bakery-app-runner@$PROJECT_ID.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "      Deleting Service Account: $SA_EMAIL..."
    gcloud iam service-accounts delete "$SA_EMAIL" --project="$PROJECT_ID" --quiet
    echo "      Service Account deleted."
else
    echo "      Service Account '$SA_EMAIL' not found. Skipping."
fi

# ------------------------------------------
# Phase 4: Local Config
# ------------------------------------------
echo "[5/7] Removing local configuration..."
if [ -f "$ENV_FILE" ]; then
    rm "$ENV_FILE"
    echo "      Deleted $ENV_FILE"
else
    echo "      .env file not found. Skipping."
fi

# ------------------------------------------
# Phase 5: Disable APIs (Optional)
# ------------------------------------------
echo "[6/7] Checking Enabled APIs..."
echo "----------------------------------------------------------------"
echo "The setup enabled: mapstools, apikeys, bigquery."
echo "NOTE: Only disable these if no other apps in this project use them."
echo ""
read -p "Do you want to disable these APIs? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Disabling APIs (this may take a moment)..."
    gcloud services disable mapstools.googleapis.com --project=$PROJECT_ID --force
    gcloud services disable bigquery.googleapis.com --project=$PROJECT_ID --force
    gcloud services disable apikeys.googleapis.com --project=$PROJECT_ID --force
    echo "APIs disabled."
else
    echo "Skipping API disablement."
fi

echo "----------------------------------------------------------------"
echo "Cleanup Complete!"
echo "----------------------------------------------------------------"
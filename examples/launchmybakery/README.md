# Launch My Bakery: Google remote MCP demo 

[![Google Cloud](https://img.shields.io/badge/Blog-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)](https://cloud.google.com/blog/products/ai-machine-learning/announcing-official-mcp-support-for-google-services)
[![Codelab](https://img.shields.io/badge/Codelab-58A55d.svg?style=for-the-badge&logo=devbox&logoColor=white)](https://codelabs.developers.google.com/adk-mcp-bigquery-maps#0)
[![Screencast](https://img.shields.io/badge/Screencast-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://www.youtube.com/watch?v=wzccErUYhTI&t=1s)

This directory contains the data artifacts and infrastructure setup scripts for the **MCP support for BigQuery & Google Maps** demo.  

## Demo Overview

This scenario demonstrates an AI Agent's ability to orchestrate enterprise data (BigQuery) and real-world geospatial context (Google Maps) to solve a complex business problem: 

> **"How would you help a friend launch a new high-end sourdough bakery in Los Angeles?"**

The agent autonomously queries BigQuery to find macro trends and uses Google Maps to validate micro-location details. The demo relies on three key datasets:

1.  **Demographics:** To identify neighborhoods with high foot traffic using census data (Macro Discovery).
2.  **Market Data:** To analyze competitor pricing and suggest a premium price point (Pricing Strategy).
3.  **Sales History:** To forecast potential revenue based on comparable store trends (Forecasting).

### Architecture Diagram

![Architecture Diagram](architecture_diagram.png)

The diagram above illustrates the flow of information in this demo. The Agent, powered by Gemini 3 Pro Preview, orchestrates requests between the user and Google Cloud services. It uses a remote (Google hosted) MCP server to securely access BigQuery for demographic and sales data, and Google Maps APIs for real-world location analysis and validation.

## Repository Structure

```text
launchmybakery/
├── data/                        # Pre-generated CSV files for BigQuery
│   ├── demographics.csv
│   ├── bakery_prices.csv
│   ├── sales_history_weekly.csv
│   └── foot_traffic.csv
├── adk_agent/                   # AI Agent Application (ADK)
│   └── mcp_bakery_app/          # App directory
│       ├── agent.py             # Agent definition
│       └── tools.py             # Custom tools for the agent
├── setup/                       # Infrastructure setup scripts
│   ├── setup_bigquery.sh        # Script to provision BigQuery dataset and tables
│   └── setup_env.sh             # Script to set up environment variables
├── cleanup/                     # Infrastructure clean up environment
│   ├── cleanup_env.sh           # Script to remove resources in environment
└── README.md                    # This documentation
```

## Prerequisites

*   **Google Cloud Project** with billing enabled.
*   **Google Cloud Shell** (Recommended) or a local terminal with the `gcloud` CLI installed.

## Deployment Guide

Follow these steps in **Google Cloud Shell** to provision the demo environment.

### 1. Clone the Repository
```bash
git clone https://github.com/google/mcp.git
cd mcp/examples/launchmybakery
```

### 2. Authenticate with Google Cloud

Run the following command to authenticate with your Google Cloud account. This is required for the ADK to access BigQuery.

```bash
gcloud config set project [YOUR-PROJECT-ID]
gcloud auth application-default login
```

Follow the prompts to complete the authentication process.

⚠️ Note: ADK does not automatically refresh your OAuth 2.0 token. If your chat session lasts more than 60 minutes, you may need to re-authenticate using the command above.

### 3. Configure Environment

Run the environment setup script. This script will:
*   Enable necessary Google Cloud APIs (Maps, BigQuery, remote MCP).
*   Create a restricted Google Maps Platform API Key.
*   Create a `.env` file with required environment variables.

```bash
chmod +x setup/setup_env.sh
./setup/setup_env.sh
```

### 4. Provision BigQuery

Run the setup script. This script automates the following:
*   Creates a Cloud Storage bucket.
*   Uploads the CSV data files.
*   Creates the `mcp_bakery` BigQuery dataset.
*   Loads the data into BigQuery tables.

```bash
chmod +x ./setup/setup_bigquery.sh
./setup/setup_bigquery.sh
```

### 5. Deploy to Google Cloud Run (Default)

The recommended deployment method is to host the chatbot application on Google Cloud Run. This runs the Streamlit UI as a secure serverless service. Cloud Run will automatically containerize the application from source using Google Cloud Buildpacks.

#### Step 1: Enable Required APIs
Before deploying, ensure that the Cloud Run, Cloud Build, Secret Manager, and Artifact Registry APIs are enabled:

```bash
gcloud services enable run.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com
```

#### Step 2: Store the Maps API Key in Secret Manager
For security, the Google Maps API Key is stored in Secret Manager and mounted as an environment variable in Cloud Run:

```bash
# Create the secret container
gcloud secrets create MAPS_API_KEY --replication-policy="automatic"

# Add your API key value to the secret (replace YOUR_KEY with your actual Maps key, which was generated in Step 3 and can be found in 'adk_agent/mcp_bakery_app/.env')
echo -n "YOUR_KEY" | gcloud secrets versions add MAPS_API_KEY --data-file=-
```

#### Step 3: Set up IAM Permissions
The application needs permission to query BigQuery and access the Secret Manager secret.

Initialize your Project ID variable:
```bash
PROJECT_ID=$(gcloud config get-value project)
```

1. Create a user-managed Service Account (`bakery-app-runner`):
   ```bash
   gcloud iam service-accounts create bakery-app-runner \
       --display-name="Bakery App Runner Service Account" \
       --project=$PROJECT_ID
   ```

2. Grant BigQuery, Vertex AI, and MCP roles to the Service Account:
   ```bash
   # Grant BigQuery Admin role
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:bakery-app-runner@$PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/bigquery.admin"

   # Grant Vertex AI User role (required for model predictions)
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:bakery-app-runner@$PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/aiplatform.user"

   # Grant MCP Tool User role (required to call remote MCP tools)
   gcloud projects add-iam-policy-binding $PROJECT_ID \
       --member="serviceAccount:bakery-app-runner@$PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/mcp.toolUser"
   ```

3. Grant Secret Manager access to the Service Account:
   ```bash
   gcloud secrets add-iam-policy-binding MAPS_API_KEY \
       --project=$PROJECT_ID \
       --member="serviceAccount:bakery-app-runner@$PROJECT_ID.iam.gserviceaccount.com" \
       --role="roles/secretmanager.secretAccessor"
   ```

> [!IMPORTANT]
> IAM permission updates can take 1–2 minutes to propagate across Google Cloud. If your deployment fails with a `Permission denied on secret` error, please wait a minute and rerun the deploy command.

#### Step 4: Deploy the Application
Deploy the service directly from source, mapping execution flags, service account, and secrets:

```bash
gcloud run deploy launchmybakery \
    --source . \
    --region="us-west1" \
    --service-account="bakery-app-runner@$(gcloud config get-value project).iam.gserviceaccount.com" \
    --command="/cnb/lifecycle/launcher" \
    --args="sh,-c,python3 -m streamlit run streamlit_app.py --server.port=\$PORT --server.address=0.0.0.0" \
    --allow-unauthenticated \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project),GOOGLE_GENAI_USE_VERTEXAI=1" \
    --set-secrets="MAPS_API_KEY=MAPS_API_KEY:latest"
```

Cloud Run will build the code and output a secure HTTPS endpoint (URL) once the deployment completes.

### 6. Chat with the Agent

Open the Cloud Run service URL provided in your browser. You can now chat with the agent and ask it questions about the bakery data.

**Sample Questions to Try:**

*   "I’m looking to open my fourth bakery location in Los Angeles. I need a neighborhood with early activity. Find the zip code with the highest 'morning' foot traffic score."
*   "Can you search for 'Bakeries' in that zip code to see if it's saturated? If there are too many, check for 'Specialty Coffee' shops, so I can position myself near them to capture foot traffic."
*    "Okay and I want to position this as a premium brand. What is the maximum price being charged for a 'Sourdough Loaf' in the LA Metro area?"
*    "Now I want a revenue projection for December 2025. Look at my sales history and take data from my best performing store for the 'Sourdough Loaf'. Run a forecast for December 2025 to estimate the quantity I'll sell. Then, calculate the projected total revenue using just under the premium price we found (let's use $18)"
*    "That'll cover my rent. Lastly, let's verify logistics. Find the closest "Restaurant Depot" to the proposed area and make sure that drive time is under 30 minutes for daily restocking."

### 7. Run Locally via ADK Web Interface (Alternative, Optional)

If you prefer to run the agent locally inside Google Cloud Shell using the standard ADK web interface:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install ADK
pip install google-adk==1.28.0

# Navigate to the app directory
cd adk_agent/

# Run the ADK web interface
adk web --allow_origins 'regex:https://.*\.cloudshell\.dev'
```

Open the link provided by `adk web` in your browser to start chatting with the agent. To abort the session, press `Ctrl+C`.

### 8. Run Locally via Streamlit UI (Alternative, Optional)

As another local alternative, you can run the premium Streamlit chatbot UI locally:

```bash
# Ensure virtual environment is active
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run streamlit_app.py
```

Open the local URL displayed in the terminal (typically `http://localhost:8501`) to start chatting with the agent.

### 9. Cleanup

To avoid incurring ongoing costs for BigQuery storage or other Google Cloud resources, you can run the cleanup script. This script will delete the BigQuery dataset, the Cloud Storage bucket, and the API keys created during setup. Navigate back to the root directory of the repository and run the following command:

```bash
chmod +x cleanup/cleanup_env.sh
./cleanup/cleanup_env.sh
```

## Data Logic & Narratives

The data in this repository is synthetic but structured to support specific demo narratives and successful agent reasoning chains.

| Table | Demo Purpose | Narrative Logic |
| :--- | :--- | :--- |
| **`foot_traffic`** | **Target Discovery**<br>Finding the target neighborhood. | **Morning** activity is uniquely spiked in **90403**, allowing the Agent to pinpoint it as the optimal location for a morning-focused business like a bakery. |
| **`demographics`** | **Community Profiling**<br>Analyzing market depth. | **Santa Monica (90403)** is modeled with a dense, established residential population, providing a stable baseline for customer volume. |
| **`bakery_prices`** | **Pricing Strategy**<br>Setting a price point. | **Erewhon Market** has the highest price ceiling for a Sourdough Loaf (~$18.50), while the market average is ~$8.20. This allows the Agent to confidently suggest a premium price point of ~$15-18. |
| **`sales_history`** | **Forecasting**<br>Predicting growth. | **Silver Lake** shows aggressive week-over-week growth trends, while **Playa Vista** represents a stable, high-volume flagship store, providing distinct patterns for forecasting models. |

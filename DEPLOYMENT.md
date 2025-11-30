# Deployment Instructions

This guide explains how to deploy the Agentic Traveler to Google Cloud.

## Prerequisites

1.  **Google Cloud Project**: Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2.  **Billing**: Enable billing for your project.
3.  **Google Cloud SDK**: Install and initialize the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
4.  **API Key**: Obtain a Google Gen AI API key from [Google AI Studio](https://aistudio.google.com/).

## Option 1: Deploy as a Cloud Function (Serverless)

Since this is a simple agent, a Cloud Function is a good fit if you want to expose it via HTTP. *Note: The current code is a CLI, so you would need to adapt `main.py` to be a Flask/Functions Framework entry point for HTTP deployment.*

## Option 2: Run on a VM (Compute Engine)

1.  **Create a VM instance**:
    ```bash
    gcloud compute instances create travel-agent-vm --zone=us-central1-a --machine-type=e2-micro
    ```

2.  **SSH into the VM**:
    ```bash
    gcloud compute ssh travel-agent-vm --zone=us-central1-a
    ```

3.  **Install Python and Git**:
    ```bash
    sudo apt-get update
    sudo apt-get install python3-pip git
    ```

4.  **Clone the repository**:
    ```bash
    git clone <your-repo-url>
    cd agentic-traveler
    ```

5.  **Install dependencies**:
    ```bash
    pip3 install -r requirements.txt
    ```

6.  **Set Environment Variable**:
    ```bash
    export GOOGLE_API_KEY="your_api_key_here"
    ```

7.  **Run the Agent**:
    ```bash
    python3 src/agentic_traveler/main.py
    ```

## Option 3: Deploy to Cloud Run (Containerized)

To deploy to Cloud Run, you need to containerize the application.

1.  **Create a `Dockerfile`** in the root directory:

    ```dockerfile
    FROM python:3.9-slim

    WORKDIR /app

    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    COPY src/ .

    # For a CLI, Cloud Run isn't the typical target unless you run it as a job or a web service.
    # If deploying as a web service, you need a web framework (like Flask/FastAPI).
    # For this CLI example, we'll just set the entrypoint.
    CMD ["python", "agentic_traveler/main.py"]
    ```

2.  **Build and Push the image**:
    ```bash
    gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/travel-agent
    ```

3.  **Deploy (as a Job)**:
    ```bash
    gcloud run jobs create travel-agent-job --image gcr.io/YOUR_PROJECT_ID/travel-agent
    ```

    *Note: You'll need to pass arguments or set env vars for the job execution.*

## Recommended: Cloud Run Job (for batch/scheduled) or Cloud Functions (for API)

For this specific CLI implementation, running it locally or on a VM is easiest. If you want to make it a web service, wrap `TravelAgent` in a Flask/FastAPI app and deploy to Cloud Run.

# Deployment Instructions

This guide explains how to deploy the Agentic Traveler to Google Cloud.

## Prerequisites

1.  **Google Cloud Project**: Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2.  **Billing**: Enable billing for your project.
3.  **Google Cloud SDK**: Install and initialize the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
4.  **API Key**: Obtain a Google Gen AI API key from [Google AI Studio](https://aistudio.google.com/).

## Deploy as a Cloud Run Function

Cloud Run Functions (formerly Cloud Functions) is a serverless execution environment for building and connecting cloud services. It is ideal for stateless, event-driven, or HTTP-triggered applications.

### Prerequisites

1.  **Google Cloud Project**: Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2.  **Billing**: Enable billing for your project.
3.  **Google Cloud SDK**: Install and initialize the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
4.  **API Key**: Obtain a Google Gen AI API key from [Google AI Studio](https://aistudio.google.com/).

### Deployment Steps

1.  **Prepare the Environment**:
    Ensure your `requirements.txt` includes `functions-framework` if you want to test locally, though it's not strictly required for deployment if you specify the entry point correctly.
    
    ```bash
    pip install functions-framework
    ```

2.  **Create an HTTP Entry Point**:
    Cloud Functions require an HTTP-triggerable function. You can create a file named `main_http.py` (or add to `main.py`) with a function that accepts a request object.

    ```python
    import functions_framework
    from agentic_traveler.travel_agent import TravelAgent

    @functions_framework.http
    def travel_agent_http(request):
        request_json = request.get_json(silent=True)
        request_args = request.args

        # Extract parameters from JSON body or Query parameters
        def get_param(name):
            if request_json and name in request_json:
                return request_json[name]
            elif request_args and name in request_args:
                return request_args[name]
            return None

        budget = get_param('budget') or 'medium'
        climate = get_param('climate') or 'any'
        activity = get_param('activity') or 'any'
        duration = get_param('duration') or '1 week'

        agent = TravelAgent()
        idea = agent.generate_travel_idea({
            "budget": budget,
            "climate": climate,
            "activity": activity,
            "duration": duration
        })
        
        return idea
    ```

3.  **Deploy**:
    Run the following command to deploy the function:

    ```bash
    gcloud functions deploy agentic-traveler-func \
        --gen2 \
        --runtime=python311 \
        --region=us-central1 \
        --source=. \
        --entry-point=travel_agent_http \
        --trigger-http \
        --allow-unauthenticated \
        --set-env-vars GOOGLE_API_KEY=YOUR_API_KEY
    ```

    *Replace `YOUR_API_KEY` with your actual API key.*

4.  **Test**:
    After deployment, you will get a URL. You can test it with `curl`:

    ```bash
    curl "https://YOUR_FUNCTION_URL?budget=low&climate=tropical"
    ```

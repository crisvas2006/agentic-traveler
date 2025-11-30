# Agentic Traveler

An agentic travel planner powered by Google Gen AI.

Common workflow to eliminate 80% of stylistic mistakes in python code:
black .
ruff check .
mypy .
pytest
isort .
## Features

- **AI Travel Agent**: Generates unique travel ideas based on your budget, climate, activity preferences, and duration.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Setup**:
    - Create a `.env` file in the root directory.
    - Add your Google API key:
      ```
      GOOGLE_API_KEY=your_api_key_here
      ```

## Usage

Run the agent via the CLI:

```bash
python src/agentic_traveler/main.py --budget "Medium" --climate "Tropical" --activity "Relaxation" --duration "1 week"
```

Or simply run it interactively:

```bash
python src/agentic_traveler/main.py
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to Google Cloud.

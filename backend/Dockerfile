FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .
RUN pip install --no-cache-dir -e .

# Cloud Run uses PORT env var (default 8080)
ENV PORT=8080

CMD ["sh", "-c", "uvicorn agentic_traveler.interfaces.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

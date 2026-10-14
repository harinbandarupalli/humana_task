FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Start orchestrator
CMD ["uvicorn", "src.orchestrator.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

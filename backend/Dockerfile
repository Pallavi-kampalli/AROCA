FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create upload and model directories
RUN mkdir -p /app/uploads /app/ml_models

# Copy application code
COPY . .

# Make sure __init__.py files exist
RUN find /app/app -type d -exec touch {}/__init__.py \;

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

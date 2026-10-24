FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install curl for healthcheck and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code, seeds, reports, logs
COPY app/ ./app/
COPY seeds/ ./seeds/
COPY reports/ ./reports/
COPY logs/ ./logs/

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV API_PORT=8080

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

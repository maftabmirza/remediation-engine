FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    git \
    wget \
    apt-transport-https \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# PowerShell installation removed - using pywinrm for Windows connections

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/
COPY migrations/ ./migrations/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY tests/ ./tests/

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Use entrypoint.sh for migrations and app startup
ENTRYPOINT ["./entrypoint.sh"]

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including curl for Atlas download
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Atlas CLI
RUN curl -sSf https://atlasgo.sh | sh

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install SpaCy language model for Presidio
RUN python -m spacy download en_core_web_lg

# Copy application code
COPY app/ ./app/
COPY templates/ ./templates/
COPY static/ ./static/

# Copy Atlas schema and migrations
COPY schema/ ./schema/
COPY atlas/ ./atlas/
COPY atlas.hcl .
# NOTE: tests/ is excluded via .dockerignore

COPY entrypoint.sh .
RUN sed -i 's/\r$//' entrypoint.sh
RUN chmod +x entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Use entrypoint.sh for migrations and app startup
ENTRYPOINT ["./entrypoint.sh"]

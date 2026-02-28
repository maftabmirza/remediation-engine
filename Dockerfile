FROM python:3.11-slim@sha256:c8271b1f627d0068857dce5b53e14a9558603b527e46f1f901722f935b786a39

WORKDIR /app

# Install system dependencies including curl for Atlas download
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    git \
    curl \
    gosu \
    pkg-config \
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
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
# We remove 'USER appuser' so the entrypoint runs as root first
# to fix bind-mount permissions, then drops privileges using gosu

EXPOSE 8080

# Use entrypoint.sh for migrations and app startup
ENTRYPOINT ["./entrypoint.sh"]

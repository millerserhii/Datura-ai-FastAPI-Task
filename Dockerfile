FROM python:3.12.9-slim-bookworm

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/.venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH

# Install system dependencies
RUN apt-get update && apt-get -y install \
    curl \
    gcc \
    libpq-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install dependencies
RUN python -m venv $VIRTUAL_ENV && pip install --no-cache-dir poetry
COPY pyproject.toml poetry.lock ./
ARG RELEASE=false
RUN ! $RELEASE && poetry install --no-cache --no-root --only dev || $RELEASE
RUN poetry install --no-cache --no-root --only main

# Add health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Copy entrypoint script
COPY scripts/entrypoint.sh /
RUN sed -i 's/\r$//g' /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy application code
COPY . /app/

# Run entrypoint
ENTRYPOINT ["/entrypoint.sh"]

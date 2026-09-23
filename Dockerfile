FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for psycopg (binary wheel avoids libpq build).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching).
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Copy the rest of the application.
COPY . .

# Expose the API port.
EXPOSE 8000

# Run the API. Use `python scripts/migrate.py apply` first on a fresh database.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

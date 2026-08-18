FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Tell uv to use the container's pre-installed system Python interpreter
ENV UV_SYSTEM_PYTHON=0 \
    UV_PYTHON=python3

# Copy dependencies manifest
COPY pyproject.toml uv.lock* ./

# Install python dependencies inside .venv using system python
RUN uv sync --no-cache

# Copy application source code
COPY . .

# Create non-root system user and grant ownership
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
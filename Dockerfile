FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv (pinned version) in the image
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /uvx /bin/

WORKDIR /app

# Copy project metadata and lockfile first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv with pinned versions from uv.lock (no dev deps)
RUN uv sync --frozen --no-dev

# Copy the rest of the project
COPY . .

# Ensure the project virtualenv's binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

# Use official Python 3.12 slim base image
FROM python:3.12-slim

# Copy official uv binary from Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency definition files first for better caching
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN uv sync --frozen --no-dev

# Copy application source code
COPY . .

# Expose backend port
EXPOSE 8000

# Start Uvicorn server
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

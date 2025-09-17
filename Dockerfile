# ---------- Base Image ----------
FROM python:3.13-slim AS base

# Set working directory
WORKDIR /app

# ---------- Install dependencies ----------
# Prevent python from writing pyc files and enable stdout flushing
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (curl for debugging, build tools for some pip deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pipenv/requirements dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Copy application ----------
COPY ./app ./app

# ---------- Expose & Run ----------
EXPOSE 8000

# Default command (can override with docker-compose/k8s)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
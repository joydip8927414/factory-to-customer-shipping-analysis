# ==============================================================================
# Nassau Candy Logistics Analytics Platform & Developer IAM Portal
# Multi-Service Production Dockerfile
# ==============================================================================

FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system utilities and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data directories and versions folder exist
RUN mkdir -p data/admin data/processed data/versions outputs/models logs

# Run production seeding to initialize database schemas and default credentials
RUN python scripts/seed_production_db.py

# Expose ports:
# 8501: Logistics Analytics Dashboard
# 8600: Developer IAM & Control Portal
EXPOSE 8501 8600

# Healthcheck on main analytics platform
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default command launches both servers concurrently
CMD ["python", "scripts/start_servers.py"]

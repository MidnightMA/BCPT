# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final runtime image
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels/packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy project source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p /app/data /app/tmp

# Persistent volumes for session files and temporary downloads
VOLUME ["/app/data", "/app/tmp"]

# Run as non-interactive python process
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "app.main"]

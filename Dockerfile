# Stage 1: Build the application
FROM docker.io/library/python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only necessary files
COPY main.py shared.py cleanerfile.py config.py ./

# Create necessary directories with correct permissions
RUN mkdir -p /app/data /app/keys && \
    chmod 755 /app/data /app/keys && \
    chown 1000:1000 /app/data /app/keys

# Run as non-root user for security
RUN useradd -r -u 1000 -g root appuser && \
    chown -R appuser:root /app
# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /app .

# Create necessary directories and set permissions
RUN mkdir -p sharedkeys chats && \
    chown -R appuser:appuser sharedkeys chats

USER appuser

# Set default command
CMD ["python", "main.py"]
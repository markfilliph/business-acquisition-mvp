FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY pyproject.toml .
COPY .env.example ./.env

# Create necessary directories
RUN mkdir -p data logs output backups

# Install the package in development mode
RUN pip install -e .

# Make scripts executable
RUN chmod +x scripts/*.py

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose any ports if needed (for future web interface)
EXPOSE 8080

# Default command
CMD ["python", "scripts/run_pipeline.py"]
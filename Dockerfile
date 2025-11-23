FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data && \
    chown -R botuser:botuser /app

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Switch to non-root user
USER botuser

# Run the bot
CMD ["python", "-m", "src.main"]


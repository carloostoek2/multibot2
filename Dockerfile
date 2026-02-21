FROM python:3.11-slim

# Install ffmpeg and other system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create temp directory for file processing
RUN mkdir -p /tmp/bot_temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMP_DIR=/tmp/bot_temp

# Run the bot
CMD ["python", "run.py"]

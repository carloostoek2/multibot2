FROM python:3.11-slim

# Install system dependencies (ffmpeg, curl for Deno, nodejs as fallback)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Deno (preferred JavaScript runtime for yt-dlp)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:${PATH}"
ENV DENO_INSTALL="/root/.deno"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install nightly yt-dlp for latest YouTube fixes
RUN pip install --upgrade --force-reinstall \
    "yt-dlp[default] @ https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.tar.gz"

# Copy the rest of the application
COPY . .

# Create temp directory for file processing
RUN mkdir -p /tmp/bot_temp

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMP_DIR=/tmp/bot_temp

# Run the bot (update yt-dlp first to ensure latest fixes)
CMD yt-dlp --update-to nightly && python run.py

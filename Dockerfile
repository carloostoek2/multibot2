FROM aiogram/telegram-bot-api:latest AS telegram-api

FROM python:3.11-slim

# Install system dependencies (ffmpeg, curl/unzip for Deno, nodejs as fallback)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    nodejs \
    npm \
    libstdc++6 \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Alpine-built binary needs musl to run on Debian
COPY --from=telegram-api /usr/local/bin/telegram-bot-api /usr/local/bin/telegram-bot-api
COPY --from=telegram-api /lib/ld-musl-x86_64.so.1 /lib/ld-musl-x86_64.so.1
COPY --from=telegram-api /usr/lib/libssl.so.3 /usr/lib/libssl.so.3
COPY --from=telegram-api /usr/lib/libcrypto.so.3 /usr/lib/libcrypto.so.3
COPY --from=telegram-api /usr/lib/libstdc++.so.6 /usr/lib/libstdc++.so.6
COPY --from=telegram-api /usr/lib/libgcc_s.so.1 /usr/lib/libgcc_s.so.1
COPY --from=telegram-api /lib/libz.so.1 /lib/libz.so.1

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

# Create temp and local API directories
RUN mkdir -p /tmp/bot_temp /var/lib/telegram-bot-api /tmp/telegram-bot-api

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TEMP_DIR=/tmp/bot_temp

COPY docker/railway-entrypoint.sh /docker/railway-entrypoint.sh
RUN chmod +x /docker/railway-entrypoint.sh

# Start local Bot API (when enabled) and the bot in the same container
CMD ["/docker/railway-entrypoint.sh"]

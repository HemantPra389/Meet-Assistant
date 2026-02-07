FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install system dependencies (need xvfb for headful bot, ffmpeg for recording)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Common Dependencies
COPY meetbot/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install API Dependencies
COPY apihandler/requirements.txt requirements_api.txt
RUN pip install --no-cache-dir -r requirements_api.txt

# Copy meetbot source (required for Bot logic)
COPY meetbot/src/ meetbot/src/

# Copy API source
COPY apihandler/src/ apihandler/src/

# Setup directories for bot artifacts
RUN mkdir -p user_data debug_screenshots recordings

# Entry point
# We run from /app so that relative paths in api.py (../meetbot) work correctly
ENTRYPOINT ["xvfb-run", "-a", "python", "-u", "apihandler/src/api.py"]

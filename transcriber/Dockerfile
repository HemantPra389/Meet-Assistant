FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY __init__.py .

# Create directory for audio files
RUN mkdir -p /audio

# Default command - file transcription mode
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

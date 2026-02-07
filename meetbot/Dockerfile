FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY start.sh .

RUN chmod +x start.sh

ENTRYPOINT ["./start.sh"]

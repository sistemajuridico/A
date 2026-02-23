FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "10000", "--timeout-keep-alive", "600", "--timeout-graceful-shutdown", "300", "--limit-concurrency", "20"]

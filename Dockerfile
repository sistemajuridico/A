FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "api:app", "--bind", "0.0.0.0:10000", "--timeout", "600"]

FROM python:3.10-slim

# Blindagem de Idioma
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalação de dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# MUDANÇA CRÍTICA: Usamos a forma de string para que o Docker entenda a variável $PORT do Render
CMD gunicorn -w 1 -k uvicorn.workers.UvicornWorker api:app --bind 0.0.0.0:$PORT --timeout 600

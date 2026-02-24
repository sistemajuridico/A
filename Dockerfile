FROM python:3.10-slim

# Blindagem de Idioma e Acentos
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalação mínima de dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando com worker único para estabilidade total no Render
CMD ["gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "api:app", "--bind", "0.0.0.0:10000", "--timeout", "600"]

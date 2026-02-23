# Usar uma imagem oficial do Python
FROM python:3.10-slim

# Instalar o FFmpeg e dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Definir o diretório de trabalho
WORKDIR /app

# Copiar os requisitos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código
COPY . .

# Comando para iniciar o servidor
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "10000", "--timeout-keep-alive", "120"]

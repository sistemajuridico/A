# Utiliza a imagem oficial do Python 3.10 slim para manter o container leve
FROM python:3.10-slim

# Instalação de dependências do sistema:
# - ffmpeg: necessário para o processamento de áudio e vídeo via moviepy/pydub
# - libmagic-dev: para identificação de tipos de ficheiro
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o ficheiro de dependências e instala as bibliotecas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código fonte para dentro do container
COPY . .

# COMANDO DE INICIALIZAÇÃO DE ALTA DISPONIBILIDADE
# -w 1: Limita a 1 worker para economizar os 512MB de RAM do Render
# --timeout 600: Dá 10 minutos para que PDFs grandes terminem o upload e processamento
# -k uvicorn.workers.UvicornWorker: Integra o Gunicorn com o FastAPI de forma estável
CMD ["gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "api:app", "--bind", "0.0.0.0:10000", "--timeout", "600"]

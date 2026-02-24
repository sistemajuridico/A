FROM python:3.10-slim

# --- BLINDAGEM DE IDIOMA (Resolve o erro do \u0303 e acentos) ---
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
# ---------------------------------------------------------------

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Comando otimizado para economia de RAM e estabilidade
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "10000", "--timeout-keep-alive", "600"]

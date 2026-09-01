FROM python:3.11-slim

# Systemabhängigkeiten:
# - exiftool: zum Schreiben der IPTC-Metadaten
# - build-essential/cmake/etc: zum Kompilieren von dlib (Gesichtserkennung)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libimage-exiftool-perl \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# dlib-Build kann 10-20 Minuten dauern - das ist normal.
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

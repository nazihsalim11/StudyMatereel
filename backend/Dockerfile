# Force linux/amd64 so pip always finds pre-built wheels (no Rust compilation needed)
FROM --platform=linux/amd64 python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    libreoffice-impress \
    build-essential \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install pydantic-core binary first, then the rest of the packages
RUN pip install --no-cache-dir --prefer-binary pydantic-core==2.18.4 \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

RUN mkdir -p temporary_storage/uploads temporary_storage/videos

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]

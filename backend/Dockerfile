FROM python:3.11-slim

# System dependencies — ffmpeg for video, poppler for PDF-to-image
RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    libreoffice-impress \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p temporary_storage/uploads temporary_storage/videos

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

# System dependencies — ffmpeg, poppler, LibreOffice + Rust build tools
# (Rust is required to compile pydantic-core on architectures without pre-built wheels)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    libreoffice-impress \
    build-essential \
    curl \
    --no-install-recommends \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .
# --prefer-binary uses pre-built wheels where available (faster, avoids Rust compile)
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

RUN mkdir -p temporary_storage/uploads temporary_storage/videos

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

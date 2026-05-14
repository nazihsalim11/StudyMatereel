FROM python:3.11

# System deps: ffmpeg (video), poppler (PDF→image), build tools (pydantic-core compile)
# LibreOffice is excluded here to keep build times low — PDF uploads work out of the box.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    build-essential \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install Rust AND Python packages in ONE RUN so cargo is on PATH during pip install.
# --prefer-binary picks pre-built wheels first; Rust is only used as a fallback compiler.
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable \
    && . /root/.cargo/env \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt \
    && rm -rf /root/.cargo/registry /root/.cargo/git

COPY . .

RUN mkdir -p temporary_storage/uploads temporary_storage/videos

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

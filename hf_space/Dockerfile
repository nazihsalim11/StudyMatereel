FROM --platform=linux/amd64 python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    poppler-utils \
    libreoffice-impress \
    build-essential \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages as root so they're available system-wide
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefer-binary pydantic-core==2.18.4 \
    && pip install --no-cache-dir --prefer-binary -r /tmp/requirements.txt

# HF Spaces requires a non-root user with UID 1000
RUN useradd -m -u 1000 user

WORKDIR /home/user/app

COPY --chown=user . .

RUN mkdir -p temporary_storage/uploads temporary_storage/videos

USER user

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]

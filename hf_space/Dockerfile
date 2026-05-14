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

# Create non-root user (UID 1000 required by HF Spaces)
# and ensure the working directory is owned by that user
RUN useradd -m -u 1000 user \
    && mkdir -p /home/user/app/temporary_storage/uploads \
               /home/user/app/temporary_storage/videos \
    && chown -R user:user /home/user/app

WORKDIR /home/user/app

COPY --chown=user . .

USER user

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]

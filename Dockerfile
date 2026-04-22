FROM python:3.14-slim

# Install system libraries that OpenCV-headless needs
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# IMPORTANT: Single worker only. POS WebSocket state lives in process memory.
# Adding --workers >1 will silently break the POS payment flow. See ADR-0005.
# Shell form required for $PORT expansion (Render sets PORT at runtime).
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*

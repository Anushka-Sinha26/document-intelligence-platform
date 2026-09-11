FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY .env.example ./.env.example

ENV PYTHONPATH=/app/backend
ENV TESSERACT_CMD=/usr/bin/tesseract

EXPOSE 10000

CMD ["gunicorn", "--chdir", "backend", "--bind", "0.0.0.0:10000", "--timeout", "180", "--workers", "1", "app.main:app"]
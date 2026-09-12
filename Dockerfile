FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY app/requirements.txt ./app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY app ./app
COPY data /backend/data

RUN mkdir -p /backend/uploads

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} app.main:app"]
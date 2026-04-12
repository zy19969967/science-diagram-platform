FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/common /app/common
COPY backend/assets /app/assets
COPY backend/gateway /app/service

RUN pip install --no-cache-dir -r /app/service/requirements.txt

ENV PYTHONPATH=/app
ENV RUNS_DIR=/app/data/runs
ENV ASSETS_DIR=/app/assets

CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]

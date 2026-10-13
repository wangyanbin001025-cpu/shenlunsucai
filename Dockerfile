FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHENLUN_HOST=0.0.0.0 \
    SHENLUN_DATA_DIR=/var/data \
    TZ=Asia/Tokyo
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
COPY . /app
RUN pip install --no-cache-dir "psycopg[binary]>=3.2,<4" && mkdir -p /var/data && chmod 755 /var/data
EXPOSE 10000
CMD ["python", "server.py"]

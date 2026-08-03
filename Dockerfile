# =====================================================
# Builder Stage
# =====================================================

FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive


# More reliable apt configuration for Docker builds
RUN printf 'Acquire::Retries "10";\nAcquire::http::Timeout "120";\nAcquire::https::Timeout "120";\nAcquire::http::Pipeline-Depth "0";\n' \
    > /etc/apt/apt.conf.d/99docker-retries


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN python -m pip install --upgrade pip && \
    pip install \
        --no-cache-dir \
        --timeout=120 \
        --retries=10 \
        -r requirements.txt && \
    python -m spacy download en_core_web_sm



# =====================================================
# Runtime Stage
# =====================================================

FROM python:3.11-slim-bookworm


WORKDIR /app


ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app



# PostgreSQL runtime library

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*



# Copy installed python packages

COPY --from=builder /usr/local /usr/local



# Application code

COPY app2 ./app2
COPY scripts ./scripts
COPY migrations ./migrations
COPY alembic.ini .
COPY docker/entrypoint.sh /entrypoint.sh



# Runtime directories

RUN groupadd --gid 10001 appuser && \
    useradd \
        --uid 10001 \
        --gid 10001 \
        --create-home \
        --shell /bin/bash \
        appuser && \
    mkdir -p \
        /app/logs \
        /app/indexes && \
    sed -i 's/\r$//' /entrypoint.sh && \
    chmod +x /entrypoint.sh && \
    chown -R appuser:appuser /app



USER appuser



EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/health', timeout=3)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]

CMD ["sh", "-c", "exec uvicorn app2.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${UVICORN_WORKERS:-1}"]

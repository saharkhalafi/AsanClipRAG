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

RUN useradd \
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



EXPOSE 8000



ENTRYPOINT ["/entrypoint.sh"]

CMD ["uvicorn", "app2.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

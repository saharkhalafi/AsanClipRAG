# AsanClip RAG System - Deployment Guide

Production deployment guide for the **AsanClip Hybrid Retrieval-Augmented Generation (RAG) System**.

This document explains how to configure, deploy, secure, monitor, and scale the system in production environments.

The architecture is designed to be:

- Cloud-native
- Containerized
- Scalable
- Security-focused
- Production-ready

---

# 1. Overview

## Current Technology Stack

The deployment stack includes:

- FastAPI (Python)
- PostgreSQL + pgvector
- Redis
- FAISS
- Docker

---

# 2. Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure the following production settings.

---

## Core Settings

```env
ENVIRONMENT=production

DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname

REDIS_URL=redis://redis:6379/0
```

---

## Security Configuration

```env
SECRET_KEY=your-very-strong-secret-key
```

Requirements:

- Use a strong random secret
- Never commit secrets into Git
- Store secrets securely in production

---

## API Configuration

```env
ALLOWED_ORIGINS=https://yourdomain.com
```

Only trusted frontend domains should be allowed.

---

## Optional / Advanced Settings

```env
LOG_LEVEL=INFO

ENABLE_CACHE=true

FAISS_INDEX_PATH=/app/data/faiss_index
```

---

# 3. Local Development with Docker

## Clone Repository

```bash
git clone <your-repo-url>

cd asanclip-rag
```

---

## Configure Environment

```bash
cp .env.example .env
```

---

## Start Services

```bash
docker-compose up --build
```

This starts:

- FastAPI application
- PostgreSQL database
- pgvector extension
- Redis cache
- Required services

---

# 4. Production Deployment Options

Recommended hosting platforms:

| Platform | Difficulty | Recommendation | Notes |
|---|---|---|---|
| Railway | Easy | ⭐⭐⭐⭐⭐ | Best option for first production deployment |
| Render | Easy | ⭐⭐⭐⭐ | Good PostgreSQL and Redis support |
| Fly.io | Medium | ⭐⭐⭐⭐ | Good performance and flexibility |
| AWS ECS/Fargate | Hard | ⭐⭐⭐ | Suitable for large-scale deployment |

---

# 5. Docker Production Setup

The production Docker configuration follows multi-stage build best practices.

Benefits:

- Smaller production image
- Faster deployments
- Better security
- Cleaner runtime environment

---

## Production Dockerfile Example

```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages \
/usr/local/lib/python3.11/site-packages

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app2.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

# 6. Production Checklist

Before deployment:

## Application Readiness

- [ ] All secrets moved to environment variables
- [ ] Docker image builds successfully
- [ ] Health check endpoint is working

```
/api/v1/health
```

- [ ] Database migrations are ready
- [ ] FAISS index generation script tested
- [ ] Rate limiting configured
- [ ] CORS properly restricted

---

## Security Hardening

- [ ] HTTPS enabled
- [ ] Strong secret keys configured
- [ ] Firewall rules configured
- [ ] Only required ports exposed
- [ ] Dependencies regularly updated
- [ ] Query Firewall fully enabled

---

# 7. Monitoring & Observability

Production monitoring should include:

---

## Logging

Implemented using:

- Structured application logs
- RetrievalLog table
- Search analytics

Tracks:

- Query execution
- Retrieval strategy
- Latency
- Ranking signals
- Quality metrics

---

## Error Tracking

Recommended:

```
Sentry
```

Purpose:

- Exception monitoring
- Error aggregation
- Production debugging

---

## Metrics

Recommended:

- Prometheus + Grafana
- Better Stack

Monitor:

- API performance
- System resources
- Retrieval quality

---

## Uptime Monitoring

Recommended:

- UptimeRobot
- Better Uptime

---

## Future APM

Planned:

```
OpenTelemetry
```

---

# Key Metrics to Monitor

## Performance Metrics

- Request latency (p95)
- Average response time
- Database latency

## Reliability Metrics

- Error rate
- Failed requests
- Service availability

## Retrieval Quality Metrics

- Cache hit ratio
- Empty result rate
- Semantic rejection rate
- Retrieval confidence

---

# 8. Scaling Strategy

The system can scale gradually.

---

## Phase 1 - Current Production

Architecture:

```
Single API Instance

        |
        |

Managed PostgreSQL

        |
        |

Redis Cache
```

Suitable for:

- Initial production release
- Controlled user traffic
- MVP stage

---

## Phase 2 - Growth

Add:

- Multiple API workers
- Redis optimization
- Database read replicas

Architecture:

```
              Load Balancer

                    |

        -------------------------

        |                       |

      API 1                   API 2

        |

 Redis + PostgreSQL
```

---

## Phase 3 - Large Scale

Future architecture:

- Auto-scaling infrastructure
- Dedicated vector retrieval service
- Kubernetes deployment
- Distributed search components

---

# 9. Backup & Recovery

Production backup strategy:

---

## PostgreSQL

- Daily database backups
- Automated recovery testing

---

## Redis

Enable:

- AOF persistence
- RDB snapshots

---

## FAISS

Maintain:

- Index backup strategy
- Versioned index files
- Recovery procedure

---

## Environment Configuration

Backup:

- Environment variables
- Deployment configuration
- Infrastructure settings

---

# 10. Deployment Workflow (GitHub Actions)

Recommended CI/CD pipeline:

```
Code Push

    |

Run Tests

    |

Build Docker Image

    |

Push Image to Container Registry

    |

Deploy to Hosting Platform

    |

Run Health Checks
```

---

# Production Deployment Principles

The AsanClip deployment architecture follows:

- Infrastructure as Code principles
- Container-first deployment
- Secure secret management
- Observable AI systems
- Incremental scalability

---

Built for reliable AI-powered search in production environments.
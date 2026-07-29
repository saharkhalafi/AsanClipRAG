# AsanClip RAG System

**Production-grade hybrid retrieval engine for intelligent video template search.**

AsanClip helps users find the right video templates using natural language (Persian, English, or mixed). It combines vector search, BM25, metadata filtering, multi-stage ranking, security gating, and full request observability.

---

## Highlights

- **Hybrid retrieval**: FAISS / pgvector + BM25 + metadata candidates
- **Persian-first query understanding**: normalization, synonyms, catalog-aware intent
- **Query firewall**: injection, abuse, cost, relevance, and semantic gating
- **Multi-stage ranking**: vector + lexical + metadata boost + alignment
- **Compact API contract**: top **5** products with unique captions
- **Production ops**: Docker, Alembic, structured `retrieval_logs`, GitHub Actions CI

---

## Evaluation (Golden Set)

Offline evaluation on **100** labeled queries after retrieval-quality fixes:

| Metric | Before | After | Change |
|--------|--------:|-------:|--------:|
| **MRR** | 0.668 | **0.686** | +2.7% |
| **Recall@10** | 0.446 | **0.617** | +38% |
| **Precision@10** | 0.239 | **0.365** | +53% |
| **nDCG@10** | 0.484 | **0.595** | +23% |
| **Hit Rate@10** | 0.756 | **0.805** | +6.5% |
| **Failed (0 results)** | 6 | **4** | −2 |

### Latency

- **Cold / warm path:** ~700–900 ms
- **Cached queries:** ~80–170 ms

Main quality gains came from deeper candidates, correct BM25→lexical scoring, stronger hybrid fusion, Persian synonym handling, and metadata boost fixes — without a latency regression.

---

# Architecture

```text
                           User Query
                               │
                               ▼
                   FastAPI (/api/v1/search)
                               │
                               ▼
                        Query Firewall
        (abuse · injection · cost · relevance · semantic intent)
                               │
                               ▼
                     SearchOrchestrator
                               │
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
      ▼                        ▼                        ▼
Query preprocess        Synonym expansion      Metadata extraction
      │                        │                        │
      └────────────────────────┼────────────────────────┘
                               ▼
                     Candidate Generation
                               │
                               ▼
                  RetrievalOrchestrator
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
      ▼                        ▼                        ▼
 Vector Search             BM25 Search          Metadata Search
(FAISS → pgvector)      (+ Persian fallback)
      │                        │                        │
      └────────────────────────┼────────────────────────┘
                               ▼
                   Hybrid Fusion & Retry Logic
                               │
                               ▼
                           Ranking
      (UnifiedRanker · metadata boost · alignment)
                               │
                               ▼
               Top 5 Products + Unique Captions
                               │
                               ▼
          Observability (isolated retrieval_logs session)
```

> **Design principle:** Maintain a large internal candidate pool to maximize ranking quality, then expose only a compact top-k response to clients.

---

## Key Components

| Layer | Responsibility |
|-------|----------------|
| **API** | FastAPI routes, request validation, response contract |
| **Firewall** | Security, abuse prevention, semantic validation |
| **Orchestration** | Pipeline control, routing, retries, fallbacks |
| **Retrieval** | Vector search, BM25, metadata candidates, hybrid fusion |
| **Ranking** | Semantic + lexical + metadata score fusion |
| **Observability** | Request tracing, latency metrics, quality signals |
| **Cache** | Query-result caching (cache key includes `top_k`) |

---

# Project Structure

```text
app2/
├── api/              # FastAPI routes
├── analytics/        # Event builders & logging
├── builders/         # Response / observability builders
├── cache/            # Cache service (tracked in Git)
├── core/             # Configuration
├── db/               # Models, sessions, database
├── firewall/         # Security & intent validation
├── metadata/         # Metadata loading & extraction
├── ranking/          # UnifiedRanker & ranking logic
├── retrieval/        # FAISS, BM25, hybrid retrieval
├── services/         # Search & retrieval orchestrators
├── utils/            # Filters, synonyms, helpers
│
evaluation/           # Golden set & offline evaluation
docs/                 # Architecture, database, deployment
docker/               # PostgreSQL init scripts
migrations/           # Alembic migrations
scripts/              # Maintenance utilities
tests/                # Automated tests
Dockerfile
docker-compose.yml
requirements.txt
```

---

# Quick Start (Docker)

## Prerequisites

- Docker
- Docker Compose
- Python 3.11+ (optional for local evaluation)

## Clone

```bash
git clone <your-repository-url>
cd AsanClipRAG
```

## Configure

```bash
cp .env.example .env
```

Update your secrets and API keys.

For Docker:

- `DB_HOST=postgres`
- `DATABASE_URL` should point to the PostgreSQL service.

## Run

```bash
docker compose up --build
```

On startup the application typically:

1. Waits for PostgreSQL
2. Enables required extensions (`pgvector`, etc.)
3. Runs Alembic migrations
4. Imports product data when configured or when the database is empty

---

## Endpoints

Application:

```
http://localhost:8000
```

Swagger UI:

```
http://localhost:8000/docs
```

---

## Useful Docker Commands

### Rebuild application

```bash
docker compose up --build -d app
```

### View logs

```bash
docker compose logs -f app
```

### PostgreSQL shell

```bash
docker compose exec postgres psql -U postgres -d Sale1404
```

### Reset everything (destructive)

```bash
docker compose down -v
docker compose up --build
```

---

# API

## Search

**POST**

```
/api/v1/search
```

### Request

```json
{
  "query": "استوری تولد کودکانه"
}
```

### Processing Pipeline

```text
Firewall
    ↓
Query preprocessing
    ↓
Hybrid retrieval
    ↓
Ranking
    ↓
Top-5 response
    ↓
Observability logging
```

Interactive API documentation is available at:

```
/docs
```

---

# Database

The system uses:

- PostgreSQL
- pgvector
- Alembic migrations

Main stored entities include:

- Product catalog (`asanclipproducts`)
- Captions
- Firewall usage
- Rich `retrieval_logs`

See:

```
docs/database.md
```

for schema details and indexing strategy.

---

# Observability

Each search request can record:

- Request ID
- Session ID
- User ID
- Original query
- Normalized query
- Firewall decisions
- Retrieval mode
- Retry information
- Quality scores
- Stage-by-stage latency
- Cache hit/miss
- Returned result snapshot

Logging uses an **isolated database session**, ensuring observability failures never interrupt user searches.

---

# Offline Evaluation

Run evaluation while the API is running:

```bash
python evaluation/evaluate.py
```

Golden dataset:

```text
evaluation/
```

Generated report:

```text
evaluation/results/eval_report.json
```

Primary metrics:

- MRR
- Recall@K
- Precision@K
- nDCG@K
- Hit Rate@K
- Latency

---

# Configuration

Configuration sources:

```
.env.example
```

Typed settings:

```
app2/core/settings.py
```

Deployment notes:

```
docs/deployment.md
```

> Never commit production `.env` files or large SQL dumps.

---

# CI / Quality Gates

GitHub Actions validates:

- Ruff lint
- Pytest
- Alembic migration integrity
- Docker build

Packaging lesson learned:

> Ignore rules should never exclude application packages (for example, prefer `/cache/` over a broad `cache/` ignore rule that removes `app2/cache`).

---

# Roadmap

- Larger Golden Set
- Continuous regression evaluation in CI
- CTR / click-based ranking calibration
- Optional learned reranker (only if justified by offline & online metrics)
- Rich observability dashboards
- Horizontal scaling (stateless API + shared cache + managed PostgreSQL)

---

# Contributing

1. Create a branch from `develop` (or the default development branch)
2. Keep pull requests focused
3. Run lint and tests locally whenever possible
4. Open a Pull Request targeting the integration branch

See `CONTRIBUTING.md` if available.

---

# License

MIT License

See:

```
LICENSE
```

---

# About

Built for real-world Persian and English template search with a focus on:

- Reliable hybrid retrieval
- Explicit security gates
- Measurable search quality
- Production-ready operations
- Observable search pipelines

**AsanClip** — *Intelligent Video Template Discovery.*

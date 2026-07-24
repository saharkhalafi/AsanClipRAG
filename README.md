# AsanClip RAG System

**Production-grade Hybrid Retrieval-Augmented Generation (RAG) Engine** for intelligent video template search.

---

## 🚀 Project Overview

AsanClip is a robust, scalable, and production-ready RAG system designed to deliver highly relevant video template search results.

The system combines:

- Semantic vector search
- Lexical retrieval (BM25)
- Metadata filtering
- Intelligent ranking
- Query routing
- Security validation
- Production-grade observability

The goal is to provide a high-quality search experience where users can express their intent naturally and receive the most relevant video templates.

---

# ✨ Key Features

## 🔍 Hybrid Retrieval Engine

AsanClip uses a multi-strategy retrieval pipeline:

- Vector similarity search
- BM25 lexical search
- Metadata-aware filtering
- Metadata boosting
- Hybrid ranking

Supports:

- Persian language queries
- English language queries
- Mixed-language search scenarios

---

## 🛡️ Advanced Query Firewall

A dedicated security layer before retrieval:

- Prompt injection detection
- Query abuse prevention
- Cost control
- Semantic intent validation
- Malicious input filtering

---

## 🧠 Intelligent Query Routing

The system dynamically selects the best retrieval strategy:

- Vector search
- Hybrid retrieval
- Lexical fallback
- Heavy fallback mode

Routing decisions are based on:

- Query characteristics
- Retrieval confidence
- Result quality signals

---

## 🏆 Multi-Stage Ranking System

The final ranking combines multiple signals:

- Semantic similarity score
- BM25 relevance score
- Metadata relevance
- Business rules
- Confidence signals

Using:

```
UnifiedRanker
```

with configurable weighted scoring.

---

## 📊 Production Observability

The system provides detailed monitoring and analytics:

- Request tracing
- Retrieval latency breakdown
- Query quality metrics
- Ranking analysis
- Cache monitoring
- Structured event logging

All retrieval events are stored in:

```
retrieval_logs
```

for future optimization and analytics.

---

# 🏗️ Architecture

The system follows a clean and modular layered architecture:

```
                    User Query
                        |
                        v
                  FastAPI API Layer
                        |
                        v
                Query Firewall Layer
                        |
                        v
             Search Orchestration Layer
                        |
                        v
        -----------------------------------
        |                |                |
        v                v                v
 Vector Retrieval   BM25 Retrieval   Metadata Search
        |                |                |
        -----------------------------------
                        |
                        v
              Unified Ranking Layer
                        |
                        v
              Quality Evaluation
                        |
                        v
                 Final Results
```

---

# 🧩 System Components

## API Layer

Technology:

```
FastAPI
```

Responsibilities:

- API request handling
- Input validation
- Response generation

---

## Security Layer

Component:

```
Query Firewall
```

Responsibilities:

- Query validation
- Security checks
- Abuse prevention
- Intent verification

---

## Orchestration Layer

Components:

```
SearchOrchestrator
RetrievalOrchestrator
```

Responsibilities:

- Pipeline execution
- Retrieval strategy selection
- Stage management
- Fallback handling

---

## Retrieval Layer

### Vector Retrieval

Technologies:

- FAISS
- PostgreSQL pgvector

Purpose:

- Semantic similarity search
- Meaning-based retrieval

---

### Lexical Retrieval

Technology:

- BM25

Purpose:

- Exact keyword matching
- Robust lexical fallback

---

### Metadata Retrieval

Purpose:

- Category filtering
- Platform matching
- Occasion matching
- Business-aware retrieval

---

# 📂 Project Structure

```bash
app2/
├── api/                    # FastAPI routes
├── core/                   # Application settings
├── db/                     # Database models and sessions
├── firewall/               # Query security and validation
├── retrieval/              # Vector, BM25, hybrid retrieval
├── ranking/                # Ranking algorithms
├── services/               # Orchestrators and business logic
├── metadata/               # Metadata processing
├── analytics/              # Metrics and analytics
├── docs/                   # Documentation
├── scripts/                # Maintenance scripts
├── tests/                  # Automated tests
│
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

# ⚙️ Installation & Local Development

## Prerequisites

Required:

- Docker
- Docker Compose
- Python 3.11+

---

# 🐳 Running with Docker

Clone the repository:

```bash
git clone <your-repository-url>

cd asanclip-rag
```

Create environment file:

```bash
cp .env.example .env
```

Set your API keys in `.env`. For Docker, keep `DB_HOST=postgres` and `DATABASE_URL` pointing at the `postgres` service (see `.env.example`).

Build and start services:

```bash
docker compose up --build
```

Run database migrations manually:

```bash
docker compose run --rm migration
```

Import all products from `Sale1404.sql` (about 2300 rows):

```bash
docker compose run --rm migration
docker compose run --rm import-db
```

On startup the app container will:

1. Wait for PostgreSQL
2. Enable `pgvector` extensions
3. Run Alembic migrations
4. Import products from `Sale1404.sql` if the database has fewer than 100 rows
5. Only use the 3-row sample seed if `SEED_DATABASE=true` and the database is still empty

To reset the database and reload everything from scratch:

```bash
docker compose down -v
docker compose up --build
```

The API will be available at:

```
http://localhost:8000
```

Swagger documentation:

```
http://localhost:8000/docs
```

---

# 🔧 Configuration

All configuration is managed using environment variables.

Configuration files:

```
.env.example
core/settings.py
docs/deployment.md
```

---

# 🔌 API

## Search Endpoint

```
POST /api/v1/search
```

Search pipeline:

```
User Query
    |
    v
Firewall Validation
    |
    v
Query Routing
    |
    v
Hybrid Retrieval
    |
    v
Ranking
    |
    v
Final Response
```

Full API documentation:

```
/docs
```

---

# 🗄️ Database

Database:

```
PostgreSQL
```

Extension:

```
pgvector
```

Capabilities:

- Vector storage
- Similarity search
- Retrieval analytics
- Request tracing

Observability table:

```
retrieval_logs
```

Detailed documentation:

```
docs/database.md
```

---

# 📈 Observability

The system provides:

## Request Tracking

- Complete request lifecycle tracing
- Pipeline execution monitoring

## Performance Monitoring

- Latency breakdown
- Stage-level timing

## Retrieval Quality

- Query routing signals
- Confidence estimation
- Retrieval mode analysis

## Cache Monitoring

- Cache hit ratio
- Query reuse analysis

---

# 🐋 Docker Architecture

The Docker setup follows production best practices:

Features:

- Multi-stage Docker build
- Optimized production image
- Slim runtime environment
- Non-root execution user
- Secure permissions handling
- Persistent volume support

Main files:

```
Dockerfile
docker-compose.yml
```

---

# 🛣️ Future Roadmap

Planned improvements:

## Ranking Intelligence

- A/B testing framework
- Automated golden dataset generation
- Learned reranker models

## Monitoring

- Advanced analytics dashboard
- Retrieval quality visualization

## Scalability

- Horizontal scaling
- Kubernetes deployment
- Distributed retrieval infrastructure

---

# 🤝 Contributing

Contributions are welcome.

Please review:

```
CONTRIBUTING.md
```

before submitting changes.

---

# 📄 License

This project is licensed under the:

```
MIT License
```

---

# ❤️ About

Built with a focus on:

- High-quality retrieval
- Production reliability
- Scalable AI architecture
- Real-world search experience

**Made with ❤️ for intelligent video template discovery.**
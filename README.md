# ⚡ Webhook Gateway & Event Delivery Engine

A production-ready, asynchronous Webhook Ingestion & Delivery Gateway built with **FastAPI**, **PostgreSQL (SQLAlchemy 2.0 asyncpg)**, **Redis**, and **Celery**. 

Features token bucket rate limiting per user tier, HMAC-SHA256 request signing, exponential backoff retries, and comprehensive delivery audit logs.

---

## Key Features

* **High-Throughput Ingestion:** Powered by asynchronous FastAPI and Celery background workers.
* **Token Bucket Rate Limiting:** Atomic Redis Lua scripts enforcing granular per-minute limits by subscription tier (`FREE`, `PRO`, `ENTERPRISE`).
* **Cryptographic Security:** End-to-end HMAC-SHA256 webhook signatures (`X-Webhook-Signature`) with timestamp drift verification to prevent replay attacks.
* **Automatic Retries:** Exponential backoff delivery retries with automatic failure handling.
* **Developer API Keys:** Scoped API key provisioning (`wh_live_...`) with fast SHA-256 hashed database indexing.
* **Full Audit Logging:** Detailed tracking of HTTP status codes, latency in milliseconds, payloads, and response bodies.

---

## Tech Stack

* **Framework:** FastAPI (Python 3.12+)
* **Database:** PostgreSQL (Async via `asyncpg` + `SQLAlchemy 2.0`)
* **Migrations:** Alembic
* **Task Queue & Caching:** Celery + Redis
* **Package Manager:** `uv`

---

## Getting Started

### 1. Prerequisites
Ensure you have PostgreSQL and Redis instances running locally or via Docker:

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7-alpine
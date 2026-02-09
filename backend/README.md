# ⚡ ElectroMart – Backend

ElectroMart is a FastAPI-based backend that powers an AI-driven **sales, marketing, and support system** for an e-commerce platform.  
It uses **agent-based LLM workflows**, **PostgreSQL + pgvector**, and **OpenAI models** to deliver intelligent responses and lead generation.

---

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL 16 + pgvector
- **ORM**: SQLAlchemy
- **AI / LLMs**: OpenAI (`gpt-4o-mini`)
- **Embeddings**: OpenAI embeddings (optional)
- **Containerization**: Docker + Docker Compose
- **Dev Tooling**: uv, uvicorn, pytest

---

## Project Structure (Simplified)

```
electromart/
│
├─ app/
│  ├─ main.py
│  ├─ seed.py
│  ├─ core/
│  ├─ services/
│  ├─ schemas/
│  ├─ agents/
│  ├─ models/
│
├─ docker/
│  └─ db-init/
│     └─ 001_pgvector.sql
│
├─ scripts
├─ tests
├─ docker-compose.yml
├─ .env
├─ README.md
├─ ARCHITECTURE.md
```

---

## Prerequisites

- Docker Desktop
- Python 3.11+
- uv (`pip install uv`)

---

## Environment Variables

Create a `.env` file in the project root:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=electromart
POSTGRES_PORT=5433

DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/electromart

OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4o-mini

EMBED_MODEL=text-embedding-3-small

SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=example_user
SMTP_PASS=example_password
SALES_TO_EMAIL=sales@example.com
```

---

## Database Setup

```bash
docker compose up -d db
```

Reset database:

```bash
docker compose down -v
docker compose up -d db
```

---

## Dependency Management (uv)

Sync dependencies:

```bash
uv sync
```

Add dependency:

```bash
uv add <package>
```

Add dev dependency:

```bash
uv add --dev <package>
```

Remove dependency:

```bash
uv remove <package>
```

Upgrade dependencies:

```bash
uv lock --upgrade
uv sync
```

Run inside uv env:

```bash
uv run python -m app.seed
uv run --active uvicorn app.main:app --reload --port 8001
```

---

## Seed the Database

```bash
uv run python -m app.seed
```

---

## Run the API Server

```bash
uv run --active uvicorn app.main:app --reload --port 8001
```

- API: http://localhost:8001
- Swagger: http://localhost:8001/docs

---

## Quick Start

```bash
docker compose up -d db
uv sync
uv run python -m app.seed
uv run --active uvicorn app.main:app --reload --port 8001
```

---

Maintained by Kusal Dissanayake

<h1 align="center">DevCrew — AI Dev Team Backend</h1>

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python"/></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI"/></a>
  <a href="https://langchain-ai.github.io/langgraph"><img src="https://img.shields.io/badge/LangGraph-0.1+-purple.svg" alt="LangGraph"/></a>
  <a href="https://postgresql.org"><img src="https://img.shields.io/badge/PostgreSQL-15+-blue.svg" alt="PostgreSQL"/></a>
  <a href="https://github.com/pgvector/pgvector"><img src="https://img.shields.io/badge/pgvector-0.5+-orange.svg" alt="pgvector"/></a>
  <a href="https://docker.com"><img src="https://img.shields.io/badge/Docker-Ready-blue.svg" alt="Docker"/></a>
  <a href="https://groq.com"><img src="https://img.shields.io/badge/Groq-llama--3.3--70b-red.svg" alt="Groq"/></a>
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"/>
</p>

<p align="center">
  A multi-agent AI backend that helps developers understand codebases, review pull requests, debug issues, generate tests, and maintain documentation.
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Codebase Q&A** | Semantic code search with pgvector + natural language Q&A |
| **PR Review** | Automated PR analysis with one-click fix application to GitHub branches |
| **Debug Agent** | Root cause analysis and fix suggestions from error messages |
| **Test Generator** | Unit, edge case, and integration test generation for any file |
| **Documentation** | README, API reference, and architecture doc generation |
| **Team Mode** | Multi-agent SSE streaming pipeline with repo health scoring |
| **Architecture Graph** | AST-based dependency graph for any GitHub repo |

---

## ⚡ Quick Start

**Prerequisites:** Docker, Docker Compose, GitHub OAuth App, Groq API Key

```bash
# 1. Clone
git clone <REPO_URL>
cd <REPO_NAME>

# 2. Environment
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)

# 3. Start
docker-compose up --build
```

> ⏳ First startup downloads the HuggingFace embedding model (~280MB). Subsequent starts are instant.

---

## 🔐 Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=devcrew
DATABASE_URL=postgresql://postgres:your_password@db:5432/devcrew

# Backend
FASTAPI_PORT=8000
SECRET_KEY=your_secret_key_here        # see below for how to generate

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_URL=https://github.com
GITHUB_API_URL=https://api.github.com

# Groq
GROQ_API_KEY=your_groq_api_key

# Frontend
FRONTEND_URL=https://devcrew-web.vercel.app
```

**Generate a SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🔑 GitHub OAuth Setup

1. Go to [github.com/settings/developers](https://github.com/settings/developers) → **New OAuth App**
2. Fill in:
   - **Homepage URL:** `http://localhost:5173`
   - **Authorization callback URL:** `http://localhost:8000/auth/github/callback`
3. Copy **Client ID** and **Client Secret** into `.env`

---

## 🤖 Groq API Key

1. Sign up at [console.groq.com](https://console.groq.com) — free tier available (100K tokens/day)
2. Go to **API Keys** → **Create API Key**
3. Copy the key into `.env` as `GROQ_API_KEY`

---

## 🔗 Service URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| PostgreSQL (external) | `localhost:5433` |
| Frontend | http://localhost:5173 |

> PostgreSQL is mapped to port `5433` externally to avoid conflicts with any locally installed PostgreSQL. Use this port in DBeaver or any DB client.

---

## 🐳 Docker

```bash
# Start
docker-compose up --build

# Stop
docker-compose down

# Reset database (⚠️ deletes all data)
docker-compose down -v && docker-compose up --build
```

---

## 📖 Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](./docs/architecture.md) | System design, folder structure, request lifecycle, key decisions |
| [Agents](./docs/agents.md) | Agent flow diagrams — codebase Q&A, PR review, debug, test, team mode, architecture graph |
| [Database](./docs/database.md) | DB models, pgvector search, schema |
| [API](./docs/api.md) | All endpoints with request/response examples |
| [Decisions](./docs/decisions.md) | Why pgvector, Groq, LangGraph, SSE, and other key choices |

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL 15 + pgvector |
| LLM | Groq — llama-3.3-70b-versatile |
| Embeddings | HuggingFace (local) |
| Multi-Agent | LangGraph |
| Auth | GitHub OAuth 2.0 + JWT |
| Containerization | Docker Compose |

---

## 🆘 Troubleshooting

**Port already in use**
```bash
lsof -i :8000
# Or change FASTAPI_PORT in .env
```

**Tables missing / schema errors**
```bash
docker-compose down -v && docker-compose up --build
```

**GitHub OAuth callback error**
- Verify callback URL in GitHub OAuth App settings: `http://localhost:8000/auth/github/callback`
- Check `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env`

**Groq rate limit (429)**
- Free tier: 100K tokens/day — resets daily
- Wait for reset or upgrade at [console.groq.com](https://console.groq.com/settings/billing)

**Embedding model download stuck**
- Wait for `Application startup complete` in logs — first download is ~280MB

---

## 🙌 Contributing

1. Open an issue describing the change
2. Fork → create a feature branch
3. Open a PR with a clear description

---

<p align="center">Built with ❤️ by the DevCrew Team</p>

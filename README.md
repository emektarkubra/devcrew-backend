<p align="center">
  <img src="./banner.png" alt="DevCrew Banner" width="100%" />
</p>

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

## 🎬 Demo

<p align="center">
  <img src="./demo.gif" alt="DevCrew Demo" width="100%" />
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
# Edit .env with your credentials

# 3. Start
docker-compose up --build
```

> ⏳ First startup downloads the HuggingFace embedding model (~280MB). Subsequent starts are instant.

---

## 🔐 Environment Variables

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DB=devcrew
DATABASE_URL=postgresql://postgres:your_password@db:5432/devcrew

# FastAPI
FASTAPI_PORT=8000
SECRET_KEY=your_secret_key_here

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_URL=https://github.com
GITHUB_API_URL=https://api.github.com

# Groq
GROQ_API_KEY=your_groq_api_key

# Frontend
FRONTEND_URL=http://localhost:5173
```

### GitHub OAuth App

1. [github.com/settings/developers](https://github.com/settings/developers) → **New OAuth App**
2. **Homepage URL:** `http://localhost:5173`
3. **Callback URL:** `http://localhost:8000/auth/github/callback`
4. Copy `Client ID` and `Client Secret` to `.env`

### Groq API Key

1. Sign up at [console.groq.com](https://console.groq.com) — free tier available
2. **API Keys** → **Create API Key** → copy to `.env`

---

## 🔗 Service URLs

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| PostgreSQL (DBeaver) | `localhost:5433` |
| Frontend | http://localhost:5173 |

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
- Verify callback URL in GitHub OAuth App: `http://localhost:8000/auth/github/callback`
- Check `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` in `.env`

**Groq rate limit (429)**
- Free tier: 100k tokens/day
- Wait for daily reset or upgrade at [console.groq.com](https://console.groq.com)

**Embedding model download stuck**
- Wait for `Application startup complete` in logs — first download is ~280MB

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

## 🙌 Contributing

1. Open an issue describing the change
2. Fork → create a feature branch
3. Open a PR with a clear description

---

<p align="center">Built with ❤️ by the DevCrew Team</p>
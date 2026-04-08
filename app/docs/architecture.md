# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DevCrew Backend                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Client Layer                                                   │
│  ├── React + Vite Frontend (http://localhost:5173)             │
│  └── GitHub OAuth Callbacks                                     │
│                                                                 │
│  API Gateway Layer                                              │
│  ├── FastAPI Application (app/main.py)                         │
│  ├── CORS Middleware                                            │
│  ├── JWT Authentication                                         │
│  └── AppError Exception Handler                                 │
│                                                                 │
│  Route Layer                                                    │
│  ├── /auth      — GitHub OAuth + JWT                           │
│  ├── /profile   — User profile + repo list                     │
│  ├── /repos     — Repo stats                                   │
│  └── /agents    — All AI agent endpoints                       │
│                                                                 │
│  Service Layer                                                  │
│  ├── codebase_qa.py      — Embedding search + LLM Q&A          │
│  ├── pr_review.py        — Diff fetch + review + fix apply     │
│  ├── debugging.py        — Error analysis + fix suggestion      │
│  ├── test_generator.py   — Test generation                      │
│  ├── documentation.py    — Doc generation                       │
│  ├── indexer.py          — Repo embedding pipeline              │
│  ├── architecture.py     — AST dependency graph                 │
│  └── team_mode/          — LangGraph multi-agent pipeline       │
│                                                                 │
│  Data Layer                                                     │
│  ├── PostgreSQL 15 + pgvector                                   │
│  └── SQLAlchemy ORM Models                                      │
│                                                                 │
│  Integration Layer                                              │
│  ├── Groq API (llama-3.3-70b-versatile)                        │
│  ├── HuggingFace Embeddings (local, 768-dim)                   │
│  └── GitHub REST API                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
app/
├── main.py                          # FastAPI app + router registration
│
├── core/
│   ├── config.py                    # Pydantic Settings — env variables
│   ├── database.py                  # SQLAlchemy engine + session factory
│   ├── exceptions.py                # AppError base exception
│   ├── error_handlers.py            # Global FastAPI exception handler
│   ├── prompts.py                   # All LLM PromptTemplate definitions
│   └── constants.py                 # TESTABLE_EXTENSIONS, EXCLUDE_PATTERNS
│
├── models/
│   ├── __init__.py                  # Model module imports
│   ├── user.py                      # GitHub OAuth profile
│   ├── repo.py                      # Synced GitHub repos
│   ├── embedding.py                 # CodeEmbedding — pgvector chunks
│   ├── code_query_history.py
│   ├── pr_review_history.py
│   ├── debug_history.py
│   ├── documentation_history.py
│   ├── test_history.py
│   └── team_mode_history.py
│
├── schemas/
│   ├── agents.py                    # Agent request/response schemas
│   ├── repos.py                     # Repo schemas
│   └── users.py                     # User schemas
│
├── routes/
│   ├── router.py                    # Main router — registers all sub-routers
│   ├── agents.py                    # All /agents/* endpoints
│   ├── users.py                     # /auth/* + /profile endpoints
│   └── health.py                    # /health endpoint
│
└── services/
    ├── repo_service.py              # fetch_all_repo_files()
    ├── user_service.py              # sync_user_repos()
    └── agents/
        ├── indexer.py               # get_embedding() + index_repo()
        ├── codebase_qa.py           # answer_codebase_question()
        ├── pr_review.py             # review_pr() + apply_fixes_to_branch()
        ├── debugging.py             # debug_error()
        ├── test_generator.py        # generate_tests()
        ├── documentation.py         # generate_documentation()
        ├── architecture.py          # analyze_architecture()
        └── team_mode/
            ├── __init__.py          # run_team_mode()
            ├── graph.py             # build_graph() — LangGraph StateGraph
            └── nodes.py             # Agent node functions + make_nodes()
```

---

## Request Lifecycle

```
Client Request
      │
      ▼
FastAPI CORS Middleware
      │
      ▼
JWT Auth (token extracted from query param or header)
      │
      ▼
Route Handler (app/routes/agents.py)
      │
      ├── get_current_user_id(token)
      ├── db.query(User).filter(...)
      └── call service function
              │
              ▼
        Service Layer
        ├── GitHub API calls (httpx)
        ├── LLM calls (Groq via LangChain)
        ├── DB reads/writes (SQLAlchemy)
        └── Embedding search (pgvector)
              │
              ▼
        Response / SSE Stream
```

---

## Error Handling

All routes follow a consistent pattern using `AppError`:

```python
try:
    result = await some_operation()
    return result
except AppError:
    raise  # Re-raise known errors as-is
except Exception as e:
    raise AppError(
        code="OPERATION_ERROR",
        message="Human readable message.",
        status_code=500,
        details={"error": str(e)},
    ) from e
```

`AppError` is caught globally by `error_handlers.py` and returned as a structured JSON response:

```json
{
  "code": "OPERATION_ERROR",
  "message": "Human readable message.",
  "details": { "error": "..." }
}
```

---

## Key Design Decisions

### Why pgvector over a dedicated vector DB?
Everything stays in one PostgreSQL instance — no additional infrastructure. pgvector's cosine similarity search is fast enough for per-user per-repo queries at this scale, and it ships free with the Docker setup.

### Why Groq?
Groq's free tier offers fast inference (llama-3.3-70b-versatile) without GPU requirements. The 100k daily token limit is managed through a hybrid model strategy in Team Mode — large model for deep analysis, small model for structural decisions.

### Why LangGraph for Team Mode?
Team Mode needs sequential agent execution with retry logic, shared state, and SSE streaming. LangGraph's `StateGraph` provides exactly this — supervisor → agent → validator → aggregator is a clean directed graph with minimal boilerplate.

### Why ground PR fixes on real file content?
Fix generation fetches the actual file content from the PR branch (not just the diff context). This significantly reduces LLM hallucinations where models invent code that doesn't fit the surrounding context.

### Why separate history tables per agent?
Each agent has a different result structure. A single `history` table with a JSON `result` column was considered, but separate tables allow typed queries, easier filtering, and cleaner schema evolution per agent.
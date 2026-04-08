# Database

DevCrew uses **PostgreSQL 15 + pgvector** with SQLAlchemy ORM. All models are in `app/models/`.

---

## Connection

```python
# app/core/database.py
DATABASE_URL = settings.DATABASE_URL  # from .env

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

External port for DBeaver / GUI clients: `localhost:5433`

---

## Models

### `users`

```python
class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True)
    github_id    = Column(String, unique=True, nullable=False)
    username     = Column(String, nullable=False)
    email        = Column(String, nullable=True)
    avatar_url   = Column(String, nullable=True)
    access_token = Column(String, nullable=False)  # GitHub OAuth token
    created_at   = Column(DateTime, server_default=func.now())
```

Created on first GitHub OAuth login. `access_token` is used for all GitHub API calls on behalf of the user.

---

### `repos`

```python
class Repo(Base):
    __tablename__ = "repos"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"))
    github_id   = Column(Integer, nullable=False)
    name        = Column(String, nullable=False)
    full_name   = Column(String, nullable=False)
    description = Column(String, nullable=True)
    language    = Column(String, nullable=True)
    is_private  = Column(Boolean, default=False)
    created_at  = Column(DateTime, server_default=func.now())
```

Synced from GitHub on login via `sync_user_repos()`. Used for repo selection across all agent screens.

---

### `embeddings`

```python
class CodeEmbedding(Base):
    __tablename__ = "embeddings"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String, nullable=False)   # "owner/repo"
    file_path  = Column(String, nullable=False)
    chunk_text = Column(String, nullable=False)
    embedding  = Column(Vector(768), nullable=False)  # pgvector
    created_at = Column(DateTime, server_default=func.now())
```

Each repo file is split into 1000-character chunks. Each chunk is embedded with HuggingFace and stored as a 768-dimensional vector.

**Similarity search:**

```python
results = (
    db.query(CodeEmbedding)
    .filter(
        CodeEmbedding.user_id == user_id,
        CodeEmbedding.repo    == repo,
    )
    .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
    .limit(5)
    .all()
)
```

---

### `code_query_history`

```python
class CodeQueryHistory(Base):
    __tablename__ = "code_query_history"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String, nullable=False)
    query      = Column(String, nullable=False)
    response   = Column(String, nullable=False)
    files      = Column(JSON, nullable=True)     # source files used
    created_at = Column(DateTime, server_default=func.now())
```

---

### `pr_review_history`

```python
class PRReviewHistory(Base):
    __tablename__ = "pr_review_history"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String, nullable=False)
    pr_number  = Column(Integer, nullable=False)
    report     = Column(JSON, nullable=False)    # { issues, suggestions, score }
    fixes      = Column(JSON, nullable=True)     # { original, fixed } pairs
    created_at = Column(DateTime, server_default=func.now())
```

---

### `debug_history`

```python
class DebugHistory(Base):
    __tablename__ = "debug_history"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    repo          = Column(String, nullable=True)
    error_message = Column(String, nullable=False)
    root_cause    = Column(String, nullable=True)
    solution      = Column(String, nullable=True)
    code_fix      = Column(String, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
```

---

### `documentation_history`

```python
class DocumentationHistory(Base):
    __tablename__ = "documentation_history"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String, nullable=False)
    doc_type   = Column(String, nullable=False)  # readme | api | architecture
    markdown   = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

---

### `test_history`

```python
class TestHistory(Base):
    __tablename__ = "test_history"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"))
    repo        = Column(String, nullable=False)
    target      = Column(String, nullable=False)   # file path
    framework   = Column(String, nullable=False)   # pytest | jest | ...
    tests       = Column(JSON, nullable=False)     # test objects array
    test_count  = Column(Integer, nullable=True)
    coverage    = Column(Integer, nullable=True)   # estimated %
    created_at  = Column(DateTime, server_default=func.now())
```

---

### `team_mode_history`

```python
class TeamModeHistory(Base):
    __tablename__ = "team_mode_history"

    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"))
    repo         = Column(String, nullable=False)
    agents       = Column(JSON, nullable=False)    # ["codebase", "test", ...]
    results      = Column(JSON, nullable=False)    # per-agent output
    health_score = Column(Integer, nullable=True)  # 0-100
    summary      = Column(String, nullable=True)
    top_actions  = Column(JSON, nullable=True)     # string[]
    created_at   = Column(DateTime, server_default=func.now())
```

---

## Summary Table

| Table | Purpose | Key JSON Fields |
|-------|---------|----------------|
| `users` | GitHub OAuth profiles | — |
| `repos` | Synced GitHub repos | — |
| `embeddings` | pgvector code chunks | `embedding (vector 768)` |
| `code_query_history` | Codebase Q&A history | `files[]` |
| `pr_review_history` | PR review reports | `report{}`, `fixes[]` |
| `debug_history` | Debug sessions | — |
| `documentation_history` | Generated docs | — |
| `test_history` | Generated tests | `tests[]` |
| `team_mode_history` | Team mode runs | `agents[]`, `results{}`, `top_actions[]` |

---

## Schema Reset

For schema changes, drop all volumes and rebuild:

```bash
docker-compose down -v && docker-compose up --build
```

> ⚠️ This deletes all data including embeddings. Repos will be re-indexed on next Codebase Q&A query.
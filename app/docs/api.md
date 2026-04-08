# API Reference

Base URL: `http://localhost:8000`

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)

---

## Authentication

All endpoints except `/auth/*` require a JWT token passed as a query parameter or request body field named `token`.

```bash
# Example
POST /agents/codebase-qa
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "owner": "myorg",
  "repo": "myrepo",
  "query": "How does authentication work?"
}
```

---

## Auth

### `GET /auth/github`
Initiates GitHub OAuth flow. Redirects to GitHub login page.

### `GET /auth/github/callback`
OAuth callback. Called by GitHub after user authorizes.

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Profile & Repos

### `GET /profile?token=...`
Returns authenticated user profile.

**Response:**
```json
{
  "id": 1,
  "github_id": "12345678",
  "username": "myorg",
  "email": "user@example.com",
  "avatar_url": "https://avatars.githubusercontent.com/u/..."
}
```

### `GET /repos?token=...`
Returns user's GitHub repo list (synced from GitHub).

**Response:**
```json
[
  {
    "id": 1,
    "full_name": "myorg/my-repo",
    "name": "my-repo",
    "language": "Python",
    "is_private": false,
    "description": "AI dev team backend"
  }
]
```

### `GET /repos/stats?token=...`
Returns repo activity statistics.

---

## Agents

### Codebase Q&A

#### `POST /agents/codebase-qa`
Ask a natural language question about a codebase.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "query": "How does the PR review agent work?"
}
```

**Response:**
```json
{
  "answer": "The PR review agent fetches the diff from GitHub API...",
  "sources": ["app/services/agents/pr_review.py", "app/routes/agents.py"]
}
```

> First query for a repo triggers auto-indexing (~30s for large repos).

---

#### `POST /agents/codebase-qa/history`
Fetch past Q&A sessions for a repo.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

**Response:**
```json
[
  {
    "id": 1,
    "query": "How does auth work?",
    "response": "...",
    "files": ["app/routes/users.py"],
    "created_at": "2026-04-07T10:00:00"
  }
]
```

---

### PR Review

#### `POST /agents/pr-review`
Review an open pull request.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "pr_number": 42
}
```

**Response:**
```json
{
  "pr_number": 42,
  "score": 78,
  "issues": [
    {
      "title": "Missing error handling",
      "severity": "high",
      "file": "app/routes/agents.py",
      "line": 120,
      "description": "..."
    }
  ],
  "suggestions": ["Add try/except around GitHub API call", "..."]
}
```

---

#### `POST /agents/pr-review/generate-fixes`
Generate fix suggestions for a reviewed PR.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "pr_number": 42
}
```

**Response:**
```json
{
  "fixes": [
    {
      "file": "app/routes/agents.py",
      "original": "result = github_api.get_pr(pr_number)",
      "fixed": "try:\n    result = github_api.get_pr(pr_number)\nexcept Exception as e:\n    raise AppError(...)"
    }
  ]
}
```

---

#### `POST /agents/pr-review/apply-fixes`
Apply generated fixes directly to the PR branch via GitHub Contents API.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "pr_number": 42,
  "fixes": [
    {
      "file": "app/routes/agents.py",
      "original": "...",
      "fixed": "..."
    }
  ]
}
```

**Response:**
```json
{
  "applied": ["app/routes/agents.py"],
  "failed": []
}
```

---

#### `POST /agents/pr-review/history`
Fetch past PR review reports.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

---

### Debug

#### `POST /agents/debug`
Analyze an error message and get root cause + fix.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "error_message": "AttributeError: 'NoneType' object has no attribute 'id'",
  "code_context": "user = db.query(User).first()\nprint(user.id)"
}
```

**Response:**
```json
{
  "root_cause": "db.query(User).first() returns None when no user exists.",
  "explanation": "...",
  "solution": "Check if user is None before accessing .id",
  "code_fix": "user = db.query(User).first()\nif user is None:\n    raise AppError(...)\nprint(user.id)"
}
```

---

#### `POST /agents/debug/history`
Fetch past debug sessions.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

---

### Test Generator

#### `POST /agents/test-generator`
Generate tests for a specific file.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "target": "app/services/agents/pr_review.py",
  "framework": "pytest"
}
```

Supported frameworks: `pytest`, `jest`, `mocha`, `rspec`, `junit`

**Response:**
```json
{
  "tests": [
    {
      "name": "test_review_pr_returns_score",
      "type": "unit",
      "description": "Verifies review_pr returns a score between 0 and 100",
      "code": "def test_review_pr_returns_score():\n    ..."
    }
  ],
  "testCount": 8,
  "unitCount": 5,
  "edgeCount": 2,
  "integrationCount": 1,
  "coverage": 82
}
```

---

#### `POST /agents/test-generator/history`
Fetch past test generation sessions.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

---

### Documentation

#### `POST /agents/documentation`
Generate documentation for a repo.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo",
  "doc_type": "readme"
}
```

Supported doc types: `readme`, `api`, `architecture`

**Response:**
```json
{
  "markdown": "# my-repo\n\nAI Dev Team Backend...",
  "doc_type": "readme"
}
```

---

#### `POST /agents/documentation/history`
Fetch past documentation generation sessions.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

---

### Team Mode

#### `GET /agents/team-mode/stream`
Run multiple agents sequentially with SSE streaming.

**Query Parameters:**

| Param | Type | Example |
|-------|------|---------|
| `token` | string | `eyJhbGci...` |
| `owner` | string | `myorg` |
| `repo` | string | `my-repo` |
| `selected_agents` | comma-separated | `codebase,pr_review,test,documentation` |

**SSE Events:**

```
event: agent_start
data: {"agent": "codebase"}

event: agent_done
data: {"agent": "codebase", "summary": "...", "actions": [...], "score": 72}

event: agent_start
data: {"agent": "pr_review"}

event: agent_done
data: {"agent": "pr_review", "summary": "...", "actions": [...], "score": 100}

event: complete
data: {
  "health_score": 86,
  "summary": "...",
  "top_actions": ["...", "..."],
  "results": {
    "codebase": { "score": 72, "issues": [...] },
    "pr_review": { "score": 100, "pr_count": 0 }
  }
}
```

**Frontend usage (EventSource):**
```typescript
const es = new EventSource(
  `/agents/team-mode/stream?token=${token}&owner=${owner}&repo=${repo}&selected_agents=codebase,pr_review`
)

es.addEventListener('agent_start', (e) => { ... })
es.addEventListener('agent_done',  (e) => { ... })
es.addEventListener('complete',    (e) => { es.close() })
es.addEventListener('error',       (e) => { es.close() })
```

---

#### `POST /agents/team-mode/history`
Fetch past team mode runs for the authenticated user.

**Request:**
```json
{
  "token": "..."
}
```

**Response:**
```json
[
  {
    "id": 1,
    "repo": "myorg/my-repo",
    "agents": ["codebase", "pr_review"],
    "health_score": 86,
    "summary": "...",
    "top_actions": ["...", "..."],
    "results": { ... },
    "timeAgo": "2026-04-07T10:00:00"
  }
]
```

---

### Architecture Graph

#### `GET /agents/architecture`
Analyze a repo's dependency graph using AST import analysis.

**Query Parameters:**

| Param | Type | Example |
|-------|------|---------|
| `token` | string | `eyJhbGci...` |
| `owner` | string | `myorg` |
| `repo` | string | `my-repo` |

**Response:**
```json
{
  "repo": "myorg/my-repo",
  "nodes": [
    {
      "id": "1",
      "type": "serviceNode",
      "position": { "x": 0, "y": 0 },
      "data": {
        "label": "agents.py",
        "type": "service",
        "language": "Python",
        "path": "app/routes/agents.py",
        "description": "Manages all agent endpoints."
      }
    }
  ],
  "edges": [
    {
      "id": "e1-2",
      "source": "1",
      "target": "2",
      "animated": true,
      "className": "architecture-graph__edge architecture-graph__edge--service"
    }
  ]
}
```

---

### Utilities

#### `POST /agents/repo-files`
List all files in a repo.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

**Response:**
```json
{
  "files": [
    "app/main.py",
    "app/routes/agents.py",
    "app/services/agents/pr_review.py"
  ]
}
```

---

#### `POST /agents/index`
Manually trigger embedding indexing for a repo.

**Request:**
```json
{
  "token": "...",
  "owner": "myorg",
  "repo": "my-repo"
}
```

**Response:**
```json
{
  "indexed": 142,
  "repo": "myorg/my-repo"
}
```

---

## Error Responses

All errors follow a consistent structure:

```json
{
  "code": "USER_NOT_FOUND",
  "message": "User not found.",
  "details": { "user_id": 42 }
}
```

| HTTP Status | When |
|-------------|------|
| `400` | Invalid request parameters |
| `401` | Missing or invalid token |
| `404` | Resource not found |
| `500` | Internal server error |
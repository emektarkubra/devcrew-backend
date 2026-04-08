# Agents

DevCrew has 7 agent modules. Each agent is a standalone async service function called from `app/routes/agents.py`.

---

## 1. Codebase Q&A

**File:** `app/services/agents/codebase_qa.py`

### Flow

```
User question (natural language)
        │
        ▼
get_embedding(question)  →  768-dim vector
        │
        ▼
pgvector cosine_distance search
  ├── Filter: user_id + repo
  └── Limit: top 5 chunks
        │
        ▼
CODEBASE_QA_PROMPT
  ├── context: relevant chunks
  └── query: user question
        │
        ▼
Groq LLM (llama-3.3-70b-versatile)
        │
        ▼
Answer + source file list
        │
        ▼
code_query_history ← save
```

### Auto-indexing

On the first query for a repo, `index_repo()` is triggered automatically:

```
fetch_all_repo_files()
        │
        ▼
Filter by supported extensions
        │
        ▼
Split each file into 1000-char chunks
        │
        ▼
HuggingFace: generate 768-dim embedding per chunk
        │
        ▼
Upsert into embeddings table (pgvector)
```

---

## 2. PR Review + Fix Application

**File:** `app/services/agents/pr_review.py`

### Flow

```
PR number selection
        │
        ▼
GitHub API: fetch open PRs
        │
        ▼
fetch_pr_diff(pr_number)  →  unified diff
        │
        ▼
PR_REVIEW_PROMPT + diff
        │
        ▼
Groq LLM
        │
        ▼
Review report
  ├── issues[]
  ├── suggestions[]
  └── score (0-100)
        │
        ├──► pr_review_history ← save
        │
        └──► [User clicks "Apply Fixes"]
                │
                ▼
        generate_fixes():
        GitHub API → fetch REAL file content from PR branch
                │
                ▼
        LLM: generate { original, fixed } pairs
                │
                ▼
        apply_fixes_to_branch():
        GitHub Contents API → commit directly to PR branch
```

> **Key design**: Fixes are generated from actual file content (not diff context) to minimize LLM hallucination.

---

## 3. Debug Agent

**File:** `app/services/agents/debugging.py`

### Flow

```
Error message + (optional) code snippet
        │
        ▼
DEBUG_PROMPT
  ├── error_message
  └── code_context (optional)
        │
        ▼
Groq LLM
        │
        ▼
{
  "root_cause":  "...",
  "explanation": "...",
  "solution":    "...",
  "code_fix":    "..."
}
        │
        ▼
debug_history ← save
```

---

## 4. Test Generator

**File:** `app/services/agents/test_generator.py`

### Flow

```
Target file selection
        │
        ▼
GitHub API: fetch file content
        │
        ▼
TEST_GENERATOR_PROMPT
  ├── content: file source
  ├── framework: pytest | jest | mocha | rspec | junit
  └── file_path
        │
        ▼
Groq LLM
        │
        ▼
{
  "tests": [
    { "name": "...", "type": "unit|edge|integration", "code": "..." }
  ],
  "unitCount": N,
  "edgeCount": N,
  "integrationCount": N,
  "coverage": N
}
        │
        ▼
test_history ← save
```

### File Prioritization

Routes and services are analyzed before config/spec files:

```python
PRIORITY_DIRS = [
    "routes/", "routers/", "services/", "service/",
    "controllers/", "handlers/", "pages/", "components/",
]

EXCLUDE_PATTERNS = [
    "test", "spec", "migration", "alembic",
    "node_modules", ".git", "dist", "build",
    "constants.py", "config.py", "settings.py",
]
```

---

## 5. Documentation Agent

**File:** `app/services/agents/documentation.py`

### Flow

```
Repo + doc_type (readme | api | architecture)
        │
        ▼
fetch_all_repo_files()  →  file list
        │
        ▼
Sample file contents for context
        │
        ▼
DOC_PROMPT (type-specific template)
        │
        ▼
Groq LLM  →  Markdown output
        │
        ▼
documentation_history ← save
```

---

## 6. Team Mode — LangGraph SSE Pipeline

**Files:** `app/services/agents/team_mode/`

### Flow

```
Client → GET /agents/team-mode/stream?selected_agents=codebase,pr_review,...
                          │
                          ▼
                   ┌─────────────────┐
                   │   Supervisor    │  picks next agent from queue
                   └────────┬────────┘
                            │
              ┌─────────────▼──────────────┐
              │   SSE: agent_start event    │ ──► Client
              └─────────────┬──────────────┘
                            │
        ┌───────────────────▼───────────────────┐
        │         Agent Node runs               │
        │  codebase / pr_review / test / doc    │
        └───────────────────┬───────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │   SSE: agent_done event     │ ──► Client
              └─────────────┬──────────────┘
                            │
                   ┌────────▼────────┐
                   │  Validator Node  │  done / retry decision
                   └────────┬────────┘
                            │
                   More agents?
                    ├── YES → Supervisor
                    └── NO  ↓
                   ┌────────▼────────┐
                   │ Aggregator Node  │  health_score + summary + top_actions
                   └────────┬────────┘
                            │
              ┌─────────────▼──────────────┐
              │   SSE: complete event       │ ──► Client
              └─────────────┬──────────────┘
                            │
                   team_mode_history ← save
```

### SSE Event Schema

| Event | Payload |
|-------|---------|
| `agent_start` | `{ agent: string }` |
| `agent_done` | `{ agent, summary, actions[], score }` |
| `complete` | `{ health_score, summary, top_actions[], results{} }` |
| `error` | `{ message: string }` |

### Model Strategy

| Node | Model | Reason |
|------|-------|--------|
| `codebase` | `llama-3.3-70b-versatile` | Deep code quality analysis |
| `pr_review` | `llama-3.3-70b-versatile` | Security + risk assessment |
| `test` | internal model | File-level test generation |
| `documentation` | internal model | Doc generation |
| `validator` | `llama-3.1-8b-instant` | Simple done/retry JSON decision |
| `aggregator` | `llama-3.1-8b-instant` | JSON aggregation — no deep reasoning needed |

### LangGraph Node Structure

```
make_nodes(db, user_id)
  ├── codebase_agent_node   →  _codebase(state, db, user_id)
  ├── pr_review_agent_node  →  _pr_review(state)
  ├── test_agent_node       →  _test(state, db, user_id)
  └── doc_agent_node        →  _doc(state, db, user_id)

supervisor_node(state)      →  picks next agent or routes to aggregator
validator_node(state)       →  done / retry decision per agent
aggregator_node(state)      →  final health report
```

---

## 7. Architecture Graph

**File:** `app/services/agents/architecture.py`

### Flow

```
owner/repo
        │
        ▼
GitHub API: GET /repos/{owner}/{repo}/git/trees/HEAD?recursive=1
        │
        ▼
Filter: .py .ts .tsx .js .jsx
Exclude: test, spec, migration, node_modules, dist, build ...
        │
        ▼
Prioritize: routes/ > services/ > models/ > core/ > schemas/
Limit: top 40 files
        │
        ▼
Per file:
  ├── GitHub API: fetch content
  ├── determine_node_type()
  │     ├── __init__.py      → middleware
  │     ├── /schemas/        → middleware
  │     ├── router.py        → middleware
  │     ├── /models/         → database
  │     ├── stripe, webhook  → external
  │     └── default          → service
  │
  ├── Python files: AST import analysis
  │     ast.parse() → Import + ImportFrom nodes
  │     match against repo file paths
  │
  └── TS/JS files: regex + os.path.normpath resolution
        relative imports → resolved absolute paths
        match against repo file paths
        │
        ▼
Edges: source → target (import relationship)
        │
        ▼
LLM enrichment (max 25 nodes):
ARCHITECTURE_PROMPT → one-sentence description per node
        │
        ▼
{ nodes[], edges[], repo }
→ Frontend: ReactFlow + dagre hierarchical layout
```

### Node Type Rules

| Condition | Type |
|-----------|------|
| `__init__.py` | middleware |
| path contains `/schemas/` | middleware |
| filename is `router.py` | middleware |
| path contains `context`, `provider`, `store`, `redux`, `slice` | middleware |
| path contains `/models/`, `database.py`, `embedding` | database |
| path contains `redis`, `postgres`, `mongo`, `pgvector` | database |
| path contains `stripe`, `webhook`, `integration`, `external` | external |
| `.tsx` or `.jsx` with `layout`, `withLayout`, `hoc` | middleware |
| everything else | service |
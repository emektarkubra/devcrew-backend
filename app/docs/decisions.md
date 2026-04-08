# Design Decisions

Key architectural and technical decisions made during DevCrew development — what was chosen, what was considered, and why.

---

## 1. pgvector over a dedicated vector database

**Decision:** Use pgvector extension on PostgreSQL instead of a dedicated vector DB (Pinecone, Weaviate, Qdrant).

**Considered:**
- Pinecone — managed, easy API, but paid and external dependency
- Qdrant — fast, open source, but requires a separate container
- pgvector — runs inside existing PostgreSQL, free, no extra infra

**Why pgvector:**
- DevCrew already uses PostgreSQL for all relational data — one less service to run and maintain
- pgvector's cosine similarity search is fast enough for per-user per-repo queries at this scale
- Docker setup stays simple — one `docker-compose.yml`, no additional containers
- If scaling becomes a concern later, migrating embeddings to a dedicated store is straightforward

---

## 2. Groq over OpenAI / local models

**Decision:** Use Groq API (llama-3.3-70b-versatile) as the primary LLM provider.

**Considered:**
- OpenAI GPT-4 — best quality, but costly and requires credit card
- Ollama (local) — free, private, but requires GPU and is slow on CPU
- Groq — free tier, fast inference, no GPU needed

**Why Groq:**
- Free tier provides 100k tokens/day — enough for development and demos
- Inference speed is significantly faster than OpenAI on the same hardware
- No GPU required — runs in Docker on any machine
- llama-3.3-70b-versatile quality is sufficient for code analysis tasks

**Trade-off:** 100k daily token limit. Managed through hybrid model strategy in Team Mode — large model only where deep reasoning is needed, small model for structural decisions.

---

## 3. LangGraph for Team Mode

**Decision:** Use LangGraph `StateGraph` for the Team Mode multi-agent pipeline instead of plain async task chaining.

**Considered:**
- Simple `asyncio.gather` — parallel but no retry logic or shared state
- Manual sequential loop — simple but no graph abstraction or validator nodes
- LangGraph — graph-based, supports retry, shared state, clean node separation

**Why LangGraph:**
- Team Mode needs: sequential execution, per-agent retry on failure, shared state across nodes, and SSE streaming
- LangGraph's `StateGraph` models this cleanly — supervisor → agent → validator → aggregator
- Each node is a pure function, easy to test and replace independently
- Validator node can decide `done` or `retry` without affecting the rest of the pipeline

---

## 4. Real file content for PR fix generation

**Decision:** When generating fix suggestions, fetch the actual file content from the PR branch — not just the diff.

**Considered:**
- Use only the diff context — simpler, fewer API calls
- Fetch full file content — more API calls but better quality

**Why full file content:**
- LLMs generating fixes from diff context alone tend to hallucinate surrounding code
- Fixes grounded in the actual file are syntactically and contextually correct
- The extra GitHub API call per file is worth the quality improvement

---

## 5. Separate history tables per agent

**Decision:** Each agent has its own history table (`code_query_history`, `pr_review_history`, etc.) instead of a single `history` table with a JSON `result` column.

**Considered:**
- Single `history` table with `agent_type` + `result JSON` — simpler schema, one migration
- Separate tables per agent — more tables, but typed schema per agent

**Why separate tables:**
- Each agent has a fundamentally different result structure — test history needs `tests[]`, `coverage`, `framework`; PR history needs `pr_number`, `fixes[]`
- Typed columns allow proper filtering, sorting, and future indexing
- Schema evolution per agent is independent — adding a column to `test_history` doesn't affect `debug_history`
- Cleaner queries on the frontend — no JSON field extraction needed for common filters

---

## 6. SSE over WebSockets for Team Mode streaming

**Decision:** Use Server-Sent Events (SSE) for real-time agent progress instead of WebSockets.

**Considered:**
- WebSockets — bidirectional, complex setup, requires connection management
- SSE — unidirectional (server → client), simple, native browser support via `EventSource`

**Why SSE:**
- Team Mode streaming is one-directional — server sends events, client only listens
- `EventSource` API in the browser is simpler than WebSocket management
- SSE works over standard HTTP — no special proxy configuration needed
- FastAPI's `StreamingResponse` with `text/event-stream` is straightforward to implement

---

## 7. HuggingFace embeddings run locally

**Decision:** Run the HuggingFace embedding model locally inside the Docker container instead of using an embedding API.

**Considered:**
- OpenAI Embeddings API — managed, no download, but costs per token
- Cohere Embeddings API — similar trade-offs
- HuggingFace local model — free, private, but ~280MB download on first start

**Why local:**
- Embedding calls are frequent — every chunk during indexing, every query during Q&A
- API costs for embeddings add up quickly for active users
- The model runs on CPU — no GPU required
- Data stays local — code is never sent to a third-party embedding service
- One-time ~280MB download on first Docker start; cached in subsequent runs

---

## 8. Token-based auth (query param) over Bearer header

**Decision:** Accept JWT token as a query parameter (`?token=...`) or request body field instead of `Authorization: Bearer` header for agent endpoints.

**Considered:**
- Standard `Authorization: Bearer` header — REST best practice
- Query param / body field — easier for SSE (`EventSource` doesn't support custom headers)

**Why query param:**
- The `EventSource` browser API does not support custom headers — SSE endpoints must accept the token via query parameter
- For consistency, other agent endpoints also accept `token` in the request body
- Trade-off: tokens in query params appear in server logs — acceptable for a development/demo tool, should be revisited for production

---

## 9. `prioritize_files` for Architecture Graph

**Decision:** Prioritize certain directories when selecting files for architecture analysis, with a limit of 40 files.

**Why:**
- Large repos can have hundreds of files — analyzing all would hit token limits and slow down the endpoint
- Business logic lives in `routes/`, `services/`, `models/`, `core/`, `schemas/` — these should always be included
- Config files, migrations, and test files add noise without adding architectural signal
- 40-file limit keeps token usage for LLM enrichment manageable (~8-10k tokens per run)
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.models.embedding import CodeEmbedding
from app.services.agents.indexer import get_embedding
from app.core.config import settings
from app.models.code_query_history import CodeQueryHistory
from app.core.exceptions import RepoNotIndexedError
from app.core.prompts import CODEBASE_QA_PROMPT, CODEBASE_SUGGESTION_PROMPT
import json

# LLM
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

# chain
chain = CODEBASE_QA_PROMPT | llm | StrOutputParser()
suggestion_chain = CODEBASE_SUGGESTION_PROMPT | llm | StrOutputParser()


# codebase qa
async def codebase_qa(query: str, owner: str, repo: str, user_id: int, db: Session) -> dict:
    repo_full    = f"{owner}/{repo}"
    query_vector = get_embedding(f"query: {query}")

    results = (
        db.query(CodeEmbedding)
        .filter(
            CodeEmbedding.user_id == user_id,
            CodeEmbedding.repo    == repo_full,
        )
        .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
        .limit(10)
        .all()
    )

    if not results:
        raise RepoNotIndexedError(repo=repo_full)

    # README varsa ekle
    readme = (
        db.query(CodeEmbedding)
        .filter(
            CodeEmbedding.user_id   == user_id,
            CodeEmbedding.repo      == repo_full,
            CodeEmbedding.file_path.ilike("%readme%"),
        )
        .first()
    )

    context = "\n\n".join([
        f"### File: {r.file_path}\n```\n{r.chunk_text}\n```"
        for r in results
    ])

    if readme and readme not in results:
        context = f"### File: README\n```\n{readme.chunk_text}\n```\n\n" + context

    answer = chain.invoke({
        "context":  context,
        "question": query,
    })

    suggestions = []
    try:
        raw         = suggestion_chain.invoke({"context": context, "question": query})
        cleaned     = raw.strip().replace("```json", "").replace("```", "")
        suggestions = json.loads(cleaned)
        if not isinstance(suggestions, list):
            suggestions = []
    except Exception:
        suggestions = []

    files = list({r.file_path for r in results})

    db.add(CodeQueryHistory(
        user_id    = user_id,
        repo       = repo_full,
        query      = query,
        response   = answer,
        file_count = len(files),
        files      = files,
    ))
    db.commit()

    return {
        "answer":      answer,
        "files":       files,
        "suggestions": suggestions,
    }
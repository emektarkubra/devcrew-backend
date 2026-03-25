import json
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.exceptions import AppError, RepoNotIndexedError
from app.models.embedding import CodeEmbedding
from app.services.agents.indexer import get_embedding
from app.models.debug_history import DebugHistory

llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

prompt = PromptTemplate(
    template="""
You are a senior software engineer specializing in debugging.
Analyze the following error carefully using the provided code context.

Error / Stacktrace:
{error}

Related Code Context:
{context}

Return the analysis ONLY in the following JSON format, nothing else:
{{
    "root_cause": "brief root cause explanation",
    "severity": "critical/high/medium/low",
    "affected_files": ["file1.py", "file2.py"],
    "fix_suggestion": "detailed fix suggestion with code example if possible",
    "explanation": "detailed explanation of what went wrong and why"
}}
""",
    input_variables=["error", "context"]
)

chain = prompt | llm | StrOutputParser()


async def debug_error(
    error:   str,
    owner:   str,
    repo:    str,
    user_id: int,
    db:      Session,
) -> dict:

    repo_full = f"{owner}/{repo}"

    # similarity search
    query_vector = get_embedding(f"query: {error}")

    results = (
        db.query(CodeEmbedding)
        .filter(
            CodeEmbedding.user_id == user_id,
            CodeEmbedding.repo    == repo_full,
        )
        .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
        .limit(5)
        .all()
    )

    if not results:
        raise RepoNotIndexedError(repo=repo_full)

    # context oluştur
    context = "\n\n".join([
        f"# {r.file_path}\n{r.chunk_text}"
        for r in results
    ])

    # LLM'e gönder
    try:
        answer = chain.invoke({
            "error":   error,
            "context": context,
        })
    except Exception as e:
        raise AppError(
            code="LLM_ERROR",
            message="LLM analysis failed.",
            status_code=500,
            details={"error": str(e)},
        )

    # JSON parse
    try:
        cleaned  = answer.strip().replace("```json", "").replace("```", "")
        analysis = json.loads(cleaned)
    except Exception:
        analysis = {
            "root_cause":     answer,
            "severity":       "unknown",
            "affected_files": [],
            "fix_suggestion": "",
            "explanation":    "",
        }

    affected_files = analysis.get("affected_files", [])

    # affected files'a kod ekle
    files_with_code = []
    for file_path in affected_files:
        chunks = (
            db.query(CodeEmbedding)
            .filter(
                CodeEmbedding.user_id  == user_id,
                CodeEmbedding.repo     == repo_full,
                CodeEmbedding.file_path == file_path,
            )
            .all()
        )
        code = "\n".join([c.chunk_text for c in chunks]) if chunks else ""
        files_with_code.append({
            "path": file_path,
            "name": file_path.split("/")[-1],
            "code": code[:500],  # preview
        })

    fix = [
        {"type": "context", "content": f"  # {analysis.get('fix_suggestion', '')}"}
    ]

    # History kaydet
    db.add(DebugHistory(
        user_id        = user_id,
        repo           = repo_full,
        error          = error[:500],
        root_cause     = analysis.get("root_cause", ""),
        severity       = analysis.get("severity", "unknown"),
        affected_files = files_with_code,
        fix            = fix,
        explanation    = analysis.get("explanation", ""),
    ))
    db.commit()

    return {
        "rootCause":     analysis.get("root_cause",     ""),
        "severity":      analysis.get("severity",       "unknown"),
        "affectedFiles": files_with_code,
        "fixSuggestion": analysis.get("fix_suggestion", ""),
        "explanation":   analysis.get("explanation",    ""),
        "contextFiles":  list({r.file_path for r in results}),
    }
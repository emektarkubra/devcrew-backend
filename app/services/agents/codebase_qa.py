from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.models.embedding import CodeEmbedding
from app.services.agents.indexer import get_embedding
from app.core.config import settings
from app.models.code_query_history import CodeQueryHistory
from app.core.exceptions import RepoNotIndexedError
import json

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

prompt = PromptTemplate(
    template="""You are a senior software engineer and expert code analyst with deep expertise in reading, understanding, and explaining codebases across all languages and frameworks.

You are analyzing a GitHub repository. Below are the most relevant code snippets retrieved based on the developer's question.

---

Repository Code Context:
{context}

Developer's Question:
{question}

---

Instructions:
- Answer in clear, flowing prose — no headers, no bullet points, no markdown formatting
- Start with a direct answer to the question
- Reference specific files, functions, and classes using backticks like `functionName()`
- Explain not just what the code does but why it works that way
- If the question is about overall structure, describe the purpose, tech stack, and how components interact
- Be specific and ground your answer in the actual code provided
- If the context is insufficient, say so clearly
- Keep the tone conversational but technical — like a senior developer explaining to a colleague

Answer:""",
    input_variables=["context", "question"]
)

chain = prompt | llm | StrOutputParser()

suggestion_prompt = PromptTemplate(
    template="""You are a senior developer reviewing a codebase. Based on the code context and the current question, generate exactly 4 insightful follow-up questions a developer might want to explore next.

Rules:
- Questions must be directly related to the code shown
- Each question should explore a different aspect: functionality, architecture, performance, or potential issues
- Keep questions short and specific (max 10 words each)
- Return ONLY a valid JSON array of 4 strings, nothing else

Code Context:
{context}

Current Question:
{question}

JSON array:""",
    input_variables=["context", "question"]
)

suggestion_chain = suggestion_prompt | llm | StrOutputParser()


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
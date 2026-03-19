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

# LLM
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

# prompt
prompt = PromptTemplate(
    template="""You are an expert code analyst. Analyze the following code snippets from a GitHub repository and answer the question clearly and concisely.

    Repository context:
    {context}

    Question: {question}

    Instructions:
    - Explain what the code does in plain language
    - Mention specific files, functions, and classes when relevant
    - If the question is about the overall repository, summarize its purpose, main features, and tech stack
    - Be specific and technical but easy to understand

    Answer:""",
        input_variables=["context", "question"]
)

# chain
chain = prompt | llm | StrOutputParser()

# suggestion prompt
suggestion_prompt = PromptTemplate(
    template="""Based on this code context, generate exactly 4 short follow-up questions that a developer might want to ask. 
    Return ONLY a JSON array of 4 strings, nothing else. Example: ["question1", "question2", "question3", "question4"]

    Context: {context}
    Current question: {question}

    JSON array:""",
        input_variables=["context", "question"]
)

# suggestion chain
suggestion_chain = suggestion_prompt | llm | StrOutputParser()


# codebase_qa
async def codebase_qa(query: str, owner: str, repo: str, user_id: int, db: Session) -> dict:
    repo_full = f"{owner}/{repo}"
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

    # README
    readme = (
        db.query(CodeEmbedding)
        .filter(
            CodeEmbedding.user_id  == user_id,
            CodeEmbedding.repo == repo_full,
            CodeEmbedding.file_path.ilike("%readme%"),
        )
        .first()
    )

    context = "\n\n".join([
        f"# {r.file_path}\n{r.chunk_text}"
        for r in results
    ])

    if readme and readme not in results:
        context = f"# README\n{readme.chunk_text}\n\n" + context

    answer = chain.invoke({
        "context":  context,
        "question": query,
    })


    # suggestion queries
    suggestions = []
    try:
        raw = suggestion_chain.invoke({"context": context, "question": query})
        suggestions = json.loads(raw)
    except Exception:
        suggestions = []


    files = list({r.file_path for r in results})

    db.add(CodeQueryHistory(
        user_id    = user_id,
        repo       = repo_full,
        query      = query,
        response   = answer, 
        file_count = len(files),
    ))
    
    db.commit()

    return {
        "answer": answer,
        "files":  files,
        "suggestions": suggestions,
    }
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.models.embedding import CodeEmbedding
from app.services.agents.indexer import get_embedding
from app.core.config import settings
from app.models.code_query_history import CodeQueryHistory

# LLM
llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

prompt = PromptTemplate(
    template="""You are an expert code assistant. Answer the question based ONLY on the provided code context.

Rules:
- Answer in the same language as the question
- If the answer is not in the context, say "I couldn't find this in the codebase."
- Include file names and line references when relevant
- Be specific and concise
- If you find relevant code, show it

Context:
{context}

Question: {question}

Answer:""",
    input_variables=["context", "question"]
)

# chain
chain = prompt | llm | StrOutputParser()


# codebase_qa
async def codebase_qa(query: str, owner: str, repo: str, user_id: int, db: Session) -> dict:
    repo_full = f"{owner}/{repo}"

    # query embbeding 
    query_vector = get_embedding(f"query: {query}")

    # pgvector similarity search
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
        return {"answer": "Bu repo henüz indexlenmemiş.", "files": []}

    # context
    context = "\n\n".join([
        f"# {r.file_path}\n{r.chunk_text}"
        for r in results
    ])

    # send LLM
    answer = chain.invoke({
        "context":  context,
        "question": query,
    })


    # save history 
    db.add(CodeQueryHistory(
        user_id    = user_id,
        repo       = repo_full,
        query      = query,
        file_count = len(list({r.file_path for r in results})),
    ))
    db.commit()

    return {
        "answer": answer,
        "files":  list({r.file_path for r in results}),
    }
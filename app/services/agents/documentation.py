from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.models.documentation_history import DocumentationHistory
from app.core.config import settings
from app.core.constants import SUPPORTED_EXTENSIONS
from app.services.repo_service import fetch_file_content, fetch_repo_file_list, fetch_all_repo_files

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

doc_prompts = {
    "function":  """Generate detailed function/class documentation. For each function include:
- Purpose and description
- Parameters with types
- Return value with type
- Usage example
- Edge cases or notes""",

    "readme":    """Generate a professional README.md with these sections:
- Project title and description
- Tech stack and key features
- Prerequisites
- Installation and setup
- Usage with examples
- Project structure
- Environment variables
- Contributing guidelines""",

    "api":       """Generate API reference documentation with:
- Base URL
- Authentication
- For each endpoint: method, path, description, request params, request body, response format, example""",

    "onboard":   """Generate a developer onboarding guide with:
- Project overview and purpose
- Tech stack explanation
- Local setup step by step
- Project structure walkthrough
- Key concepts and architecture decisions
- Common tasks and workflows
- Debugging tips""",

    "guide": """Analyze the codebase and generate a user guide for the application's UI and features. Include:
- What this application does (based on the code)
- Each page/screen and what it does
- Each button, form, and interactive element and what it does
- Step by step workflows (e.g. how to login, how to create X)
- What each agent/feature does from a user perspective
Focus on the actual UI components, routes, and functionality found in the code.""",

    "arch":      """Generate an architecture document with:
- System overview
- Component diagram description
- Data flow
- Key design decisions and tradeoffs
- Dependencies and integrations
- Scalability considerations""",

    "changelog": """Generate a structured changelog with:
- Version grouping
- Breaking changes
- New features
- Bug fixes
- Performance improvements
- Migration notes if needed""",
}

DOC_LIMITS = {
    "guide":     12,
    "arch":      10,
    "api":        8,
    "readme":     6,
    "onboard":   10,
    "changelog":  5,
    "function":   1,
}

prompt = PromptTemplate(
    template="""You are a senior technical writer and software architect.

Repository: {target}

Code context:
{context}

Task: {task}

Guidelines:
- Write in clear, professional English
- Use proper markdown formatting with headers, code blocks, and lists
- Be specific and practical, not generic
- Include actual file names, functions, and configurations found in the code
- Make it immediately useful for a developer

Generate the documentation now:""",
    input_variables=["context", "target", "task"]
)

chain = prompt | llm | StrOutputParser()


async def generate_documentation(
    target:       str,
    owner:        str,
    repo:         str,
    user_id:      int,
    doc_type:     str,
    access_token: str,
    db:           Session,
) -> dict:

    repo_full = f"{owner}/{repo}"
    is_repo_level = target == repo_full
    limit = DOC_LIMITS.get(doc_type, 8)

    if is_repo_level:
        file_list = await fetch_all_repo_files(access_token, owner, repo)

        if doc_type in ("guide", "onboard"):
            priority = [f for f in file_list if any(
                p in f for p in ["pages/", "components/", "routes", "App."]
            ) and f.endswith(SUPPORTED_EXTENSIONS)][:limit]

        elif doc_type == "api":
            priority = [f for f in file_list if any(
                p in f for p in ["routes/", "services/", "schemas/", "models/"]
            ) and f.endswith(SUPPORTED_EXTENSIONS)][:limit]

        elif doc_type == "arch":
            priority = [f for f in file_list if any(
                p in f for p in ["routes/", "services/", "pages/", "App.", "main."]
            ) and f.endswith(SUPPORTED_EXTENSIONS)][:limit]

        else:
            priority = [f for f in file_list if f.endswith(SUPPORTED_EXTENSIONS)][:limit]

        config = [f for f in file_list if f.endswith((".md", ".json", ".yaml", ".yml", ".env"))][:2]

        important = priority + config
        contents  = []
        for f in important:
            content = await fetch_file_content(access_token, owner, repo, f)
            contents.append(f"# {f}\n{content[:2000]}")
        context = "\n\n".join(contents)
    else:
        context = await fetch_file_content(access_token, owner, repo, target)

    answer = chain.invoke({
        "context": context,
        "target":  target,
        "task":    doc_prompts.get(doc_type, doc_prompts["function"]),
    })

    lines       = answer.strip().splitlines()
    description = next((l for l in lines if l and not l.startswith("#")), "")

    db.add(DocumentationHistory(
        user_id     = user_id,
        repo        = repo_full,
        target      = target,
        doc_type    = doc_type,
        description = description,
        content     = answer,
    ))
    db.commit()

    return {
        "fileName":    target,
        "description": description,
        "markdown":    answer,
        "contextFiles": [],
    }
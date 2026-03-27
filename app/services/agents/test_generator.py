from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.models.test_history import TestHistory
from app.services.repo_service import fetch_file_content
from app.models.test_history import TestHistory
import json

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

prompt = PromptTemplate(
    template="""You are a senior software engineer specializing in test-driven development.

    File: {target}
    Framework: {framework}

    Code:
    {context}

    Generate comprehensive tests for this code. Return ONLY a JSON object in this exact format, nothing else:
    {{
        "totalTests": <number>,
        "coverage": <estimated coverage percentage as number>,
        "unitCount": <number>,
        "edgeCount": <number>,
        "integrationCount": <number>,
        "tests": [
            {{
                "name": "test_function_name",
                "type": "unit|edge|integration",
                "description": "What this test verifies",
                "code": "actual test code here"
            }}
        ]
    }}

    Rules:
    - Generate unit tests for each function/method
    - Generate edge case tests for boundary conditions, null inputs, invalid data
    - Generate integration tests for interactions between components
    - Use {framework} syntax and conventions
    - Make tests realistic and specific to the actual code
    - Include imports in the first test's code block""",
        input_variables=["target", "framework", "context"]
)

chain = prompt | llm | StrOutputParser()


async def generate_tests(
    target:       str,
    owner:        str,
    repo:         str,
    user_id:      int,
    framework:    str,
    access_token: str,
    db:           Session,
) -> dict:

    context = await fetch_file_content(access_token, owner, repo, target)

    answer = chain.invoke({
        "target":    target,
        "framework": framework,
        "context":   context,
    })

    try:
        cleaned = answer.strip().replace("```json", "").replace("```", "")
        result  = json.loads(cleaned)
    except Exception:
        result = {
            "totalTests":       0,
            "coverage":         0,
            "unitCount":        0,
            "edgeCount":        0,
            "integrationCount": 0,
            "tests":            [],
        }

    db.add(TestHistory(
        user_id    = user_id,
        repo       = f"{owner}/{repo}",
        target     = target,
        framework  = framework,
        test_count = result.get("totalTests", 0),
        coverage   = result.get("coverage", 0),
        tests      = result.get("tests", []),
    ))
    db.commit()

    return result
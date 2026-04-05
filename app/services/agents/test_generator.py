import json
import re
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.exceptions import AppError
from app.models.test_history import TestHistory
from app.services.repo_service import fetch_file_content
from app.core.prompts import TEST_GENERATOR_PROMPT

llm = ChatGroq(
    model_name    = "llama-3.3-70b-versatile",
    temperature   = 0,
    api_key       = settings.GROQ_API_KEY,
)

chain = TEST_GENERATOR_PROMPT | llm | StrOutputParser()


# clean LLM output to be parseable JSON
def clean_llm_json(raw: str) -> str:

    # remove code block markers and trim whitespace
    cleaned = raw.strip()
    cleaned = re.sub(r'^```json\s*', '', cleaned)
    cleaned = re.sub(r'^```\s*',     '', cleaned)
    cleaned = re.sub(r'\s*```$',     '', cleaned)
    cleaned = cleaned.strip()

    # escape double quotes, backslashes, and control characters in all string values
    def escape_string_content(match: re.Match) -> str:
        content = match.group(1)
        content = content.replace('\\', '\\\\')  
        content = content.replace('"',  '\\"')  
        content = content.replace('\n', '\\n')    
        content = content.replace('\r', '\\r')   
        content = content.replace('\t', '\\t')   
        content = content.replace('\b', '\\b')
        content = content.replace('\f', '\\f')
        # get back to original \n, \t, \r, \" after escaping backslashes
        content = content.replace('\\\\n',  '\\n')
        content = content.replace('\\\\t',  '\\t')
        content = content.replace('\\\\r',  '\\r')
        content = content.replace('\\\\"',  '\\"')
        content = content.replace('\\\\\\\\', '\\\\')
        return f'"{content}"'

    # scan for all string values and escape them
    cleaned = re.sub(
        r'"((?:[^"\\]|\\.)*)"',
        escape_string_content,
        cleaned,
        flags=re.DOTALL,
    )

    return cleaned



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

    if not context:
        raise AppError(
            code        = "FILE_NOT_FOUND",
            message     = f"Could not fetch file content for {target}.",
            status_code = 404,
            details     = {"target": target, "repo": f"{owner}/{repo}"},
        )

    # dosya büyükse chunk'lara böl, her chunk için ayrı test üret
    MAX_CHARS = 6000
    if len(context) > MAX_CHARS:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=MAX_CHARS, chunk_overlap=200)
        chunks   = splitter.split_text(context)
    else:
        chunks = [context]

    all_tests        = []
    total_unit       = 0
    total_edge       = 0
    total_integration = 0
    total_coverage   = 0

    for i, chunk in enumerate(chunks[:3]):  # max 3 chunk — fazlası çok yavaş olur
        try:
            answer = chain.invoke({
                "target":    target,
                "framework": framework,
                "context":   chunk,
            })
        except Exception as e:
            continue  # bir chunk hata verse bile devam et

        try:
            cleaned = clean_llm_json(answer)
            result  = json.loads(cleaned)
        except Exception:
            continue

        chunk_tests        = result.get("tests", [])
        all_tests         += chunk_tests
        total_unit        += result.get("unitCount",        0)
        total_edge        += result.get("edgeCount",        0)
        total_integration += result.get("integrationCount", 0)
        total_coverage    += result.get("coverage",         0)

    if not all_tests:
        raise AppError(
            code        = "TEST_PARSE_ERROR",
            message     = "Could not generate any tests.",
            status_code = 500,
        )

    avg_coverage = total_coverage // len(chunks[:3])

    result = {
        "totalTests":       len(all_tests),
        "coverage":         avg_coverage,
        "unitCount":        total_unit,
        "edgeCount":        total_edge,
        "integrationCount": total_integration,
        "tests":            all_tests,
    }

    merged_code = merge_tests(all_tests, target)

    try:
        db.add(TestHistory(
            user_id     = user_id,
            repo        = f"{owner}/{repo}",
            target      = target,
            framework   = framework,
            test_count  = len(all_tests),
            coverage    = avg_coverage,
            tests       = all_tests,
            merged_code = merged_code,
        ))
        db.commit()
    except Exception as e:
        raise AppError(
            code        = "DB_ERROR",
            message     = "Failed to save test history.",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e


    return {
        "target":           target,
        "framework":        framework,
        "testCount":        len(all_tests),
        "coverage":         avg_coverage,
        "unitCount":        total_unit,
        "edgeCount":        total_edge,
        "integrationCount": total_integration,
        "tests":            all_tests,
        "mergedCode":       merged_code,
    }



def merge_tests(tests: list, target: str) -> str:
    """Her testin code field'ından importları dedupe edip tek dosya üretir."""
    if not tests:
        return ""

    ext       = target.split('.')[-1]
    base_name = target.split('/')[-1].replace(f'.{ext}', '')

    # importları ilk testten al
    first_code    = tests[0].get('code', '')
    import_lines  = [
        line for line in first_code.split('\n')
        if line.strip().startswith('import')
    ]
    import_block  = '\n'.join(import_lines)

    # her testten it() bloklarını çıkar
    it_blocks = []
    for test in tests:
        code  = test.get('code', '')
        lines = code.split('\n')
        block = []
        depth = 0
        in_it = False

        for line in lines:
            trimmed = line.strip()
            if not in_it and (
                trimmed.startswith("it(") or
                trimmed.startswith("it('") or
                trimmed.startswith('it("') or
                trimmed.startswith("def test_")
            ):
                in_it = True

            if in_it:
                block.append(line)
                depth += line.count('{') - line.count('}')
                # Python için
                if trimmed.startswith("def test_") and depth == 0 and len(block) > 1:
                    in_it = False
                # JS için
                elif depth <= 0 and not trimmed.startswith("def test_"):
                    in_it = False
                    depth = 0

        if block:
            it_blocks.append('\n'.join(block))

    it_content = '\n\n'.join(it_blocks)

    # Python ise describe wrapper yok
    if ext == 'py':
        return f"{import_block}\n\n{it_content}"

    return f"{import_block}\n\ndescribe('{base_name}', () => {{\n{it_content}\n}})"
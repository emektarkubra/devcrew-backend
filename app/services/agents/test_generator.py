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
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

chain = TEST_GENERATOR_PROMPT | llm | StrOutputParser()


def clean_llm_json(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def try_parse_json(raw: str) -> dict | None:
    # 1. direkt parse
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2. backtick temizle
    try:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception:
        pass

    # 3. ilk { ile son } arasını bul
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        pass

    return None


async def generate_tests(
    target: str,
    owner: str,
    repo: str,
    user_id: int,
    framework: str,
    access_token: str,
    db: Session,
) -> dict:

    context = await fetch_file_content(access_token, owner, repo, target)

    if not context:
        raise AppError(
            code="FILE_NOT_FOUND",
            message=f"Could not fetch file content for {target}.",
            status_code=404,
            details={"target": target, "repo": f"{owner}/{repo}"},
        )

    MAX_CHARS = 6000
    if len(context) > MAX_CHARS:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=MAX_CHARS, chunk_overlap=200
        )
        chunks = splitter.split_text(context)
    else:
        chunks = [context]

    all_tests = []
    total_unit = 0
    total_edge = 0
    total_integration = 0
    total_coverage = 0

    for chunk in chunks[:3]:
        try:
            answer = chain.invoke(
                {
                    "target": target,
                    "framework": framework,
                    "context": chunk,
                }
            )
        except Exception:
            continue

        result = try_parse_json(answer)
        if not result:
            continue

        chunk_tests = result.get("tests", [])
        all_tests += chunk_tests
        total_unit += result.get("unitCount", 0)
        total_edge += result.get("edgeCount", 0)
        total_integration += result.get("integrationCount", 0)
        total_coverage += result.get("coverage", 0)

    if not all_tests:
        raise AppError(
            code="TEST_PARSE_ERROR",
            message="Could not generate any tests.",
            status_code=500,
        )

    avg_coverage = total_coverage // max(len(chunks[:3]), 1)

    merged_code = merge_tests(all_tests, target)

    try:
        db.add(
            TestHistory(
                user_id=user_id,
                repo=f"{owner}/{repo}",
                target=target,
                framework=framework,
                test_count=len(all_tests),
                coverage=avg_coverage,
                tests=all_tests,
                merged_code=merged_code,
            )
        )
        db.commit()
    except Exception as e:
        raise AppError(
            code="DB_ERROR",
            message="Failed to save test history.",
            status_code=500,
            details={"error": str(e)},
        ) from e

    return {
        "target": target,
        "framework": framework,
        "testCount": len(all_tests),
        "coverage": avg_coverage,
        "unitCount": total_unit,
        "edgeCount": total_edge,
        "integrationCount": total_integration,
        "tests": all_tests,
        "mergedCode": merged_code,
    }


def merge_tests(tests: list, target: str) -> str:
    if not tests:
        return ""

    ext = target.split(".")[-1].lower()
    base_name = target.split("/")[-1].replace(f".{ext}", "")

    first_code = tests[0].get("code", "")

    # Dile göre import pattern'ları
    IMPORT_KEYWORDS = {
        "py": ("import ", "from "),
        "go": ("import ", "package "),
        "java": ("import ", "package "),
        "kt": ("import ", "package "),
        "rb": ("require ", "require_relative "),
        "rs": ("use ", "extern "),
        "cs": ("using ", "namespace "),
        "swift": ("import ",),
        "php": ("use ", "require ", "namespace "),
    }

    keywords = IMPORT_KEYWORDS.get(ext, ("import ",))
    import_lines = [
        line
        for line in first_code.split("\n")
        if any(line.strip().startswith(kw) for kw in keywords)
    ]
    import_block = "\n".join(import_lines)

    # Dile göre test fonksiyon başlangıç pattern'ları
    TEST_PATTERNS = {
        "py": ("def test_",),
        "go": ("func Test",),
        "java": ("@Test", "void test", "public void test"),
        "kt": ("@Test", "fun test", "fun `"),
        "rb": ("it ", "it(", "def test_", "test "),
        "rs": ("#[test]", "fn test_"),
        "cs": ("[Fact]", "[Test]", "public void Test", "public async Task Test"),
        "swift": ("func test",),
        "php": ("public function test", "it(", "test("),
    }

    js_patterns = ("it(", "it('", 'it("', "test(", "test('", 'test("')
    patterns = TEST_PATTERNS.get(ext, js_patterns)

    it_blocks = []
    for test in tests:
        code = test.get("code", "")
        lines = code.split("\n")
        block = []
        depth = 0
        in_it = False

        for line in lines:
            trimmed = line.strip()
            if not in_it and any(trimmed.startswith(p) for p in patterns):
                in_it = True

            if in_it:
                block.append(line)
                depth += line.count("{") - line.count("}")

                is_py_like = ext in ("py", "rb")
                if is_py_like and depth == 0 and len(block) > 1:
                    in_it = False
                elif not is_py_like and depth <= 0 and len(block) > 1:
                    in_it = False
                    depth = 0

        if block:
            it_blocks.append("\n".join(block))

    it_content = "\n\n".join(it_blocks)

    # Dile göre wrapper
    if ext == "py":
        return f"{import_block}\n\n{it_content}"
    elif ext == "go":
        return f"package {base_name}_test\n\n{import_block}\n\n{it_content}"
    elif ext in ("java", "kt"):
        return f"{import_block}\n\npublic class {base_name}Test {{\n{it_content}\n}}"
    elif ext == "rs":
        return f"{import_block}\n\n#[cfg(test)]\nmod tests {{\n{it_content}\n}}"
    elif ext == "cs":
        return f"{import_block}\n\npublic class {base_name}Tests {{\n{it_content}\n}}"
    elif ext in ("rb",):
        return f"{import_block}\n\n{it_content}"
    else:
        # JS/TS/JSX/TSX ve diğerleri
        return f"{import_block}\n\ndescribe('{base_name}', () => {{\n{it_content}\n}})"

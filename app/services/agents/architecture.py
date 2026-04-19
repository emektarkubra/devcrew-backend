import ast
import re
import httpx
import json
import base64
import os
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.prompts import ARCHITECTURE_PROMPT

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

INCLUDE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}

EXCLUDE_PATTERNS = [
    "test",
    "spec",
    "migration",
    "alembic",
    "__pycache__",
    "node_modules",
    ".git",
    "dist",
    "build",
    "venv",
    ".env",
    "constants.py",
    "config.py",
    "settings.py",
]

PRIORITY_DIRS = [
    "routes/",
    "routers/",
    "services/",
    "models/",
    "core/",
    "schemas/",
    "controllers/",
    "handlers/",
]


async def fetch_file_list(owner: str, repo: str, access_token: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/git/trees/HEAD",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"recursive": "1"},
        )
    if resp.status_code != 200:
        return []
    return resp.json().get("tree", [])


async def fetch_file_content(
    owner: str, repo: str, path: str, access_token: str
) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        return ""
    data = resp.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    return ""


def extract_python_imports(
    source: str, file_path: str, all_paths: list[str]
) -> list[str]:
    imports = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.replace(".", "/"))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.replace(".", "/"))
    except Exception:
        pass

    matched = []
    for imp in imports:
        for path in all_paths:
            stem = path.replace(".py", "").replace(".ts", "").replace(".tsx", "")
            if imp in stem or stem.endswith(imp.split("/")[-1]):
                if path != file_path:
                    matched.append(path)
    return list(set(matched))


def resolve_ts_path(imp: str, file_path: str) -> str:
    """Relative import path'i normalize eder."""
    base_dir = os.path.dirname(file_path)
    resolved = os.path.normpath(os.path.join(base_dir, imp)).replace("\\", "/")
    resolved = resolved.lstrip("/")
    return resolved


def extract_ts_imports(source: str, file_path: str, all_paths: list[str]) -> list[str]:
    pattern = r"""(?:import|from)\s+['"]([^'"]+)['"]"""
    raw_imports = re.findall(pattern, source)

    path_stems: dict[str, str] = {}
    for path in all_paths:
        stem = path
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            stem = stem.replace(ext, "")
        path_stems[path] = stem

    matched = []
    for imp in raw_imports:
        if not imp.startswith("."):
            continue

        resolved = resolve_ts_path(imp, file_path)

        for path, stem in path_stems.items():
            if path == file_path:
                continue

            if stem == resolved:
                matched.append(path)
                break

            if stem == resolved + "/index" or stem == resolved.rstrip("/index"):
                matched.append(path)
                break

            resolved_name = resolved.split("/")[-1]
            stem_name = stem.split("/")[-1]
            if (
                resolved_name
                and resolved_name == stem_name
                and resolved_name != "index"
            ):
                resolved_parts = resolved.split("/")
                stem_parts = stem.split("/")
                common = sum(
                    1
                    for a, b in zip(reversed(resolved_parts), reversed(stem_parts))
                    if a == b
                )
                if common >= min(2, len(resolved_parts)):
                    matched.append(path)
                    break

    return list(set(matched))


def determine_node_type(path: str, content: str) -> str:
    p = path.lower()

    if p.endswith("__init__.py"):
        return "middleware"

    if "/schemas/" in p or "/schema/" in p:
        return "middleware"

    if any(x in p for x in ["router.py", "middleware", "cors", "jwt", "guard"]):
        return "middleware"

    # Context/Provider → middleware
    if any(x in p for x in ["context", "provider", "store", "redux", "slice"]):
        return "middleware"

    if any(
        x in p
        for x in [
            "/models/",
            "model.py",
            "database.py",
            "db.py",
            "migration",
            "embedding",
        ]
    ):
        return "database"

    if any(x in p for x in ["redis", "postgres", "mongo", "sqlite", "pgvector"]):
        return "database"

    if any(
        x in p
        for x in ["external", "integration", "webhook", "stripe", "github", "client"]
    ):
        return "external"

    # TS/TSX
    if p.endswith(".tsx") or p.endswith(".jsx"):
        if any(x in p for x in ["layout", "withLayout", "hoc"]):
            return "middleware"
        return "service"

    return "service"


def determine_language(path: str) -> str:
    ext = path.split(".")[-1].lower()
    return {
        "py": "Python",
        "ts": "TypeScript",
        "tsx": "TypeScript",
        "js": "JavaScript",
        "jsx": "JavaScript",
        "go": "Go",
        "rb": "Ruby",
        "java": "Java",
    }.get(ext, "")


def should_analyze(path: str) -> bool:
    ext = "." + path.split(".")[-1]
    if ext not in INCLUDE_EXTENSIONS:
        return False
    if any(x in path.lower() for x in EXCLUDE_PATTERNS):
        return False
    return True


def prioritize_files(all_paths: list[str], limit: int = 40) -> list[str]:
    analyzable = [p for p in all_paths if should_analyze(p)]

    priority = [p for p in analyzable if any(d in p for d in PRIORITY_DIRS)]
    rest = [p for p in analyzable if p not in priority]

    return (priority + rest)[:limit]


async def enrich_with_llm(nodes: list[dict], repo: str) -> list[dict]:
    if not nodes:
        return nodes

    node_list = "\n".join(
        [
            f"- {n['id']}: {n['data']['label']} ({n['data']['type']}, {n['data'].get('language', '')})"
            for n in nodes[:25]
        ]
    )

    try:
        chain = ARCHITECTURE_PROMPT | llm | StrOutputParser()
        raw = chain.invoke({"repo": repo, "nodes": node_list})
        cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
        descriptions: dict = json.loads(cleaned)

        for node in nodes:
            node_id = node["id"]
            if node_id in descriptions:
                node["data"]["description"] = descriptions[node_id]
    except Exception:
        pass

    return nodes


async def analyze_architecture(
    owner: str,
    repo: str,
    access_token: str,
) -> dict:
    repo_full = f"{owner}/{repo}"

    # fetch file list
    tree = await fetch_file_list(owner, repo, access_token)
    all_paths = [item["path"] for item in tree if item["type"] == "blob"]

    # select files with prioritize
    analyzable = prioritize_files(all_paths, limit=40)

    if not analyzable:
        return {"nodes": [], "edges": [], "repo": repo_full}

    # create node for every file
    nodes: list[dict] = []
    edges: list[dict] = []
    path_to_id: dict = {}
    edge_set: set = set()

    for idx, path in enumerate(analyzable):
        node_id = str(idx + 1)
        path_to_id[path] = node_id

        content = await fetch_file_content(owner, repo, path, access_token)
        ext = "." + path.split(".")[-1]
        lang = determine_language(path)
        typ = determine_node_type(path, content)
        label = path.split("/")[-1]

        nodes.append(
            {
                "id": node_id,
                "type": "serviceNode",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": label,
                    "type": typ,
                    "language": lang,
                    "path": path,
                },
            }
        )

        # analyze import
        if ext == ".py":
            imports = extract_python_imports(content, path, analyzable)
        else:
            imports = extract_ts_imports(content, path, analyzable)

        for imp_path in imports:
            if imp_path in path_to_id:
                src = node_id
                tgt = path_to_id[imp_path]
                edge_key = f"{src}-{tgt}"
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edges.append(
                        {
                            "id": f"e{src}-{tgt}",
                            "source": src,
                            "target": tgt,
                            "animated": typ in ("service", "middleware"),
                            "className": f"architecture-graph__edge architecture-graph__edge--{typ}",
                        }
                    )

    # add description
    nodes = await enrich_with_llm(nodes, repo_full)

    return {
        "repo": repo_full,
        "nodes": nodes,
        "edges": edges,
    }

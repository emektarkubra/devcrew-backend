from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.prompts import DOC_PROMPT, TASK_PROMPT, HALLUCINATION_GUARD
from app.models.documentation_history import DocumentationHistory
from app.core.config import settings
from app.services.repo_service import fetch_file_content, fetch_all_repo_files
from app.core.exceptions import (
    FileContextError,
    DocumentationGenerationError,
    AIRateLimitError,
    ValidationAppError,
)
import json
import re

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=8192,
    api_key=settings.GROQ_API_KEY,
)

chain = DOC_PROMPT | llm | StrOutputParser()

DOC_LIMITS = {
    "guide":     30,
    "arch":      10,
    "api":       15,
    "readme":     6,
    "onboard":   10,
    "changelog":  5,
    "function":   1,
}

CODE_EXTENSIONS = (
    ".tsx", ".ts", ".jsx", ".js", ".vue", ".py", ".go", ".rs",
    ".java", ".kt", ".rb", ".php", ".swift", ".cs", ".scala",
    ".c", ".cpp", ".h", ".hpp",
)

FRONTEND_EXTENSIONS = {".tsx", ".jsx", ".vue", ".svelte"}

BACKEND_INDICATORS = [
    "routes/", "routers/", "controllers/", "endpoints/", "handlers/",
    ".py", ".go", ".java", ".cs", ".rb", ".php", ".rs", ".kt", ".scala",
]

IS_MAIN_ROUTER_NAMES = {
    "router.py", "index.js", "index.ts",
    "app.js", "app.ts", "server.js", "server.ts",
    "main.go", "program.cs", "startup.cs", "application.java",
}

IS_SCHEMA_PATHS = [
    "schemas/", "schema/",
    "dto/", "dtos/",
    "models/response", "models/dto",
    "types/", "interfaces/",
    "serializers/", "contracts/",
]

IS_ROUTE_PATHS = [
    "routes/", "route/", "routers/", "router/",
    "controllers/", "controller/",
    "endpoints/", "endpoint/",
    "handlers/", "handler/",
    "views/", "api/",
]


def _is_frontend_repo(file_list: list[str]) -> bool:
    has_frontend = any(
        any(f.endswith(e) for e in FRONTEND_EXTENSIONS)
        for f in file_list
    )
    has_backend = any(
        any(ind in f for ind in BACKEND_INDICATORS)
        for f in file_list
    )
    return has_frontend and not has_backend


def _is_main_router(f: str) -> bool:
    return f.split("/")[-1].lower() in IS_MAIN_ROUTER_NAMES


def _is_schema(f: str) -> bool:
    return any(p in f for p in IS_SCHEMA_PATHS)


def _is_route(f: str) -> bool:
    return any(p in f for p in IS_ROUTE_PATHS)


def _extract_route_signatures(content: str, file_path: str = "") -> str:
    lines = content.splitlines()
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    PATTERNS_BY_LANG = {
        "py": [
            "@router.", "@app.", "@bp.", "@api.",
            "APIRouter(", "Blueprint(", "router = ", "app = ",
            "async def ", "def ", "prefix", "include_router",
        ],
        "java": [
            "@RestController", "@Controller", "@RequestMapping",
            "@GetMapping", "@PostMapping", "@PutMapping",
            "@DeleteMapping", "@PatchMapping", "@PathVariable",
            "@RequestBody", "@RequestParam", "@ResponseBody",
            "public ", "private ", "protected ",
            "ResponseEntity", "HttpStatus", "class ",
        ],
        "go": [
            "func ", "router.GET", "router.POST", "router.PUT",
            "router.DELETE", "router.PATCH", "router.Group",
            "e.GET", "e.POST", "e.PUT", "e.DELETE",
            "r.GET", "r.POST", "r.PUT", "r.DELETE",
            "http.HandleFunc", "http.Handle",
            "gin.Default()", "gin.New()",
            "fiber.New()", "echo.New()",
            "mux.NewRouter()",
        ],
        "ts": [
            "router.get(", "router.post(", "router.put(",
            "router.delete(", "router.patch(",
            "app.get(", "app.post(", "app.put(",
            "app.delete(", "app.patch(",
            "@Get(", "@Post(", "@Put(", "@Delete(", "@Patch(",
            "@Controller(", "@Injectable(",
            "express.Router()", "Router()",
            "fastify.get(", "fastify.post(",
            "async ", "export ",
        ],
        "js": [
            "router.get(", "router.post(", "router.put(",
            "router.delete(", "router.patch(",
            "app.get(", "app.post(", "app.put(",
            "app.delete(", "app.patch(",
            "express.Router()", "Router()",
            "module.exports", "exports.",
            "async ", "const ", "function ",
        ],
        "rb": [
            "get '", "post '", "put '", "delete '", "patch '",
            "get \"", "post \"", "put \"", "delete \"", "patch \"",
            "resources :", "resource :",
            "namespace :", "scope :", "mount ",
            "def index", "def show", "def create",
            "def update", "def destroy", "def new", "def edit",
        ],
        "php": [
            "Route::get(", "Route::post(", "Route::put(",
            "Route::delete(", "Route::patch(", "Route::resource(",
            "Route::group(", "Route::prefix(", "Route::middleware(",
            "#[Route(", "#[Get(", "#[Post(", "#[Put(", "#[Delete(",
            "public function ", "$app->get(", "$app->post(",
            "$router->get(", "$router->post(",
        ],
        "cs": [
            "[HttpGet", "[HttpPost", "[HttpPut",
            "[HttpDelete", "[HttpPatch",
            "[Route(", "[ApiController", "[Controller",
            "[Authorize", "[FromBody", "[FromQuery", "[FromRoute",
            "app.MapGet(", "app.MapPost(", "app.MapPut(",
            "app.MapDelete(", "app.MapPatch(",
            "public async Task", "public Task",
            "public IActionResult", "public ActionResult",
            "return Ok(", "return NotFound(", "return BadRequest(",
            "namespace ", "public class ",
        ],
        "rs": [
            "#[get(", "#[post(", "#[put(",
            "#[delete(", "#[patch(", "#[route(",
            "#[web::get", "#[web::post",
            "async fn ", "pub fn ", "pub async fn ",
            "Router::new()", ".route(", ".nest(",
            "HttpServer::new", "web::scope(",
            "#[tokio::main]",
        ],
        "swift": [
            "app.get(", "app.post(", "app.put(",
            "app.delete(", "app.patch(",
            "router.get(", "router.post(",
            "drop.get(", "drop.post(",
            "routes.get(", "routes.post(",
            "func ", "class ", "struct ", "var ", "let ",
        ],
        "kt": [
            "@RestController", "@Controller", "@RequestMapping",
            "@GetMapping", "@PostMapping", "@PutMapping",
            "@DeleteMapping", "@PatchMapping",
            "@PathVariable", "@RequestBody", "@RequestParam",
            "fun ", "class ", "object ", "data class ",
        ],
        "scala": [
            "get(", "post(", "put(", "delete(", "patch(",
            "path(", "pathPrefix(", "pathEnd",
            "complete(", "entity(",
            "def ", "class ", "object ", "trait ",
        ],
        "c": [
            "MHD_create_response", "MHD_add_connection_handler",
            "mg_set_request_handler", "mg_bind(", "mg_http_serve",
            "int main(", "static int", "static void",
            "void *", "char *", "#include",
        ],
        "cpp": [
            "CROW_ROUTE(", "crow::SimpleApp",
            "Rest::Router", "Rest::Routes::Get",
            "Rest::Routes::Post", "Rest::Routes::Put",
            "OATPP_COMPONENT(", "ENDPOINT(",
            "router->get(", "router->post(",
            "namespace ", "class ", "struct ",
            "public:", "virtual ", "template<",
        ],
        "h": [
            "typedef ", "struct ", "void ", "int ",
            "extern ", "#define ", "#ifndef ",
        ],
        "hpp": [
            "class ", "struct ", "namespace ",
            "template<", "virtual ", "public:",
        ],
    }

    patterns = PATTERNS_BY_LANG.get(ext, [])

    if not patterns:
        patterns = [
            "route", "endpoint", "handler", "controller",
            "get(", "post(", "put(", "delete(", "patch(",
            "prefix", "middleware", "class ", "func ", "def ",
            "async ", "export ",
        ]

    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped and any(p in stripped for p in patterns):
            filtered.append(line)

    if not filtered:
        return "\n".join(lines[:100])

    return "\n".join(filtered)


def _parse_provider_error(e: Exception) -> dict:
    err_str = str(e)

    http_code = None
    code_match = re.search(r"Error code:\s*(\d+)", err_str)
    if code_match:
        http_code = int(code_match.group(1))

    json_match = re.search(r"\{.*\}", err_str, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group().replace("'", '"')
            parsed   = json.loads(json_str)
            error    = parsed.get("error", {})
            return {
                "http_code":        http_code,
                "provider_message": error.get("message"),
                "provider_type":    error.get("type"),
                "provider_code":    error.get("code"),
            }
        except Exception:
            pass

    return {
        "http_code":        http_code,
        "provider_message": err_str,
    }


def _handle_ai_exception(e: Exception, owner: str, repo: str, target: str):
    err_str = str(e).lower()

    if "rate_limit" in err_str or "tokens per minute" in err_str or "429" in err_str:
        raise AIRateLimitError(owner=owner, repo=repo) from e

    if "request too large" in err_str or "context_length" in err_str:
        raise ValidationAppError(
            code    = "CONTEXT_TOO_LARGE",
            message = "Request too large for AI model.",
            details = {"owner": owner, "repo": repo},
        ) from e

    provider = _parse_provider_error(e)

    raise DocumentationGenerationError(
        target    = target,
        http_code = provider.get("http_code"),
        details   = {
            k: v for k, v in {
                "target":  target,
                "message": provider.get("provider_message"),
                "type":    provider.get("provider_type"),
                "code":    provider.get("provider_code"),
            }.items() if v is not None
        },
    ) from e


async def _extract_active_pages(
    file_list:    list[str],
    access_token: str,
    owner:        str,
    repo:         str,
) -> set[str]:

    route_files = [f for f in file_list if any(
        f.split("/")[-1].lower() == s for s in [
            "router.tsx", "router.ts", "router.jsx", "router.js",
            "routes.tsx", "routes.ts", "routes.jsx", "routes.js",
            "app.tsx",    "app.ts",    "app.jsx",    "app.js",
            "app-routing.module.ts", "app.routes.ts",
            "_app.tsx", "_app.js",
        ]
    )][:4]

    active_pages: set[str] = set()

    for rf in route_files:
        try:
            content = await fetch_file_content(access_token, owner, repo, rf)
            for line in content.splitlines():
                line_lower = line.lower()
                if "import" not in line_lower:
                    continue
                for folder in ("pages/", "views/", "screens/", "routes/"):
                    if folder not in line_lower:
                        continue
                    idx = line_lower.index(folder) + len(folder)
                    remainder = line_lower[idx:]
                    page_name = (
                        remainder.split("/")[0]
                        .split("'")[0]
                        .split('"')[0]
                        .split(".")[0]
                        .strip()
                    )
                    if page_name:
                        active_pages.add(page_name)
        except Exception:
            continue

    return active_pages


async def generate_documentation(
    target:       str,
    owner:        str,
    repo:         str,
    user_id:      int,
    doc_type:     str,
    access_token: str,
    db:           Session,
) -> dict:

    repo_full            = f"{owner}/{repo}"
    REPO_LEVEL_DOC_TYPES = {"readme", "arch", "onboard", "changelog", "api", "guide"}
    is_repo_level        = target == repo_full and doc_type in REPO_LEVEL_DOC_TYPES
    limit                = DOC_LIMITS.get(doc_type, 8)

    if is_repo_level:
        file_list = await fetch_all_repo_files(access_token, owner, repo)

        # ── GUIDE / ONBOARD ──────────────────────────────────────────
        if doc_type in ("guide", "onboard"):
            active_pages = await _extract_active_pages(file_list, access_token, owner, repo)

            if active_pages:
                priority = [f for f in file_list if (
                    any(p in f for p in ["pages/", "Pages/", "views/", "screens/"])
                    and any(page in f.lower() for page in active_pages)
                ) and f.endswith(CODE_EXTENSIONS)][:limit]
            else:
                priority = [f for f in file_list if (
                    any(p in f for p in ["pages/", "Pages/", "views/", "screens/"]) or
                    any(f.endswith(x) for x in [
                        "App.tsx", "App.ts", "App.jsx", "App.js",
                        "App.vue", "app.svelte",
                    ])
                ) and f.endswith(CODE_EXTENSIONS)][:limit]

            if not priority:
                return {
                    "fileName":    target,
                    "description": "No frontend code found in this repository.",
                    "markdown": (
                        "# User Guide\n\n"
                        "This repository does not appear to contain frontend code.\n\n"
                        "The **User Guide** documentation type is designed for frontend applications "
                        "(React, Vue, Angular, Svelte, etc.).\n\n"
                        "Consider using one of these instead:\n"
                        "- **API Reference** — for backend endpoints and services\n"
                        "- **Architecture** — for system design and component overview\n"
                        "- **Onboarding** — for developer setup guide\n"
                        "- **README** — for general project documentation\n"
                    ),
                    "contextFiles": [],
                }

        # ── API ──────────────────────────────────────────────────────
        elif doc_type == "api":

            # Frontend repo kontrolü — frontend'de API doc üretme
            if _is_frontend_repo(file_list):
                return {
                    "fileName":    target,
                    "description": "API Reference is not available for frontend repositories.",
                    "markdown": (
                        "# API Reference\n\n"
                        "This repository is a **frontend application** and does not define API endpoints.\n\n"
                        "Frontend applications consume APIs rather than define them.\n\n"
                        "Consider using one of these instead:\n"
                        "- **User Guide** — for end-user features and flows\n"
                        "- **Architecture** — for component structure and data flow\n"
                        "- **Onboarding** — for developer setup guide\n"
                        "- **README** — for general project documentation\n"
                    ),
                    "contextFiles": [],
                }

            router_files = [f for f in file_list
                            if _is_main_router(f) and f.endswith(CODE_EXTENSIONS)]

            schema_files = [f for f in file_list
                            if _is_schema(f) and f.endswith(CODE_EXTENSIONS)]

            all_routes = [f for f in file_list
                          if _is_route(f)
                          and f.endswith(CODE_EXTENSIONS)
                          and f not in router_files
                          and f not in schema_files]

            LARGE_ROUTE_KEYWORDS = ["agent", "admin", "v1", "v2", "v3"]
            other_routes = [f for f in all_routes
                            if not any(k in f.lower() for k in LARGE_ROUTE_KEYWORDS)]
            large_routes = [f for f in all_routes
                            if any(k in f.lower() for k in LARGE_ROUTE_KEYWORDS)]

            priority = router_files + schema_files + other_routes + large_routes

        # ── ARCH ─────────────────────────────────────────────────────
        elif doc_type == "arch":
            priority = [f for f in file_list if any(
                p in f for p in [
                    "routes/", "routers/",
                    "services/", "service/",
                    "controllers/", "handlers/",
                    "pages/", "views/", "screens/",
                    "core/", "lib/", "utils/",
                    "models/", "entities/",
                    "App.", "main.", "index.",
                ]
            ) and f.endswith(CODE_EXTENSIONS)][:limit]

        # ── README ───────────────────────────────────────────────────
        elif doc_type == "readme":
            env_configs = [f for f in file_list if f.split("/")[-1] in [
                ".env.example", ".env",
                "config.js", "config.ts", "config.py",
                "docker-compose.yml", "docker-compose.yaml",
                "vite.config.ts", "vite.config.js",
                "next.config.js", "next.config.ts",
                "nuxt.config.js", "nuxt.config.ts",
                "angular.json",
                "webpack.config.js",
            ]]

            auth_files = [f for f in file_list if any(
                x in f.lower() for x in [
                    "authcontext", "auth.ts", "auth.tsx", "auth.js",
                    "oauth", "keycloak", "jwt", "passport",
                    "authentication", "authorization",
                ]
            ) and f.endswith(CODE_EXTENSIONS)][:2]

            build_configs = [f for f in file_list if f.split("/")[-1] in [
                "requirements.txt", "pyproject.toml", "setup.py",
                "pom.xml", "build.gradle",
                "go.mod", "Cargo.toml", "Gemfile",
                "composer.json", "Dockerfile",
                "package.json",
            ]]

            already_included = set(env_configs + auth_files + build_configs)
            code_files = [f for f in file_list
                          if f.endswith(CODE_EXTENSIONS)
                          and f not in already_included][:limit]

            priority = env_configs + auth_files + build_configs + code_files

        # ── CHANGELOG / FUNCTION / DİĞER ─────────────────────────────
        else:
            priority = [f for f in file_list if f.endswith(CODE_EXTENSIONS)][:limit]

        # ── CONFIG DOSYALARI ─────────────────────────────────────────
        if doc_type == "readme":
            config = [f for f in file_list if f.split("/")[-1] == "README.md"][:1]
        elif doc_type == "api":
            config = []
        else:
            config = [f for f in file_list if
                      f.endswith((".md", ".json", ".yaml", ".yml", ".toml"))][:2]

        # ── CONTEXT BUILD ─────────────────────────────────────────────
        important = priority + config

        schema_contents = []
        router_contents = []
        route_contents  = []
        other_contents  = []

        for f in important:
            try:
                content = await fetch_file_content(access_token, owner, repo, f)

                if doc_type == "api":
                    if _is_main_router(f):
                        router_contents.append(
                            f"# ROUTER FILE (contains prefix definitions): {f}\n{content}"
                        )
                    elif _is_schema(f):
                        schema_contents.append(
                            f"# RESPONSE/REQUEST MODELS FILE: {f}\n"
                            f"# Use these class definitions to fill Response (200) sections\n"
                            f"{content}"
                        )
                    elif _is_route(f):
                        route_contents.append(
                            f"# ROUTE DEFINITIONS FILE: {f}\n"
                            f"# Combine prefix from ROUTER FILE + route path for full endpoint\n"
                            f"{_extract_route_signatures(content, f)}"
                        )
                    else:
                        other_contents.append(f"# {f}\n{content[:1500]}")
                else:
                    other_contents.append(f"# {f}\n{content[:2000]}")

            except Exception as e:
                raise FileContextError(file_path=f) from e

        # Schema önce → router → route'lar → diğerleri
        all_contents = schema_contents + router_contents + route_contents + other_contents
        context = "\n\n".join(all_contents)

    else:
        context = await fetch_file_content(access_token, owner, repo, target)

    # ── AI CALL ───────────────────────────────────────────────────────
    try:
        answer = chain.invoke({
            "context": context,
            "target":  target,
            "task":    TASK_PROMPT.get(doc_type, TASK_PROMPT["function"]),
            "guard":   HALLUCINATION_GUARD,
        })
    except Exception as e:
        _handle_ai_exception(e, owner, repo, target)

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
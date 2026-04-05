# app/core/constants.py

SUPPORTED_EXTENSIONS = (
    # Python
    ".py", ".pyx", ".pxd",
    # JavaScript / TypeScript
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Java
    ".java",
    # Kotlin
    ".kt", ".kts",
    # Go
    ".go",
    # Rust
    ".rs",
    # C / C++
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    # C#
    ".cs",
    # Ruby
    ".rb",
    # PHP
    ".php",
    # Swift
    ".swift",
    # Scala
    ".scala",
    # Shell
    ".sh", ".bash", ".zsh",
    # SQL
    ".sql",
    # Jupyter
    ".ipynb",
    # Web
    ".html",
    # Config / Infra
    ".yaml", ".yml", ".json", ".toml", ".ini", ".env",
    # Dockerfile
    "Dockerfile",
    # Markdown
    ".md", ".mdx",
    # R
    ".r", ".R",
    # Dart
    ".dart",
    # Elixir
    ".ex", ".exs",
    # Haskell
    ".hs",
    # Lua
    ".lua",
    # Perl
    ".pl",
    # Terraform
    ".tf",
)


TESTABLE_EXTENSIONS = [
    ".py",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java",
    ".kt", ".kts",
    ".go",
    ".rs",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".scala",
    ".dart",
    ".ex", ".exs",
    ".hs",
    ".lua",
    ".pl",
    ".r", ".R",
]

EXCLUDE_PATTERNS = [
    "test", "spec", "node_modules", "__pycache__",
    "postcss.config", "tailwind.config", "vite.config",
    "jest.config", "eslint", ".d.ts", "webpack.config",
    "alembic", "migration", "migrations",   # ← ekle
]
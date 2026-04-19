from app.services.agents.architecture import extract_ts_imports, resolve_ts_path

source = """
import { api } from '../../services/api'
import { useRepo } from '../../context/repoContext'
import withLayout from '../../layout/withLayout'
"""

file_path = "src/pages/profile/index.tsx"
all_paths = [
    "src/services/api/index.tsx",
    "src/services/index.ts",
    "src/context/repoContext.tsx",
    "src/layout/withLayout.tsx",
]

for imp in [
    "../../services/api",
    "../../context/repoContext",
    "../../layout/withLayout",
]:
    resolved = resolve_ts_path(imp, file_path)
    print(f"{imp} -> {resolved}")

result = extract_ts_imports(source, file_path, all_paths)
print("matched:", result)

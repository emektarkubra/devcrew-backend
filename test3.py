import os


def resolve_ts_path(imp, file_path):
    base_dir = os.path.dirname(file_path)
    resolved = os.path.normpath(os.path.join(base_dir, imp)).replace("\\", "/")
    resolved = resolved.lstrip("/")
    return resolved


file_path = "src/pages/profile/index.tsx"
all_paths = [
    "src/services/api/index.tsx",
    "src/services/index.ts",
    "src/context/repoContext.tsx",
    "src/layout/withLayout.tsx",
]

path_stems = {}
for path in all_paths:
    stem = path
    for ext in (".ts", ".tsx", ".js", ".jsx"):
        stem = stem.replace(ext, "")
    path_stems[path] = stem

for imp in [
    "../../services/api",
    "../../context/repoContext",
    "../../layout/withLayout",
]:
    resolved = resolve_ts_path(imp, file_path)
    print(f"\nimp={imp!r}")
    print(f"resolved={resolved!r}")
    for path, stem in path_stems.items():
        eq1 = stem == resolved
        eq2 = stem == resolved + "/index"
        print(f"  stem={stem!r}  ==resolved:{eq1}  ==resolved+/index:{eq2}")

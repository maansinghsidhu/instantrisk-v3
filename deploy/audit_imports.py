"""
Static import audit - checks all internal app.* imports resolve to actual files.
Also checks requirements.txt has all third-party imports.
"""
import ast
import os
import sys
from pathlib import Path
from collections import defaultdict

BASE = Path("backend-merged")
APP = BASE / "app"

# Get all Python files
py_files = list(APP.rglob("*.py"))
print(f"Scanning {len(py_files)} Python files...\n")

# Build set of available internal modules
available_modules = set()
for f in py_files:
    rel = f.relative_to(BASE)
    # Convert path to module name: app/routers/auth.py -> app.routers.auth
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        mod = ".".join(parts[:-1])
    else:
        mod = ".".join(parts)[:-3]  # strip .py
    available_modules.add(mod)

# Also add package names (directories with __init__.py)
for d in APP.rglob("__init__.py"):
    rel = d.parent.relative_to(BASE)
    available_modules.add(".".join(rel.parts))

# Parse requirements.txt for available third-party packages
req_file = BASE / "requirements.txt"
req_packages = set()
if req_file.exists():
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            # Extract package name (before ==, >=, etc.)
            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
            # Normalize: replace hyphens with underscores for import names
            req_packages.add(pkg.lower().replace("-", "_"))

# Common stdlib + well-known package import name mappings
PACKAGE_TO_IMPORT = {
    "python_jose": "jose",
    "python_dotenv": "dotenv",
    "python_multipart": "multipart",
    "python_dateutil": "dateutil",
    "python_magic": "magic",
    "python_bidi": "bidi",
    "pillow": "pil",
    "pymupdf": "fitz",
    "pydantic_settings": "pydantic_settings",
    "scikit_learn": "sklearn",
    "scikit_image": "skimage",
    "pyyaml": "yaml",
    "opencv_python": "cv2",
    "rapidocr_onnxruntime": "rapidocr_onnxruntime",
    "sentence_transformers": "sentence_transformers",
    "redis": "redis",
    "qdrant_client": "qdrant_client",
}

# Build import-name -> package mapping
available_imports = set()
for pkg in req_packages:
    available_imports.add(pkg)
    if pkg in PACKAGE_TO_IMPORT:
        available_imports.add(PACKAGE_TO_IMPORT[pkg])

# Add stdlib modules
import pkgutil
stdlib = {m.name for m in pkgutil.iter_modules()}
stdlib.update(sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') else set())

# Scan all files for imports
errors = []
warnings = []
internal_imports = defaultdict(list)  # module -> [(importing_file, line)]

for f in py_files:
    rel_path = str(f.relative_to(BASE))
    try:
        source = f.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as e:
        errors.append(f"SYNTAX ERROR: {rel_path}: {e}")
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app."):
                # Internal import - check if target module exists
                mod = node.module
                # Check exact module
                if mod not in available_modules:
                    # Check if it's a package (might import from __init__)
                    parts = mod.split(".")
                    found = False
                    # Try progressively shorter paths
                    for i in range(len(parts), 0, -1):
                        candidate = ".".join(parts[:i])
                        if candidate in available_modules:
                            found = True
                            break
                    if not found:
                        errors.append(f"MISSING MODULE: {rel_path}:{node.lineno} -> from {mod} import ...")
                internal_imports[mod].append((rel_path, node.lineno))

            elif node.module:
                # Third-party import - check if in requirements
                top_level = node.module.split(".")[0].lower()
                if top_level not in stdlib and top_level not in available_imports and top_level not in available_modules:
                    warnings.append(f"MISSING PACKAGE? {rel_path}:{node.lineno} -> from {node.module} import ... (top-level: {top_level})")

        elif isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0].lower()
                if top_level not in stdlib and top_level not in available_imports and top_level.startswith("app."):
                    if top_level not in available_modules:
                        errors.append(f"MISSING MODULE: {rel_path}:{node.lineno} -> import {alias.name}")

# Report
print("=" * 60)
print("IMPORT AUDIT RESULTS")
print("=" * 60)

if errors:
    print(f"\nERRORS ({len(errors)}):")
    for e in sorted(set(errors)):
        print(f"  {e}")

if warnings:
    print(f"\nWARNINGS ({len(warnings)}):")
    for w in sorted(set(warnings)):
        print(f"  {w}")

if not errors and not warnings:
    print("\nALL IMPORTS VERIFIED - No issues found!")

print(f"\nTotal files: {len(py_files)}")
print(f"Internal modules: {len(available_modules)}")
print(f"Requirements packages: {len(req_packages)}")

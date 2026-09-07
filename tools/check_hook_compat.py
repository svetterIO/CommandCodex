#!/usr/bin/env python3
"""Source-level regression checks for the Material 9.x search bridge."""
from __future__ import annotations

import ast
from pathlib import Path

HOOK = Path("hooks/in_memory_content.py")
text = HOOK.read_text(encoding="utf-8")
tree = ast.parse(text, filename=str(HOOK))

required = [
    '"material/search"',
    'suffix="search"',
    '_PatchedMaterialWarningFilter',
    'mkdocs.plugins.encryptcontent',
    'original_generate(*args, **kwargs)',
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(f"Hook compatibility markers missing: {missing}")

wrapper = None
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "generate_search_index_without_protected_disk_copy":
        wrapper = node
        break
if wrapper is None:
    raise SystemExit("Search-index wrapper function is missing")
if wrapper.args.vararg is None or wrapper.args.kwarg is None:
    raise SystemExit(
        "Search-index wrapper must accept *args and **kwargs so Material 9.7's "
        "search_index_prev argument is forwarded"
    )

print("Hook compatibility check passed:")
print("- Material namespaced search is supported")
print("- generate_search_index positional/keyword arguments are forwarded")

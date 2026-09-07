#!/usr/bin/env python3
"""Verify live command variables cannot be pre-seeded or persisted by the site."""
from pathlib import Path

SOURCE = Path("docs/assets/js/variables.js")
if not SOURCE.is_file():
    raise SystemExit(f"Missing live-variable script: {SOURCE}")

text = SOURCE.read_text(encoding="utf-8")
for forbidden in (
    "localStorage",
    "sessionStorage",
    "PENTEST_VAR_",
    "PENTEST_VAR_DEFAULTS",
    "BUILTIN_DEFAULTS",
    "BUILD_DEFAULTS",
):
    if forbidden in text:
        raise SystemExit(f"Live-variable script contains forbidden persistence/default primitive: {forbidden}")

for forbidden_path in (
    Path(".env.example"),
    Path("docs/assets/js/var-defaults.js"),
    Path("hooks/env_defaults.py"),
):
    if forbidden_path.exists():
        raise SystemExit(f"Legacy build-time variable-default artifact exists: {forbidden_path}")

site_script = Path("site/assets/js/variables.js")
if site_script.is_file():
    built = site_script.read_text(encoding="utf-8", errors="replace")
    for forbidden in ("localStorage", "sessionStorage", "PENTEST_VAR_", "BUILTIN_DEFAULTS", "BUILD_DEFAULTS"):
        if forbidden in built:
            raise SystemExit(f"Generated variable script contains forbidden primitive: {forbidden}")

print("Live-variable security check passed: no defaults, build-time injection, or browser storage.")

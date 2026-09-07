#!/usr/bin/env python3
"""Fail if a protected authoring page has been materialized as plaintext."""
from pathlib import Path

MARKER = "<!-- encrypted-source -->"
DOCS = Path("docs")
CONTENT = Path("content")

protected = []
for page in DOCS.rglob("*.md"):
    if page.read_text(encoding="utf-8").strip() != MARKER:
        continue
    rel = page.relative_to(DOCS)
    encrypted = CONTENT / Path(str(rel) + ".enc.json")
    if not encrypted.is_file():
        raise SystemExit(f"Marker page has no matching encrypted source: {page} -> {encrypted}")
    protected.append((page, encrypted))

if not protected:
    raise SystemExit("No protected marker pages were found")

for encrypted in CONTENT.rglob("*.md.enc.json"):
    rel_text = str(encrypted.relative_to(CONTENT))
    marker_rel = Path(rel_text.removesuffix(".enc.json"))
    marker = DOCS / marker_rel
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != MARKER:
        raise SystemExit(f"Encrypted source has no matching marker page: {encrypted}")

for pattern in ("content/**/*.md", "*.decrypted.md", "plaintext/**/*.md"):
    matches = [p for p in Path(".").glob(pattern) if p.is_file()]
    if matches:
        raise SystemExit(f"Plaintext protected authoring file detected: {matches[0]}")

print(
    f"Source-layout check passed: {len(protected)} protected page(s), "
    "with no plaintext protected authoring Markdown file."
)

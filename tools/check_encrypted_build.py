#!/usr/bin/env python3
"""Verify protected content is encrypted in generated output and search."""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

from page_crypto import decrypt_source

SITE = Path("site")
DOCS = Path("docs")
CONTENT = Path("content")
MARKER = "<!-- encrypted-source -->"
PASSWORD_ENV = "CONTENT_PASSWORD"

required = [
    SITE / "index.html",
    SITE / "search" / "search_index.json",
    SITE / "search" / "encrypted_search_index.json",
    SITE / "assets" / "javascripts" / "decrypt-contents.js",
    SITE / "editor" / "index.html",
    SITE / "editor" / "app.js",
    SITE / "editor" / "crypto.js",
]
for path in required:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Missing expected build artifact: {path}")

for path in SITE.rglob("*.md"):
    if path.is_file():
        raise SystemExit(f"Unexpected Markdown file in generated site: {path}")

protected_pages = []
for marker_page in DOCS.rglob("*.md"):
    if marker_page.read_text(encoding="utf-8").strip() != MARKER:
        continue
    rel = marker_page.relative_to(DOCS)
    source = CONTENT / Path(str(rel) + ".enc.json")
    if not source.is_file():
        raise SystemExit(f"Missing encrypted source for marker page: {marker_page}")
    if rel.name == "index.md":
        output = SITE / rel.parent / "index.html"
        location = "" if str(rel.parent) == "." else rel.parent.as_posix().rstrip("/") + "/"
    else:
        stem = rel.with_suffix("")
        output = SITE / stem / "index.html"
        location = stem.as_posix().rstrip("/") + "/"
    protected_pages.append((rel, source, output, location))

if not protected_pages:
    raise SystemExit("No protected pages found for encrypted-build verification")

for rel, source, output, location in protected_pages:
    if not output.is_file():
        raise SystemExit(f"Missing protected page output for {rel}: {output}")
    page_html = output.read_text(encoding="utf-8")
    for marker in (
        'id="mkdocs-encrypted-content"',
        'id="mkdocs-decrypted-content"',
        'id="mkdocs-content-password"',
    ):
        if marker not in page_html:
            raise SystemExit(f"Protected page {rel} is missing encryptcontent marker: {marker}")
    match = re.search(
        r'<div id="mkdocs-encrypted-content"[^>]*>([^<]+)</div>',
        page_html,
        flags=re.IGNORECASE,
    )
    if not match or match.group(1).count(";") != 1:
        raise SystemExit(f"Protected page {rel} does not contain the expected ciphertext bundle")

# Home is intentionally public and must not accidentally be globally encrypted.
public_home = (SITE / "index.html").read_text(encoding="utf-8")
if 'id="mkdocs-encrypted-content"' in public_home:
    raise SystemExit("Public home page was unexpectedly encrypted")

clear_search = json.loads((SITE / "search" / "search_index.json").read_text(encoding="utf-8"))
for entry in clear_search.get("docs", []):
    location = entry.get("location", "")
    for _, _, _, protected_location in protected_pages:
        if location == protected_location or location.startswith(protected_location + "#"):
            raise SystemExit(
                f"Clear search index contains protected page entry at {location!r}"
            )
if "index" in clear_search:
    raise SystemExit("Clear search index contains a prebuilt index that could retain protected terms")

encrypted_search = json.loads(
    (SITE / "search" / "encrypted_search_index.json").read_text(encoding="utf-8")
)
if not isinstance(encrypted_search, dict) or not encrypted_search:
    raise SystemExit("Encrypted search index is empty")
for key_id, bundle in encrypted_search.items():
    if not isinstance(key_id, str) or not isinstance(bundle, str) or bundle.count(";") != 1:
        raise SystemExit("Encrypted search index has an unexpected format")

decrypt_js = (SITE / "assets" / "javascripts" / "decrypt-contents.js").read_text(encoding="utf-8")
if "encryptcontent_event" not in decrypt_js:
    raise SystemExit("Generated decryptor is missing encryptcontent_event")

bundle_dir = SITE / "assets" / "javascripts"
bundles = sorted(p for p in bundle_dir.glob("bundle*.js") if p.is_file() and p.stat().st_size)
if not bundles:
    raise SystemExit("Generated Material JavaScript bundle was not found")
if not any("encrypted_search_index.json" in p.read_text(encoding="utf-8", errors="replace") for p in bundles):
    raise SystemExit("Generated Material bundle is missing the dynamic encrypted-search patch")

# Editor must remain self-contained and must not contain an outbound fetch/XHR endpoint.
editor_files = [SITE / "editor" / "index.html", SITE / "editor" / "app.js", SITE / "editor" / "crypto.js"]
editor_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in editor_files)
for forbidden in ("fetch(", "XMLHttpRequest", "navigator.sendBeacon", "localStorage.", "indexedDB."):
    if forbidden in editor_text:
        raise SystemExit(f"Editor contains forbidden persistence/network primitive: {forbidden}")

password = os.environ.get(PASSWORD_ENV)
if not password:
    raise SystemExit(f"{PASSWORD_ENV} is required for the in-memory leakage check")

probes: set[bytes] = set()
for _, source, _, _ in protected_pages:
    payload = json.loads(source.read_text(encoding="utf-8"))
    try:
        protected_text = decrypt_source(payload, password).decode("utf-8")
    except Exception as exc:
        raise SystemExit(f"Could not decrypt {source} for leakage verification") from exc

    for raw_line in protected_text.splitlines():
        source_line = raw_line.strip()
        if not source_line or source_line.startswith("```"):
            continue
        variants = {source_line}
        structural = re.sub(r"^(?:#{1,6}|>|[-+*]|\d+[.)])\s+", "", source_line).strip()
        if structural:
            variants.add(structural)
        delimiter_free = re.sub(r"[`*_~]", "", structural).strip()
        if delimiter_free:
            variants.add(delimiter_free)
        for value in variants:
            if len(value) < 20:
                continue
            for representation in (value, html.escape(value, quote=False)):
                probes.add(representation.encode("utf-8"))
    del protected_text

for path in SITE.rglob("*"):
    if not path.is_file():
        continue
    data = path.read_bytes()
    for probe in probes:
        if probe in data:
            raise SystemExit(
                f"Potential protected-source fragment leaked into generated file: {path} "
                f"(fragment length {len(probe)} bytes)"
            )

print("Encrypted build check passed.")
print(f"- {len(protected_pages)} protected page(s) emitted only as encrypted content")
print("- clear search index contains no protected page entries")
print("- encrypted search index and patched Material search runtime are present")
print("- integrated browser editor is present and contains no network/persistence API use")
print(f"- {len(probes)} in-memory source-derived leak probes were absent from generated files")

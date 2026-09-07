#!/usr/bin/env python3
"""Verify live variables are schema-free in public JS and configured only after unlock."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SOURCE = Path("docs/assets/js/variables.js")
CONTENT = Path("content")
SITE = Path("site")
PASSWORD_ENV = "CONTENT_PASSWORD"
TEMPLATE_ID = "commandcodex-variable-config"
TOKEN_PATTERN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
CONFIG_PATTERN = re.compile(
    rf'<template\s+id=["\']{re.escape(TEMPLATE_ID)}["\']\s*>(.*?)</template>',
    flags=re.IGNORECASE | re.DOTALL,
)

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
    "const TOKENS",
    "MASKED_TOKENS",
):
    if forbidden in text:
        raise SystemExit(
            f"Live-variable script contains forbidden persistence/public-schema primitive: {forbidden}"
        )

for required in (
    TEMPLATE_ID,
    "TOKEN_PATTERN",
    "discoverTokens",
    "JSON.parse",
    "manualOverrides",
    "Restore page defaults",
):
    if required not in text:
        raise SystemExit(f"Live-variable script is missing dynamic encrypted-config support: {required}")

for forbidden_path in (
    Path(".env.example"),
    Path("docs/assets/js/var-defaults.js"),
    Path("hooks/env_defaults.py"),
):
    if forbidden_path.exists():
        raise SystemExit(f"Legacy build-time variable-default artifact exists: {forbidden_path}")

validated_blocks = 0
all_discovered_tokens: set[str] = set()
password = os.environ.get(PASSWORD_ENV)
if password:
    sys.path.insert(0, str(Path("tools").resolve()))
    from page_crypto import decrypt_source  # type: ignore

    for source in CONTENT.rglob("*.md.enc.json"):
        payload = json.loads(source.read_text(encoding="utf-8"))
        try:
            clear = decrypt_source(payload, password).decode("utf-8")
        except Exception as exc:
            raise SystemExit(f"Could not decrypt {source} while validating variable config") from exc

        discovered = set(TOKEN_PATTERN.findall(clear))
        all_discovered_tokens.update(discovered)

        for match in CONFIG_PATTERN.finditer(clear):
            validated_blocks += 1
            try:
                config = json.loads(match.group(1).strip())
            except Exception as exc:
                raise SystemExit(f"Invalid encrypted variable-config JSON in {source}") from exc
            if not isinstance(config, dict):
                raise SystemExit(f"Encrypted variable config must be a JSON object in {source}")
            all_discovered_tokens.update(config.keys())

            for token, spec in config.items():
                if not re.fullmatch(r"[A-Z][A-Z0-9_]*", token):
                    raise SystemExit(f"Invalid encrypted variable name {token!r} in {source}")
                if not isinstance(spec, dict):
                    raise SystemExit(f"Encrypted config for {token} in {source} must be an object")
                unknown_props = set(spec) - {"default", "secret"}
                if unknown_props:
                    raise SystemExit(
                        f"Unsupported encrypted config properties for {token} in {source}: "
                        + ", ".join(sorted(unknown_props))
                    )
                value = spec.get("default", "")
                if value is not None and not isinstance(value, (str, int, float, bool)):
                    raise SystemExit(f"Encrypted default for {token} in {source} must be scalar")
                if "secret" in spec and not isinstance(spec["secret"], bool):
                    raise SystemExit(f"Encrypted secret flag for {token} in {source} must be boolean")
        del clear

# Learn the real schema only from decrypted content, then ensure none of those names
# were hardcoded as string literals in the public variable engine.
for token in all_discovered_tokens:
    literal = re.compile(rf"(['\"])({re.escape(token)})\1")
    if literal.search(text):
        raise SystemExit(
            f"Public variable engine hardcodes a protected-page variable name: {token}"
        )

site_script = SITE / "assets" / "js" / "variables.js"
if site_script.is_file():
    built = site_script.read_text(encoding="utf-8", errors="replace")
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "PENTEST_VAR_",
        "BUILTIN_DEFAULTS",
        "BUILD_DEFAULTS",
        "const TOKENS",
        "MASKED_TOKENS",
    ):
        if forbidden in built:
            raise SystemExit(f"Generated variable script contains forbidden primitive: {forbidden}")
    for token in all_discovered_tokens:
        literal = re.compile(rf"(['\"])({re.escape(token)})\1")
        if literal.search(built):
            raise SystemExit(
                f"Generated public variable engine hardcodes protected-page variable name: {token}"
            )

if SITE.is_dir():
    raw_template = f'<template id="{TEMPLATE_ID}">'.encode("utf-8")
    for page in SITE.rglob("*.html"):
        if raw_template in page.read_bytes():
            raise SystemExit(f"Encrypted variable config leaked into generated HTML: {page}")

print(
    "Live-variable security check passed: public JS contains no fixed variable schema, "
    "no browser persistence/build-time defaults; "
    f"validated {validated_blocks} encrypted variable-config block(s)."
)

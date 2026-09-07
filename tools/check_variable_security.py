#!/usr/bin/env python3
"""Verify live command variables are memory-only and page defaults stay encrypted."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SOURCE = Path("docs/assets/js/variables.js")
CONTENT = Path("content")
DOCS = Path("docs")
SITE = Path("site")
PASSWORD_ENV = "CONTENT_PASSWORD"
TEMPLATE_ID = "commandcodex-variable-defaults"
TOKENS = {
    "IP", "PORT", "URL", "DOMAIN", "DC", "IFACE", "LHOST", "LPORT",
    "USER", "PASS", "HASH", "TOKEN", "WORDLIST", "SHARE", "OUT",
}

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
        raise SystemExit(
            f"Live-variable script contains forbidden persistence/public-default primitive: {forbidden}"
        )

for required in (
    TEMPLATE_ID,
    "JSON.parse",
    "MANUAL_OVERRIDES",
    "Restore page defaults",
):
    if required not in text:
        raise SystemExit(f"Live-variable script is missing encrypted-default support: {required}")

for forbidden_path in (
    Path(".env.example"),
    Path("docs/assets/js/var-defaults.js"),
    Path("hooks/env_defaults.py"),
):
    if forbidden_path.exists():
        raise SystemExit(f"Legacy build-time variable-default artifact exists: {forbidden_path}")

# Public documentation may mention the template syntax, but actual default values
# are validated only from encrypted content sources below.

site_script = SITE / "assets" / "js" / "variables.js"
if site_script.is_file():
    built = site_script.read_text(encoding="utf-8", errors="replace")
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "PENTEST_VAR_",
        "BUILTIN_DEFAULTS",
        "BUILD_DEFAULTS",
    ):
        if forbidden in built:
            raise SystemExit(f"Generated variable script contains forbidden primitive: {forbidden}")

# If the build password is available, inspect encrypted sources in memory and validate
# any per-page defaults block. The plaintext is never written to a file.
validated_blocks = 0
password = os.environ.get(PASSWORD_ENV)
if password:
    sys.path.insert(0, str(Path("tools").resolve()))
    from page_crypto import decrypt_source  # type: ignore

    pattern = re.compile(
        rf'<template\s+id=["\']{re.escape(TEMPLATE_ID)}["\']\s*>(.*?)</template>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    for source in CONTENT.rglob("*.md.enc.json"):
        payload = json.loads(source.read_text(encoding="utf-8"))
        try:
            clear = decrypt_source(payload, password).decode("utf-8")
        except Exception as exc:
            raise SystemExit(f"Could not decrypt {source} while validating page defaults") from exc

        for match in pattern.finditer(clear):
            validated_blocks += 1
            try:
                defaults = json.loads(match.group(1).strip())
            except Exception as exc:
                raise SystemExit(f"Invalid encrypted variable-default JSON in {source}") from exc
            if not isinstance(defaults, dict):
                raise SystemExit(f"Encrypted variable defaults must be a JSON object in {source}")
            unknown = set(defaults) - TOKENS
            if unknown:
                raise SystemExit(
                    f"Encrypted variable defaults contain unsupported token(s) in {source}: "
                    + ", ".join(sorted(unknown))
                )
            for token, value in defaults.items():
                if value is not None and not isinstance(value, (str, int, float, bool)):
                    raise SystemExit(
                        f"Encrypted variable default {token} in {source} must be a scalar value"
                    )
        del clear

# Once a site exists, raw defaults templates must not survive into generated HTML;
# they are expected to be inside encryptcontent ciphertext until browser unlock.
if SITE.is_dir():
    raw_template = f'<template id="{TEMPLATE_ID}">'.encode("utf-8")
    for page in SITE.rglob("*.html"):
        if raw_template in page.read_bytes():
            raise SystemExit(f"Encrypted variable-default template leaked into generated HTML: {page}")

print(
    "Live-variable security check passed: no public/build-time defaults or browser storage; "
    f"validated {validated_blocks} encrypted page-default block(s)."
)

"""Decrypt protected Markdown only in memory and keep protected search plaintext off disk.

Any Markdown file under ``docs/`` whose entire body is ``<!-- encrypted-source -->``
is a protected page. Its authoring source is resolved by path under ``content/``:
``docs/cheatsheets/nmap.md`` -> ``content/cheatsheets/nmap.md.enc.json``.

The source is decrypted to a Python string in ``on_page_markdown``. No plaintext
Markdown file is created. Dynamic search is also intercepted so protected search
entries are encrypted directly from memory rather than first being written to the
normal search index.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from mkdocs import plugins

log = logging.getLogger("mkdocs.hooks.in_memory_content")

TARGET_MARKER = "<!-- encrypted-source -->"
SOURCE_AAD = b"security-reference:source:v1"
PASSWORD_ENV = "CONTENT_PASSWORD"

_STATE: dict[str, Any] = {
    "clear_search_json": None,
    "dynamic_decrypt_js": None,
}


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value)


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    ).derive(password.encode("utf-8"))


def _project_root(config) -> Path:
    return Path(config["config_file_path"]).resolve().parent


def _source_path_for_page(config, src_uri: str) -> Path:
    relative = Path(src_uri)
    return _project_root(config) / "content" / Path(str(relative) + ".enc.json")


def _decrypt_source(config, src_uri: str) -> str:
    password = os.environ.get(PASSWORD_ENV)
    if not password:
        raise RuntimeError(
            f"{PASSWORD_ENV} is required; refusing to decrypt protected source"
        )

    source_path = _source_path_for_page(config, src_uri)
    if not source_path.is_file():
        raise RuntimeError(f"Encrypted source is missing for {src_uri}: {source_path}")

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise RuntimeError("Unsupported encrypted source format")

    aad = _b64decode(payload["aad"])
    if aad != SOURCE_AAD:
        raise RuntimeError("Unexpected encrypted source label")

    key = _derive_key(password, _b64decode(payload["salt"]), int(payload["iterations"]))
    try:
        plaintext = AESGCM(key).decrypt(
            _b64decode(payload["iv"]),
            _b64decode(payload["ciphertext"]),
            aad,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Incorrect content password or damaged encrypted source for {src_uri}"
        ) from exc

    try:
        markdown = plaintext.decode("utf-8")
    finally:
        del plaintext

    if not markdown.strip() or not markdown.lstrip().startswith(("#", "---")):
        raise RuntimeError(f"Decrypted source for {src_uri} failed sanity checks")
    return markdown


@plugins.event_priority(100)
def on_page_markdown(markdown, page, config, **kwargs):
    """Replace an encrypted-source marker with decrypted Markdown in memory."""
    stripped = markdown.strip()
    if stripped != TARGET_MARKER:
        return markdown

    log.info(
        "Loading protected source for %s into memory (no plaintext Markdown file)",
        page.file.src_uri,
    )
    return _decrypt_source(config, page.file.src_uri)


def _matches_protected_location(location: str, protected_location: str) -> bool:
    return location == protected_location or location.startswith(protected_location + "#")


def _strip_protected_docs(index_data: dict[str, Any], locations: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(index_data)
    docs = []
    for entry in index_data.get("docs", []):
        location = entry.get("location", "")
        if any(_matches_protected_location(location, p) for p in locations):
            continue
        docs.append(entry)
    sanitized["docs"] = docs
    sanitized.pop("index", None)
    return sanitized


_PATCH_WARNING = (
    "To enable EXPERIMENTAL search index decryption mkdocs-material needs to be "
    "customized (patched)!"
)


class _PatchedMaterialWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == "mkdocs.plugins.encryptcontent"
            and record.levelno == logging.WARNING
            and record.getMessage() == _PATCH_WARNING
        )


_PATCH_WARNING_FILTER = _PatchedMaterialWarningFilter()


@plugins.event_priority(100)
def on_config(config, **kwargs):
    # Protected source cannot be built without the encryption password. Keep the
    # password in the process environment only; never materialize it into docs/.
    if not os.environ.get(PASSWORD_ENV):
        raise RuntimeError(
            f"{PASSWORD_ENV} is required; refusing to build protected pages without a password"
        )

    logger = logging.getLogger("mkdocs.plugins.encryptcontent")
    if _PATCH_WARNING_FILTER not in logger.filters:
        logger.addFilter(_PATCH_WARNING_FILTER)
    return config


def _resolve_plugin(config, *exact_names: str, suffix: str | None = None):
    collection = config.plugins
    for name in exact_names:
        plugin = collection.get(name)
        if plugin is not None:
            return name, plugin
    if suffix:
        for name, plugin in collection.items():
            if name == suffix or name.endswith("/" + suffix):
                return name, plugin
    return None, None


@plugins.event_priority(-100)
def on_pre_build(config, **kwargs):
    """Wrap search-index generation so protected entries never hit disk in clear."""
    search_name, search_plugin = _resolve_plugin(
        config, "material/search", "search", suffix="search"
    )
    encrypt_name, encrypt_plugin = _resolve_plugin(
        config, "encryptcontent", suffix="encryptcontent"
    )
    if search_plugin is None or encrypt_plugin is None:
        available = ", ".join(config.plugins.keys())
        raise RuntimeError(
            "Both search and encryptcontent plugins are required; "
            f"loaded plugins: {available}"
        )

    log.info(
        "Resolved search plugin %r and encryption plugin %r", search_name, encrypt_name
    )

    if _STATE.pop("search_mode_temporarily_clear", False):
        encrypt_plugin.config["search_index"] = "dynamically"
    _STATE["clear_search_json"] = None
    _STATE["dynamic_decrypt_js"] = None

    if encrypt_plugin.config["search_index"] != "dynamically":
        raise RuntimeError("encryptcontent.search_index must remain 'dynamically'")
    if not hasattr(search_plugin, "search_index"):
        raise RuntimeError("Search index was not initialized before in-memory hook")

    original_generate = search_plugin.search_index.generate_search_index

    def generate_search_index_without_protected_disk_copy(*args, **kwargs):
        clear_json = original_generate(*args, **kwargs)
        _STATE["clear_search_json"] = clear_json
        clear_data = json.loads(clear_json)
        locations = encrypt_plugin.setup.get("locations", {})
        sanitized = _strip_protected_docs(clear_data, locations)
        return json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"))

    search_plugin.search_index.generate_search_index = (
        generate_search_index_without_protected_disk_copy
    )


def _build_encrypted_search_index(clear_data: dict[str, Any], encrypt_plugin) -> dict[str, str]:
    encrypted_search: dict[str, tuple[bytes, list[dict[str, Any]]]] = {}
    locations = encrypt_plugin.setup.get("locations", {})

    for entry in clear_data.get("docs", []):
        location = entry.get("location", "")
        for protected_location, key_and_id in locations.items():
            if _matches_protected_location(location, protected_location):
                page_key, page_id = key_and_id
                if page_key is not None:
                    if page_id not in encrypted_search:
                        encrypted_search[page_id] = (page_key, [])
                    encrypted_search[page_id][1].append(entry)
                break

    result: dict[str, str] = {}
    encrypt_text = getattr(encrypt_plugin, "__encrypt_text__", None)
    if encrypt_text is None:
        raise RuntimeError(
            "mkdocs-encryptcontent-plugin internals changed; expected __encrypt_text__"
        )

    for key_id, (key, entries) in encrypted_search.items():
        plaintext_json = json.dumps(entries, ensure_ascii=False)
        iv, ciphertext = encrypt_text(plaintext_json, key)
        result[key_id] = f"{iv};{ciphertext}"

    return result


@plugins.event_priority(-100)
def on_post_build(config, **kwargs):
    """Write protected search entries encrypted and avoid upstream plaintext rewrite."""
    _, encrypt_plugin = _resolve_plugin(config, "encryptcontent", suffix="encryptcontent")
    if encrypt_plugin is None:
        available = ", ".join(config.plugins.keys())
        raise RuntimeError(
            "encryptcontent plugin missing at post-build; "
            f"loaded plugins: {available}"
        )

    clear_json = _STATE.get("clear_search_json")
    if not clear_json:
        raise RuntimeError("Clear search index was not captured in memory")

    clear_data = json.loads(clear_json)
    encrypted_search = _build_encrypted_search_index(clear_data, encrypt_plugin)
    if not encrypted_search:
        raise RuntimeError("No encrypted search entries were generated")

    search_dir = Path(config["site_dir"]) / "search"
    search_dir.mkdir(parents=True, exist_ok=True)
    (search_dir / "encrypted_search_index.json").write_text(
        json.dumps(encrypted_search, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    generate_js = getattr(encrypt_plugin, "__generate_decrypt_js__", None)
    if generate_js is None:
        raise RuntimeError(
            "mkdocs-encryptcontent-plugin internals changed; expected __generate_decrypt_js__"
        )
    dynamic_js = generate_js()
    _STATE["dynamic_decrypt_js"] = dynamic_js
    encrypt_plugin.__generate_decrypt_js__ = lambda: dynamic_js
    encrypt_plugin.config["search_index"] = "clear"
    _STATE["search_mode_temporarily_clear"] = True

    log.info(
        "Protected search entries encrypted directly from memory; no clear protected search index was written"
    )

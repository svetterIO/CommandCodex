#!/usr/bin/env python3
"""Encrypt/decrypt authoring Markdown stored outside docs/.

The normal site build never invokes the decrypt-to-stdout command. Protected
Markdown is decrypted directly in the MkDocs process by hooks/in_memory_content.py.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 600_000
SOURCE_AAD = b"security-reference:source:v1"
PASSWORD_ENV = "CONTENT_PASSWORD"


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(data: str) -> bytes:
    return base64.b64decode(data)


def derive(password: str, salt: bytes, iterations: int) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations
    ).derive(password.encode("utf-8"))


def read_password(confirm: bool) -> str:
    value = os.environ.get(PASSWORD_ENV)
    if value:
        return value
    first = getpass.getpass("Content password: ")
    if not first:
        raise SystemExit("Password must not be empty")
    if confirm:
        second = getpass.getpass("Confirm password: ")
        if first != second:
            raise SystemExit("Passwords do not match")
    return first


def encrypt_source(data: bytes, password: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = derive(password, salt, ITERATIONS)
    ciphertext = AESGCM(key).encrypt(iv, data, SOURCE_AAD)
    return {
        "version": 1,
        "cipher": "AES-256-GCM",
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": ITERATIONS,
        "salt": b64(salt),
        "iv": b64(iv),
        "aad": b64(SOURCE_AAD),
        "ciphertext": b64(ciphertext),
    }


def decrypt_source(payload: dict, password: str) -> bytes:
    if payload.get("version") != 1:
        raise ValueError("Unsupported encrypted payload version")
    aad = unb64(payload["aad"])
    if aad != SOURCE_AAD:
        raise ValueError("Unexpected encrypted-source label")
    key = derive(password, unb64(payload["salt"]), int(payload["iterations"]))
    return AESGCM(key).decrypt(
        unb64(payload["iv"]), unb64(payload["ciphertext"]), aad
    )


def cmd_encrypt(args: argparse.Namespace) -> None:
    data = sys.stdin.buffer.read() if args.input == "-" else Path(args.input).read_bytes()
    payload = encrypt_source(data, read_password(confirm=True))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Encrypted authoring source: {out}")


def cmd_decrypt(args: argparse.Namespace) -> None:
    payload = json.loads(Path(args.source).read_text(encoding="utf-8"))
    try:
        data = decrypt_source(payload, read_password(confirm=False))
    except Exception as exc:
        raise SystemExit("Incorrect password or damaged encrypted source") from exc
    sys.stdout.buffer.write(data)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encrypt-source", help="Encrypt Markdown authoring source")
    enc.add_argument("input", help="Markdown path, or - for stdin")
    enc.add_argument("--output", required=True, help="Destination .md.enc.json path")
    enc.set_defaults(func=cmd_encrypt)

    dec = sub.add_parser("decrypt-source", help="Decrypt Markdown source to stdout")
    dec.add_argument("source", help="Encrypted .md.enc.json path")
    dec.set_defaults(func=cmd_decrypt)
    return p


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

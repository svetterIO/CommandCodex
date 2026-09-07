#!/usr/bin/env python3
"""Fetch pinned browser-side vendor assets used by the local site."""

from __future__ import annotations

import pathlib
import urllib.request

MERMAID_VERSION = "11.16.1"
MERMAID_URL = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
DEST = pathlib.Path("docs/assets/vendor/mermaid.min.js")


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size > 1_000_000:
        print(f"Mermaid runtime already present: {DEST}")
        return

    print(f"Fetching Mermaid {MERMAID_VERSION}...")
    request = urllib.request.Request(
        MERMAID_URL,
        headers={"User-Agent": "commandcodex-build/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()

    if len(data) < 1_000_000:
        raise SystemExit("Downloaded Mermaid asset is unexpectedly small")

    DEST.write_bytes(data)
    print(f"Wrote {DEST} ({len(data)} bytes)")


if __name__ == "__main__":
    main()

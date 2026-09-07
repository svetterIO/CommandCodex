---
password: ""
---

# CommandCodex

**Fast reference. Ready commands. One collection.**

A command-focused security cheat sheet collection built to grow across tools, techniques, and workflows. Protected cheat-sheet content is encrypted on disk and decrypted only in browser memory after you enter the site password.

!!! warning "Verify all commands before use"
    Validate commands, scope, timing, and impact before using anything from this reference. Use intrusive techniques only on systems you own or are explicitly authorized to test.

## Cheat sheets

- [Nmap](cheatsheets/nmap.md) — discovery, TCP/UDP scanning, service and OS detection, NSE, and evidence-oriented output.

## Browser source editor

Use the [Encrypted Markdown Source Editor](source-editor.md) to open a `content/**/*.md.enc.json` file, decrypt it in browser memory, edit the raw Markdown, and re-encrypt it without intentionally creating a plaintext Markdown file on disk.

## Adding more cheat sheets

Each protected page uses a harmless marker under `docs/` and a matching encrypted source under `content/`. For example:

```text
# Published page marker
docs/cheatsheets/example.md

# Encrypted authoring source
content/cheatsheets/example.md.enc.json
```

The marker file contains only:

```text
<!-- encrypted-source -->
```

Add the new Markdown page to `nav` in `mkdocs.yml`, then rebuild. The in-memory hook resolves the encrypted source from the page path automatically.

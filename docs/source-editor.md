---
password: ""
---

# Encrypted Markdown Source Editor

The editor is part of this same repository and is served as a static browser-only utility. It reads the encrypted source file locally in your browser, decrypts it with Web Crypto, and writes only a newly encrypted JSON payload when you save.

[Open the source editor](../editor/){ .md-button .md-button--primary }

The editor does not submit selected files or decrypted Markdown to the web server. On Chromium-based browsers, direct file handles can overwrite the same encrypted file after browser permission is granted. Other browsers use the normal local file picker and save a replacement encrypted file.

Use the password that was used to encrypt the selected source. Use a long, unique password for real content.

## Per-page variable defaults

When editing a protected cheat sheet, you can keep its live-command defaults inside the encrypted Markdown using a `<template id="commandcodex-variable-defaults">` JSON block. The template is not rendered as page content; CommandCodex reads it only after unlock and pre-fills the Variables panel in browser memory.

Do not place real defaults in `variables.js`, `.env`, or another public asset.

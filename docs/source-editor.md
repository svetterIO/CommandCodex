---
password: ""
---

# Encrypted Markdown Source Editor

The editor is part of this same repository and is served as a static browser-only utility. It reads the encrypted source file locally in your browser, decrypts it with Web Crypto, and writes only a newly encrypted JSON payload when you save.

<a class="md-button md-button--primary" href="../editor/">Open the source editor</a>

The editor does not submit selected files or decrypted Markdown to the web server. On Chromium-based browsers, direct file handles can overwrite the same encrypted file after browser permission is granted. Other browsers use the normal local file picker and save a replacement encrypted file.

Use the password that was used to encrypt the selected source. Use a long, unique password for real content.

## Per-page variable configuration

When editing a protected cheat sheet, keep its variable schema and defaults inside the encrypted Markdown using a `<template id="commandcodex-variable-config">` JSON block. Each entry can define a `default` value and `secret: true` for masked inputs.

`variables.js` contains no fixed variable names: after unlock it discovers `{{NAME}}` placeholders from that page and combines them with the encrypted configuration in browser memory. Do not place real variable names/defaults in public JavaScript, `.env`, or another public asset.

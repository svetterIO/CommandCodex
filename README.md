# CommandCodex

**Fast reference. Ready commands. One collection.**

CommandCodex is a command-focused security cheat sheet collection for fast, practical reference across tools, techniques, and workflows. The repository also includes a browser-only encrypted Markdown source editor. The repository is intentionally not tied to one tool: Nmap is the first protected cheat sheet, and additional sheets can be added under `docs/cheatsheets/` + `content/cheatsheets/`.

> **AI-generated content — verify before use.** Validate commands, scope, timing, and impact. Use intrusive techniques only on systems you own or are explicitly authorized to test.

## What is included

- MkDocs Material reference site with live command variables and copy-ready `text` blocks.
- `mkdocs-encryptcontent-plugin==3.1.0` with the official Material 9.7 encrypted-search patch.
- MkDocs PanZoom for Mermaid diagrams after unlock.
- Protected Markdown kept encrypted on disk under `content/`.
- In-memory build hook: protected Markdown is never intentionally materialized as a plaintext file by the normal build.
- Integrated browser source editor at `/editor/`.
- Windows + Podman container build.
- GitHub Pages deployment workflow.

## Current content

- `content/cheatsheets/nmap.md.enc.json` → published as `/cheatsheets/nmap/`.
- Demo password: `passw0rd`.

The demo password is intentionally weak. A static deployment allows offline password guessing against downloaded ciphertext, so use a long, unique password for real content.

## Windows + Podman

PowerShell:

```powershell
$env:CONTENT_PASSWORD = "passw0rd"

podman build --no-cache `
  --build-arg "CONTENT_PASSWORD=$env:CONTENT_PASSWORD" `
  -t commandcodex .

Remove-Item Env:CONTENT_PASSWORD
```

Run:

```powershell
podman run --rm -it `
  -p 127.0.0.1:8000:80 `
  commandcodex
```

Open:

```text
http://127.0.0.1:8000/
```

The integrated editor is:

```text
http://127.0.0.1:8000/editor/
```

The helper scripts are equivalent:

```powershell
.\scripts\build-podman.ps1 -Password "passw0rd"
.\scripts\run-podman.ps1
```

The build-argument fallback can expose the **password** in transient process/build metadata. Where your Podman build-secret implementation works, prefer a secret named `content_password`. This does not change the protected-Markdown property: the normal build decrypts source only into Python process memory.

## Browser source editor

The editor can open any encrypted `content/**/*.md.enc.json` file. It uses the Web Crypto API for PBKDF2-HMAC-SHA256 + AES-256-GCM and does not intentionally upload plaintext or ciphertext to the host.

On Edge/Chrome, **Open encrypted file** can retain a file handle and **Encrypt & save current file** can overwrite that same encrypted file after permission is granted. **Upload fallback** uses the standard local file picker and saves a replacement encrypted file instead.

The editor also has **New source**, which starts a blank Markdown document in browser memory and lets you save it directly as ciphertext. For sources used by the site build, encrypt them with the same password configured as `CONTENT_PASSWORD`.

The editor deliberately avoids `localStorage`, IndexedDB, service workers, fetch/XHR, analytics and remote scripts. Plaintext necessarily exists in browser memory while unlocked; OS swap, hibernation, crash dumps and endpoint memory inspection are outside what a browser-only design can prevent.

## Add another encrypted cheat sheet

For a new sheet named `example`:

1. Use `/editor/` → **New source**, write the Markdown, and save it as:

   ```text
   content/cheatsheets/example.md.enc.json
   ```

2. Create the harmless marker file:

   ```text
   docs/cheatsheets/example.md
   ```

   containing only:

   ```text
   <!-- encrypted-source -->
   ```

3. Add it to `nav` in `mkdocs.yml`:

   ```yaml
   nav:
     - Home: index.md
     - Cheat sheets:
         - Nmap: cheatsheets/nmap.md
         - Example: cheatsheets/example.md
     - Source editor: source-editor.md
   ```

4. Rebuild. `hooks/in_memory_content.py` automatically maps `docs/cheatsheets/example.md` to `content/cheatsheets/example.md.enc.json` and decrypts only into the MkDocs process.

## Encryption architecture

On disk, protected authoring content is stored as AES-256-GCM JSON using a generic AAD label:

```text
security-reference:source:v1
```

During a build:

```text
encrypted content/**/*.md.enc.json
            │
            ▼
hooks/in_memory_content.py
            │  decrypts to Python string only
            ▼
MkDocs Markdown rendering
            │
            ▼
mkdocs-encryptcontent-plugin 3.1.0
            │
            ├─ encrypted page body
            └─ encrypted protected search entries
            │
            ▼
site/
```

Public pages such as the landing page and editor launcher use an explicit empty `password` metadata value to override the global password. Protected marker pages inherit the global `CONTENT_PASSWORD`.

Dynamic search is intercepted in memory. The normal search plugin writes only public entries to `search_index.json`; protected entries are encrypted directly into `encrypted_search_index.json`. The official Material 9.7 patch decrypts/merges those entries in browser memory after the protected page is unlocked.

## GitHub Pages

1. Push this repository to GitHub.
2. Add a repository Actions secret named `CONTENT_PASSWORD`. For the bundled demo source, use `passw0rd`.
3. **Before the first workflow run**, open **Settings → Pages → Build and deployment → Source** and select **GitHub Actions**. GitHub must create/enable the Pages site once before `actions/configure-pages` can query it.
4. Push to `main` or run **Deploy CommandCodex** manually.

If the workflow reports **“Get Pages site failed … Not Found”**, Pages has not yet been enabled for that repository. Set **Settings → Pages → Source → GitHub Actions** and re-run the workflow. The workflow also has a preflight check that now reports this condition with a direct error message before the Pages action runs.

The workflow uses the Node-24-compatible GitHub Pages action generations: `actions/configure-pages@v6`, `actions/upload-pages-artifact@v5`, and `actions/deploy-pages@v5`. The `node-version: "22"` setting is only the Node.js version used to build MkDocs Material; it is separate from the runtime used internally by GitHub Actions.

`.github/workflows/deploy.yml` runs the same editor crypto tests, source-layout checks, strict MkDocs build, encrypted-search checks and protected-source leak probes used by the Podman image build. It uploads only the generated `site/` directory, including the integrated static editor under `site/editor/`.

[Github Pages Link](https://svetterio.github.io/CommandCodex)

## Live variables

Variable names are **not hardcoded in public JavaScript**. After a protected page is unlocked, `variables.js` scans the decrypted command blocks for placeholders matching `{{NAME}}` and builds the Variables panel dynamically. A different cheat sheet may therefore use a completely different variable schema without changing JavaScript.

A protected cheat sheet may optionally define defaults and secret-field behavior inside its **encrypted Markdown body**:

```html
<template id="commandcodex-variable-config">
{
  "TARGET": {"default": "", "secret": false},
  "CREDENTIAL": {"default": "", "secret": true}
}
</template>
```

The names above are documentation-only examples. At runtime, the encrypted configuration defines the page's declared variable schema and preferred panel order. Any additional `{{NAME}}` placeholders found in decrypted command blocks are discovered automatically and added with empty defaults. Each encrypted config entry can provide an optional default and whether its input is masked.

Because the configuration is part of protected Markdown, the real variable names, defaults and masking metadata for a cheat sheet are encrypted together with the page. They do not appear in `variables.js`, `.env`, a generated defaults asset, clear search data, or pre-unlock page HTML. After unlock, the configuration is parsed into browser memory and its raw `<template>` is removed from the live DOM.

Manual edits take priority over page defaults for the current unlocked page session. **Restore page defaults** reapplies the encrypted defaults, while **Clear all values** keeps every discovered placeholder empty for that session. Reader-entered values and decrypted defaults are never written to `localStorage`, `sessionStorage`, IndexedDB, a generated defaults file, or build output. Reloading/closing the tab clears the reader-entered values.

The earlier build-time variable-default mechanism remains intentionally removed. Build-time injection would make values publicly retrievable from a static deployment.

The command-variable implementation is separate from page decryption state. Dynamic encrypted search in the currently pinned `mkdocs-encryptcontent-plugin`/Material integration requires temporary decrypted page keys in browser `sessionStorage` after unlock; `remember_password` remains disabled, and command-variable values are never written there. Closing the tab clears that session state.

## Build checks

Both Podman and GitHub Pages run:

```text
npm --prefix editor test
python tools/check_source_layout.py
python tools/check_variable_security.py
python tools/check_hook_compat.py
mkdocs build --strict
# copy editor/app into site/editor
python tools/check_encrypted_build.py
python tools/check_variable_security.py
python tools/check_source_layout.py
```

The checks verify protected marker/source pairing, memory-only live variables, encrypted per-page defaults (with no public/build-time defaults or browser persistence), Material search compatibility, encrypted page/search artifacts, absence of protected entries in the clear search index, editor self-containment, and source-derived plaintext leak probes generated only in RAM. Generic control-plane markers used by the public editor (for example the variable-config `<template>` wrapper itself) are narrowly excluded from leak probes; variable names, defaults, commands and protected prose remain covered.

## Important boundary

This design prevents the normal application/build workflow from intentionally materializing protected Markdown or protected search content as plaintext files. It cannot prevent plaintext from existing in process/browser memory while content is being rendered or viewed, nor can it prevent an operating system or endpoint security product from inspecting memory or persisting it through swap, hibernation, dumps, or browser internals.

## License

**Proprietary — All Rights Reserved.** Copyright (c) 2026 Sebastian Vetter. Copying, modification, redistribution, republication, hosting, mirroring, derivative works, incorporation into another project, and commercial use are prohibited without prior written permission. See `LICENSE`.

Licensing inquiries: **svetterIO@proton.me**

# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip git patch curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

ARG MATERIAL_VERSION=9.7.1
RUN git clone --depth 1 --branch "${MATERIAL_VERSION}" \
      https://github.com/squidfunk/mkdocs-material.git /opt/mkdocs-material
WORKDIR /opt/mkdocs-material
RUN curl -fsSL \
      https://raw.githubusercontent.com/unverbuggt/mkdocs-encryptcontent-plugin/version3/patches/material_bundle9_7.patch \
      -o /tmp/material_bundle9_7.patch \
    && patch -p0 < /tmp/material_bundle9_7.patch \
    && npm install \
    && npm run build \
    && pip install --no-cache-dir .

WORKDIR /site
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python tools/fetch_vendor.py

# Preferred: --secret=id=content_password,...
# Windows/PowerShell fallback: --build-arg CONTENT_PASSWORD=...
# Only the password uses the fallback. Protected Markdown is still decrypted
# directly into Python process memory by the MkDocs hook and is never written
# as a plaintext source file by the normal build.
ARG CONTENT_PASSWORD
RUN --mount=type=secret,id=content_password \
    if [ -r /run/secrets/content_password ]; then \
      CONTENT_PASSWORD="$(cat /run/secrets/content_password)"; \
    fi && \
    export CONTENT_PASSWORD && \
    if [ -z "${CONTENT_PASSWORD}" ]; then \
      echo >&2 "ERROR: supply content_password as a build secret or CONTENT_PASSWORD as a build arg"; \
      exit 2; \
    fi && \
    npm --prefix editor test && \
    python tools/check_source_layout.py && \
    python tools/check_variable_security.py && \
    python tools/check_hook_compat.py && \
    mkdocs build --strict && \
    mkdir -p site/editor && \
    cp -a editor/app/. site/editor/ && \
    python tools/check_encrypted_build.py && \
    python tools/check_variable_security.py && \
    python tools/check_source_layout.py

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /site/site/ /usr/share/nginx/html/
EXPOSE 80

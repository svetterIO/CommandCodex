(() => {
  "use strict";

  // Generic engine only. Variable names, defaults and secret-field metadata are
  // discovered from the decrypted page; this public asset contains no page schema.
  const CONFIG_TEMPLATE_ID = "commandcodex-variable-config";
  const TOKEN_PATTERN = /\{\{([A-Z][A-Z0-9_]*)\}\}/g;

  let pageKey = null;
  let tokens = [];
  let config = new Map();
  let values = new Map();
  let pageDefaults = new Map();
  let manualOverrides = new Set();
  let configLoaded = false;
  let defaultsApplied = false;

  function currentPageKey() {
    return `${window.location.origin}${window.location.pathname}`;
  }

  function resetForPage(nextPageKey) {
    pageKey = nextPageKey;
    tokens = [];
    config = new Map();
    values = new Map();
    pageDefaults = new Map();
    manualOverrides = new Set();
    configLoaded = false;
    defaultsApplied = false;
    document.getElementById("live-vars")?.remove();
  }

  function ensurePageState() {
    const next = currentPageKey();
    if (pageKey !== next) resetForPage(next);
  }

  function originalCommandText(code) {
    return code.dataset.liveTemplate || code.textContent || "";
  }

  function discoverTokens() {
    const discovered = [];
    const seen = new Set();

    document.querySelectorAll("pre > code").forEach((code) => {
      const text = originalCommandText(code);
      TOKEN_PATTERN.lastIndex = 0;
      for (const match of text.matchAll(TOKEN_PATTERN)) {
        const token = match[1];
        if (!seen.has(token)) {
          seen.add(token);
          discovered.push(token);
        }
      }
    });

    return discovered;
  }

  function normalizeConfigSpec(token, raw) {
    if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
      throw new Error(`configuration for ${token} must be an object`);
    }

    const allowed = new Set(["default", "secret"]);
    for (const key of Object.keys(raw)) {
      if (!allowed.has(key)) throw new Error(`unsupported property ${key} for ${token}`);
    }

    const defaultValue = raw.default;
    if (
      defaultValue !== undefined &&
      defaultValue !== null &&
      !["string", "number", "boolean"].includes(typeof defaultValue)
    ) {
      throw new Error(`default for ${token} must be a scalar value`);
    }

    if (raw.secret !== undefined && typeof raw.secret !== "boolean") {
      throw new Error(`secret for ${token} must be true or false`);
    }

    return {
      default: defaultValue === undefined || defaultValue === null ? "" : String(defaultValue),
      secret: raw.secret === true,
    };
  }

  function parsePageConfig() {
    if (configLoaded) return;
    configLoaded = true;

    const template = document.getElementById(CONFIG_TEMPLATE_ID);
    if (!template) return;

    try {
      const rawText = template.content ? template.content.textContent : template.textContent;
      const parsed = JSON.parse((rawText || "").trim());
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("variable configuration must be a JSON object");
      }

      const next = new Map();
      for (const [token, rawSpec] of Object.entries(parsed)) {
        if (!/^[A-Z][A-Z0-9_]*$/.test(token)) {
          throw new Error(`invalid variable name: ${token}`);
        }
        next.set(token, normalizeConfigSpec(token, rawSpec));
      }
      config = next;
    } catch (error) {
      console.warn("CommandCodex ignored invalid encrypted variable configuration:", error);
      config = new Map();
    } finally {
      // Configuration is now represented as JavaScript state only.
      template.remove();
    }
  }

  function orderTokens(discovered) {
    const ordered = [];

    // The encrypted config defines the protected page's declared schema/order.
    // Placeholders not declared there are still discovered automatically.
    for (const token of config.keys()) ordered.push(token);
    for (const token of discovered) {
      if (!ordered.includes(token)) ordered.push(token);
    }
    return ordered;
  }

  function initializeValues() {
    if (defaultsApplied) return;
    defaultsApplied = true;

    for (const token of tokens) {
      const defaultValue = config.get(token)?.default || "";
      pageDefaults.set(token, defaultValue);
      if (!manualOverrides.has(token)) values.set(token, defaultValue);
    }
  }

  function substitute(template) {
    let text = template;
    for (const token of tokens) {
      const value = values.get(token) || "";
      if (!value) continue;
      text = text.split(`{{${token}}}`).join(value);
    }
    return text;
  }

  function refreshCommands() {
    document.querySelectorAll("pre > code").forEach((code) => {
      const original = originalCommandText(code);
      TOKEN_PATTERN.lastIndex = 0;
      if (!TOKEN_PATTERN.test(original)) return;
      if (!code.dataset.liveTemplate) code.dataset.liveTemplate = original;
      code.textContent = substitute(code.dataset.liveTemplate);
    });
  }

  function syncPanelFields() {
    const panel = document.getElementById("live-vars");
    if (!panel) return;
    panel.querySelectorAll("input[data-token]").forEach((input) => {
      input.value = values.get(input.dataset.token) || "";
    });
  }

  function field(token) {
    const wrapper = document.createElement("label");
    wrapper.className = "live-vars__field";

    const name = document.createElement("span");
    name.textContent = token;

    const input = document.createElement("input");
    input.type = config.get(token)?.secret ? "password" : "text";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.value = values.get(token) || "";
    input.dataset.token = token;
    input.setAttribute("aria-label", `Value for ${token}`);
    input.addEventListener("input", () => {
      manualOverrides.add(token);
      values.set(token, input.value);
      refreshCommands();
    });

    wrapper.append(name, input);
    return wrapper;
  }

  function restorePageDefaults() {
    manualOverrides.clear();
    for (const token of tokens) values.set(token, pageDefaults.get(token) || "");
    syncPanelFields();
    refreshCommands();
  }

  function clearValues() {
    // Treat empties as manual overrides so a subsequent Material lifecycle event
    // cannot silently restore defaults during this unlocked page session.
    for (const token of tokens) {
      manualOverrides.add(token);
      values.set(token, "");
    }
    syncPanelFields();
    refreshCommands();
  }

  function mountPanel() {
    const signature = JSON.stringify(tokens);
    const existing = document.getElementById("live-vars");
    if (existing && existing.dataset.tokenSignature === signature) {
      syncPanelFields();
      refreshCommands();
      return;
    }
    existing?.remove();

    const panel = document.createElement("aside");
    panel.id = "live-vars";
    panel.className = "live-vars is-collapsed";
    panel.dataset.tokenSignature = signature;
    panel.setAttribute("aria-label", "Live command variables");

    const header = document.createElement("div");
    header.className = "live-vars__header";

    const title = document.createElement("strong");
    title.textContent = "Variables";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "live-vars__toggle";
    toggle.textContent = "Open";
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", () => {
      const collapsed = panel.classList.toggle("is-collapsed");
      toggle.textContent = collapsed ? "Open" : "Close";
      toggle.setAttribute("aria-expanded", String(!collapsed));
    });

    header.append(title, toggle);

    const intro = document.createElement("p");
    intro.className = "live-vars__intro";
    intro.textContent = config.size
      ? "Variable definitions came from this decrypted cheat sheet. Changes stay only in this browser tab's memory."
      : "Variables were discovered from this decrypted cheat sheet. Empty values leave placeholders unchanged.";

    const fields = document.createElement("div");
    fields.className = "live-vars__fields";
    for (const token of tokens) fields.appendChild(field(token));

    const actions = document.createElement("div");
    actions.className = "live-vars__actions";

    if (config.size) {
      const restore = document.createElement("button");
      restore.type = "button";
      restore.textContent = "Restore page defaults";
      restore.addEventListener("click", restorePageDefaults);
      actions.appendChild(restore);
    }

    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "Clear all values";
    clear.addEventListener("click", clearValues);
    actions.appendChild(clear);

    panel.append(header, intro, fields, actions);
    document.body.appendChild(panel);
    refreshCommands();
  }

  function init() {
    ensurePageState();

    const discovered = discoverTokens();
    if (!discovered.length) {
      document.getElementById("live-vars")?.remove();
      return;
    }

    // Protected configuration is not present until encryptcontent unlocks the page.
    parsePageConfig();
    tokens = orderTokens(discovered);
    initializeValues();
    mountPanel();
    syncPanelFields();
    refreshCommands();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }

  if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
    document$.subscribe(() => window.setTimeout(init, 0));
  }

  window.addEventListener("encryptcontent_event", () => window.setTimeout(init, 0));
})();

(() => {
  "use strict";

  const TOKENS = [
    "IP", "PORT", "URL", "DOMAIN", "DC", "IFACE", "LHOST", "LPORT",
    "USER", "PASS", "HASH", "TOKEN", "WORDLIST", "SHARE", "OUT"
  ];

  const DEFAULTS_TEMPLATE_ID = "commandcodex-variable-defaults";
  const MASKED_TOKENS = new Set(["PASS", "HASH", "TOKEN"]);

  // Values and defaults live only in this JavaScript context. Page defaults are
  // discovered from a <template> that itself lives inside the encrypted page body,
  // so no values are present in variables.js or any other public defaults asset.
  const VALUES = Object.fromEntries(TOKENS.map((token) => [token, ""]));
  const PAGE_DEFAULTS = Object.fromEntries(TOKENS.map((token) => [token, ""]));
  const MANUAL_OVERRIDES = new Set();
  let defaultsLoaded = false;

  function currentValues() {
    return { ...VALUES };
  }

  function substitute(template, values) {
    return TOKENS.reduce((text, token) => {
      const value = values[token];
      if (value === undefined || value === null || value === "") return text;
      return text.replace(new RegExp(`\\{\\{${token}\\}\\}`, "g"), String(value));
    }, template);
  }

  function refreshCommands() {
    const values = currentValues();
    document.querySelectorAll("pre > code").forEach((code) => {
      const text = code.dataset.liveTemplate || code.textContent;
      if (!TOKENS.some((token) => text.includes(`{{${token}}}`))) return;
      if (!code.dataset.liveTemplate) code.dataset.liveTemplate = text;
      code.textContent = substitute(code.dataset.liveTemplate, values);
    });
  }

  function syncPanelFields() {
    const panel = document.getElementById("live-vars");
    if (!panel) return;
    panel.querySelectorAll("input[data-token]").forEach((input) => {
      input.value = VALUES[input.dataset.token] || "";
    });
  }

  function parsePageDefaults() {
    const template = document.getElementById(DEFAULTS_TEMPLATE_ID);
    if (!template) return false;

    try {
      const raw = template.content
        ? template.content.textContent
        : template.textContent;
      const parsed = JSON.parse(raw.trim());
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("default payload must be a JSON object");
      }

      TOKENS.forEach((token) => {
        const value = parsed[token];
        PAGE_DEFAULTS[token] = value === undefined || value === null ? "" : String(value);
        if (!MANUAL_OVERRIDES.has(token)) VALUES[token] = PAGE_DEFAULTS[token];
      });
      defaultsLoaded = true;

      // The defaults are already in memory; remove their raw JSON from the live DOM.
      template.remove();
      return true;
    } catch (error) {
      console.warn("CommandCodex ignored invalid encrypted variable defaults:", error);
      template.remove();
      return false;
    }
  }

  function field(token) {
    const wrapper = document.createElement("label");
    wrapper.className = "live-vars__field";

    const name = document.createElement("span");
    name.textContent = token;

    const input = document.createElement("input");
    input.type = MASKED_TOKENS.has(token) ? "password" : "text";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.value = VALUES[token];
    input.dataset.token = token;
    input.setAttribute("aria-label", `Value for ${token}`);
    input.addEventListener("input", () => {
      MANUAL_OVERRIDES.add(token);
      VALUES[token] = input.value;
      refreshCommands();
    });

    wrapper.append(name, input);
    return wrapper;
  }

  function restorePageDefaults() {
    MANUAL_OVERRIDES.clear();
    TOKENS.forEach((token) => {
      VALUES[token] = PAGE_DEFAULTS[token] || "";
    });
    syncPanelFields();
    refreshCommands();
  }

  function clearValues() {
    // Mark every token as manually overridden so a later lifecycle event doesn't
    // silently re-apply page defaults after the reader deliberately cleared them.
    TOKENS.forEach((token) => {
      MANUAL_OVERRIDES.add(token);
      VALUES[token] = "";
    });
    syncPanelFields();
    refreshCommands();
  }

  function mountPanel() {
    const existing = document.getElementById("live-vars");
    if (existing) {
      syncPanelFields();
      refreshCommands();
      return;
    }

    const panel = document.createElement("aside");
    panel.id = "live-vars";
    panel.className = "live-vars is-collapsed";
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
    intro.textContent = defaultsLoaded
      ? "Defaults came from this decrypted cheat sheet. Changes stay only in this browser tab's memory."
      : "Values stay only in this browser tab's memory. Empty values leave placeholders unchanged.";

    const fields = document.createElement("div");
    fields.className = "live-vars__fields";
    TOKENS.forEach((token) => fields.appendChild(field(token)));

    const actions = document.createElement("div");
    actions.className = "live-vars__actions";

    if (defaultsLoaded) {
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

  function hasLiveCommands() {
    return Array.from(document.querySelectorAll("pre > code")).some((code) =>
      TOKENS.some((token) => (code.dataset.liveTemplate || code.textContent).includes(`{{${token}}}`))
    );
  }

  function init() {
    // Protected command blocks and their defaults do not exist until encryptcontent
    // unlocks the page, so neither defaults nor the panel are exposed before then.
    if (!hasLiveCommands()) {
      document.getElementById("live-vars")?.remove();
      return;
    }

    if (!defaultsLoaded) parsePageDefaults();
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

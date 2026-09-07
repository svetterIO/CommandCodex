(() => {
  "use strict";

  const TOKENS = [
    "IP", "PORT", "URL", "DOMAIN", "DC", "IFACE", "LHOST", "LPORT",
    "USER", "PASS", "HASH", "TOKEN", "WORDLIST", "SHARE", "OUT"
  ];

  // Live values intentionally exist only in this JavaScript context.
  // They are never pre-seeded, written to browser storage, or emitted at build time.
  const VALUES = Object.fromEntries(TOKENS.map((token) => [token, ""]));
  const MASKED_TOKENS = new Set(["PASS", "HASH", "TOKEN"]);

  function currentValues() {
    return { ...VALUES };
  }

  function substitute(template, values) {
    return TOKENS.reduce((text, token) => {
      const placeholder = `{{${token}}}`;
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
      VALUES[token] = input.value;
      refreshCommands();
    });

    wrapper.append(name, input);
    return wrapper;
  }

  function clearValues() {
    TOKENS.forEach((token) => {
      VALUES[token] = "";
    });
  }

  function mountPanel() {
    if (document.getElementById("live-vars")) {
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
    intro.textContent = "Values stay only in this browser tab's memory. Empty values leave placeholders unchanged.";

    const fields = document.createElement("div");
    fields.className = "live-vars__fields";
    TOKENS.forEach((token) => fields.appendChild(field(token)));

    const actions = document.createElement("div");
    actions.className = "live-vars__actions";

    const reset = document.createElement("button");
    reset.type = "button";
    reset.textContent = "Clear all values";
    reset.addEventListener("click", () => {
      clearValues();
      panel.remove();
      mountPanel();
    });

    actions.appendChild(reset);
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
    // Protected command blocks do not exist until encryptcontent unlocks the page.
    // The panel therefore stays absent before decryption.
    if (!hasLiveCommands()) {
      document.getElementById("live-vars")?.remove();
      return;
    }
    mountPanel();
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

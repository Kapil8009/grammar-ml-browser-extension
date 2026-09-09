(() => {
  const state = {
    activeElement: null,
    lastRange: null,
    button: null,
    card: null,
    timer: null,
    requestSerial: 0,
  };

  const isEditable = (element) =>
    element instanceof HTMLTextAreaElement ||
    (element instanceof HTMLInputElement && ["text", "search", "email", "url"].includes(element.type)) ||
    element?.isContentEditable;

  const readText = (element) => {
    if (!element) return "";
    if ("value" in element) return element.value;
    return element.innerText || "";
  };

  const writeText = (element, value) => {
    if (!element) return;
    if ("value" in element) {
      const prototype = element instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      setter ? setter.call(element, value) : (element.value = value);
    } else {
      element.innerText = value;
    }
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertReplacementText", data: value }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };

  document.addEventListener("focusin", (event) => {
    if (!isEditable(event.target)) return;
    state.activeElement = event.target;
    rememberSelection(event.target);
    showButton(event.target);
  });

  document.addEventListener("selectionchange", () => rememberSelection(document.activeElement));

  document.addEventListener("input", async (event) => {
    if (!isEditable(event.target)) return;
    state.activeElement = event.target;
    repositionButton();
    const { autoCheck, debounceMs } = await chrome.storage.sync.get({ autoCheck: false, debounceMs: 900 });
    if (!autoCheck) return;
    clearTimeout(state.timer);
    const target = event.target;
    state.timer = setTimeout(() => requestCorrection(readText(target), target, false), Number(debounceMs) || 900);
  }, true);

  window.addEventListener("scroll", repositionButton, true);
  window.addEventListener("resize", repositionButton);

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "GRAMMAR_ML_GET_ACTIVE_TEXT") {
      const element = isEditable(document.activeElement) ? document.activeElement : state.activeElement;
      sendResponse({ text: readText(element), editable: Boolean(element) });
      return false;
    }
    if (message?.type === "GRAMMAR_ML_APPLY_TEXT") {
      const element = isEditable(document.activeElement) ? document.activeElement : state.activeElement;
      if (element) writeText(element, message.text || "");
      sendResponse({ applied: Boolean(element) });
      return false;
    }
    if (message?.type === "GRAMMAR_ML_CORRECT_ACTIVE") {
      const element = isEditable(document.activeElement) ? document.activeElement : state.activeElement;
      requestCorrection(readText(element), element, true);
      return false;
    }
    if (message?.type === "GRAMMAR_ML_CORRECT_SELECTION") {
      requestCorrection(message.text || window.getSelection()?.toString() || "", state.activeElement, true, true);
      return false;
    }
    return false;
  });

  function rememberSelection(element) {
    if (!element?.isContentEditable) return;
    const selection = window.getSelection();
    if (selection?.rangeCount && element.contains(selection.anchorNode)) {
      state.lastRange = selection.getRangeAt(0).cloneRange();
    }
  }

  function showButton(element) {
    if (!state.button) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "grammar-ml-trigger";
      button.textContent = "G";
      button.title = "Correct with Grammar ML (Alt+G)";
      button.setAttribute("aria-label", button.title);
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () => requestCorrection(readText(state.activeElement), state.activeElement, true));
      document.documentElement.appendChild(button);
      state.button = button;
    }
    state.button.hidden = false;
    positionNear(element, state.button, 32);
  }

  function repositionButton() {
    if (state.button && state.activeElement?.isConnected) positionNear(state.activeElement, state.button, 32);
  }

  function positionNear(element, floating, inset = 8) {
    if (!element) return;
    const rect = element.getBoundingClientRect();
    floating.style.top = `${Math.max(8, rect.bottom - inset)}px`;
    floating.style.left = `${Math.max(8, rect.right - inset)}px`;
  }

  async function requestCorrection(text, element, visible, selectionOnly = false) {
    if (!text?.trim()) {
      if (visible) showCard({ error: "There is no text to correct." }, element);
      return;
    }
    const serial = ++state.requestSerial;
    if (visible) showCard({ loading: true }, element);
    try {
      const response = await chrome.runtime.sendMessage({ type: "GRAMMAR_ML_CORRECT", text });
      if (serial !== state.requestSerial) return;
      if (!response?.ok) throw new Error(response?.error || "Correction failed.");
      if (visible || response.result.changed) showCard({ result: response.result, selectionOnly }, element);
    } catch (error) {
      if (serial === state.requestSerial) showCard({ error: error.message }, element);
    }
  }

  function showCard(view, element) {
    state.card?.remove();
    const card = document.createElement("section");
    card.className = "grammar-ml-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", "Grammar correction suggestion");
    const header = document.createElement("div");
    header.className = "grammar-ml-card__header";
    const title = document.createElement("strong");
    title.textContent = "Grammar ML";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "grammar-ml-card__close";
    close.textContent = "×";
    close.setAttribute("aria-label", "Close");
    close.addEventListener("click", () => card.remove());
    header.append(title, close);
    card.append(header);

    if (view.loading) {
      const loading = document.createElement("p");
      loading.className = "grammar-ml-loading";
      loading.textContent = "Checking with the model…";
      card.append(loading);
    } else if (view.error) {
      const error = document.createElement("p");
      error.className = "grammar-ml-error";
      error.textContent = view.error;
      card.append(error);
    } else {
      const result = view.result;
      const status = document.createElement("p");
      status.className = "grammar-ml-status";
      status.textContent = result.changed
        ? `${result.suggestions.length} suggested edit${result.suggestions.length === 1 ? "" : "s"}`
        : "No changes suggested";
      const corrected = document.createElement("div");
      corrected.className = "grammar-ml-corrected";
      corrected.textContent = result.corrected;
      card.append(status, corrected);
      if (result.changed) {
        const actions = document.createElement("div");
        actions.className = "grammar-ml-actions";
        const apply = document.createElement("button");
        apply.type = "button";
        apply.className = "grammar-ml-primary";
        apply.textContent = view.selectionOnly ? "Copy correction" : "Apply correction";
        apply.addEventListener("click", async () => {
          if (view.selectionOnly) {
            await navigator.clipboard.writeText(result.corrected);
            apply.textContent = "Copied";
          } else {
            writeText(element, result.corrected);
            card.remove();
          }
        });
        const copy = document.createElement("button");
        copy.type = "button";
        copy.textContent = "Copy";
        copy.addEventListener("click", async () => {
          await navigator.clipboard.writeText(result.corrected);
          copy.textContent = "Copied";
        });
        actions.append(apply, copy);
        card.append(actions);
      }
    }
    document.documentElement.appendChild(card);
    const rect = element?.getBoundingClientRect();
    const top = rect ? Math.min(window.innerHeight - 300, Math.max(12, rect.bottom + 8)) : 20;
    const left = rect ? Math.min(window.innerWidth - 380, Math.max(12, rect.left)) : 20;
    card.style.top = `${Math.max(12, top)}px`;
    card.style.left = `${Math.max(12, left)}px`;
    state.card = card;
  }
})();

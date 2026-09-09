(() => {
  const AUTO_CHECK_DEFAULTS = { autoCheck: true, debounceMs: 1600 };
  const state = {
    activeElement: null,
    button: null,
    badge: null,
    card: null,
    timer: null,
    requestSerial: 0,
    inFlight: false,
    queuedRequest: null,
    latestResult: null,
    latestElement: null,
    latestSelectionOnly: false,
  };

  const isEditable = (element) =>
    element instanceof HTMLTextAreaElement ||
    (element instanceof HTMLInputElement &&
      ["text", "search", "email", "url"].includes(element.type)) ||
    element?.isContentEditable;

  const readText = (element) => {
    if (!element) return "";
    if ("value" in element) return element.value;
    return element.innerText || "";
  };

  const writeText = (element, value) => {
    if (!element) return;
    if ("value" in element) {
      const prototype =
        element instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
      setter ? setter.call(element, value) : (element.value = value);
    } else {
      element.innerText = value;
    }
    element.dispatchEvent(
      new InputEvent("input", {
        bubbles: true,
        inputType: "insertReplacementText",
        data: value,
      }),
    );
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };

  document.addEventListener("focusin", (event) => {
    if (!isEditable(event.target)) return;
    if (state.activeElement !== event.target) dismissCard();
    state.activeElement = event.target;
    showButton(event.target);
  });

  document.addEventListener(
    "input",
    async (event) => {
      if (!isEditable(event.target)) return;
      state.activeElement = event.target;
      repositionButton();

      const text = readText(event.target);
      if (state.latestElement === event.target && state.latestResult?.original !== text) {
        dismissCard();
        state.latestResult = null;
        setTriggerState();
      }

      const settings = await chrome.storage.sync.get(AUTO_CHECK_DEFAULTS);
      if (!settings.autoCheck) return;
      clearTimeout(state.timer);
      if (text.trim().length < 3) return;

      const target = event.target;
      state.timer = setTimeout(
        () => requestCorrection(readText(target), target, false),
        Number(settings.debounceMs) || AUTO_CHECK_DEFAULTS.debounceMs,
      );
    },
    true,
  );

  document.addEventListener(
    "keydown",
    (event) => {
      if (event.altKey && !event.ctrlKey && !event.metaKey && event.key.toLowerCase() === "g") {
        const element = isEditable(document.activeElement)
          ? document.activeElement
          : state.activeElement;
        if (!element) return;
        event.preventDefault();
        requestCorrection(readText(element), element, true);
        return;
      }
      if (event.altKey && event.key === "Enter" && state.card) {
        event.preventDefault();
        applyLatest();
        return;
      }
      if (event.key === "Escape" && state.card) dismissCard();
    },
    true,
  );

  window.addEventListener("scroll", repositionFloatingUi, true);
  window.addEventListener("resize", repositionFloatingUi);

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "GRAMMAR_ML_GET_ACTIVE_TEXT") {
      const element = currentEditable();
      sendResponse({ text: readText(element), editable: Boolean(element) });
      return false;
    }
    if (message?.type === "GRAMMAR_ML_APPLY_TEXT") {
      const element = currentEditable();
      if (element) writeText(element, message.text || "");
      sendResponse({ applied: Boolean(element) });
      return false;
    }
    if (message?.type === "GRAMMAR_ML_CORRECT_ACTIVE") {
      const element = currentEditable();
      requestCorrection(readText(element), element, true);
      return false;
    }
    if (message?.type === "GRAMMAR_ML_APPLY_LATEST") {
      applyLatest();
      return false;
    }
    if (message?.type === "GRAMMAR_ML_CORRECT_SELECTION") {
      requestCorrection(
        message.text || window.getSelection()?.toString() || "",
        state.activeElement,
        true,
        true,
      );
      return false;
    }
    return false;
  });

  function currentEditable() {
    return isEditable(document.activeElement) ? document.activeElement : state.activeElement;
  }

  function showButton(element) {
    if (!state.button) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "grammar-ml-trigger";
      button.title = "Check writing with Grammar ML (Alt+G)";
      button.setAttribute("aria-label", button.title);

      const logo = document.createElement("span");
      logo.className = "grammar-ml-trigger__logo";
      logo.textContent = "G";
      const badge = document.createElement("span");
      badge.className = "grammar-ml-trigger__badge";
      badge.hidden = true;
      button.append(logo, badge);

      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () => {
        if (state.latestResult && readText(state.activeElement) === state.latestResult.original) {
          showCard(
            { result: state.latestResult, selectionOnly: state.latestSelectionOnly },
            state.activeElement,
          );
          return;
        }
        requestCorrection(readText(state.activeElement), state.activeElement, true);
      });
      document.documentElement.appendChild(button);
      state.button = button;
      state.badge = badge;
    }
    state.button.hidden = false;
    positionNear(element, state.button, 32);
  }

  function setTriggerState({ loading = false, count = 0, error = false } = {}) {
    if (!state.button || !state.badge) return;
    state.button.classList.toggle("is-loading", loading);
    state.button.classList.toggle("has-error", error);
    state.badge.hidden = !count && !error;
    state.badge.textContent = error ? "!" : count > 9 ? "9+" : String(count);
    state.button.title = loading
      ? "Grammar ML is checking your writing…"
      : count
        ? `${count} writing suggestion${count === 1 ? "" : "s"} (Alt+G)`
        : "Check writing with Grammar ML (Alt+G)";
    state.button.setAttribute("aria-label", state.button.title);
  }

  function repositionFloatingUi() {
    repositionButton();
    if (state.card && state.latestElement) positionCard(state.latestElement, state.card);
  }

  function repositionButton() {
    if (state.button && state.activeElement?.isConnected) {
      positionNear(state.activeElement, state.button, 32);
    }
  }

  function positionNear(element, floating, inset = 8) {
    if (!element) return;
    const rect = element.getBoundingClientRect();
    floating.style.top = `${Math.max(8, rect.bottom - inset)}px`;
    floating.style.left = `${Math.max(8, rect.right - inset)}px`;
  }

  async function requestCorrection(text, element, visible, selectionOnly = false) {
    if (!text?.trim()) {
      if (visible) showCard({ error: "There is no text to check." }, element);
      return;
    }
    if (state.inFlight) {
      state.queuedRequest = { text, element, visible, selectionOnly };
      if (visible) showCard({ loading: true }, element);
      return;
    }

    state.inFlight = true;
    const serial = ++state.requestSerial;
    setTriggerState({ loading: true });
    if (visible) showCard({ loading: true }, element);

    try {
      const response = await chrome.runtime.sendMessage({ type: "GRAMMAR_ML_CORRECT", text });
      if (serial !== state.requestSerial) return;
      if (!response?.ok) throw new Error(response?.error || "Correction failed.");

      const isCurrent = selectionOnly || (element?.isConnected && readText(element) === text);
      if (!isCurrent) {
        setTriggerState();
        return;
      }

      state.latestResult = response.result;
      state.latestElement = element;
      state.latestSelectionOnly = selectionOnly;
      const count = response.result.changed ? response.result.suggestions.length : 0;
      setTriggerState({ count });
      if (visible || response.result.changed) {
        showCard({ result: response.result, selectionOnly }, element);
      }
    } catch (error) {
      if (serial === state.requestSerial) {
        setTriggerState({ error: true });
        if (visible) showCard({ error: error.message }, element);
      }
    } finally {
      state.inFlight = false;
      const queued = state.queuedRequest;
      state.queuedRequest = null;
      if (queued?.text === text && queued.visible && state.latestResult) {
        showCard(
          { result: state.latestResult, selectionOnly: queued.selectionOnly },
          queued.element,
        );
      } else if (queued && queued.text !== text) {
        requestCorrection(queued.text, queued.element, queued.visible, queued.selectionOnly);
      }
    }
  }

  function showCard(view, element) {
    dismissCard();
    const card = document.createElement("section");
    card.className = "grammar-ml-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", "Grammar ML writing suggestions");

    const header = document.createElement("div");
    header.className = "grammar-ml-card__header";
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = "Grammar ML";
    const subtitle = document.createElement("span");
    subtitle.textContent = "AI writing assistant";
    heading.append(title, subtitle);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "grammar-ml-card__close";
    close.textContent = "×";
    close.setAttribute("aria-label", "Close suggestions");
    close.addEventListener("click", dismissCard);
    header.append(heading, close);
    card.append(header);

    if (view.loading) {
      const loading = document.createElement("div");
      loading.className = "grammar-ml-loading";
      const spinner = document.createElement("span");
      spinner.className = "grammar-ml-spinner";
      const text = document.createElement("p");
      text.textContent = "Checking your writing with the model…";
      loading.append(spinner, text);
      card.append(loading);
    } else if (view.error) {
      const error = document.createElement("p");
      error.className = "grammar-ml-error";
      error.textContent = view.error;
      card.append(error);
    } else {
      renderResult(card, view.result, element, view.selectionOnly);
    }

    document.documentElement.appendChild(card);
    positionCard(element, card);
    state.card = card;
  }

  function renderResult(card, result, element, selectionOnly) {
    const status = document.createElement("div");
    status.className = `grammar-ml-status ${result.changed ? "has-suggestions" : "is-clear"}`;
    const statusIcon = document.createElement("span");
    statusIcon.textContent = result.changed ? String(result.suggestions.length) : "✓";
    const statusText = document.createElement("p");
    statusText.textContent = result.changed
      ? `${result.suggestions.length} improvement${result.suggestions.length === 1 ? "" : "s"} found`
      : "Your writing looks clear";
    status.append(statusIcon, statusText);
    card.append(status);

    if (!result.changed) return;

    const list = document.createElement("div");
    list.className = "grammar-ml-suggestions";
    for (const suggestion of result.suggestions.slice(0, 8)) {
      const item = document.createElement("article");
      item.className = "grammar-ml-suggestion";
      const change = document.createElement("div");
      change.className = "grammar-ml-suggestion__change";

      const original = document.createElement("span");
      original.className = "grammar-ml-original";
      original.textContent = suggestion.original || "Add text";
      const arrow = document.createElement("span");
      arrow.className = "grammar-ml-arrow";
      arrow.textContent = "→";
      const replacement = document.createElement("span");
      replacement.className = "grammar-ml-replacement";
      replacement.textContent = suggestion.replacement || "Remove";
      change.append(original, arrow, replacement);

      const apply = document.createElement("button");
      apply.type = "button";
      apply.className = "grammar-ml-apply-one";
      apply.textContent = selectionOnly ? "Copy" : "Accept";
      apply.setAttribute("aria-label", `${apply.textContent}: ${suggestion.message}`);
      apply.addEventListener("click", async () => {
        if (selectionOnly) {
          await navigator.clipboard.writeText(result.corrected);
          apply.textContent = "Copied";
          return;
        }
        applySuggestion(element, result, suggestion);
      });
      item.append(change, apply);
      list.append(item);
    }
    card.append(list);

    const preview = document.createElement("details");
    preview.className = "grammar-ml-preview";
    const summary = document.createElement("summary");
    summary.textContent = "Preview corrected text";
    const corrected = document.createElement("p");
    corrected.textContent = result.corrected;
    preview.append(summary, corrected);
    card.append(preview);

    const actions = document.createElement("div");
    actions.className = "grammar-ml-actions";
    const applyAll = document.createElement("button");
    applyAll.type = "button";
    applyAll.className = "grammar-ml-primary";
    applyAll.textContent = selectionOnly ? "Copy correction" : "Accept all";
    applyAll.addEventListener("click", () => applyResult(element, result, selectionOnly));
    const shortcut = document.createElement("span");
    shortcut.textContent = selectionOnly ? "" : "Alt+Enter";
    actions.append(applyAll, shortcut);
    card.append(actions);
  }

  function applySuggestion(element, result, suggestion) {
    const current = readText(element);
    if (current !== result.original) {
      showCard({ error: "The text changed. Check it again before applying this suggestion." }, element);
      return;
    }
    const corrected = `${current.slice(0, suggestion.start)}${suggestion.replacement}${current.slice(
      suggestion.end,
    )}`;
    writeText(element, corrected);
    dismissCard();
    state.latestResult = null;
    setTriggerState();
    requestCorrection(corrected, element, false);
  }

  async function applyResult(element, result, selectionOnly) {
    if (selectionOnly) {
      await navigator.clipboard.writeText(result.corrected);
      return;
    }
    if (readText(element) !== result.original) {
      showCard({ error: "The text changed. Check it again before accepting all edits." }, element);
      return;
    }
    writeText(element, result.corrected);
    state.latestResult = null;
    dismissCard();
    setTriggerState();
  }

  function applyLatest() {
    if (!state.latestResult?.changed || !state.latestElement) return;
    applyResult(state.latestElement, state.latestResult, state.latestSelectionOnly);
  }

  function positionCard(element, card) {
    const rect = element?.getBoundingClientRect();
    const top = rect ? Math.min(window.innerHeight - 520, Math.max(12, rect.bottom + 8)) : 20;
    const left = rect ? Math.min(window.innerWidth - 400, Math.max(12, rect.right - 380)) : 20;
    card.style.top = `${Math.max(12, top)}px`;
    card.style.left = `${Math.max(12, left)}px`;
  }

  function dismissCard() {
    state.card?.remove();
    state.card = null;
  }
})();

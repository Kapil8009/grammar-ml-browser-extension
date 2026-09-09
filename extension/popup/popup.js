const elements = {
  text: document.querySelector("#text"),
  status: document.querySelector("#status"),
  result: document.querySelector("#result"),
  corrected: document.querySelector("#corrected"),
  editCount: document.querySelector("#edit-count"),
  correct: document.querySelector("#correct"),
  apply: document.querySelector("#apply"),
  copy: document.querySelector("#copy"),
  settings: document.querySelector("#settings"),
};

let activeTabId = null;
let correction = "";

initialize();

async function initialize() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  activeTabId = tab?.id || null;
  if (!activeTabId) return;
  try {
    const response = await chrome.tabs.sendMessage(activeTabId, { type: "GRAMMAR_ML_GET_ACTIVE_TEXT" });
    if (response?.text) elements.text.value = response.text;
    elements.apply.hidden = !response?.editable;
  } catch {
    elements.status.textContent = "Open a normal web page, or paste text here.";
  }
}

elements.correct.addEventListener("click", async () => {
  const text = elements.text.value;
  if (!text.trim()) return setStatus("Enter some text first.", true);
  setBusy(true);
  setStatus("Checking with the model…");
  try {
    const response = await chrome.runtime.sendMessage({ type: "GRAMMAR_ML_CORRECT", text });
    if (!response?.ok) throw new Error(response?.error || "Correction failed.");
    correction = response.result.corrected;
    elements.corrected.textContent = correction;
    const count = response.result.suggestions.length;
    elements.editCount.textContent = response.result.changed
      ? `${count} edit${count === 1 ? "" : "s"}`
      : "No changes";
    elements.result.hidden = false;
    elements.copy.hidden = false;
    setStatus(`${response.result.model} · ${Math.round(response.result.latency_ms)} ms`);
  } catch (error) {
    setStatus(error.message || "Correction failed.", true);
  } finally {
    setBusy(false);
  }
});

elements.apply.addEventListener("click", async () => {
  if (!correction || !activeTabId) return;
  const response = await chrome.tabs.sendMessage(activeTabId, {
    type: "GRAMMAR_ML_APPLY_TEXT",
    text: correction,
  });
  setStatus(response?.applied ? "Applied to the page." : "Focus a text field first.", !response?.applied);
});

elements.copy.addEventListener("click", async () => {
  await navigator.clipboard.writeText(correction);
  setStatus("Copied to clipboard.");
});

elements.settings.addEventListener("click", () => chrome.runtime.openOptionsPage());

function setBusy(busy) {
  elements.correct.disabled = busy;
  elements.correct.textContent = busy ? "Checking…" : "Check writing";
}

function setStatus(message, error = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", error);
}

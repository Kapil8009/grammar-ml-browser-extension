const DEFAULTS = Object.freeze({
  apiUrl: "https://grammar-ml-api.onrender.com",
  autoCheck: false,
  debounceMs: 900,
});

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.sync.get(DEFAULTS);
  await chrome.storage.sync.set(current);
  chrome.contextMenus.create({
    id: "grammar-ml-correct-selection",
    title: "Correct with Grammar ML",
    contexts: ["selection", "editable"],
  });
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "GRAMMAR_ML_CORRECT") return false;
  correctText(message.text)
    .then((result) => sendResponse({ ok: true, result }))
    .catch((error) => sendResponse({ ok: false, error: readableError(error) }));
  return true;
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "grammar-ml-correct-selection" || !tab?.id) return;
  await chrome.tabs.sendMessage(tab.id, {
    type: "GRAMMAR_ML_CORRECT_SELECTION",
    text: info.selectionText || "",
  });
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "correct-current-field") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.id) {
    await chrome.tabs.sendMessage(tab.id, { type: "GRAMMAR_ML_CORRECT_ACTIVE" });
  }
});

async function correctText(text) {
  if (!text || !text.trim()) throw new Error("Enter some text first.");
  const settings = await chrome.storage.sync.get(DEFAULTS);
  const { apiKey } = await chrome.storage.local.get({ apiKey: "" });
  const base = settings.apiUrl.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(base)) throw new Error("The API URL must start with http:// or https://.");

  const headers = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;
  const controller = new AbortController();
  // Render Free can need 50+ seconds to wake before it starts model inference.
  const timeout = setTimeout(() => controller.abort(), 180000);
  try {
    const response = await fetch(`${base}/v1/correct`, {
      method: "POST",
      headers,
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`The API returned an unreadable response (${response.status}).`);
    }
    if (!response.ok) throw new Error(payload.detail || `API request failed (${response.status}).`);
    return payload;
  } finally {
    clearTimeout(timeout);
  }
}

function readableError(error) {
  if (error?.name === "AbortError") return "The correction request timed out.";
  if (error instanceof TypeError) return "Could not reach the Grammar ML API. Check its URL and CORS settings.";
  return error?.message || "Correction failed.";
}

const DEFAULTS = { apiUrl: "http://localhost:8000", autoCheck: false, debounceMs: 900 };
const form = document.querySelector("#settings-form");
const apiUrl = document.querySelector("#api-url");
const apiKey = document.querySelector("#api-key");
const autoCheck = document.querySelector("#auto-check");
const debounce = document.querySelector("#debounce");
const status = document.querySelector("#status");

load();

async function load() {
  const settings = await chrome.storage.sync.get(DEFAULTS);
  const secret = await chrome.storage.local.get({ apiKey: "" });
  apiUrl.value = settings.apiUrl;
  apiKey.value = secret.apiKey;
  autoCheck.checked = settings.autoCheck;
  debounce.value = settings.debounceMs;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = apiUrl.value.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) return showStatus("Enter a valid HTTP or HTTPS URL.", true);
  await chrome.storage.sync.set({
    apiUrl: url,
    autoCheck: autoCheck.checked,
    debounceMs: Math.min(5000, Math.max(300, Number(debounce.value) || 900)),
  });
  await chrome.storage.local.set({ apiKey: apiKey.value.trim() });
  showStatus("Settings saved.");
});

document.querySelector("#test").addEventListener("click", async () => {
  showStatus("Testing connection…");
  const base = apiUrl.value.trim().replace(/\/+$/, "");
  try {
    const response = await fetch(`${base}/health`);
    if (!response.ok) throw new Error(`Server returned ${response.status}.`);
    const body = await response.json();
    if (body.status !== "ok") throw new Error("Unexpected health response.");
    showStatus("Connection successful.");
  } catch (error) {
    showStatus(error.message || "Connection failed.", true);
  }
});

function showStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle("error", error);
}

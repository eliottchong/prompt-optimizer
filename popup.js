"use strict";

const MODEL = "gemini-2.5-flash";
const API_URL =
  `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

function estimateTokens(text) {
  return text ? Math.ceil(text.length / 4) : 0;
}

function buildRequest(prompt) {
  return [
    "Optimize the prompt below for lower token count.",
    "Rules:",
    "- Preserve every requirement, fact, number, code block, URL, name, and requested output format.",
    "- Remove only redundancy, filler, and awkward wording.",
    '- Remove greetings and direct address like "hey chat", "hi there", or "hello chat".',
    '- Prefer key semantic words when safe, e.g. "what will the weather be next week" -> "weather next week".',
    "- Do not answer the prompt.",
    "- Return only the optimized prompt text.",
    "",
    "Prompt:",
    "<<<PROMPT",
    prompt,
    "PROMPT>>>",
  ].join("\n");
}

function chooseCandidate(original, candidate) {
  return estimateTokens(candidate) < estimateTokens(original)
    ? candidate
    : original;
}

async function generateCandidate(apiKey, prompt) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": apiKey,
    },
    body: JSON.stringify({
      contents: [{ parts: [{ text: buildRequest(prompt) }] }],
    }),
  });

  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`Gemini returned invalid response (${response.status}).`);
  }

  if (!response.ok) {
    throw new Error(
      payload?.error?.message || `Gemini request failed (${response.status}).`,
    );
  }

  const candidate = (payload?.candidates?.[0]?.content?.parts || [])
    .map((part) => part.text || "")
    .join("")
    .trim();

  if (!candidate) {
    throw new Error("Gemini returned empty text.");
  }

  return candidate;
}

function selfTest() {
  const request = buildRequest("hello");
  const checks = [
    estimateTokens("") === 0,
    estimateTokens("abcd") === 1,
    estimateTokens("abcde") === 2,
    chooseCandidate("abcdefgh", "abcd") === "abcd",
    chooseCandidate("abcd", "abcdefgh") === "abcd",
    request.includes("Remove greetings and direct address"),
    request.includes("weather next week"),
    request.includes("Do not answer the prompt"),
  ];

  if (checks.includes(false)) {
    throw new Error("Optimizer self-test failed.");
  }
}

function setupPopup() {
  const apiKey = document.querySelector("#apiKey");
  const saveKey = document.querySelector("#saveKey");
  const keyStatus = document.querySelector("#keyStatus");
  const prompt = document.querySelector("#prompt");
  const optimizeButton = document.querySelector("#optimizeButton");
  const status = document.querySelector("#status");
  const result = document.querySelector("#result");
  const metrics = document.querySelector("#metrics");
  const output = document.querySelector("#output");
  const copyButton = document.querySelector("#copyButton");

  function showStatus(element, message, isError = false) {
    element.textContent = message;
    element.dataset.kind = isError ? "error" : "info";
  }

  chrome.storage.local.get("geminiApiKey").then(({ geminiApiKey }) => {
    apiKey.value = geminiApiKey || "";
  }).catch((error) => {
    showStatus(keyStatus, `Could not load key: ${error.message}`, true);
  });

  saveKey.addEventListener("click", async () => {
    const key = apiKey.value.trim();
    if (!key) {
      showStatus(keyStatus, "Enter API key.", true);
      return;
    }

    try {
      await chrome.storage.local.set({ geminiApiKey: key });
      showStatus(keyStatus, "Key saved.");
    } catch (error) {
      showStatus(keyStatus, `Could not save key: ${error.message}`, true);
    }
  });

  optimizeButton.addEventListener("click", async () => {
    const key = apiKey.value.trim();
    const original = prompt.value.trim();

    if (!key) {
      showStatus(status, "Enter and save API key.", true);
      return;
    }
    if (!original) {
      showStatus(status, "Enter prompt.", true);
      return;
    }

    optimizeButton.disabled = true;
    result.hidden = true;
    showStatus(status, "Optimizing…");

    try {
      const candidate = await generateCandidate(key, original);
      const optimized = chooseCandidate(original, candidate);
      const originalTokens = estimateTokens(original);
      const optimizedTokens = estimateTokens(optimized);

      output.value = optimized;
      metrics.textContent =
        `Estimated tokens: ${originalTokens} → ${optimizedTokens} ` +
        `(${originalTokens - optimizedTokens} saved)`;
      result.hidden = false;
      showStatus(
        status,
        optimized === original
          ? "Gemini result was not shorter; original kept."
          : "Optimized.",
      );
    } catch (error) {
      showStatus(status, `Gemini request failed: ${error.message}`, true);
    } finally {
      optimizeButton.disabled = false;
    }
  });

  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(output.value);
      showStatus(status, "Copied.");
    } catch (error) {
      showStatus(status, `Copy failed: ${error.message}`, true);
    }
  });
}

selfTest();

if (typeof document !== "undefined") {
  setupPopup();
}

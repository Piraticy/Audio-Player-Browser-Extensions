const OFFSCREEN_DOCUMENT_PATH = "offscreen.html";

const defaultState = {
  track: null,
  playing: false,
  duration: 0,
  currentTime: 0,
  volume: 0.8,
  error: ""
};

let playerState = { ...defaultState };

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ playerState });
});

chrome.storage.local.get("playerState").then(({ playerState: savedState }) => {
  if (savedState) {
    playerState = { ...defaultState, ...savedState, playing: false };
  }
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target === "background" && message.type === "player:get-state") {
    sendResponse({ ok: true, state: playerState });
    return false;
  }

  if (message?.target === "background" && message.type === "player:load") {
    forwardToOffscreen({
      target: "offscreen",
      type: "offscreen:load",
      track: message.track,
      autoPlay: message.autoPlay ?? true
    }).then(sendResponse);
    return true;
  }

  if (message?.target === "background" && message.type === "player:command") {
    forwardToOffscreen({
      target: "offscreen",
      type: "offscreen:command",
      command: message.command,
      value: message.value
    }).then(sendResponse);
    return true;
  }

  if (message?.target === "background" && message.type === "player:state") {
    playerState = { ...playerState, ...message.state };
    chrome.storage.local.set({ playerState });
    sendResponse({ ok: true });
    return false;
  }

  return false;
});

async function forwardToOffscreen(message) {
  try {
    await ensureOffscreenDocument();
    return await chrome.runtime.sendMessage(message);
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Unable to reach audio player."
    };
  }
}

async function ensureOffscreenDocument() {
  const offscreenUrl = chrome.runtime.getURL(OFFSCREEN_DOCUMENT_PATH);

  if (await hasOffscreenDocument(offscreenUrl)) {
    return;
  }

  await chrome.offscreen.createDocument({
    url: OFFSCREEN_DOCUMENT_PATH,
    reasons: ["AUDIO_PLAYBACK"],
    justification: "Audio should keep playing when the extension popup is closed."
  });
}

async function hasOffscreenDocument(offscreenUrl) {
  if ("getContexts" in chrome.runtime) {
    const contexts = await chrome.runtime.getContexts({
      contextTypes: ["OFFSCREEN_DOCUMENT"],
      documentUrls: [offscreenUrl]
    });
    return contexts.length > 0;
  }

  return Boolean(await chrome.offscreen.hasDocument());
}

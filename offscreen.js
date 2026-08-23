const audio = document.getElementById("audio");

let state = {
  track: null,
  playing: false,
  duration: 0,
  currentTime: 0,
  volume: 0.8,
  error: ""
};

audio.volume = state.volume;

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.target !== "offscreen") {
    return false;
  }

  if (message.type === "offscreen:load") {
    loadTrack(message.track, message.autoPlay)
      .then(() => sendResponse({ ok: true, state }))
      .catch((error) => sendResponse(toErrorResponse(error)));
    return true;
  }

  if (message.type === "offscreen:command") {
    handleCommand(message.command, message.value)
      .then(() => sendResponse({ ok: true, state }))
      .catch((error) => sendResponse(toErrorResponse(error)));
    return true;
  }

  return false;
});

audio.addEventListener("loadedmetadata", () => {
  updateState({ duration: audio.duration || 0, error: "" });
});

audio.addEventListener("timeupdate", () => {
  updateState({ currentTime: audio.currentTime || 0 });
});

audio.addEventListener("play", () => {
  updateState({ playing: true, error: "" });
});

audio.addEventListener("pause", () => {
  updateState({ playing: false });
});

audio.addEventListener("ended", () => {
  updateState({ playing: false, currentTime: 0 });
});

audio.addEventListener("error", () => {
  updateState({
    playing: false,
    error: "This audio file could not be played."
  });
});

async function loadTrack(track, autoPlay) {
  if (!track?.dataUrl) {
    throw new Error("Choose an audio file first.");
  }

  audio.pause();
  audio.src = track.dataUrl;
  audio.currentTime = 0;

  updateState({
    track: {
      id: track.id,
      name: track.name,
      type: track.type,
      size: track.size
    },
    playing: false,
    duration: 0,
    currentTime: 0,
    error: ""
  });

  audio.load();

  if (autoPlay) {
    await audio.play();
  }
}

async function handleCommand(command, value) {
  if (command === "play") {
    await audio.play();
    return;
  }

  if (command === "pause") {
    audio.pause();
    return;
  }

  if (command === "toggle") {
    if (audio.paused) {
      await audio.play();
    } else {
      audio.pause();
    }
    return;
  }

  if (command === "seek") {
    audio.currentTime = clamp(Number(value), 0, audio.duration || 0);
    updateState({ currentTime: audio.currentTime });
    return;
  }

  if (command === "volume") {
    audio.volume = clamp(Number(value), 0, 1);
    updateState({ volume: audio.volume });
    return;
  }

  if (command === "stop") {
    audio.pause();
    audio.currentTime = 0;
    updateState({ playing: false, currentTime: 0 });
  }
}

function updateState(nextState) {
  state = { ...state, ...nextState };
  chrome.runtime.sendMessage({
    target: "background",
    type: "player:state",
    state
  });
}

function clamp(value, min, max) {
  if (Number.isNaN(value)) {
    return min;
  }
  return Math.min(Math.max(value, min), max);
}

function toErrorResponse(error) {
  const message = error instanceof Error ? error.message : "Audio command failed.";
  updateState({ playing: false, error: message });
  return { ok: false, error: message, state };
}

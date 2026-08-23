const fileInput = document.getElementById("fileInput");
const trackName = document.getElementById("trackName");
const trackMeta = document.getElementById("trackMeta");
const seek = document.getElementById("seek");
const currentTime = document.getElementById("currentTime");
const duration = document.getElementById("duration");
const previousButton = document.getElementById("previousButton");
const playButton = document.getElementById("playButton");
const playIcon = document.getElementById("playIcon");
const nextButton = document.getElementById("nextButton");
const volume = document.getElementById("volume");
const playlistElement = document.getElementById("playlist");
const clearButton = document.getElementById("clearButton");
const statusElement = document.getElementById("status");

let playlist = [];
let activeIndex = -1;
let state = {
  track: null,
  playing: false,
  duration: 0,
  currentTime: 0,
  volume: 0.8,
  error: ""
};
let seeking = false;

init();

function init() {
  fileInput.addEventListener("change", handleFiles);
  previousButton.addEventListener("click", playPrevious);
  playButton.addEventListener("click", togglePlayback);
  nextButton.addEventListener("click", playNext);
  clearButton.addEventListener("click", clearPlaylist);

  seek.addEventListener("input", () => {
    seeking = true;
    currentTime.textContent = formatTime(Number(seek.value));
  });

  seek.addEventListener("change", async () => {
    await sendCommand("seek", Number(seek.value));
    seeking = false;
  });

  volume.addEventListener("input", () => {
    sendCommand("volume", Number(volume.value));
  });

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes.playerState?.newValue) {
      setState(changes.playerState.newValue);
    }
  });

  chrome.runtime
    .sendMessage({ target: "background", type: "player:get-state" })
    .then((response) => {
      if (response?.ok) {
        setState(response.state);
      }
    });
}

async function handleFiles(event) {
  const files = [...event.target.files].filter((file) => file.type.startsWith("audio/"));
  statusElement.textContent = "";

  if (!files.length) {
    statusElement.textContent = "Choose one or more audio files.";
    return;
  }

  const tracks = await Promise.all(files.map(fileToTrack));
  playlist = [...playlist, ...tracks];
  renderPlaylist();

  if (activeIndex === -1) {
    playTrack(0);
  }

  fileInput.value = "";
}

function fileToTrack(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      resolve({
        id: `${file.name}-${file.size}-${file.lastModified}`,
        name: file.name,
        type: file.type || "audio",
        size: file.size,
        dataUrl: reader.result
      });
    });
    reader.addEventListener("error", () => reject(new Error(`Could not read ${file.name}.`)));
    reader.readAsDataURL(file);
  });
}

async function playTrack(index) {
  const nextTrack = playlist[index];

  if (!nextTrack) {
    return;
  }

  activeIndex = index;
  renderPlaylist();
  setStatus("");

  const response = await chrome.runtime.sendMessage({
    target: "background",
    type: "player:load",
    track: nextTrack,
    autoPlay: true
  });

  handleResponse(response);
}

function playPrevious() {
  if (!playlist.length) {
    return;
  }
  playTrack((activeIndex - 1 + playlist.length) % playlist.length);
}

function playNext() {
  if (!playlist.length) {
    return;
  }
  playTrack((activeIndex + 1) % playlist.length);
}

async function togglePlayback() {
  if (!state.track && playlist[0]) {
    await playTrack(0);
    return;
  }

  if (!state.track) {
    setStatus("Choose an audio file first.");
    return;
  }

  const response = await sendCommand("toggle");
  handleResponse(response);
}

async function sendCommand(command, value) {
  const response = await chrome.runtime.sendMessage({
    target: "background",
    type: "player:command",
    command,
    value
  });

  handleResponse(response);
  return response;
}

function clearPlaylist() {
  playlist = [];
  activeIndex = -1;
  renderPlaylist();
}

function renderPlaylist() {
  playlistElement.replaceChildren();

  playlist.forEach((track, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const title = document.createElement("span");
    const meta = document.createElement("span");

    button.type = "button";
    button.className = index === activeIndex ? "is-active" : "";
    title.className = "playlist-title";
    meta.className = "playlist-meta";
    title.textContent = track.name;
    meta.textContent = prettyFileSize(track.size);

    button.append(title, meta);
    button.addEventListener("click", () => playTrack(index));
    item.append(button);
    playlistElement.append(item);
  });
}

function setState(nextState) {
  state = { ...state, ...nextState };

  if (state.track) {
    trackName.textContent = state.track.name;
    trackMeta.textContent = `${state.track.type || "audio"} / ${prettyFileSize(state.track.size)}`;
  } else {
    trackName.textContent = "Choose an audio file";
    trackMeta.textContent = "MP3, WAV, OGG, M4A";
  }

  playIcon.textContent = state.playing ? "Pause" : "Play";
  playButton.setAttribute("aria-label", state.playing ? "Pause" : "Play");
  volume.value = state.volume;
  duration.textContent = formatTime(state.duration);
  seek.max = state.duration || 100;

  if (!seeking) {
    seek.value = state.currentTime || 0;
    currentTime.textContent = formatTime(state.currentTime);
  }

  setStatus(state.error || "");
}

function handleResponse(response) {
  if (!response?.ok && response?.error) {
    setStatus(response.error);
  }
}

function setStatus(message) {
  statusElement.textContent = message;
}

function formatTime(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
}

function prettyFileSize(bytes = 0) {
  if (!bytes) {
    return "";
  }

  const megabytes = bytes / 1024 / 1024;
  return `${megabytes.toFixed(megabytes >= 10 ? 0 : 1)} MB`;
}

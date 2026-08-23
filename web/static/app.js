const fileInput = document.getElementById("fileInput");
const audio = document.getElementById("audio");
const playerPanel = document.querySelector(".player-panel");
const trackName = document.getElementById("trackName");
const trackMeta = document.getElementById("trackMeta");
const demoButton = document.getElementById("demoButton");
const dropZone = document.getElementById("dropZone");
const previousButton = document.getElementById("previousButton");
const playButton = document.getElementById("playButton");
const nextButton = document.getElementById("nextButton");
const back20Button = document.getElementById("back20Button");
const back10Button = document.getElementById("back10Button");
const forward10Button = document.getElementById("forward10Button");
const forward20Button = document.getElementById("forward20Button");
const clearButton = document.getElementById("clearButton");
const convertButton = document.getElementById("convertButton");
const autoConvertMp3 = document.getElementById("autoConvertMp3");
const format = document.getElementById("format");
const playlistElement = document.getElementById("playlist");
const statusElement = document.getElementById("status");
const youtubeSearchForm = document.getElementById("youtubeSearchForm");
const youtubeSearchInput = document.getElementById("youtubeSearchInput");
const youtubeStatus = document.getElementById("youtubeStatus");
const mediaLinkForm = document.getElementById("mediaLinkForm");
const mediaLinkInput = document.getElementById("mediaLinkInput");
const cloneLinkButton = document.getElementById("cloneLinkButton");
const linkStatus = document.getElementById("linkStatus");
const saveSearchButton = document.getElementById("saveSearchButton");
const rememberSearches = document.getElementById("rememberSearches");
const suggestionsElement = document.getElementById("suggestions");
const savedSearchesElement = document.getElementById("savedSearches");
const visualizer = document.getElementById("visualizer");
const visualizerMode = document.getElementById("visualizerMode");
const visualizerContext = visualizer.getContext("2d");

let playlist = [];
let activeIndex = -1;
let suggestionTimer = 0;
let audioContext;
let analyser;
let mediaSource;
let visualizerFrame;
const searchStorageKey = "audioPlayer.searches";
const rememberStorageKey = "audioPlayer.rememberSearches";
const visualizerModeKey = "audioPlayer.visualizerMode";
const autoConvertStorageKey = "auralith.autoConvertMp3";
const playableExtensions = new Set(["aac", "aiff", "flac", "m4a", "mkv", "mov", "mp3", "mp4", "oga", "ogg", "opus", "wav", "webm"]);

restorePreferences();
renderSavedSearches();
drawIdleVisualizer();

fileInput.addEventListener("change", () => {
  addFiles([...fileInput.files]);
  fileInput.value = "";
});

demoButton.addEventListener("click", () => {
  addFiles([createDemoTrack()]);
});

["dragenter", "dragover"].forEach((eventName) => {
  playerPanel.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-active");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  playerPanel.addEventListener(eventName, (event) => {
    event.preventDefault();
    if (eventName === "drop") {
      addFiles([...event.dataTransfer.files]);
    }
    dropZone.classList.remove("is-active");
  });
});

previousButton.addEventListener("click", () => {
  if (playlist.length) {
    playTrack((activeIndex - 1 + playlist.length) % playlist.length);
  }
});

playButton.addEventListener("click", async () => {
  if (!audio.src && playlist.length) {
    playTrack(0);
    return;
  }

  if (!audio.src) {
    setStatus("Choose a media file first.");
    return;
  }

  if (audio.paused) {
    await audio.play();
  } else {
    audio.pause();
  }
});

nextButton.addEventListener("click", () => {
  if (playlist.length) {
    playTrack((activeIndex + 1) % playlist.length);
  }
});

back20Button.addEventListener("click", () => seekBy(-20));
back10Button.addEventListener("click", () => seekBy(-10));
forward10Button.addEventListener("click", () => seekBy(10));
forward20Button.addEventListener("click", () => seekBy(20));

clearButton.addEventListener("click", () => {
  audio.pause();
  audio.removeAttribute("src");
  playlist = [];
  activeIndex = -1;
  renderPlaylist();
  updateTrackCopy();
  setStatus("Playlist cleared.");
});

convertButton.addEventListener("click", convertSelected);
autoConvertMp3.addEventListener("change", () => {
  localStorage.setItem(autoConvertStorageKey, String(autoConvertMp3.checked));
});
saveSearchButton.addEventListener("click", () => saveSearch(youtubeSearchInput.value));
rememberSearches.addEventListener("change", () => {
  localStorage.setItem(rememberStorageKey, String(rememberSearches.checked));
});
visualizerMode.addEventListener("change", () => {
  localStorage.setItem(visualizerModeKey, visualizerMode.value);
  if (visualizerMode.value === "off") {
    cancelAnimationFrame(visualizerFrame);
    drawIdleVisualizer();
  }
});
youtubeSearchInput.addEventListener("input", () => {
  clearTimeout(suggestionTimer);
  suggestionTimer = window.setTimeout(fetchSuggestions, 240);
});
youtubeSearchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = youtubeSearchInput.value.trim();

  if (!query) {
    youtubeStatus.textContent = "Enter a search term first.";
    return;
  }

  if (rememberSearches.checked) {
    saveSearch(query, false);
  }

  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
  window.open(url, "_blank", "noopener,noreferrer");
  youtubeStatus.textContent = "Opened official YouTube search results.";
});
mediaLinkForm.addEventListener("submit", (event) => {
  event.preventDefault();
  playMediaLink();
});
cloneLinkButton.addEventListener("click", cloneMediaLink);

audio.addEventListener("play", () => {
  playButton.textContent = "Pause";
  startVisualizer();
});
audio.addEventListener("pause", () => {
  playButton.textContent = "Play";
});
audio.addEventListener("ended", () => {
  if (playlist.length) {
    playTrack((activeIndex + 1) % playlist.length);
  }
});
audio.addEventListener("error", () => {
  const track = playlist[activeIndex];
  playButton.textContent = "Play";
  if (isLinkTrack(track)) {
    linkStatus.textContent = "This URL is not a playable direct media file.";
    setStatus("Use a direct MP3, WAV, M4A, OGG, FLAC, or video file link.");
  } else {
    setStatus("This file could not be played by the browser.");
  }
});
document.addEventListener("keydown", handleKeyboardShortcuts);

function addFiles(files) {
  const mediaFiles = files.filter(isPlayableFile);

  if (!mediaFiles.length) {
    setStatus("Add audio or video files.");
    return;
  }

  if (autoConvertMp3.checked) {
    autoConvertFiles(mediaFiles);
    return;
  }

  addPlayableFiles(mediaFiles);
}

function addPlayableFiles(files) {
  const firstNewIndex = playlist.length;
  playlist.push(...files);
  renderPlaylist();

  if (activeIndex === -1 && files.length) {
    playTrack(firstNewIndex);
  } else {
    setStatus(`Added ${files.length} file(s).`);
  }
}

function playTrack(index) {
  const track = playlist[index];
  if (!track) {
    return;
  }

  if (isLinkTrack(track)) {
    const linkUrl = parsedHttpUrl(track.url);
    if (!linkUrl) {
      removePlaylistTrack(index, "Removed an invalid link from the playlist.");
      return;
    }
    if (routeStreamingLink(linkUrl)) {
      removePlaylistTrack(index, "Removed YouTube watch page from the playlist.");
      return;
    }
  }

  if (audio.src.startsWith("blob:")) {
    URL.revokeObjectURL(audio.src);
  }

  activeIndex = index;
  audio.src = isLinkTrack(track) ? track.url : URL.createObjectURL(track);
  audio.play().catch(() => {
    setStatus("Press Play to start this file.");
  });
  updateTrackCopy(track);
  renderPlaylist();
  setStatus(`Playing ${track.name}`);
}

function playMediaLink() {
  const url = mediaLinkUrl();
  if (!url || routeStreamingLink(url)) {
    return;
  }

  const track = {
    kind: "link",
    name: nameFromLink(url.href),
    type: "Direct media link",
    size: 0,
    url: url.href
  };
  addPlayableFiles([track]);
  linkStatus.textContent = "Playing direct media link.";
}

async function cloneMediaLink() {
  const url = mediaLinkUrl();
  if (!url || routeStreamingLink(url)) {
    return;
  }

  cloneLinkButton.disabled = true;
  linkStatus.textContent = "Cloning direct media link...";

  try {
    const response = await fetch("/api/clone-link", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url.href })
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || "Could not clone this media link.");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = getFilename(disposition) || nameFromLink(url.href);
    addFiles([new File([blob], filename, { type: blob.type || "application/octet-stream" })]);
    linkStatus.textContent = "Cloned media into the playlist.";
  } catch (error) {
    linkStatus.textContent = error instanceof Error ? error.message : "Could not clone this media link.";
  } finally {
    cloneLinkButton.disabled = false;
  }
}

function mediaLinkUrl() {
  const rawLink = mediaLinkInput.value.trim();
  const url = parsedHttpUrl(rawLink);

  if (!url) {
    linkStatus.textContent = "Paste a valid http or https direct media link.";
    return null;
  }

  return url;
}

function routeStreamingLink(url) {
  if (!isYouTubeUrl(url)) {
    return false;
  }

  youtubeSearchInput.value = youtubeQueryFromUrl(url);
  youtubeStatus.textContent = "YouTube links open on official YouTube.";
  linkStatus.textContent = "YouTube pages are not direct media files, so they cannot play in Direct Media.";
  window.open(url.href, "_blank", "noopener,noreferrer");
  return true;
}

function handleKeyboardShortcuts(event) {
  const tagName = event.target?.tagName?.toLowerCase();
  if (tagName === "input" || tagName === "select" || tagName === "textarea") {
    return;
  }

  if (event.code === "Space") {
    event.preventDefault();
    playButton.click();
  } else if (event.key === "ArrowLeft") {
    event.preventDefault();
    seekBy(event.shiftKey ? -20 : -10);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    seekBy(event.shiftKey ? 20 : 10);
  } else if (event.key.toLowerCase() === "n") {
    nextButton.click();
  } else if (event.key.toLowerCase() === "p") {
    previousButton.click();
  }
}

function seekBy(seconds) {
  if (!audio.src || !Number.isFinite(audio.duration)) {
    setStatus("Load a playable file before seeking.");
    return;
  }

  audio.currentTime = clamp(audio.currentTime + seconds, 0, audio.duration);
}

async function convertSelected() {
  const file = playlist[activeIndex];
  if (!file) {
    setStatus("Choose a media file first.");
    return;
  }
  if (isLinkTrack(file)) {
    setStatus("Clone the link into the playlist before converting it.");
    return;
  }

  setStatus(`Converting ${file.name}...`);
  convertButton.disabled = true;

  try {
    const { blob, filename } = await convertFile(file, format.value);
    downloadBlob(blob, filename);
    setStatus(`Converted ${filename}`);
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "Conversion failed.");
  } finally {
    convertButton.disabled = false;
  }
}

async function autoConvertFiles(files) {
  autoConvertMp3.disabled = true;
  convertButton.disabled = true;
  const convertedFiles = [];
  const failedFiles = [];

  for (const [index, file] of files.entries()) {
    setStatus(`Auto-converting ${index + 1}/${files.length}: ${file.name}`);
    try {
      const { blob, filename } = await convertFile(file, "mp3");
      convertedFiles.push(new File([blob], filename, { type: "audio/mpeg" }));
    } catch {
      failedFiles.push(file);
    }
  }

  addPlayableFiles([...convertedFiles, ...failedFiles]);
  autoConvertMp3.disabled = false;
  convertButton.disabled = false;

  if (failedFiles.length) {
    setStatus(`Auto-converted ${convertedFiles.length}; added ${failedFiles.length} original file(s).`);
  } else {
    setStatus(`Auto-converted ${convertedFiles.length} file(s) to MP3.`);
  }
}

async function convertFile(file, outputFormat) {
  const body = new FormData();
  body.append("file", file);
  body.append("format", outputFormat);

  const response = await fetch("/api/convert", {
    method: "POST",
    body
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Conversion failed.");
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = getFilename(disposition) || `${stripExtension(file.name)}.${outputFormat}`;
  return { blob, filename };
}

async function fetchSuggestions() {
  const query = youtubeSearchInput.value.trim();
  if (!query) {
    suggestionsElement.replaceChildren();
    return;
  }

  try {
    const response = await fetch(`/api/youtube-suggestions?q=${encodeURIComponent(query)}`);
    const payload = await response.json();
    renderSuggestions(payload.suggestions || []);
  } catch {
    renderSuggestions([]);
  }
}

function renderSuggestions(suggestions) {
  suggestionsElement.replaceChildren();

  suggestions.forEach((suggestion) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = suggestion;
    button.addEventListener("click", () => {
      youtubeSearchInput.value = suggestion;
      suggestionsElement.replaceChildren();
      youtubeSearchInput.focus();
    });
    suggestionsElement.append(button);
  });
}

function saveSearch(rawQuery, showStatus = true) {
  const query = rawQuery.trim();
  if (!query) {
    youtubeStatus.textContent = "Enter a search term first.";
    return;
  }

  const searches = getSavedSearches();
  const nextSearches = [query, ...searches.filter((search) => search.toLowerCase() !== query.toLowerCase())].slice(0, 10);
  localStorage.setItem(searchStorageKey, JSON.stringify(nextSearches));
  renderSavedSearches();

  if (showStatus) {
    youtubeStatus.textContent = "Search saved.";
  }
}

function getSavedSearches() {
  try {
    const searches = JSON.parse(localStorage.getItem(searchStorageKey) || "[]");
    return Array.isArray(searches) ? searches.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function renderSavedSearches() {
  savedSearchesElement.replaceChildren();

  getSavedSearches().forEach((search) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = search;
    button.addEventListener("click", () => {
      youtubeSearchInput.value = search;
      fetchSuggestions();
    });
    savedSearchesElement.append(button);
  });
}

function restorePreferences() {
  rememberSearches.checked = localStorage.getItem(rememberStorageKey) !== "false";
  visualizerMode.value = localStorage.getItem(visualizerModeKey) || "bars";
  autoConvertMp3.checked = localStorage.getItem(autoConvertStorageKey) !== "false";
}

function startVisualizer() {
  if (visualizerMode.value === "off") {
    drawIdleVisualizer();
    return;
  }

  if (!audioContext) {
    audioContext = new AudioContext();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    mediaSource = audioContext.createMediaElementSource(audio);
    mediaSource.connect(analyser);
    analyser.connect(audioContext.destination);
  }

  audioContext.resume();
  cancelAnimationFrame(visualizerFrame);
  drawVisualizer();
}

function drawVisualizer() {
  resizeCanvas();
  const width = visualizer.width;
  const height = visualizer.height;
  const mode = visualizerMode.value;

  visualizerContext.clearRect(0, 0, width, height);

  if (!analyser || mode === "off") {
    drawIdleVisualizer();
    return;
  }

  if (mode === "wave") {
    drawWave(width, height);
  } else if (mode === "halo") {
    drawHalo(width, height);
  } else {
    drawBars(width, height);
  }

  visualizerFrame = requestAnimationFrame(drawVisualizer);
}

function drawBars(width, height) {
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  const barCount = 54;
  const gap = 4;
  const barWidth = (width - gap * (barCount - 1)) / barCount;

  for (let index = 0; index < barCount; index += 1) {
    const value = data[Math.floor(index * data.length / barCount)] / 255;
    const barHeight = Math.max(6, value * height * 0.88);
    const x = index * (barWidth + gap);
    const y = height - barHeight;
    visualizerContext.fillStyle = `rgba(${47 + index}, ${210 + Math.floor(value * 45)}, ${200 - index}, ${0.38 + value * 0.55})`;
    visualizerContext.fillRect(x, y, barWidth, barHeight);
  }
}

function drawWave(width, height) {
  const data = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(data);
  visualizerContext.lineWidth = 4;
  visualizerContext.strokeStyle = "rgba(47, 230, 200, 0.86)";
  visualizerContext.beginPath();

  data.forEach((value, index) => {
    const x = index / (data.length - 1) * width;
    const y = value / 255 * height;
    if (index === 0) {
      visualizerContext.moveTo(x, y);
    } else {
      visualizerContext.lineTo(x, y);
    }
  });

  visualizerContext.stroke();
}

function drawHalo(width, height) {
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  const average = data.reduce((sum, value) => sum + value, 0) / data.length / 255;
  const radius = Math.min(width, height) * (0.18 + average * 0.22);
  const gradient = visualizerContext.createRadialGradient(width / 2, height / 2, 4, width / 2, height / 2, radius * 2.4);

  gradient.addColorStop(0, "rgba(245, 242, 236, 0.95)");
  gradient.addColorStop(0.24, "rgba(47, 230, 200, 0.65)");
  gradient.addColorStop(0.7, "rgba(93, 140, 255, 0.24)");
  gradient.addColorStop(1, "rgba(242, 193, 77, 0)");
  visualizerContext.fillStyle = gradient;
  visualizerContext.beginPath();
  visualizerContext.arc(width / 2, height / 2, radius * 2.2, 0, Math.PI * 2);
  visualizerContext.fill();
}

function drawIdleVisualizer() {
  resizeCanvas();
  const width = visualizer.width;
  const height = visualizer.height;
  visualizerContext.clearRect(0, 0, width, height);
  visualizerContext.fillStyle = "rgba(245, 242, 236, 0.08)";
  for (let index = 0; index < 36; index += 1) {
    const x = index / 35 * width;
    const barHeight = 10 + Math.sin(index * 0.8) * 6 + 16;
    visualizerContext.fillRect(x, height / 2 - barHeight / 2, 4, barHeight);
  }
}

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  const rect = visualizer.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width * ratio));
  const height = Math.max(1, Math.floor(rect.height * ratio));

  if (visualizer.width !== width || visualizer.height !== height) {
    visualizer.width = width;
    visualizer.height = height;
  }
}

function renderPlaylist() {
  playlistElement.replaceChildren();

  playlist.forEach((file, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const name = document.createElement("span");
    const meta = document.createElement("span");

    button.type = "button";
    button.className = index === activeIndex ? "active" : "";
    name.textContent = file.name;
    meta.textContent = isLinkTrack(file) ? "Link" : prettySize(file.size);
    button.append(name, meta);
    button.addEventListener("click", () => playTrack(index));
    item.append(button);
    playlistElement.append(item);
  });
}

function removePlaylistTrack(index, message) {
  playlist.splice(index, 1);
  if (activeIndex === index) {
    audio.pause();
    audio.removeAttribute("src");
    activeIndex = -1;
    updateTrackCopy();
  } else if (activeIndex > index) {
    activeIndex -= 1;
  }

  renderPlaylist();
  setStatus(message);
}

function updateTrackCopy(file) {
  if (!file) {
    trackName.textContent = "Choose a media file";
    trackMeta.textContent = "MP3 conversion defaults to 320 kbps.";
    return;
  }

  trackName.textContent = file.name;
  trackMeta.textContent = isLinkTrack(file) ? file.type : `${file.type || "media"} / ${prettySize(file.size)}`;
}

function setStatus(message) {
  statusElement.textContent = message;
}

function prettySize(bytes) {
  if (!bytes) {
    return "0 MB";
  }
  const mb = bytes / 1024 / 1024;
  return `${mb.toFixed(mb >= 10 ? 0 : 1)} MB`;
}

function isPlayableFile(file) {
  const type = file.type || "";
  const extension = extensionFromName(file.name);
  return type.startsWith("audio/") || type.startsWith("video/") || playableExtensions.has(extension);
}

function isLinkTrack(track) {
  return track?.kind === "link";
}

function nameFromLink(url) {
  try {
    const name = decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).pop() || "");
    return name || new URL(url).hostname;
  } catch {
    return "linked-media";
  }
}

function parsedHttpUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }
    return url;
  } catch {
    return null;
  }
}

function isYouTubeUrl(url) {
  const hostname = url.hostname.toLowerCase().replace(/^www\./, "");
  return hostname === "youtube.com" || hostname === "m.youtube.com" || hostname === "youtu.be";
}

function youtubeQueryFromUrl(url) {
  if (url.hostname.toLowerCase().replace(/^www\./, "") === "youtu.be") {
    return url.pathname.split("/").filter(Boolean)[0] || url.href;
  }

  return url.searchParams.get("v") || url.searchParams.get("search_query") || url.href;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function stripExtension(name) {
  return name.replace(/\.[^.]+$/, "");
}

function extensionFromName(name) {
  return name.toLowerCase().split(".").pop() || "";
}

function getFilename(disposition) {
  const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch) {
    return decodeURIComponent(encodedMatch[1]);
  }

  const quotedMatch = disposition.match(/filename="([^"]+)"/i);
  if (quotedMatch) {
    return quotedMatch[1];
  }

  const plainMatch = disposition.match(/filename=([^;]+)/i);
  return plainMatch?.[1]?.trim();
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function createDemoTrack() {
  const sampleRate = 44100;
  const duration = 8;
  const sampleCount = sampleRate * duration;
  const samples = new Float32Array(sampleCount);

  for (let index = 0; index < sampleCount; index += 1) {
    const time = index / sampleRate;
    const envelope = Math.min(1, time * 2, (duration - time) * 2);
    const bass = Math.sin(Math.PI * 2 * 110 * time) * 0.24;
    const lead = Math.sin(Math.PI * 2 * (220 + Math.sin(time * 3) * 24) * time) * 0.18;
    const shimmer = Math.sin(Math.PI * 2 * 660 * time) * 0.04;
    samples[index] = (bass + lead + shimmer) * envelope;
  }

  return new File([encodeWav(samples, sampleRate)], "auralith-demo.wav", { type: "audio/wav" });
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeText(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(view, 8, "WAVE");
  writeText(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);

  samples.forEach((sample, index) => {
    const value = clamp(sample, -1, 1);
    view.setInt16(44 + index * 2, value < 0 ? value * 0x8000 : value * 0x7fff, true);
  });

  return buffer;
}

function writeText(view, offset, text) {
  [...text].forEach((character, index) => {
    view.setUint8(offset + index, character.charCodeAt(0));
  });
}

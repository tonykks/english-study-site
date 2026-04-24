const CONTENT_PARAM_KEY = "content";
const DEFAULT_CONTENT = "Crisis_in_Middle_East";
const bodyDataset = document.body?.dataset || {};
const pathSegments = window.location.pathname.split("/").filter(Boolean);
const inferredContentId = pathSegments.at(-1) === "index.html" && pathSegments.length >= 2
  ? decodeURIComponent(pathSegments.at(-2))
  : "";
const contentId = bodyDataset.contentId || new URLSearchParams(window.location.search).get(CONTENT_PARAM_KEY) || inferredContentId || DEFAULT_CONTENT;
const BASE_DIR = bodyDataset.baseDir || (inferredContentId ? "." : `data/${contentId}`);
const SERVICE_WORKER_PATH = bodyDataset.swPath || "./service-worker.js";
const META_KEYS = new Set([
  "title",
  "level",
  "description",
  "source",
  "video_id",
  "video_url",
  "channel",
  "thumbnail_image",
  "cover_image",
  "notes"
]);
const STORAGE_KEY = `english-study-${contentId}-state-v1`;

let activeSpeechButton = null;
let activeUtterance = null;
let selectedVoice = null;
let ttsRate = 0.95;
let currentWordCards = [];
let sfxContext = null;

const appState = {
  flipped: new Set(),
  favorites: new Set(),
  difficulties: {},
  badges: new Set(),
  startAt: Date.now(),
  totalStudySeconds: 0,
  theme: "light",
  reviewScores: {}
};

const hangmanState = {
  items: [],
  index: 0,
  selectedWords: [],
  poolWords: [],
  wrongCount: 0,
  score: 0,
  maxSteps: 7,
  finished: false
};

function normalizeText(text) {
  return String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function playWrongSfx() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!sfxContext) sfxContext = new AudioCtx();
    const osc = sfxContext.createOscillator();
    const gain = sfxContext.createGain();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(220, sfxContext.currentTime);
    osc.frequency.exponentialRampToValueAtTime(130, sfxContext.currentTime + 0.18);
    gain.gain.setValueAtTime(0.001, sfxContext.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.12, sfxContext.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, sfxContext.currentTime + 0.2);
    osc.connect(gain);
    gain.connect(sfxContext.destination);
    osc.start();
    osc.stop(sfxContext.currentTime + 0.21);
  } catch (error) {
    console.warn("wrong sfx unavailable", error);
  }
}

function playDeathSfx() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!sfxContext) sfxContext = new AudioCtx();

    const now = sfxContext.currentTime;
    const master = sfxContext.createGain();
    master.gain.setValueAtTime(0.001, now);
    master.gain.exponentialRampToValueAtTime(0.18, now + 0.02);
    master.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
    master.connect(sfxContext.destination);

    const osc1 = sfxContext.createOscillator();
    const osc2 = sfxContext.createOscillator();
    osc1.type = "triangle";
    osc2.type = "sawtooth";
    osc1.frequency.setValueAtTime(280, now);
    osc1.frequency.exponentialRampToValueAtTime(90, now + 0.45);
    osc2.frequency.setValueAtTime(180, now);
    osc2.frequency.exponentialRampToValueAtTime(55, now + 0.45);

    const lowpass = sfxContext.createBiquadFilter();
    lowpass.type = "lowpass";
    lowpass.frequency.setValueAtTime(1200, now);
    lowpass.frequency.exponentialRampToValueAtTime(280, now + 0.5);

    osc1.connect(lowpass);
    osc2.connect(lowpass);
    lowpass.connect(master);

    osc1.start(now);
    osc2.start(now);
    osc1.stop(now + 0.48);
    osc2.stop(now + 0.48);

    const impact = sfxContext.createOscillator();
    const impactGain = sfxContext.createGain();
    impact.type = "square";
    impact.frequency.setValueAtTime(85, now + 0.36);
    impactGain.gain.setValueAtTime(0.001, now + 0.35);
    impactGain.gain.exponentialRampToValueAtTime(0.12, now + 0.37);
    impactGain.gain.exponentialRampToValueAtTime(0.001, now + 0.52);
    impact.connect(impactGain);
    impactGain.connect(master);
    impact.start(now + 0.35);
    impact.stop(now + 0.53);
  } catch (error) {
    console.warn("death sfx unavailable", error);
  }
}

function playCorrectSfx() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!sfxContext) sfxContext = new AudioCtx();

    const now = sfxContext.currentTime;
    const gain = sfxContext.createGain();
    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(0.14, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.24);
    gain.connect(sfxContext.destination);

    const oscA = sfxContext.createOscillator();
    const oscB = sfxContext.createOscillator();
    oscA.type = "sine";
    oscB.type = "triangle";
    oscA.frequency.setValueAtTime(660, now);
    oscA.frequency.exponentialRampToValueAtTime(880, now + 0.18);
    oscB.frequency.setValueAtTime(990, now + 0.03);
    oscB.frequency.exponentialRampToValueAtTime(1320, now + 0.2);
    oscA.connect(gain);
    oscB.connect(gain);
    oscA.start(now);
    oscB.start(now + 0.03);
    oscA.stop(now + 0.2);
    oscB.stop(now + 0.24);
  } catch (error) {
    console.warn("correct sfx unavailable", error);
  }
}

function playWinSfx() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    if (!sfxContext) sfxContext = new AudioCtx();

    const now = sfxContext.currentTime;
    const master = sfxContext.createGain();
    master.gain.setValueAtTime(0.001, now);
    master.gain.exponentialRampToValueAtTime(0.18, now + 0.02);
    master.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
    master.connect(sfxContext.destination);

    const notes = [523.25, 659.25, 783.99, 1046.5];
    notes.forEach((freq, idx) => {
      const osc = sfxContext.createOscillator();
      const gain = sfxContext.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(freq, now + idx * 0.1);
      gain.gain.setValueAtTime(0.001, now + idx * 0.1);
      gain.gain.exponentialRampToValueAtTime(0.12, now + idx * 0.1 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.1 + 0.15);
      osc.connect(gain);
      gain.connect(master);
      osc.start(now + idx * 0.1);
      osc.stop(now + idx * 0.1 + 0.16);
    });
  } catch (error) {
    console.warn("win sfx unavailable", error);
  }
}

function saveState() {
  const payload = {
    flipped: Array.from(appState.flipped),
    favorites: Array.from(appState.favorites),
    difficulties: appState.difficulties,
    badges: Array.from(appState.badges),
    totalStudySeconds: appState.totalStudySeconds,
    theme: appState.theme,
    reviewScores: appState.reviewScores,
    hangman: {
      score: hangmanState.score,
      index: hangmanState.index
    }
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    appState.flipped = new Set(parsed.flipped || []);
    appState.favorites = new Set(parsed.favorites || []);
    appState.difficulties = parsed.difficulties || {};
    appState.badges = new Set(parsed.badges || []);
    appState.totalStudySeconds = parsed.totalStudySeconds || 0;
    appState.theme = parsed.theme || "light";
    appState.reviewScores = parsed.reviewScores || {};
    hangmanState.score = parsed.hangman?.score || 0;
    hangmanState.index = parsed.hangman?.index || 0;
  } catch (error) {
    console.warn("state load failed", error);
  }
}

function getHangmanCurrentItem() {
  if (!hangmanState.items.length) return null;
  return hangmanState.items[hangmanState.index % hangmanState.items.length];
}

function renderHangmanSentence() {
  const sentenceNode = document.getElementById("hangman-sentence");
  const item = getHangmanCurrentItem();
  if (!sentenceNode || !item) return;
  const targetWords = item.en.toUpperCase().split(/\s+/).filter(Boolean);
  const selected = hangmanState.selectedWords;
  let html = "";
  for (let i = 0; i < targetWords.length; i += 1) {
    const text = selected[i] || "____";
    html += `<span style="display:inline-block;margin-right:6px;margin-bottom:6px;padding:3px 8px;border:1px dashed #5f76a4;border-radius:8px;">${escapeHtml(text)}</span>`;
  }
  sentenceNode.innerHTML = html;
}

function renderHangmanStats() {
  const step = document.getElementById("hangman-step");
  const score = document.getElementById("hangman-score");
  const progress = document.getElementById("hangman-progress");
  if (step) step.textContent = `${hangmanState.wrongCount} / ${hangmanState.maxSteps}`;
  if (score) score.textContent = String(hangmanState.score);
  if (progress) progress.textContent = `${Math.min(hangmanState.index + 1, hangmanState.items.length)} / ${hangmanState.items.length}`;
}

function renderHangmanHint() {
  const hint = document.getElementById("hangman-hint");
  const item = getHangmanCurrentItem();
  if (!hint || !item) return;
  hint.textContent = item.kr || "-";
}

function renderHangmanWordChips() {
  const root = document.getElementById("hangman-word-buttons");
  if (!root) return;
  root.innerHTML = "";
  hangmanState.poolWords.forEach((entry) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "hangman-word-chip";
    btn.textContent = entry.word;
    btn.disabled = hangmanState.finished;
    btn.addEventListener("click", () => {
      if (hangmanState.finished) return;
      const item = getHangmanCurrentItem();
      if (!item) return;
      const targetWords = item.en.toUpperCase().split(/\s+/).filter(Boolean);
      const targetIdx = hangmanState.selectedWords.length;
      const expected = targetWords[targetIdx];
      if (entry.word === expected) {
        hangmanState.selectedWords.push(entry.word);
        hangmanState.poolWords = hangmanState.poolWords.filter((w) => w.id !== entry.id);
        playCorrectSfx();
        setHangmanStatus("정답 위치 단어입니다! 계속 선택하세요.");
        renderHangmanSentence();
        renderHangmanWordChips();
        renderHangmanFigure();
        renderHangmanStats();
        checkHangmanResult();
      } else {
        hangmanState.wrongCount += 1;
        if (hangmanState.wrongCount >= hangmanState.maxSteps) {
          playDeathSfx();
        } else {
          playWrongSfx();
        }
        btn.classList.add("shake-wrong");
        setHangmanStatus("틀린 위치입니다. 다시 선택해보세요.");
        setTimeout(() => {
          renderHangmanWordChips();
          renderHangmanFigure();
          renderHangmanStats();
          checkHangmanResult();
        }, 180);
      }
    });
    root.appendChild(btn);
  });
}

function renderHangmanFigure() {
  const parts = Array.from(document.querySelectorAll("#hangman-svg .hg-part"));
  parts.forEach((part) => {
    const step = Number(part.getAttribute("data-step"));
    part.classList.toggle("active", hangmanState.wrongCount >= step);
  });
}

function setHangmanStatus(message, mode = "") {
  const node = document.getElementById("hangman-status");
  const wrap = document.getElementById("hangman-game");
  if (!node || !wrap) return;
  node.textContent = message;
  node.classList.remove("win", "lose");
  wrap.classList.remove("game-celebrate", "game-shake");
  if (mode) {
    node.classList.add(mode);
    wrap.classList.add(mode === "win" ? "game-celebrate" : "game-shake");
    setTimeout(() => wrap.classList.remove("game-celebrate", "game-shake"), 450);
  }
}

function checkHangmanResult() {
  const item = getHangmanCurrentItem();
  if (!item) return;
  const target = item.en.toUpperCase().split(/\s+/).filter(Boolean);
  if (hangmanState.selectedWords.length === target.length) {
    hangmanState.finished = true;
    hangmanState.score += 1;
    playWinSfx();
    setHangmanStatus("정답! 어순이 정확합니다. +1점", "win");
    saveState();
    renderHangmanStats();
    return;
  }
  if (hangmanState.wrongCount >= hangmanState.maxSteps) {
    hangmanState.finished = true;
    setHangmanStatus(`행맨이 완성되어 실패했습니다. 정답: ${target.join(" ")}`, "lose");
    saveState();
    renderHangmanStats();
  }
}

function startHangmanRound() {
  const item = getHangmanCurrentItem();
  if (!item) return;
  const words = item.en.toUpperCase().split(/\s+/).filter(Boolean);
  hangmanState.poolWords = words.map((word, idx) => ({ id: `${idx}-${word}`, word })).sort(() => Math.random() - 0.5);
  hangmanState.selectedWords = [];
  hangmanState.wrongCount = 0;
  hangmanState.finished = false;
  setHangmanStatus("단어를 어순대로 선택하세요.");
  renderHangmanSentence();
  renderHangmanHint();
  renderHangmanFigure();
  renderHangmanWordChips();
  renderHangmanStats();
}

function setupHangman(items) {
  hangmanState.items = items.map((item) => ({ en: item.en || "", kr: item.kr || "" })).filter((item) => item.en);
  if (!hangmanState.items.length) return;
  hangmanState.index = hangmanState.index % hangmanState.items.length;
  const nextBtn = document.getElementById("hangman-next-btn");
  const resetBtn = document.getElementById("hangman-reset-btn");
  const checkBtn = document.getElementById("hangman-check-btn");
  const clearBtn = document.getElementById("hangman-clear-btn");
  const playerNode = document.getElementById("hangman-player");
  if (playerNode) playerNode.textContent = "PLAYER 1";

  nextBtn?.addEventListener("click", () => {
    hangmanState.index = (hangmanState.index + 1) % hangmanState.items.length;
    saveState();
    startHangmanRound();
  });
  resetBtn?.addEventListener("click", () => {
    hangmanState.score = 0;
    hangmanState.index = 0;
    saveState();
    startHangmanRound();
  });
  checkBtn?.addEventListener("click", () => {
    checkHangmanResult();
    if (!hangmanState.finished) {
      setHangmanStatus("아직 완성되지 않았습니다. 어순대로 계속 선택하세요.");
    }
  });
  clearBtn?.addEventListener("click", () => {
    const item = getHangmanCurrentItem();
    if (!item) return;
    const words = item.en.toUpperCase().split(/\s+/).filter(Boolean);
    hangmanState.poolWords = words.map((word, idx) => ({ id: `${idx}-${word}`, word })).sort(() => Math.random() - 0.5);
    hangmanState.selectedWords = [];
    hangmanState.wrongCount = 0;
    hangmanState.finished = false;
    setHangmanStatus("선택을 초기화했습니다.");
    renderHangmanSentence();
    renderHangmanWordChips();
    renderHangmanFigure();
    renderHangmanStats();
  });

  startHangmanRound();
}

function updateOnlineStatus() {
  const node = document.getElementById("online-status");
  if (!node) return;
  const online = navigator.onLine;
  node.textContent = online ? "온라인" : "오프라인";
  node.className = online
    ? "rounded-full bg-emerald-50 px-2 py-1 font-semibold text-emerald-700"
    : "rounded-full bg-amber-50 px-2 py-1 font-semibold text-amber-700";
}

function updateStats() {
  const allCount = currentWordCards.length;
  const flippedCount = appState.flipped.size;
  const favoriteCount = appState.favorites.size;
  const badgeCount = appState.badges.size;
  const setText = (id, value) => {
    const node = document.getElementById(id);
    if (node) node.textContent = String(value);
  };
  setText("stat-total-cards", allCount);
  setText("stat-flipped-cards", flippedCount);
  setText("stat-favorites", favoriteCount);
  setText("stat-badges", badgeCount);
}

function updateBadges() {
  if (appState.flipped.size >= 3) appState.badges.add("first_flips");
  if (appState.favorites.size >= 3) appState.badges.add("bookmark_lover");
  if (appState.flipped.size >= Math.max(5, Math.floor(currentWordCards.length * 0.8))) appState.badges.add("deep_reader");
  if (appState.totalStudySeconds >= 600) appState.badges.add("focus_10min");
  saveState();

  const badgeMap = {
    first_flips: "🚀 First Flips",
    bookmark_lover: "⭐ Bookmark Lover",
    deep_reader: "📘 Deep Reader",
    focus_10min: "⏱ 10min Focus"
  };
  const area = document.getElementById("badge-area");
  if (!area) return;
  area.innerHTML = "";
  Array.from(appState.badges).forEach((key) => {
    const chip = document.createElement("span");
    chip.className = "badge-chip";
    chip.textContent = badgeMap[key] || key;
    area.appendChild(chip);
  });
}

function classifyDifficulty(card) {
  const text = `${card.definition_en || ""} ${card.example_en || ""}`;
  const words = text.split(/\s+/).filter(Boolean).length;
  if (words >= 28) return "hard";
  if (words >= 18) return "medium";
  return "easy";
}

function parseKeyValueText(text) {
  const lines = normalizeText(text).split("\n");
  const result = {};
  let currentKey = null;

  lines.forEach((raw) => {
    const line = raw.trim();
    if (!line) return;
    const idx = line.indexOf(":");

    if (idx > 0) {
      const key = line.slice(0, idx).trim().toLowerCase();
      const value = line.slice(idx + 1).trim();
      result[key] = value;
      currentKey = key;
      return;
    }

    if (currentKey) {
      result[currentKey] = `${result[currentKey]}\n${line}`.trim();
    }
  });

  return result;
}

function parseTaggedBlocks(text) {
  const lines = normalizeText(text).split("\n");
  const blocks = [];
  let current = null;
  let currentField = "";

  lines.forEach((raw) => {
    const line = raw.trim();
    if (!line) return;

    if (/^\[.+\]$/.test(line)) {
      if (current) blocks.push(current);
      current = { label: line.slice(1, -1), en: "", kr: "" };
      currentField = "";
      return;
    }

    if (!current) return;
    const idx = line.indexOf(":");
    const key = (idx > -1 ? line.slice(0, idx) : "").trim().toLowerCase();
    const value = idx > -1 ? line.slice(idx + 1).trim() : line;

    if (key === "en" || key === "kr") {
      current[key] = value;
      currentField = key;
      return;
    }

    if (currentField) {
      current[currentField] = `${current[currentField]}\n${value}`.trim();
    }
  });

  if (current) blocks.push(current);
  return blocks;
}

function clearSpeakingState(button) {
  if (!button) return;
  button.classList.remove("is-speaking");
  button.setAttribute("aria-pressed", "false");
}

function markSpeaking(button) {
  if (!button) return;
  button.classList.add("is-speaking");
  button.setAttribute("aria-pressed", "true");
}

function setTtsStatus(message) {
  const status = document.getElementById("tts-status");
  if (status) status.textContent = message;
}

function getEnglishVoice() {
  if (selectedVoice) return selectedVoice;
  const voices = window.speechSynthesis.getVoices();
  selectedVoice = voices.find((v) => /en-US/i.test(v.lang))
    || voices.find((v) => /^en/i.test(v.lang))
    || null;
  return selectedVoice;
}

function speakEnglish(text, sourceButton) {
  if (!text) return;
  if (!("speechSynthesis" in window)) {
    alert("이 브라우저는 음성 합성을 지원하지 않습니다.");
    return;
  }

  if (activeSpeechButton && activeSpeechButton !== sourceButton) {
    clearSpeakingState(activeSpeechButton);
  }
  if (activeUtterance) {
    window.speechSynthesis.cancel();
    activeUtterance = null;
    resetLessonCoverPlaybackState();
  }

  if (sourceButton && sourceButton === activeSpeechButton) {
    clearSpeakingState(sourceButton);
    activeSpeechButton = null;
    setTtsStatus("TTS 재생을 중지했습니다.");
    return;
  }

  activeSpeechButton = sourceButton || null;
  if (activeSpeechButton) markSpeaking(activeSpeechButton);

  window.speechSynthesis.cancel();
  resetLessonCoverPlaybackState();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = ttsRate;
  utterance.pitch = 1;
  utterance.voice = getEnglishVoice();
  setTtsStatus(`TTS 재생 중: "${text.slice(0, 48)}${text.length > 48 ? "..." : ""}"`);
  utterance.onend = () => {
    clearSpeakingState(activeSpeechButton);
    activeSpeechButton = null;
    activeUtterance = null;
    setTtsStatus("TTS 대기 중");
  };
  utterance.onerror = () => {
    clearSpeakingState(activeSpeechButton);
    activeSpeechButton = null;
    activeUtterance = null;
    setTtsStatus("TTS 오류가 발생했습니다.");
  };
  activeUtterance = utterance;
  window.speechSynthesis.speak(utterance);
}

function createTtsButton(label, text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tts-btn";
  button.textContent = `🔊 ${label}`;
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    speakEnglish(text, button);
  });
  return button;
}

function createSmallTtsButton(text, ariaLabel) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tts-btn-small";
  button.textContent = "🔊";
  button.setAttribute("aria-label", ariaLabel);
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    speakEnglish(text, button);
  });
  return button;
}

function toggleWordCard(cardElement) {
  if (!cardElement || cardElement.dataset.flipLock === "1") return;
  cardElement.dataset.flipLock = "1";
  const flipped = !cardElement.classList.contains("flipped");
  cardElement.classList.toggle("flipped", flipped);
  cardElement.setAttribute("aria-expanded", String(flipped));
  const key = cardElement.dataset.cardKey;
  if (key) {
    if (flipped) appState.flipped.add(key);
    else appState.flipped.delete(key);
    appState.reviewScores[key] = (appState.reviewScores[key] || 0) + (flipped ? 1 : 0);
    saveState();
    updateStats();
    updateBadges();
  }
  setTimeout(() => {
    cardElement.dataset.flipLock = "0";
  }, 320);
}

function extractVideoIdFromUrl(url) {
  if (!url) return "";
  const text = String(url).trim();
  const direct = text.match(/(?:youtu\.be\/|youtube\.com\/embed\/|v=)([a-zA-Z0-9_-]{11})/);
  return direct ? direct[1] : "";
}

function normalizeMeta(meta) {
  if (!meta || typeof meta !== "object") return {};
  const normalized = { ...meta };
  ["video_id", "video_url", "channel"].forEach((key) => {
    const val = String(normalized[key] ?? "").trim();
    if (/^none$/i.test(val)) normalized[key] = "";
  });
  const notes = String(normalized.notes || "");
  if (!normalized.video_url) {
    const match = notes.match(/video_url\s*:\s*(https?:\/\/[^\s;]+)/i);
    if (match) normalized.video_url = match[1].trim();
  }
  if (!normalized.video_id) {
    normalized.video_id = extractVideoIdFromUrl(normalized.video_url || "");
  }
  return normalized;
}

function resolveStaticLessonImage(raw) {
  const src = String(raw || "").trim();
  if (!src || /^none$/i.test(src)) return "";
  if (/^https?:\/\//i.test(src)) return src;
  if (src.startsWith("/")) return src;
  const base = window.location.href;
  try {
    if (src.startsWith("assets/")) {
      return new URL(`../../../../${src}`, base).href;
    }
    if (src.startsWith("images/")) {
      return new URL(`../../../../${src}`, base).href;
    }
    return new URL(src, base).href;
  } catch {
    return src;
  }
}

function renderVideo(meta) {
  const wrap = document.getElementById("video-frame-wrap");
  const label = document.getElementById("video-label");
  const channelNode = document.getElementById("video-channel");
  channelNode.textContent = `Channel: ${meta.channel || "-"}`;

  const thumb = resolveStaticLessonImage(meta.thumbnail_image || meta.cover_image);
  if (thumb) {
    label.textContent = meta.duration ? `Duration: ${meta.duration}` : "Lesson image";
    const alt = escapeHtml(meta.title || "My Passion Image");
    wrap.innerHTML = `<img src="${escapeHtml(thumb)}" alt="${alt}" loading="lazy">`;
    return;
  }

  const videoId = (meta.video_id || "").trim() || extractVideoIdFromUrl(meta.video_url || "");

  if (!videoId) {
    label.textContent = "video_id가 없어 YouTube 임베드를 표시할 수 없습니다.";
    wrap.innerHTML = "<div class=\"video-placeholder\">video_id가 필요합니다.</div>";
    return;
  }

  const title = meta.title || "English Lesson Video";
  const src = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?rel=0&modestbranding=1`;
  label.textContent = meta.duration ? `Duration: ${meta.duration}` : "YouTube embedded lesson";
  wrap.innerHTML = `
    <iframe
      src="${src}"
      title="${escapeHtml(title)}"
      loading="lazy"
      referrerpolicy="strict-origin-when-cross-origin"
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
      allowfullscreen
    ></iframe>
  `;
}

function normalizeCoverAudioScript(text) {
  return normalizeText(text)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join(" ");
}

let lessonCoverScriptPlain = "";
let lessonCoverClickTimer = null;
let lessonCoverListenersBound = false;
/** idle | playing | paused — 브라우저의 paused/speaking 플래그와 어긋나는 경우를 피하기 위해 사용 */
let lessonCoverPlaybackState = "idle";

function resetLessonCoverPlaybackState() {
  lessonCoverPlaybackState = "idle";
}

function updateLessonCoverVideoLabel(mode) {
  const label = document.getElementById("video-label");
  if (!label) return;
  if (mode === "playing") {
    label.textContent = "재생 중 · 한 번 더 탭하면 일시정지";
  } else if (mode === "paused") {
    label.textContent = "일시정지됨 · 탭하면 이어듣기";
  } else if (mode === "stopped") {
    label.textContent = "재생이 완전히 중지되었습니다. 탭하면 처음부터 듣기";
  } else {
    label.textContent =
      "탭해서 전체 영어 스크립트 듣기 · 탭: 일시정지/이어듣기 · 더블탭: 완전히 중지";
  }
}

function stopLessonCoverNarrationCompletely() {
  window.speechSynthesis.cancel();
  resetLessonCoverPlaybackState();
  if (activeSpeechButton) {
    clearSpeakingState(activeSpeechButton);
    activeSpeechButton = null;
  }
  activeUtterance = null;
  updateLessonCoverVideoLabel("stopped");
  window.setTimeout(() => updateLessonCoverVideoLabel("idle"), 1600);
}

function toggleLessonCoverNarration() {
  if (!lessonCoverScriptPlain) return;
  if (!("speechSynthesis" in window)) {
    window.alert("이 브라우저는 음성 합성을 지원하지 않습니다.");
    return;
  }

  if (lessonCoverPlaybackState === "playing") {
    window.speechSynthesis.pause();
    lessonCoverPlaybackState = "paused";
    updateLessonCoverVideoLabel("paused");
    return;
  }

  if (lessonCoverPlaybackState === "paused") {
    window.speechSynthesis.resume();
    lessonCoverPlaybackState = "playing";
    updateLessonCoverVideoLabel("playing");
    return;
  }

  if (activeSpeechButton) {
    clearSpeakingState(activeSpeechButton);
    activeSpeechButton = null;
  }
  activeUtterance = null;
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(lessonCoverScriptPlain);
  utterance.lang = "en-US";
  utterance.rate = ttsRate;
  utterance.pitch = 1;
  utterance.voice = getEnglishVoice();
  utterance.onend = () => {
    activeUtterance = null;
    resetLessonCoverPlaybackState();
    updateLessonCoverVideoLabel("idle");
  };
  utterance.onerror = () => {
    activeUtterance = null;
    resetLessonCoverPlaybackState();
    updateLessonCoverVideoLabel("idle");
  };
  activeUtterance = utterance;
  lessonCoverPlaybackState = "playing";
  window.speechSynthesis.speak(utterance);
  updateLessonCoverVideoLabel("playing");
}

function setupLessonImageNarration(rawText) {
  const plain = normalizeCoverAudioScript(rawText || "");
  if (!plain) return;
  lessonCoverScriptPlain = plain;
  const wrap = document.getElementById("video-frame-wrap");
  const img = wrap?.querySelector("img");
  if (!img) return;
  img.classList.add("lesson-cover-tts");
  img.setAttribute("tabindex", "0");
  img.setAttribute("role", "button");
  img.setAttribute(
    "aria-label",
    "전체 영어 스크립트 듣기. 탭으로 재생·일시정지·이어듣기. 더블탭으로 완전히 중지."
  );
  updateLessonCoverVideoLabel("idle");
  if (lessonCoverListenersBound) return;
  lessonCoverListenersBound = true;
  img.addEventListener("dblclick", (event) => {
    event.preventDefault();
    if (lessonCoverClickTimer) {
      window.clearTimeout(lessonCoverClickTimer);
      lessonCoverClickTimer = null;
    }
    stopLessonCoverNarrationCompletely();
  });
  img.addEventListener("click", () => {
    if (lessonCoverClickTimer) window.clearTimeout(lessonCoverClickTimer);
    lessonCoverClickTimer = window.setTimeout(() => {
      lessonCoverClickTimer = null;
      toggleLessonCoverNarration();
    }, 280);
  });
  img.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleLessonCoverNarration();
    }
  });
}

function setHeroMeta(meta) {
  document.title = meta.title || "English Story Study";
  document.getElementById("hero-title").textContent = meta.title || "English Story Study";
  document.getElementById("hero-level").textContent = `Level: ${meta.level || "-"}`;
  document.getElementById("hero-source").textContent = meta.source ? `Source: ${meta.source}` : "Source: -";
  document.getElementById("hero-desc").textContent = meta.description || "영어 쉐도잉 학습을 위한 자동 생성 페이지입니다.";
  const breadcrumbLevel = document.getElementById("breadcrumb-level");
  const breadcrumbTitle = document.getElementById("breadcrumb-title");
  if (breadcrumbLevel) breadcrumbLevel.textContent = meta.level || "Level 3";
  if (breadcrumbTitle) breadcrumbTitle.textContent = meta.title || "Learning Content";

  const extra = Object.entries(meta).filter(([key]) => !META_KEYS.has(key));
  const target = document.getElementById("hero-meta");
  target.innerHTML = "";
  extra.forEach(([key, value]) => {
    const chip = document.createElement("span");
    chip.className = "meta-chip";
    chip.textContent = `${key}: ${value}`;
    target.appendChild(chip);
  });
}

function renderIntro(meta, intro) {
  const box = document.getElementById("intro-content");
  box.innerHTML = "";

  const introEn = intro.en || intro.EN || meta.description || "Intro English content is missing.";
  const introKr = intro.kr || intro.KR || "소개 한국어 내용이 없습니다.";

  const article = document.createElement("article");
  article.className = "content-item";
  article.innerHTML = `
    <p class="content-en">${escapeHtml(introEn)}</p>
    <p class="content-kr">${escapeHtml(introKr)}</p>
  `;
  article.appendChild(createTtsButton("EN 듣기", introEn));
  box.appendChild(article);
}

function renderEnKrList(targetId, items, emptyMessage) {
  const root = document.getElementById(targetId);
  root.innerHTML = "";

  if (!items.length) {
    root.innerHTML = `<article class="content-item"><p class="content-kr">${escapeHtml(emptyMessage)}</p></article>`;
    return;
  }

  const fragment = document.createDocumentFragment();
  items.forEach((item, index) => {
    const en = item.en || "English content missing.";
    const kr = item.kr || "한국어 번역이 없습니다.";
    const title = item.label || `Item ${index + 1}`;
    const article = document.createElement("article");
    article.className = "content-item";
    article.innerHTML = `
      <h3 class="content-title">${escapeHtml(title)}</h3>
      <p class="content-en">${escapeHtml(en)}</p>
      <p class="content-kr">${escapeHtml(kr)}</p>
    `;
    article.appendChild(createTtsButton("EN 듣기", en));
    fragment.appendChild(article);
  });
  root.appendChild(fragment);
}

function renderFullScript(items) {
  const root = document.getElementById("script-content");
  root.innerHTML = "";

  if (!items.length) {
    root.innerHTML = "<article class=\"content-item\"><p class=\"content-kr\">Full Script 데이터가 없습니다.</p></article>";
    return;
  }

  const fragment = document.createDocumentFragment();
  items.forEach((item, index) => {
    const en = item.en || "English paragraph missing.";
    const kr = item.kr || "한국어 문단이 없습니다.";
    const article = document.createElement("article");
    article.className = "content-item content-full";
    article.innerHTML = `
      <h3 class="content-title">Paragraph ${index + 1}</h3>
      <p class="content-en">${escapeHtml(en)}</p>
      <p class="content-kr">${escapeHtml(kr)}</p>
    `;
    article.appendChild(createTtsButton("문단 EN 듣기", en));
    fragment.appendChild(article);
  });
  root.appendChild(fragment);
}

function parseWordCardsLooseNumbered(text) {
  const blocks = text.trim().split(/\n(?=\d+\.\s+)/);
  const cards = [];
  blocks.forEach((rawBlock) => {
    const block = rawBlock.trim();
    if (!block) return;
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    const headMatch = lines[0]?.match(/^\d+\.\s*(.+)$/);
    if (!headMatch) return;
    const card = {
      label: `[Card ${cards.length + 1}]`,
      headword: headMatch[1].trim(),
      part_of_speech: "",
      meaning_kr: "",
      definition_en: "",
      definition_kr_literal: "",
      example_en: "",
      example_kr_literal: "-"
    };
    let lastProp = "";
    const applyKey = (key, val) => {
      if (key === "pos") {
        card.part_of_speech = val;
        lastProp = "part_of_speech";
      } else if (key === "meaning") {
        card.meaning_kr = val;
        lastProp = "meaning_kr";
      } else if (key === "en") {
        card.definition_en = val;
        lastProp = "definition_en";
      } else if (key === "kr") {
        card.definition_kr_literal = val;
        lastProp = "definition_kr_literal";
      } else if (key === "sentence") {
        card.example_en = val;
        lastProp = "example_en";
      }
    };
    for (let i = 1; i < lines.length; i += 1) {
      const line = lines[i];
      const idx = line.indexOf(":");
      if (idx > 0) {
        applyKey(line.slice(0, idx).trim().toLowerCase(), line.slice(idx + 1).trim());
      } else if (lastProp && card[lastProp] !== undefined) {
        card[lastProp] = `${card[lastProp]} ${line}`.trim();
      }
    }
    cards.push(card);
  });
  return cards;
}

function parseWordCardsBracketKV(text) {
  const lines = text.split("\n");
  const cards = [];
  let current = null;
  let currentKey = "";

  lines.forEach((raw) => {
    const line = raw.trim();
    if (!line) return;
    if (/^\[.+\]$/.test(line)) {
      if (current) cards.push(current);
      current = { label: line.slice(1, -1) };
      currentKey = "";
      return;
    }
    if (!current) return;

    const idx = line.indexOf(":");
    if (idx > 0) {
      currentKey = line.slice(0, idx).trim().toLowerCase();
      current[currentKey] = line.slice(idx + 1).trim();
      return;
    }

    if (currentKey) {
      current[currentKey] = `${current[currentKey]}\n${line}`.trim();
    }
  });

  if (current) cards.push(current);
  return cards;
}

function parseWordCardsByKV(text) {
  const normalized = normalizeText(text);
  if (!/\[Card/i.test(normalized) && /^\d+\.\s+\S/m.test(normalized.trim())) {
    const loose = parseWordCardsLooseNumbered(normalized);
    if (loose.length) return loose;
  }
  return parseWordCardsBracketKV(normalized);
}

function renderWordCards(cards) {
  const root = document.getElementById("wordcard-content");
  root.innerHTML = "";
  currentWordCards = [...cards];

  if (!cards.length) {
    root.innerHTML = "<article class=\"word-card\"><p class=\"content-kr\">Word Card 데이터가 없습니다.</p></article>";
    return;
  }

  const fragment = document.createDocumentFragment();
  cards.forEach((card) => {
    const headword = card.headword || "Unknown";
    const cardKey = headword.toLowerCase();
    const pos = card.part_of_speech || "-";
    const meaningKr = card.meaning_kr || "-";
    const definitionEn = card.definition_en || "-";
    const definitionKr = card.definition_kr_literal || "-";
    const exampleEn = card.example_en || "-";
    const exampleKr = card.example_kr_literal || "-";

    const article = document.createElement("article");
    article.className = "word-card";
    article.setAttribute("tabindex", "0");
    article.setAttribute("role", "button");
    article.setAttribute("aria-label", `${headword} 플래시카드 뒤집기`);
    article.setAttribute("aria-expanded", "false");
    article.dataset.flipLock = "0";
    article.dataset.cardKey = cardKey;
    const difficulty = appState.difficulties[cardKey] || classifyDifficulty(card);
    appState.difficulties[cardKey] = difficulty;
    article.dataset.difficulty = difficulty;
    if (appState.flipped.has(cardKey)) {
      article.classList.add("flipped");
      article.setAttribute("aria-expanded", "true");
    }
    if (appState.favorites.has(cardKey)) {
      article.classList.add("bookmarked");
    }

    article.innerHTML = `
      <div class="word-card-inner">
        <div class="card-face card-front flex h-full flex-col">
          <div class="mb-4 flex items-start justify-between gap-2">
            <h3 class="text-2xl font-bold text-gray-900">${escapeHtml(headword)}</h3>
            <div class="flex items-center gap-1">
              <button type="button" class="bookmark-btn ${appState.favorites.has(cardKey) ? "active" : ""}" data-bookmark-btn="1" aria-label="즐겨찾기 토글">★</button>
              <div class="front-tts-anchor"></div>
            </div>
          </div>
          <p class="mb-2 text-xs font-semibold uppercase text-indigo-600">난이도: ${difficulty}</p>
          <p class="mt-auto text-center text-sm text-gray-500">클릭 또는 Enter/Space로 뒤집기</p>
        </div>

        <div class="card-face card-back flex h-full flex-col">
          <div class="mb-3 flex items-center justify-between border-b border-indigo-200 pb-2">
            <span class="rounded bg-indigo-100 px-2 py-1 text-xs font-bold uppercase text-indigo-700">${escapeHtml(pos)}</span>
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-gray-700">의미: ${escapeHtml(meaningKr)}</span>
              <span class="flip-back-hint" aria-hidden="true">↺</span>
            </div>
          </div>

          <div class="mb-2 flex items-start gap-2">
            <p class="flex-1 text-sm font-medium leading-relaxed text-gray-800">${escapeHtml(definitionEn)}</p>
            <div class="def-tts-anchor"></div>
          </div>

          <p class="mb-3 text-xs leading-relaxed text-gray-600">직역: ${escapeHtml(definitionKr)}</p>

          <div class="mb-2 flex items-start gap-2">
            <p class="flex-1 text-sm italic leading-relaxed text-gray-800">${escapeHtml(exampleEn)}</p>
            <div class="example-tts-anchor"></div>
          </div>

          <p class="text-xs leading-relaxed text-gray-600">예문 직역: ${escapeHtml(exampleKr)}</p>
        </div>
      </div>
    `;

    article.querySelector(".front-tts-anchor").appendChild(createSmallTtsButton(headword, `${headword} 발음 듣기`));
    article.querySelector(".def-tts-anchor").appendChild(createSmallTtsButton(definitionEn, `${headword} 영어 정의 듣기`));
    article.querySelector(".example-tts-anchor").appendChild(createSmallTtsButton(exampleEn, `${headword} 예문 듣기`));
    fragment.appendChild(article);
  });
  root.appendChild(fragment);
  updateStats();
  updateBadges();
  applyCardFilters();
  saveState();
}

function activateTab(tabName) {
  const buttons = Array.from(document.querySelectorAll(".tab-btn"));
  const panels = Array.from(document.querySelectorAll(".tab-panel"));
  buttons.forEach((button) => {
    const isActive = button.dataset.tab === tabName;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  panels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

function setupTabs() {
  const buttons = Array.from(document.querySelectorAll(".tab-btn"));
  buttons.forEach((button, index) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const next = event.key === "ArrowRight"
        ? (index + 1) % buttons.length
        : (index - 1 + buttons.length) % buttons.length;
      buttons[next].focus();
      activateTab(buttons[next].dataset.tab);
    });
  });
}

function setupMobileMenu() {
  const mobileBtn = document.getElementById("mobile-menu-btn");
  const mobileMenu = document.getElementById("mobile-menu");
  if (!mobileBtn || !mobileMenu) return;

  mobileBtn.addEventListener("click", () => {
    mobileMenu.classList.toggle("hidden");
  });
}

function setupWordCardInteractions() {
  const root = document.getElementById("wordcard-content");
  if (!root) return;

  root.addEventListener("click", (event) => {
    const bookmarkBtn = event.target.closest("[data-bookmark-btn='1']");
    if (bookmarkBtn) {
      event.stopPropagation();
      const card = event.target.closest(".word-card");
      if (!card) return;
      const key = card.dataset.cardKey;
      if (!key) return;
      if (appState.favorites.has(key)) appState.favorites.delete(key);
      else appState.favorites.add(key);
      card.classList.toggle("bookmarked", appState.favorites.has(key));
      bookmarkBtn.classList.toggle("active", appState.favorites.has(key));
      saveState();
      updateStats();
      updateBadges();
      applyCardFilters();
      return;
    }
    const ttsButton = event.target.closest(".tts-btn-small, .tts-btn");
    if (ttsButton) return;
    const card = event.target.closest(".word-card");
    if (card) toggleWordCard(card);
  });

  root.addEventListener("keydown", (event) => {
    const card = event.target.closest(".word-card");
    if (!card) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      toggleWordCard(card);
    }
    if (event.key === "Escape") {
      card.classList.remove("flipped");
      card.setAttribute("aria-expanded", "false");
    }
  });
}

function applyCardFilters() {
  const q = (document.getElementById("card-search-input")?.value || "").toLowerCase().trim();
  const difficulty = document.getElementById("difficulty-filter")?.value || "all";
  const bookmark = document.getElementById("bookmark-filter")?.value || "all";
  const root = document.getElementById("wordcard-content");
  if (!root) return;
  const cards = Array.from(root.querySelectorAll(".word-card"));
  cards.forEach((card) => {
    const key = card.dataset.cardKey || "";
    const text = card.textContent.toLowerCase();
    const textPass = !q || text.includes(q);
    const diffPass = difficulty === "all" || card.dataset.difficulty === difficulty;
    const markPass = bookmark === "all" || (bookmark === "bookmarked" && appState.favorites.has(key));
    card.style.display = textPass && diffPass && markPass ? "" : "none";
  });
}

function setupWordCardControls() {
  const flipAllBtn = document.getElementById("flip-all-btn");
  const resetBtn = document.getElementById("reset-cards-btn");
  const shuffleBtn = document.getElementById("shuffle-cards-btn");
  const rateSelect = document.getElementById("tts-rate-select");
  const stopBtn = document.getElementById("tts-stop-btn");
  const smartReviewBtn = document.getElementById("smart-review-btn");
  const shareBtn = document.getElementById("share-progress-btn");
  const searchInput = document.getElementById("card-search-input");
  const difficultyFilter = document.getElementById("difficulty-filter");
  const bookmarkFilter = document.getElementById("bookmark-filter");
  const clearFiltersBtn = document.getElementById("clear-filters-btn");
  const root = document.getElementById("wordcard-content");
  if (!root) return;

  flipAllBtn?.addEventListener("click", () => {
    const cards = root.querySelectorAll(".word-card");
    cards.forEach((card) => {
      card.classList.add("flipped");
      card.setAttribute("aria-expanded", "true");
      if (card.dataset.cardKey) appState.flipped.add(card.dataset.cardKey);
    });
    saveState();
    updateStats();
    updateBadges();
  });

  resetBtn?.addEventListener("click", () => {
    const cards = root.querySelectorAll(".word-card");
    cards.forEach((card) => {
      card.classList.remove("flipped");
      card.setAttribute("aria-expanded", "false");
      if (card.dataset.cardKey) appState.flipped.delete(card.dataset.cardKey);
    });
    saveState();
    updateStats();
  });

  shuffleBtn?.addEventListener("click", () => {
    if (!currentWordCards.length) return;
    for (let i = currentWordCards.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [currentWordCards[i], currentWordCards[j]] = [currentWordCards[j], currentWordCards[i]];
    }
    renderWordCards(currentWordCards);
  });

  smartReviewBtn?.addEventListener("click", () => {
    const sorted = [...currentWordCards].sort((a, b) => {
      const ak = (a.headword || "").toLowerCase();
      const bk = (b.headword || "").toLowerCase();
      const aFav = appState.favorites.has(ak) ? 1 : 0;
      const bFav = appState.favorites.has(bk) ? 1 : 0;
      const aSeen = appState.reviewScores[ak] || 0;
      const bSeen = appState.reviewScores[bk] || 0;
      const aDiff = appState.difficulties[ak] === "hard" ? 2 : appState.difficulties[ak] === "medium" ? 1 : 0;
      const bDiff = appState.difficulties[bk] === "hard" ? 2 : appState.difficulties[bk] === "medium" ? 1 : 0;
      return (bDiff + bFav * 2 - bSeen * 0.1) - (aDiff + aFav * 2 - aSeen * 0.1);
    });
    currentWordCards = sorted;
    renderWordCards(sorted);
    setTtsStatus("스마트 복습 순서로 카드를 재배열했습니다.");
  });

  rateSelect?.addEventListener("change", () => {
    ttsRate = Number(rateSelect.value) || 0.95;
    setTtsStatus(`TTS 속도 변경: ${ttsRate}x`);
  });

  stopBtn?.addEventListener("click", () => {
    window.speechSynthesis.cancel();
    clearSpeakingState(activeSpeechButton);
    activeSpeechButton = null;
    activeUtterance = null;
    setTtsStatus("TTS 재생을 정지했습니다.");
  });

  shareBtn?.addEventListener("click", async () => {
    const text = `English Study 진행률: 카드 ${appState.flipped.size}/${currentWordCards.length}, 즐겨찾기 ${appState.favorites.size}, 배지 ${appState.badges.size}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "English Study Progress", text, url: location.href });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(`${text} ${location.href}`);
        setTtsStatus("진도 링크를 클립보드에 복사했습니다.");
      }
    } catch (error) {
      console.warn("share cancelled or failed", error);
    }
  });

  [searchInput, difficultyFilter, bookmarkFilter].forEach((node) => {
    node?.addEventListener("input", applyCardFilters);
    node?.addEventListener("change", applyCardFilters);
  });
  clearFiltersBtn?.addEventListener("click", () => {
    if (searchInput) searchInput.value = "";
    if (difficultyFilter) difficultyFilter.value = "all";
    if (bookmarkFilter) bookmarkFilter.value = "all";
    applyCardFilters();
  });
}

function setupThemeToggle() {
  const buttons = [
    document.getElementById("theme-toggle-btn"),
    document.getElementById("theme-toggle-btn-mobile")
  ].filter(Boolean);
  const apply = () => {
    document.body.classList.toggle("dark-mode", appState.theme === "dark");
    buttons.forEach((btn) => {
      btn.textContent = appState.theme === "dark" ? "☀️ 라이트모드" : "🌙 다크모드";
    });
  };
  apply();
  buttons.forEach((btn) => btn.addEventListener("click", () => {
    appState.theme = appState.theme === "dark" ? "light" : "dark";
    saveState();
    apply();
  }));
}

function setupSessionTimer() {
  const node = document.getElementById("session-timer");
  if (!node) return;
  setInterval(() => {
    const elapsed = Math.floor((Date.now() - appState.startAt) / 1000);
    const total = appState.totalStudySeconds + elapsed;
    const mm = String(Math.floor(total / 60)).padStart(2, "0");
    const ss = String(total % 60).padStart(2, "0");
    node.textContent = `${mm}:${ss}`;
    updateBadges();
  }, 1000);
}

function setupOfflineSupport() {
  updateOnlineStatus();
  window.addEventListener("online", updateOnlineStatus);
  window.addEventListener("offline", updateOnlineStatus);
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(SERVICE_WORKER_PATH).catch((error) => {
      console.warn("service worker registration failed", error);
    });
  }
}

function showError(message) {
  console.error("[StudyPageError]", message);
  const main = document.querySelector("main");
  main.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
}

function decodeContent(buffer) {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch (utfError) {
    console.warn("UTF-8 decode failed, trying EUC-KR fallback.", utfError);
    try {
      return new TextDecoder("euc-kr").decode(buffer);
    } catch (eucError) {
      console.warn("EUC-KR decode also failed.", eucError);
      return new TextDecoder().decode(buffer);
    }
  }
}

async function loadText(name) {
  const path = `${BASE_DIR}/${name}`;
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${name} 파일을 찾을 수 없습니다. (status: ${response.status})`);
  }
  const buffer = await response.arrayBuffer();
  return decodeContent(buffer);
}

function normalizeCoreLabel(items, prefix) {
  return items.filter((item) => new RegExp(`^${prefix}`, "i").test(item.label || ""));
}

async function init() {
  loadState();
  setupTabs();
  setupMobileMenu();
  setupThemeToggle();
  setupSessionTimer();
  setupOfflineSupport();
  setupWordCardInteractions();
  setupWordCardControls();
  setTtsStatus("TTS 대기 중");
  window.speechSynthesis?.addEventListener?.("voiceschanged", () => {
    selectedVoice = null;
    getEnglishVoice();
  });
  window.addEventListener("beforeunload", () => {
    appState.totalStudySeconds += Math.floor((Date.now() - appState.startAt) / 1000);
    saveState();
    window.speechSynthesis.cancel();
    resetLessonCoverPlaybackState();
  });

  try {
    const [metaTxt, introTxt, coreTxt, summaryTxt, scriptTxt, cardTxt] = await Promise.all([
      loadText("00_meta.txt"),
      loadText("01_intro.txt"),
      loadText("02_core.txt"),
      loadText("03_summary.txt"),
      loadText("04_full_script.txt"),
      loadText("05_wordcard.txt")
    ]);

    const meta = normalizeMeta(parseKeyValueText(metaTxt));
    const intro = parseKeyValueText(introTxt);
    const coreAll = parseTaggedBlocks(coreTxt);
    const summaryAll = parseTaggedBlocks(summaryTxt);
    const scriptAll = parseTaggedBlocks(scriptTxt);
    const words = parseWordCardsByKV(cardTxt);

    const core = normalizeCoreLabel(coreAll, "sentence");
    const summary = normalizeCoreLabel(summaryAll, "part");
    const script = normalizeCoreLabel(scriptAll, "paragraph");

    renderVideo(meta);
    setHeroMeta(meta);
    renderIntro(meta, intro);
    renderEnKrList("core-content", core, "Core Sentences 데이터가 없습니다.");
    renderEnKrList("summary-content", summary, "Summary 데이터가 없습니다.");
    renderFullScript(script);
    setupHangman(core);
    renderWordCards(words);

    if (bodyDataset.audioScript) {
      try {
        const coverTxt = await loadText(bodyDataset.audioScript);
        setupLessonImageNarration(coverTxt);
      } catch (coverErr) {
        console.warn("data-audio-script 로드 실패:", coverErr);
      }
    }
  } catch (error) {
    showError(`데이터를 불러오지 못했습니다. 데이터 경로를 확인해 주세요. (${error.message})`);
  }
}

init();

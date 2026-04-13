const BASE_DIR = "data";
const META_KEYS = new Set(["title", "level", "description", "source"]);

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

function parseWordCards(text) {
  const blocks = parseTaggedBlocks(text);
  return blocks.map((block) => {
    const card = { label: block.label };
    const body = [block.en ? `en: ${block.en}` : "", block.kr ? `kr: ${block.kr}` : ""]
      .filter(Boolean)
      .join("\n");
    const kv = parseKeyValueText(body);
    Object.assign(card, kv);
    return card;
  }).filter((card) => card.label.toLowerCase().startsWith("card"));
}

function speakEnglish(text) {
  if (!text) return;
  if (!("speechSynthesis" in window)) {
    alert("이 브라우저는 음성 합성을 지원하지 않습니다.");
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.95;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
}

function createTtsButton(label, text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tts-btn";
  button.textContent = `🔊 ${label}`;
  button.addEventListener("click", () => speakEnglish(text));
  return button;
}

function createSmallTtsButton(text, ariaLabel) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tts-btn-small";
  button.textContent = "🔊";
  button.setAttribute("aria-label", ariaLabel);
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    speakEnglish(text);
  });
  return button;
}

function toggleWordCard(cardElement) {
  if (!cardElement || cardElement.dataset.flipLock === "1") return;
  cardElement.dataset.flipLock = "1";
  cardElement.classList.toggle("flipped");
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

function renderVideo(meta) {
  const wrap = document.getElementById("video-frame-wrap");
  const label = document.getElementById("video-label");
  const channelNode = document.getElementById("video-channel");
  const videoId = (meta.video_id || "").trim() || extractVideoIdFromUrl(meta.video_url || "");
  channelNode.textContent = `Channel: ${meta.channel || "-"}`;

  if (!videoId) {
    label.textContent = "video_id가 없어 YouTube 임베드를 표시할 수 없습니다.";
    wrap.innerHTML = `<div class="video-placeholder">video_id가 필요합니다.</div>`;
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

function setHeroMeta(meta) {
  document.title = meta.title || "English Story Study";
  document.getElementById("hero-title").textContent = meta.title || "English Story Study";
  document.getElementById("hero-level").textContent = `Level: ${meta.level || "-"}`;
  document.getElementById("hero-source").textContent = meta.source ? `Source: ${meta.source}` : "Source: -";
  document.getElementById("hero-desc").textContent = meta.description || "영어 쉐도잉 학습을 위한 자동 생성 페이지입니다.";

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
    root.appendChild(article);
  });
}

function renderFullScript(items) {
  const root = document.getElementById("script-content");
  root.innerHTML = "";

  if (!items.length) {
    root.innerHTML = `<article class="content-item"><p class="content-kr">Full Script 데이터가 없습니다.</p></article>`;
    return;
  }

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
    root.appendChild(article);
  });
}

function parseWordCardsByKV(text) {
  const lines = normalizeText(text).split("\n");
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

function renderWordCards(cards) {
  const root = document.getElementById("wordcard-content");
  root.innerHTML = "";

  if (!cards.length) {
    root.innerHTML = `<article class="word-card"><p class="content-kr">Word Card 데이터가 없습니다.</p></article>`;
    return;
  }

  cards.forEach((card) => {
    const headword = card.headword || "Unknown";
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
    article.dataset.flipLock = "0";

    article.innerHTML = `
      <div class="word-card-inner">
        <div class="card-face card-front flex h-full flex-col">
          <div class="mb-4 flex items-start justify-between gap-2">
            <h3 class="text-2xl font-bold text-gray-900">${escapeHtml(headword)}</h3>
            <div class="front-tts-anchor"></div>
          </div>
          <p class="mt-auto text-center text-sm text-gray-500">클릭 또는 Enter/Space로 뒤집기</p>
        </div>

        <div class="card-face card-back flex h-full flex-col">
          <div class="mb-3 flex items-center justify-between border-b border-indigo-200 pb-2">
            <span class="rounded bg-indigo-100 px-2 py-1 text-xs font-bold uppercase text-indigo-700">${escapeHtml(pos)}</span>
            <span class="text-sm font-semibold text-gray-700">의미: ${escapeHtml(meaningKr)}</span>
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

    article.addEventListener("click", () => toggleWordCard(article));
    article.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleWordCard(article);
      }
    });

    article.querySelector(".front-tts-anchor").appendChild(createSmallTtsButton(headword, `${headword} 발음 듣기`));
    article.querySelector(".def-tts-anchor").appendChild(createSmallTtsButton(definitionEn, `${headword} 영어 정의 듣기`));
    article.querySelector(".example-tts-anchor").appendChild(createSmallTtsButton(exampleEn, `${headword} 예문 듣기`));
    root.appendChild(article);
  });
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

async function init() {
  setupTabs();

  try {
    const [metaTxt, introTxt, coreTxt, summaryTxt, scriptTxt, cardTxt] = await Promise.all([
      loadText("00_meta.txt"),
      loadText("01_intro.txt"),
      loadText("02_core.txt"),
      loadText("03_summary.txt"),
      loadText("04_full_script.txt"),
      loadText("05_wordcard.txt")
    ]);

    const meta = parseKeyValueText(metaTxt);
    const intro = parseKeyValueText(introTxt);
    const coreAll = parseTaggedBlocks(coreTxt);
    const summaryAll = parseTaggedBlocks(summaryTxt);
    const scriptAll = parseTaggedBlocks(scriptTxt);
    const words = parseWordCardsByKV(cardTxt);

    const core = coreAll.filter((item) => /^sentence/i.test(item.label));
    const summary = summaryAll.filter((item) => /^part/i.test(item.label));
    const script = scriptAll.filter((item) => /^paragraph/i.test(item.label));

    renderVideo(meta);
    setHeroMeta(meta);
    renderIntro(meta, intro);
    renderEnKrList("core-content", core, "Core Sentences 데이터가 없습니다.");
    renderEnKrList("summary-content", summary, "Summary 데이터가 없습니다.");
    renderFullScript(script);
    renderWordCards(words);

    console.log("[StudyPage] Loaded", {
      core: core.length,
      summary: summary.length,
      script: script.length,
      words: words.length
    });
  } catch (error) {
    showError(`데이터를 불러오지 못했습니다. Live Server 또는 로컬 서버에서 실행해 주세요. (${error.message})`);
  }
}

init();

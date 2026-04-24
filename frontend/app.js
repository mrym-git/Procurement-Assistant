const API = "http://localhost:8000";

// ── Chart.js global defaults (dark theme) ────────────────────────────────────
if (window.Chart) {
  Chart.defaults.color       = "#94a3b8";
  Chart.defaults.borderColor = "rgba(255,255,255,0.05)";
  Chart.defaults.font.family = "'Inter', -apple-system, sans-serif";
  Chart.defaults.font.size   = 12;
}

// ── Session ────────────────────────────────────────────────────────────────
let sessionId = localStorage.getItem("procurement_session") || null;

// ── DOM refs ───────────────────────────────────────────────────────────────
const messagesEl = document.getElementById("messages");
const inputEl    = document.getElementById("userInput");
const sendBtn    = document.getElementById("sendBtn");

// ── Health check ───────────────────────────────────────────────────────────
async function checkHealth() {
  const dot  = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  try {
    const res  = await fetch(`${API}/api/health`);
    const data = await res.json();
    const ok   = data.status === "ok" && data.mongodb === "connected";
    dot.className    = "status-dot " + (ok ? "online" : "offline");
    text.textContent = ok ? "Connected" : "MongoDB unreachable";
  } catch {
    dot.className    = "status-dot offline";
    text.textContent = "Server offline";
  }
}
checkHealth();
setInterval(checkHealth, 30_000);

// ── Text formatting ────────────────────────────────────────────────────────
function formatText(raw) {
  const paragraphs = raw.split(/\n{2,}/);
  return paragraphs.map(para => {
    const lines  = para.trim().split("\n").filter(Boolean);
    const isList = lines.length > 1 && lines.every(
      l => /^[-*•]\s/.test(l.trim()) || /^\d+\.\s/.test(l.trim())
    );
    if (isList) {
      const tag   = /^\d+\./.test(lines[0].trim()) ? "ol" : "ul";
      const items = lines.map(
        l => `<li>${formatInline(l.replace(/^[-*•\d.]+\s+/, ""))}</li>`
      ).join("");
      return `<${tag}>${items}</${tag}>`;
    }
    return `<p>${lines.map(formatInline).join("<br>")}</p>`;
  }).join("");
}

function formatInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g,     "<em>$1</em>")
    .replace(/`(.+?)`/g,       "<code>$1</code>")
    .replace(/(\$[\d,]+(?:\.\d+)?)/g, "<strong>$1</strong>");
}

// ── Add message bubble ─────────────────────────────────────────────────────
function addMessage(html, role) {
  const isUser  = role === "user";
  const wrapper = document.createElement("div");
  wrapper.className = `message ${isUser ? "user" : "assistant"}-message`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${isUser ? "user" : "assistant"}-avatar`;
  avatar.innerHTML = isUser
    ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
         <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>`
    : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
         <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = html;

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
  return { wrapper, bubble };
}

// ── Typing indicator ───────────────────────────────────────────────────────
function showTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant-message";
  wrapper.id = "typingIndicator";
  const avatar = document.createElement("div");
  avatar.className = "avatar assistant-avatar";
  avatar.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`;
  const bubble = document.createElement("div");
  bubble.className = "bubble typing-bubble";
  bubble.innerHTML = `<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>`;
  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
}
function hideTyping() {
  const el = document.getElementById("typingIndicator");
  if (el) el.remove();
}

// ── Chart rendering ────────────────────────────────────────────────────────
function renderChart(bubble, chartConfig) {
  if (!chartConfig || !window.Chart) return;

  const isCurrency = chartConfig.format === "currency";

  function fmt(v) {
    if (isCurrency) {
      if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
      if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
      if (v >= 1e3) return "$" + (v / 1e3).toFixed(1) + "K";
      return "$" + Number(v).toLocaleString();
    }
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
    return Number(v).toLocaleString();
  }

  const isHorizontal = chartConfig.options.indexAxis === "y";
  const valueAxis    = isHorizontal ? "x" : "y";

  if (chartConfig.options.scales?.[valueAxis]?.ticks) {
    chartConfig.options.scales[valueAxis].ticks.callback = fmt;
  }
  if (!chartConfig.options.plugins.tooltip) chartConfig.options.plugins.tooltip = {};
  chartConfig.options.plugins.tooltip.callbacks = {
    label: ctx => fmt(ctx.parsed[isHorizontal ? "x" : "y"] ?? ctx.parsed.y),
  };

  for (const axis of Object.values(chartConfig.options.scales || {})) {
    if (axis.ticks && !axis.ticks.color) axis.ticks.color = "#94a3b8";
    if (axis.grid  && !axis.grid.color)  axis.grid.color  = "rgba(255,255,255,0.05)";
  }

  delete chartConfig.format;

  const container = document.createElement("div");
  container.className = "chart-container";
  const canvas = document.createElement("canvas");
  container.appendChild(canvas);
  bubble.appendChild(container);
  new Chart(canvas, chartConfig);
  scrollToBottom();
}

// ── Anomaly banner ─────────────────────────────────────────────────────────
function renderAnomalies(bubble, anomalies) {
  if (!anomalies || anomalies.length === 0) return;
  const banner = document.createElement("div");
  banner.className = "anomaly-banner";
  const items = anomalies.slice(0, 3).map(a => {
    const v = a.value >= 1e9
      ? `$${(a.value / 1e9).toFixed(2)}B`
      : a.value >= 1e6
        ? `$${(a.value / 1e6).toFixed(1)}M`
        : `$${Number(a.value).toLocaleString()}`;
    return `<strong>${a.label}</strong> (${v})`;
  });
  const plural = anomalies.length > 1 ? `${anomalies.length} outliers` : "1 outlier";
  banner.innerHTML =
    `<span class="anomaly-icon">⚠</span>` +
    `<span>${plural} detected: ${items.join(", ")} significantly exceed the group.</span>`;
  bubble.appendChild(banner);
}

// ── Confidence + cache meta row ────────────────────────────────────────────
function renderMeta(bubble, confidence, isCached) {
  if (!confidence && !isCached) return;
  const meta = document.createElement("div");
  meta.className = "message-meta";
  if (confidence && confidence !== "N/A") {
    const pill = document.createElement("span");
    pill.className = `confidence-pill ${confidence.toLowerCase()}`;
    pill.textContent = `${confidence} confidence`;
    meta.appendChild(pill);
  }
  if (isCached) {
    const badge = document.createElement("span");
    badge.className = "cache-badge";
    badge.innerHTML = "&#9889; Cached";
    meta.appendChild(badge);
  }
  if (meta.children.length > 0) bubble.appendChild(meta);
}

// ── Follow-up suggestion chips ─────────────────────────────────────────────
function renderSuggestions(bubble, suggestions) {
  if (!suggestions || suggestions.length === 0) return;
  const section = document.createElement("div");
  section.className = "followup-chips";
  const label = document.createElement("p");
  label.className = "followup-label";
  label.textContent = "Follow-up questions:";
  section.appendChild(label);
  const chips = document.createElement("div");
  chips.className = "chips-row";
  suggestions.forEach(q => {
    const btn = document.createElement("button");
    btn.className = "chip";
    btn.textContent = q;
    btn.onclick = () => askSample(q);
    chips.appendChild(btn);
  });
  section.appendChild(chips);
  bubble.appendChild(section);
  scrollToBottom();
}

// ── CSV export ─────────────────────────────────────────────────────────────
function renderCsvButton(bubble, results) {
  if (!results || results.length === 0) return;
  const btn = document.createElement("button");
  btn.className = "csv-btn";
  btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="2.5">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg> Export CSV`;
  btn.onclick = () => downloadCSV(results);
  bubble.appendChild(btn);
}

function downloadCSV(results) {
  if (!results || !results.length) return;
  const flat = results.map(row => {
    const out = {};
    for (const [k, v] of Object.entries(row)) {
      if (k === "_id" && typeof v === "object" && v !== null) {
        for (const [ik, iv] of Object.entries(v)) out[ik] = iv;
      } else {
        out[k] = v;
      }
    }
    return out;
  });
  const headers = Object.keys(flat[0]);
  const csv = [
    headers.join(","),
    ...flat.map(row =>
      headers.map(h => {
        const v = row[h] ?? "";
        return typeof v === "string" && v.includes(",") ? `"${v}"` : v;
      }).join(",")
    ),
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "procurement_export.csv"; a.click();
  URL.revokeObjectURL(url);
}

// ── Send message ───────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || sendBtn.disabled) return;

  inputEl.value = "";
  autoResize(inputEl);
  addMessage(formatInline(text), "user");
  setLoading(true);
  showTyping();

  let bubble = null;
  let rawText = "";
  let isCached = false;

  try {
    const res = await fetch(`${API}/api/stream`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ session_id: sessionId, message: text }),
    });

    if (!res.ok) throw new Error(`Server error ${res.status}`);

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE lines are separated by double newlines
      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep incomplete chunk

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        let event;
        try { event = JSON.parse(line.slice(5).trim()); }
        catch { continue; }

        if (event.type === "session") {
          sessionId = event.session_id;
          localStorage.setItem("procurement_session", sessionId);

        } else if (event.type === "cache_hit") {
          isCached = true;

        } else if (event.type === "token") {
          if (!bubble) {
            hideTyping();
            ({ bubble } = addMessage("", "assistant"));
          }
          rawText += event.content;
          bubble.innerHTML = formatText(rawText);
          scrollToBottom();

        } else if (event.type === "chart") {
          if (bubble) renderChart(bubble, event.data);

        } else if (event.type === "anomalies") {
          if (bubble && event.data?.length) renderAnomalies(bubble, event.data);

        } else if (event.type === "results") {
          if (bubble && event.data?.length) renderCsvButton(bubble, event.data);

        } else if (event.type === "meta") {
          if (bubble) renderMeta(bubble, event.confidence, isCached);

        } else if (event.type === "suggestions") {
          if (bubble && event.data?.length) renderSuggestions(bubble, event.data);

        } else if (event.type === "error") {
          hideTyping();
          addMessage(`<p>Sorry, something went wrong: <strong>${event.content}</strong></p>`, "assistant");

        } else if (event.type === "done") {
          if (!bubble) { hideTyping(); addMessage("<p>No response.</p>", "assistant"); }
        }
      }
    }

  } catch (err) {
    hideTyping();
    addMessage(
      `<p>Sorry, something went wrong: <strong>${err.message}</strong>. Please check that the server is running.</p>`,
      "assistant"
    );
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function setLoading(state) {
  sendBtn.disabled = state;
  inputEl.disabled = state;
}

function scrollToBottom() {
  messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: "smooth" });
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 140) + "px";
}

function handleKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function askSample(question) {
  inputEl.value = question;
  autoResize(inputEl);
  inputEl.focus();
  sendMessage();
}

function newChat() {
  sessionId = null;
  localStorage.removeItem("procurement_session");
  const msgs = messagesEl.querySelectorAll(".message:not(#welcomeMsg)");
  msgs.forEach(m => m.remove());
  inputEl.focus();
}

window.addEventListener("load", () => inputEl.focus());

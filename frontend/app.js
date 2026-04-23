const API = "http://localhost:8000";

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
    const res = await fetch(`${API}/api/health`);
    const data = await res.json();
    const ok = data.status === "ok" && data.mongodb === "connected";
    dot.className  = "status-dot " + (ok ? "online" : "offline");
    text.textContent = ok ? "Connected" : "MongoDB unreachable";
  } catch {
    dot.className  = "status-dot offline";
    text.textContent = "Server offline";
  }
}

checkHealth();
setInterval(checkHealth, 30_000);

// ── Format response text ───────────────────────────────────────────────────
function formatText(raw) {
  // Split into paragraphs on double newline or single newline sequences
  const paragraphs = raw.split(/\n{2,}/);

  return paragraphs.map(para => {
    const lines = para.trim().split("\n").filter(Boolean);

    // Detect bullet lists (lines starting with - or *)
    const isList = lines.every(l => /^[-*•]\s/.test(l.trim()) || /^\d+\.\s/.test(l.trim()));
    if (isList && lines.length > 1) {
      const tag = /^\d+\./.test(lines[0].trim()) ? "ol" : "ul";
      const items = lines.map(l => `<li>${formatInline(l.replace(/^[-*•\d.]+\s+/, ""))}</li>`).join("");
      return `<${tag}>${items}</${tag}>`;
    }

    // Regular paragraph
    return `<p>${lines.map(formatInline).join("<br>")}</p>`;
  }).join("");
}

function formatInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g,     "<em>$1</em>")
    .replace(/`(.+?)`/g,       "<code>$1</code>")
    .replace(/(\$[\d,]+(?:\.\d+)?)/g, "<strong>$1</strong>");  // highlight dollar amounts
}

// ── Add message bubble ─────────────────────────────────────────────────────
function addMessage(html, role) {
  const isUser = role === "user";

  const wrapper = document.createElement("div");
  wrapper.className = `message ${isUser ? "user" : "assistant"}-message`;

  const avatar = document.createElement("div");
  avatar.className = `avatar ${isUser ? "user" : "assistant"}-avatar`;
  avatar.innerHTML = isUser
    ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>`
    : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = html;

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubble);
  messagesEl.appendChild(wrapper);
  scrollToBottom();
  return wrapper;
}

// ── Typing indicator ───────────────────────────────────────────────────────
function showTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant-message";
  wrapper.id = "typingIndicator";

  const avatar = document.createElement("div");
  avatar.className = "avatar assistant-avatar";
  avatar.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>`;

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

// ── Send message ───────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || sendBtn.disabled) return;

  inputEl.value = "";
  autoResize(inputEl);

  addMessage(formatInline(text), "user");

  setLoading(true);
  showTyping();

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });

    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || "Server error");

    sessionId = data.session_id;
    localStorage.setItem("procurement_session", sessionId);

    hideTyping();
    addMessage(formatText(data.reply), "assistant");

  } catch (err) {
    hideTyping();
    addMessage(`<p>Sorry, something went wrong: <strong>${err.message}</strong>. Please check that the server is running.</p>`, "assistant");
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

  // Remove all messages except welcome
  const msgs = messagesEl.querySelectorAll(".message:not(#welcomeMsg)");
  msgs.forEach(m => m.remove());
  inputEl.focus();
}

// ── Focus input on load ────────────────────────────────────────────────────
window.addEventListener("load", () => inputEl.focus());

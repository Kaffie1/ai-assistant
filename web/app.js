const chatBox = document.getElementById("chatBox");
const input = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const voiceBtn = document.getElementById("voiceBtn");
const modeBadge = document.getElementById("modeBadge");
let thinkingEl = null;
let notificationTimer = null;
let mediaRecorder = null;
let recordingChunks = [];
let isRecording = false;
let isTranscribing = false;

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  if (role === "assistant" && String(text || "").startsWith("[Recent Context]")) {
    el.classList.add("recentCard");
    el.innerHTML = renderRecentContextCard(String(text || ""));
  } else if (role === "assistant" && String(text || "").startsWith("[Recent Context Cleared]")) {
    el.classList.add("recentCard", "recentClearCard");
    el.innerHTML = renderRecentContextClearCard(String(text || ""));
  } else {
    el.textContent = text;
  }
  chatBox.appendChild(el);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderRecentContextCard(text) {
  const lines = String(text || "").split("\n");
  const meta = {};
  let injectedContext = "";
  let readingContext = false;

  lines.slice(1).forEach((line) => {
    const raw = String(line || "");
    if (raw.startsWith("- injected_context:")) {
      readingContext = true;
      const value = raw.split(":").slice(1).join(":").trim();
      if (value && value !== "(empty)") {
        injectedContext = value;
      }
      return;
    }
    if (readingContext) {
      injectedContext += (injectedContext ? "\n" : "") + raw;
      return;
    }
    const match = raw.match(/^- ([^=]+)=(.*)$/);
    if (match) {
      meta[match[1].trim()] = match[2].trim();
    }
  });

  const metaItems = [
    ["缓存文件", meta.path || "-"],
    ["是否存在", meta.exists || "false"],
    ["最近更新", meta.updated_at || "-"],
    ["已存轮次", meta.stored_turns || "0"],
    ["是否过期", meta.expired || "true"],
  ]
    .map(
      ([label, value]) =>
        `<div class="recentMetaItem"><span class="recentMetaLabel">${escapeHtml(label)}</span><span class="recentMetaValue">${escapeHtml(value)}</span></div>`
    )
    .join("");

  const contextHtml = injectedContext.trim()
    ? `<pre class="recentContextBlock">${escapeHtml(injectedContext.trim())}</pre>`
    : '<div class="recentContextEmpty">当前没有可注入的短期上下文</div>';

  return `
    <div class="recentCardHeader">短期记忆</div>
    <div class="recentCardSub">最近几轮对话缓存</div>
    <div class="recentMetaGrid">${metaItems}</div>
    <div class="recentSectionTitle">当前注入内容</div>
    ${contextHtml}
  `;
}

function renderRecentContextClearCard(text) {
  const lines = String(text || "").split("\n");
  const meta = {};

  lines.slice(1).forEach((line) => {
    const match = String(line || "").match(/^- ([^=]+)=(.*)$/);
    if (match) {
      meta[match[1].trim()] = match[2].trim();
    }
  });

  const status = meta.status === "cleared" ? "已清空" : "本来为空";
  const statusClass = meta.status === "cleared" ? "success" : "muted";
  const message = meta.message || "当前短期记忆状态已更新";
  const metaItems = [
    ["缓存文件", meta.path || "-"],
    ["当前状态", status],
    ["缓存是否存在", meta.exists || "false"],
    ["剩余轮次", meta.stored_turns || "0"],
    ["最近更新", meta.updated_at || "-"],
  ]
    .map(
      ([label, value]) =>
        `<div class="recentMetaItem"><span class="recentMetaLabel">${escapeHtml(label)}</span><span class="recentMetaValue">${escapeHtml(value)}</span></div>`
    )
    .join("");

  return `
    <div class="recentCardHeader">短期记忆已处理</div>
    <div class="recentCardSub">当前会话的短期上下文缓存重置结果</div>
    <div class="recentStatusBanner ${statusClass}">${escapeHtml(message)}</div>
    <div class="recentMetaGrid">${metaItems}</div>
  `;
}

function showThinking() {
  if (thinkingEl) return;
  thinkingEl = document.createElement("div");
  thinkingEl.className = "msg assistant thinking";
  thinkingEl.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span><span class="thinkingText">正在思考</span>';
  chatBox.appendChild(thinkingEl);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function hideThinking() {
  if (!thinkingEl) return;
  thinkingEl.remove();
  thinkingEl = null;
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    modeBadge.textContent = `对话模式：${data.mode} · Tool Calling`;
  } catch (_) {
    modeBadge.textContent = "连接失败";
  }
}

async function pollNotifications() {
  try {
    const res = await fetch("/api/notifications");
    const data = await res.json();
    const items = Array.isArray(data.messages) ? data.messages : [];
    items.forEach((item) => {
      if (item && item.text) {
        addMessage("assistant", item.text);
      }
    });
  } catch (_) {
    // 后台提醒轮询失败时静默忽略，不打断主对话体验。
  }
}

function setInputControlsDisabled(disabled) {
  sendBtn.disabled = disabled;
  if (voiceBtn) {
    voiceBtn.disabled = disabled && !isRecording;
  }
}

async function sendMessageText(rawMessage) {
  const message = String(rawMessage || "").trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  setInputControlsDisabled(true);
  showThinking();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    hideThinking();
    addMessage("assistant", data.reply || "无回复");
  } catch (err) {
    hideThinking();
    addMessage("assistant", `请求失败：${String(err)}`);
  } finally {
    hideThinking();
    setInputControlsDisabled(false);
    input.focus();
  }
}

async function sendMessage() {
  await sendMessageText(input.value);
}

function updateVoiceButton() {
  if (!voiceBtn) return;
  if (isTranscribing) {
    voiceBtn.textContent = "转";
    voiceBtn.classList.add("active");
    voiceBtn.disabled = true;
    return;
  }
  if (isRecording) {
    voiceBtn.textContent = "停";
    voiceBtn.classList.add("active");
    voiceBtn.disabled = false;
    return;
  }
  voiceBtn.textContent = "录";
  voiceBtn.classList.remove("active");
  voiceBtn.disabled = false;
}

async function uploadAudio(blob) {
  const form = new FormData();
  form.append("audio", blob, "speech.webm");
  const res = await fetch("/api/asr", {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`ASR 请求失败：${res.status}`);
  }
  const data = await res.json();
  const text = String(data.text || "").trim();
  if (!text) {
    throw new Error("没有识别到有效语音");
  }
  return text;
}

async function stopRecordingAndSend() {
  if (!mediaRecorder) return;
  isRecording = false;
  isTranscribing = true;
  updateVoiceButton();
  mediaRecorder.stop();
}

async function startRecording() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    addMessage("assistant", "当前浏览器不支持语音输入。");
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordingChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        recordingChunks.push(event.data);
      }
    });
    mediaRecorder.addEventListener("stop", async () => {
      const audioBlob = new Blob(recordingChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      stream.getTracks().forEach((track) => track.stop());
      try {
        const recognizedText = await uploadAudio(audioBlob);
        await sendMessageText(recognizedText);
      } catch (err) {
        addMessage("assistant", `语音识别失败：${String(err)}`);
      } finally {
        isTranscribing = false;
        mediaRecorder = null;
        recordingChunks = [];
        updateVoiceButton();
      }
    });
    mediaRecorder.start();
    isRecording = true;
    updateVoiceButton();
  } catch (err) {
    addMessage("assistant", `无法开始录音：${String(err)}`);
  }
}

async function toggleVoiceRecording() {
  if (isTranscribing) return;
  if (isRecording) {
    await stopRecordingAndSend();
    return;
  }
  await startRecording();
}

sendBtn.addEventListener("click", sendMessage);
if (voiceBtn) {
  voiceBtn.addEventListener("click", toggleVoiceRecording);
}

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

updateVoiceButton();
checkHealth();
pollNotifications();
notificationTimer = window.setInterval(pollNotifications, 3000);

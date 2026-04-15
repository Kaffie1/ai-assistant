const chatBox = document.getElementById("chatBox");
const input = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const modeBadge = document.getElementById("modeBadge");
const learnMeta = document.getElementById("learnMeta");
let thinkingEl = null;

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  chatBox.appendChild(el);
  chatBox.scrollTop = chatBox.scrollHeight;
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
    modeBadge.textContent = `回复模式：${data.mode}`;
  } catch (_) {
    modeBadge.textContent = "连接失败";
  }
}

async function sendMessage() {
  const message = input.value.trim();
  if (!message) return;

  addMessage("user", message);
  input.value = "";
  sendBtn.disabled = true;
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
    const t = data.learn.tasks ?? 0;
    learnMeta.textContent = `[learn] extracted=${data.learn.extracted}, profile=${data.learn.profile}, knowledge=${data.learn.knowledge}, tasks=${t}, reason=${data.learn.reason}`;
  } catch (err) {
    hideThinking();
    addMessage("assistant", `请求失败：${String(err)}`);
  } finally {
    hideThinking();
    sendBtn.disabled = false;
    input.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.dataset.text || "";
    input.focus();
  });
});

addMessage("assistant", "AI 助手已启动。你可以直接提问，或先点下方快捷按钮。");
checkHealth();

/* =========================================================
   NOD CHAT APPLICATION
   Complete frontend with Ollama streaming integration
========================================================= */

const NOD = (() => {

  /* =======================================================
     STATE
  ======================================================= */
  const state = {
    currentChatId: null,
    chats: {},
    sidebarCollapsed: false,
    theme: "light",
    fontSize: "medium",
    currentModel: "qwen3:8b",
    availableModels: ["qwen3:8b"],
    settings: {
      voiceOutput: false,
      soundEffects: false,
      enterToSend: true,
      autoSendVoice: false
    },
    isGenerating: false,
    abortController: null,
    currentAssistantBubble: null,
    renameChatId: null,
    user: null
  };

  /* =======================================================
     MARKDOWN SETUP
  ======================================================= */
  marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false,
    sanitize: false
  });

  /* =======================================================
     UTILITIES
  ======================================================= */
  function createId() {
    return "chat-" + Date.now() + "-" + Math.random().toString(36).substring(2, 8);
  }

  function formatTime(date) {
    return new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit" }).format(date);
  }

  function escapeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /* =======================================================
     API HELPERS
  ======================================================= */
  async function apiGet(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function apiPost(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function apiDelete(url) {
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  /* =======================================================
     USER
  ======================================================= */
  async function loadUser() {
    try {
      state.user = await NODAuth.getUser();
      if (state.user) {
        document.getElementById("userName").textContent = state.user.name || "User";
        document.getElementById("userEmail").textContent = state.user.email;
        document.getElementById("userAvatar").textContent = (state.user.name || "U").charAt(0).toUpperCase();
      }
    } catch (e) {
      console.error("Failed to load user:", e);
    }
  }

  function logout() {
    NODAuth.logout();
  }

  /* =======================================================
     MODELS
  ======================================================= */
  async function loadModels() {
    try {
      const data = await apiGet("/api/models");
      state.availableModels = data.models || ["qwen3:8b"];
      const select = document.getElementById("modelSelect");
      select.innerHTML = state.availableModels.map(m => 
        `<option value="${m}" ${m === state.currentModel ? "selected" : ""}>${m}</option>`
      ).join("");
    } catch (e) {
      console.error("Failed to load models:", e);
    }
  }

  function setModel(model) {
    state.currentModel = model;
    localStorage.setItem("nod_model", model);
  }

  /* =======================================================
     CHAT CRUD
  ======================================================= */
  async function loadChats() {
    try {
      state.chats = await apiGet("/api/chats");
      renderHistory();
    } catch (e) {
      console.error("Failed to load chats:", e);
    }
  }

  async function newChat() {
    try {
      const chat = await apiPost("/api/chats", { title: "New Chat" });
      state.chats[chat.id] = chat;
      state.currentChatId = chat.id;
      renderHistory();
      renderCurrentChat();
      document.getElementById("messageInput").focus();
    } catch (e) {
      showToast("Failed to create chat");
    }
  }

  async function selectChat(id) {
    if (!state.chats[id]) return;
    state.currentChatId = id;
    renderHistory();
    renderCurrentChat();
    closeMobileSidebar();
  }

  async function deleteChat(id, event) {
    if (event) event.stopPropagation();
    if (!state.chats[id]) return;
    if (!confirm("Delete this chat?")) return;
    try {
      await apiDelete("/api/chats/" + id);
      delete state.chats[id];
      if (state.currentChatId === id) state.currentChatId = null;
      renderHistory();
      renderCurrentChat();
    } catch (e) {
      showToast("Failed to delete chat");
    }
  }

  async function clearCurrentChat() {
    if (!state.currentChatId) {
      showToast("No active chat");
      return;
    }
    try {
      const chat = await apiPost("/api/chats/" + state.currentChatId + "/clear", {});
      state.chats[state.currentChatId] = chat;
      renderHistory();
      renderCurrentChat();
      showToast("Chat cleared");
    } catch (e) {
      showToast("Failed to clear chat");
    }
  }

  async function clearAllChats() {
    if (!confirm("Delete ALL chats? This cannot be undone.")) return;
    try {
      for (const id of Object.keys(state.chats)) {
        await apiDelete("/api/chats/" + id);
      }
      state.chats = {};
      state.currentChatId = null;
      renderHistory();
      renderCurrentChat();
      closeSettings();
      showToast("All chats deleted");
    } catch (e) {
      showToast("Failed to delete chats");
    }
  }

  /* =======================================================
     RENAME
  ======================================================= */
  function openRenameModal(id) {
    state.renameChatId = id;
    const chat = state.chats[id];
    document.getElementById("renameInput").value = chat ? chat.title : "";
    document.getElementById("renameModal").classList.add("active");
  }

  function closeRenameModal() {
    state.renameChatId = null;
    document.getElementById("renameModal").classList.remove("active");
  }

  async function confirmRename() {
    const newTitle = document.getElementById("renameInput").value.trim();
    if (!newTitle || !state.renameChatId) {
      closeRenameModal();
      return;
    }
    try {
      const chat = await apiPost("/api/chats/" + state.renameChatId + "/rename", { title: newTitle });
      state.chats[state.renameChatId] = chat;
      renderHistory();
      if (state.currentChatId === state.renameChatId) {
        document.getElementById("chatTitle").textContent = newTitle;
      }
      closeRenameModal();
    } catch (e) {
      showToast("Failed to rename chat");
    }
  }

  /* =======================================================
     HISTORY RENDER
  ======================================================= */
  function renderHistory(search = "") {
    const container = document.getElementById("historyContent");
    container.innerHTML = "";
    const chats = Object.values(state.chats)
      .filter(chat => chat.title.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => new Date(b.updated_at || b.updatedAt) - new Date(a.updated_at || a.updatedAt));

    chats.forEach(chat => {
      const item = document.createElement("div");
      item.className = "history-item" + (chat.id === state.currentChatId ? " active" : "");
      item.onclick = () => selectChat(chat.id);
      item.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/>
        </svg>
        <div class="history-name">${escapeHTML(chat.title)}</div>
        <div class="history-actions">
          <button class="history-action rename" title="Rename" onclick="event.stopPropagation(); NOD.openRenameModal('${chat.id}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="history-action" title="Delete" onclick="event.stopPropagation(); NOD.deleteChat('${chat.id}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;
      container.appendChild(item);
    });
  }

  function filterHistory(value) {
    renderHistory(value);
  }

  /* =======================================================
     RENDER CURRENT CHAT
  ======================================================= */
  function renderCurrentChat() {
    const messages = document.getElementById("messages");
    const title = document.getElementById("chatTitle");
    messages.innerHTML = "";

    if (!state.currentChatId || !state.chats[state.currentChatId]) {
      title.textContent = "New Chat";
      renderEmptyState();
      return;
    }

    const chat = state.chats[state.currentChatId];
    title.textContent = chat.title;

    if (!chat.messages || !chat.messages.length) {
      renderEmptyState();
      return;
    }

    chat.messages.forEach(msg => renderMessage(msg));
    scrollToBottom();
  }

  function renderEmptyState() {
    const messages = document.getElementById("messages");
    messages.innerHTML = `
      <div class="empty-state">
        <svg class="empty-logo" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round">
          <path d="M16 25c0 0 8-13 16-13s16 13 16 13"/>
          <path d="M16 25c0 0 8 18 16 18s16-18 16-18" opacity=".3"/>
        </svg>
        <div class="empty-title">How can I help?</div>
        <div class="empty-subtitle">Welcome to NOD. Ask a question, describe an idea, or choose one of the suggestions below.</div>
        <div class="suggestions">
          <button class="suggestion" onclick="NOD.useSuggestion('Explain quantum computing in simple terms')">Explain quantum computing</button>
          <button class="suggestion" onclick="NOD.useSuggestion('Help me write a Python function')">Help me write code</button>
          <button class="suggestion" onclick="NOD.useSuggestion('Plan a 7-day trip to Japan')">Plan a trip</button>
          <button class="suggestion" onclick="NOD.useSuggestion('Give me some healthy breakfast ideas')">Breakfast ideas</button>
        </div>
      </div>
    `;
  }
    /* =======================================================
     MARKDOWN RENDERING
  ======================================================= */
  function renderMarkdown(text) {
    if (!text) return "";
    const html = marked.parse(text);
    return wrapCodeBlocks(html);
  }

  function wrapCodeBlocks(html) {
    const temp = document.createElement("div");
    temp.innerHTML = html;
    temp.querySelectorAll("pre").forEach(pre => {
      const code = pre.querySelector("code");
      if (!code) return;
      const lang = code.className.replace("language-", "").replace("hljs", "").trim() || "code";
      const wrapper = document.createElement("div");
      wrapper.className = "code-block";
      const header = document.createElement("div");
      header.className = "code-header";
      header.innerHTML = `<span>${escapeHTML(lang)}</span><button class="copy-btn" onclick="NOD.copyCode(this)">Copy</button>`;
      wrapper.appendChild(header);
      wrapper.appendChild(pre.cloneNode(true));
      pre.replaceWith(wrapper);
    });
    return temp.innerHTML;
  }

  function highlightCode() {
    document.querySelectorAll("pre code").forEach(block => {
      hljs.highlightElement(block);
    });
  }

  function copyCode(btn) {
    const block = btn.closest(".code-block");
    const code = block.querySelector("code");
    const text = code ? code.textContent : "";
    navigator.clipboard.writeText(text).then(() => {
      btn.textContent = "Copied!";
      btn.classList.add("copied");
      setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 2000);
    });
  }

  /* =======================================================
     RENDER MESSAGE
  ======================================================= */
  function renderMessage(message, isStreaming = false) {
    const messages = document.getElementById("messages");

    if (isStreaming && state.currentAssistantBubble) {
      const bubble = state.currentAssistantBubble.querySelector(".bubble");
      bubble.innerHTML = renderMarkdown(message.content);
      highlightCode();
      scrollToBottom();
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "message " + (message.role === "user" ? "user" : "assistant");
    wrapper.dataset.msgId = message.time || Date.now();

    const avatar = message.role === "user"
      ? `<div class="avatar">YOU</div>`
      : `<div class="avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg></div>`;

    const body = document.createElement("div");
    body.className = "message-body";

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (message.role === "assistant") {
      bubble.innerHTML = renderMarkdown(message.content);
    } else {
      bubble.textContent = message.content;
    }

    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = formatTime(new Date(message.time));

    body.appendChild(bubble);
    body.appendChild(time);

    if (message.role === "assistant" && !isStreaming) {
      const actions = document.createElement("div");
      actions.className = "message-actions";
      actions.innerHTML = `
        <button class="msg-action" onclick="NOD.copyMessage(this)" title="Copy">Copy</button>
        <button class="msg-action" onclick="NOD.regenerate()" title="Regenerate">Regenerate</button>
      `;
      body.appendChild(actions);
    }

    wrapper.innerHTML = avatar;
    wrapper.appendChild(body);
    messages.appendChild(wrapper);

    if (message.role === "assistant") {
      highlightCode();
    }

    if (isStreaming) {
      state.currentAssistantBubble = wrapper;
    }

    scrollToBottom();
  }

  function copyMessage(btn) {
    const bubble = btn.closest(".message-body").querySelector(".bubble");
    const text = bubble.textContent;
    navigator.clipboard.writeText(text).then(() => {
      btn.textContent = "Copied!";
      setTimeout(() => btn.textContent = "Copy", 2000);
    });
  }

  /* =======================================================
     SEND MESSAGE (STREAMING)
  ======================================================= */
  async function sendMessage() {
    const input = document.getElementById("messageInput");
    const text = input.value.trim();
    if (!text) return;
    if (state.isGenerating) return;

    if (!state.currentChatId) {
      await newChat();
    }

    const userMsg = { role: "user", content: text, time: new Date().toISOString() };
    const chat = state.chats[state.currentChatId];
    chat.messages.push(userMsg);
    chat.updatedAt = new Date().toISOString();
    if (chat.title === "New Chat") {
      chat.title = text.length > 32 ? text.substring(0, 32) + "..." : text;
    }

    input.value = "";
    handleInput();
    renderHistory();
    renderCurrentChat();

    await streamResponse(text);
  }

  async function streamResponse(userText) {
    state.isGenerating = true;
    state.abortController = new AbortController();
    document.getElementById("stopBtn").style.display = "flex";
    document.getElementById("regenBtn").style.display = "none";

    showTyping();

    let assistantMsg = { role: "assistant", content: "", time: new Date().toISOString() };
    let fullText = "";

    try {
      const response = await fetch("/api/chats/" + state.currentChatId + "/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText, model: state.currentModel }),
        signal: state.abortController.signal
      });

      hideTyping();

      if (!response.ok) {
        throw new Error("Failed to get response");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      renderMessage({ ...assistantMsg, content: "" }, true);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);
            if (data.error) {
              throw new Error(data.error);
            }
            if (data.text) {
              fullText += data.text;
              assistantMsg.content = fullText;
              renderMessage({ ...assistantMsg }, true);
            }
            if (data.done) {
              fullText = data.full || fullText;
              assistantMsg.content = fullText;
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
      }

      state.currentAssistantBubble = null;
      renderCurrentChat();

      if (state.settings.voiceOutput && "speechSynthesis" in window && fullText) {
        speak(fullText);
      }

    } catch (err) {
      hideTyping();
      state.currentAssistantBubble = null;
      if (err.name === "AbortError") {
        assistantMsg.content = fullText || "(stopped)";
        renderCurrentChat();
      } else {
        showToast(err.message || "Error getting response. Is Ollama running?");
        const chat = state.chats[state.currentChatId];
        if (chat && chat.messages.length && chat.messages[chat.messages.length - 1].role === "assistant") {
          chat.messages.pop();
        }
        renderCurrentChat();
      }
    } finally {
      state.isGenerating = false;
      state.abortController = null;
      document.getElementById("stopBtn").style.display = "none";
      document.getElementById("regenBtn").style.display = "flex";
      loadChats();
    }
  }

  function stopGenerating() {
    if (state.abortController) {
      state.abortController.abort();
    }
  }

  async function regenerate() {
    if (!state.currentChatId) return;
    const chat = state.chats[state.currentChatId];
    if (!chat || !chat.messages.length) return;

    const lastMsg = chat.messages[chat.messages.length - 1];
    if (lastMsg.role === "assistant") {
      chat.messages.pop();
    }

    let lastUserMsg = null;
    for (let i = chat.messages.length - 1; i >= 0; i--) {
      if (chat.messages[i].role === "user") {
        lastUserMsg = chat.messages[i];
        break;
      }
    }

    if (!lastUserMsg) {
      showToast("No user message to regenerate from");
      return;
    }

    renderCurrentChat();
    await streamResponse(lastUserMsg.content);
  }

  /* =======================================================
     TYPING INDICATOR
  ======================================================= */
  function showTyping() {
    const messages = document.getElementById("messages");
    if (document.getElementById("typingMessage")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant";
    wrapper.id = "typingMessage";
    wrapper.innerHTML = `
      <div class="avatar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg></div>
      <div class="message-body"><div class="typing"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div></div>
    `;
    messages.appendChild(wrapper);
    scrollToBottom();
  }

  function hideTyping() {
    const typing = document.getElementById("typingMessage");
    if (typing) typing.remove();
  }

  function scrollToBottom() {
    const area = document.getElementById("chatArea");
    setTimeout(() => { area.scrollTop = area.scrollHeight; }, 50);
  }

  /* =======================================================
     INPUT HANDLING
  ======================================================= */
  function handleInput() {
    const input = document.getElementById("messageInput");
    const send = document.getElementById("sendBtn");
    send.classList.toggle("visible", input.value.trim().length > 0);
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }

  function handleKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey && state.settings.enterToSend) {
      event.preventDefault();
      sendMessage();
    }
  }

  function useSuggestion(text) {
    const input = document.getElementById("messageInput");
    input.value = text;
    handleInput();
    input.focus();
  }

  /* =======================================================
     FILE ATTACHMENT
  ======================================================= */
  function triggerFileUpload() {
    document.getElementById("fileInput").click();
  }

  function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    showToast("File: " + file.name + " (upload coming soon)");
    event.target.value = "";
  }

  /* =======================================================
     SIDEBAR
  ======================================================= */
  function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    state.sidebarCollapsed = !state.sidebarCollapsed;
    sidebar.classList.toggle("collapsed", state.sidebarCollapsed);
  }

  function toggleMobileSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("mobile-open");
  }

  function closeMobileSidebar() {
    document.getElementById("sidebar").classList.remove("mobile-open");
  }

  /* =======================================================
     SETTINGS
  ======================================================= */
  function openSettings() {
    document.getElementById("settings").classList.add("active");
    document.getElementById("overlay").classList.add("active");
  }

  function closeSettings() {
    document.getElementById("settings").classList.remove("active");
    document.getElementById("overlay").classList.remove("active");
  }

  function setTheme(theme) {
    state.theme = theme;
    let actualTheme = theme;
    if (theme === "auto") {
      actualTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.setAttribute("data-theme", actualTheme);
    document.querySelectorAll("[data-theme-option]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.themeOption === theme);
    });
    const hljsTheme = document.getElementById("hljs-theme");
    if (hljsTheme) {
      hljsTheme.href = actualTheme === "dark"
        ? "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css"
        : "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";
    }
    localStorage.setItem("nod_theme", theme);
  }

  function setFont(size) {
    state.fontSize = size;
    let scale = 1;
    if (size === "small") scale = 0.9;
    if (size === "large") scale = 1.1;
    document.body.style.fontSize = scale + "em";
    document.querySelectorAll("[data-font-option]").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.fontOption === size);
    });
    localStorage.setItem("nod_font", size);
  }

  function toggleSetting(name) {
    state.settings[name] = !state.settings[name];
    const map = {
      voiceOutput: "voiceOutputToggle",
      soundEffects: "soundToggle",
      enterToSend: "enterToggle",
      autoSendVoice: "autoVoiceToggle"
    };
    const element = document.getElementById(map[name]);
    if (element) {
      element.classList.toggle("active", state.settings[name]);
    }
    localStorage.setItem("nod_settings", JSON.stringify(state.settings));
  }

  /* =======================================================
     VOICE MODE
  ======================================================= */
  function openVoiceMode() {
    document.getElementById("voiceOverlay").classList.add("active");
    document.getElementById("voiceLabel").textContent = "Voice Mode";
    showToast("Voice integration coming soon");
  }

  function closeVoiceMode() {
    document.getElementById("voiceOverlay").classList.remove("active");
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    speechSynthesis.speak(utterance);
  }

  /* =======================================================
     TOAST
  ======================================================= */
  function showToast(message) {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
  }

  /* =======================================================
     LOAD SETTINGS
  ======================================================= */
  function loadSettings() {
    const theme = localStorage.getItem("nod_theme");
    const font = localStorage.getItem("nod_font");
    const settings = localStorage.getItem("nod_settings");
    const model = localStorage.getItem("nod_model");

    if (theme) state.theme = theme;
    if (font) state.fontSize = font;
    if (model) state.currentModel = model;

    if (settings) {
      try {
        state.settings = { ...state.settings, ...JSON.parse(settings) };
      } catch { console.log("Invalid settings"); }
    }

    setTheme(state.theme);
    setFont(state.fontSize);

    Object.keys(state.settings).forEach(name => {
      const map = {
        voiceOutput: "voiceOutputToggle",
        soundEffects: "soundToggle",
        enterToSend: "enterToggle",
        autoSendVoice: "autoVoiceToggle"
      };
      const element = document.getElementById(map[name]);
      if (element) {
        element.classList.toggle("active", state.settings[name]);
      }
    });
  }

  /* =======================================================
     INITIALIZE
  ======================================================= */
  async function init() {
    await loadUser();
    await loadModels();
    await loadChats();
    loadSettings();
    renderCurrentChat();
    document.getElementById("messageInput").focus();

    document.addEventListener("click", (e) => {
      const sidebar = document.getElementById("sidebar");
      const menuBtn = document.querySelector(".mobile-menu");
      if (window.innerWidth <= 900 && sidebar.classList.contains("mobile-open")) {
        if (!sidebar.contains(e.target) && !menuBtn.contains(e.target)) {
          closeMobileSidebar();
        }
      }
    });

    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (state.theme === "auto") setTheme("auto");
    });
  }

  /* =======================================================
     PUBLIC API
  ======================================================= */
  return {
    init,
    newChat,
    selectChat,
    deleteChat,
    clearCurrentChat,
    clearAllChats,
    filterHistory,
    sendMessage,
    handleInput,
    handleKeydown,
    useSuggestion,
    toggleSidebar,
    toggleMobileSidebar,
    openSettings,
    closeSettings,
    setTheme,
    setFont,
    toggleSetting,
    openVoiceMode,
    closeVoiceMode,
    showToast,
    logout,
    triggerFileUpload,
    handleFileSelect,
    stopGenerating,
    regenerate,
    copyCode,
    copyMessage,
    openRenameModal,
    closeRenameModal,
    confirmRename,
    setModel
  };

})();

/* =========================================================
   START NOD
========================================================= */
document.addEventListener("DOMContentLoaded", () => {
  NOD.init();
});
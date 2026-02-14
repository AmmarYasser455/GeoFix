/* ═══════════════════════════════════════════════
   GeoFix — Chat Application Logic v2
   ═══════════════════════════════════════════════ */

(() => {
    "use strict";

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ── Selectors ───────────────────────────────────
    const sidebar = $("#sidebar");
    const sidebarOpen = $("#sidebar-open");
    const sidebarClose = $("#sidebar-close");
    const sidebarOverlay = $("#sidebar-overlay");
    const btnNewChat = $("#btn-new-chat");
    const searchInput = $("#search-input");
    const convList = $("#conversations-list");
    const welcomeScreen = $("#welcome-screen");
    const messagesEl = $("#messages");
    const typingIndicator = $("#typing-indicator");
    const messageInput = $("#message-input");
    const btnSend = $("#btn-send");
    const fileInput = $("#file-input");
    const filePreview = $("#file-preview");
    const modelSelect = $("#model-select");
    const topbarLabel = $("#topbar-label");

    // Modals
    const modalWorkspace = $("#modal-workspace");
    const modalSettings = $("#modal-settings");
    const btnWorkspace = $("#btn-workspace-settings");
    const btnUserSettings = $("#user-profile-btn");

    // ── State ───────────────────────────────────────
    let ws = null;
    let currentConvId = null;
    let sessionId = "s_" + Math.random().toString(36).slice(2, 10);
    let isStreaming = false;
    let streamingMessageEl = null;
    let streamedContent = "";
    let reconnectAttempts = 0;
    let pendingFiles = [];
    let sidebarIsOpen = true;

    // ── marked.js ───────────────────────────────────
    if (typeof marked !== "undefined") {
        marked.setOptions({
            highlight: (code, lang) => {
                if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang))
                    return hljs.highlight(code, { language: lang }).value;
                return code;
            },
            breaks: true,
            gfm: true,
        });
    }

    // ═══════════════════════════════════════════════
    // SIDEBAR TOGGLE
    // ═══════════════════════════════════════════════

    function openSidebar() {
        sidebar.classList.remove("collapsed");
        sidebar.classList.add("open");
        sidebarIsOpen = true;
        if (window.innerWidth <= 768) sidebarOverlay.classList.add("visible");
    }

    function closeSidebar() {
        sidebar.classList.add("collapsed");
        sidebar.classList.remove("open");
        sidebarIsOpen = false;
        sidebarOverlay.classList.remove("visible");
    }

    function toggleSidebar() { sidebarIsOpen ? closeSidebar() : openSidebar(); }

    sidebarOpen.addEventListener("click", openSidebar);
    sidebarClose.addEventListener("click", closeSidebar);
    sidebarOverlay.addEventListener("click", closeSidebar);

    // ═══════════════════════════════════════════════
    // WEBSOCKET
    // ═══════════════════════════════════════════════

    function connect() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${proto}//${location.host}/ws/chat`);
        ws.onopen = () => { reconnectAttempts = 0; showConnectionBadge(true); };
        ws.onmessage = (e) => handleWSMessage(JSON.parse(e.data));
        ws.onclose = () => {
            showConnectionBadge(false);
            setTimeout(connect, Math.min(1000 * 2 ** reconnectAttempts++, 10000));
        };
        ws.onerror = () => ws.close();
    }

    function handleWSMessage(data) {
        switch (data.type) {
            case "token":
                if (!streamingMessageEl) {
                    typingIndicator.hidden = true;
                    streamingMessageEl = appendMessage("assistant", "", true);
                    streamedContent = "";
                }
                streamedContent += data.content;
                updateStreamingBody(streamedContent);
                scrollToBottom();
                break;

            case "done":
                if (streamingMessageEl) {
                    const body = streamingMessageEl.querySelector(".message-body");
                    body.classList.remove("streaming-cursor");
                    renderMarkdown(body, streamedContent);
                    streamingMessageEl = null;
                    streamedContent = "";
                }
                isStreaming = false;
                if (data.conversation_id) currentConvId = data.conversation_id;
                enableInput();
                loadConversations();
                scrollToBottom();
                break;

            case "conversation_created":
                currentConvId = data.conversation_id;
                topbarLabel.textContent = data.title || "New Chat";
                highlightActive(data.conversation_id);
                break;

            case "error":
                typingIndicator.hidden = true;
                if (streamingMessageEl) {
                    streamingMessageEl.querySelector(".message-body").classList.remove("streaming-cursor");
                    streamingMessageEl = null;
                }
                appendMessage("assistant", `⚠️ Error: ${data.content}`);
                isStreaming = false;
                enableInput();
                break;
        }
    }

    function showConnectionBadge(connected) {
        let badge = $(".connection-badge");
        if (!badge) {
            badge = document.createElement("div");
            badge.className = "connection-badge";
            document.body.appendChild(badge);
        }
        badge.className = `connection-badge ${connected ? "connected" : "disconnected"}`;
        badge.innerHTML = `<span class="connection-dot"></span>${connected ? "Connected" : "Reconnecting..."}`;
        badge.style.opacity = "1";
        if (connected) setTimeout(() => (badge.style.opacity = "0"), 3000);
    }

    // ═══════════════════════════════════════════════
    // SEND MESSAGE
    // ═══════════════════════════════════════════════

    function sendMessage() {
        const text = messageInput.value.trim();
        if (!text || isStreaming || !ws || ws.readyState !== WebSocket.OPEN) return;

        if (pendingFiles.length) {
            uploadFiles(pendingFiles);
            pendingFiles = [];
            filePreview.hidden = true;
            filePreview.innerHTML = "";
        }

        appendMessage("user", text);
        showMessagesArea();
        scrollToBottom();

        messageInput.value = "";
        autoResize();
        disableInput();

        isStreaming = true;
        typingIndicator.hidden = false;
        scrollToBottom();

        // Include API key if user set one
        const apiKey = localStorage.getItem("geofix_api_key") || "";

        ws.send(JSON.stringify({
            message: text,
            conversation_id: currentConvId,
            session_id: sessionId,
            model: modelSelect.value,
            api_key: apiKey || undefined,
        }));
    }

    // ═══════════════════════════════════════════════
    // FILE UPLOAD
    // ═══════════════════════════════════════════════

    async function uploadFiles(files) {
        for (const file of files) {
            const fd = new FormData();
            fd.append("file", file);
            fd.append("session_id", sessionId);
            try {
                const resp = await fetch("/api/upload", { method: "POST", body: fd });
                const data = await resp.json();
                showMessagesArea();
                appendMessage("user", `📎 Uploaded: **${data.filename}**`);
                if (data.profile) appendMessage("assistant", data.profile);
                scrollToBottom();
            } catch (err) {
                appendMessage("assistant", `⚠️ Upload failed: ${err.message}`);
            }
        }
    }

    // ═══════════════════════════════════════════════
    // MESSAGES
    // ═══════════════════════════════════════════════

    function appendMessage(role, content, streaming = false) {
        const msg = document.createElement("div");
        msg.className = "message";
        const displayName = localStorage.getItem("geofix_display_name") || "You";
        const avatar = role === "user"
            ? `<div class="message-avatar user">${displayName.charAt(0).toUpperCase()}</div>`
            : `<div class="message-avatar assistant"><img src="/public/avatars/logo_orange.svg" alt="GeoFix" /></div>`;

        msg.innerHTML = `
      <div class="message-row">
        ${avatar}
        <div class="message-content">
          <div class="message-role ${role}">${role === "user" ? displayName : "GeoFix"}</div>
          <div class="message-body ${streaming ? "streaming-cursor" : ""}"></div>
        </div>
      </div>`;

        const body = msg.querySelector(".message-body");
        streaming ? (body.textContent = content) : renderMarkdown(body, content);
        messagesEl.appendChild(msg);
        return msg;
    }

    function updateStreamingBody(content) {
        if (!streamingMessageEl) return;
        streamingMessageEl.querySelector(".message-body").textContent = content;
    }

    function renderMarkdown(el, content) {
        if (typeof marked !== "undefined") {
            el.innerHTML = marked.parse(content);
            el.querySelectorAll("pre code").forEach((block) => {
                if (typeof hljs !== "undefined") hljs.highlightElement(block);
                const wrapper = document.createElement("div");
                wrapper.className = "code-block-wrapper";
                block.parentElement.parentElement.insertBefore(wrapper, block.parentElement);
                wrapper.appendChild(block.parentElement);
                const btn = document.createElement("button");
                btn.className = "code-copy-btn";
                btn.textContent = "Copy";
                btn.onclick = () => {
                    navigator.clipboard.writeText(block.textContent);
                    btn.textContent = "Copied!";
                    setTimeout(() => (btn.textContent = "Copy"), 2000);
                };
                wrapper.appendChild(btn);
            });
        } else {
            el.textContent = content;
        }
    }

    function showMessagesArea() {
        welcomeScreen.style.display = "none";
        messagesEl.classList.add("has-messages");
    }

    function showWelcomeScreen() {
        welcomeScreen.style.display = "flex";
        messagesEl.classList.remove("has-messages");
        messagesEl.innerHTML = "";
        topbarLabel.textContent = "New Chat";
    }

    function scrollToBottom() {
        requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; });
    }

    function disableInput() { btnSend.disabled = true; messageInput.disabled = true; }
    function enableInput() { messageInput.disabled = false; updateSendBtn(); messageInput.focus(); }
    function updateSendBtn() { btnSend.disabled = !messageInput.value.trim() || isStreaming; }
    function autoResize() {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 180) + "px";
    }

    // ═══════════════════════════════════════════════
    // CONVERSATIONS
    // ═══════════════════════════════════════════════

    async function loadConversations() {
        try {
            const resp = await fetch("/api/conversations");
            const convs = await resp.json();
            renderConversations(convs);
        } catch { convList.innerHTML = '<div class="conv-empty">Failed to load</div>'; }
    }

    function renderConversations(convs) {
        if (!convs?.length) {
            convList.innerHTML = `
        <div class="conv-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <div>No chats yet</div>
        </div>`;
            return;
        }

        convList.innerHTML = convs.map((c) => `
      <div class="conv-item ${c.id === currentConvId ? "active" : ""}" data-id="${c.id}">
        <svg class="conv-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span class="conv-title" title="${esc(c.title)}">${esc(c.title)}</span>
        <div class="conv-actions">
          <button class="conv-action-btn delete" data-id="${c.id}" title="Delete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      </div>`).join("");

        convList.querySelectorAll(".conv-item").forEach((el) => {
            el.addEventListener("click", (e) => {
                if (e.target.closest(".conv-action-btn")) return;
                loadConversation(el.dataset.id);
                if (window.innerWidth <= 768) closeSidebar();
            });
        });

        convList.querySelectorAll(".conv-action-btn.delete").forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                await fetch(`/api/conversations/${id}`, { method: "DELETE" });
                if (currentConvId === id) { currentConvId = null; showWelcomeScreen(); }
                loadConversations();
            });
        });
    }

    async function loadConversation(convId) {
        currentConvId = convId;
        highlightActive(convId);
        try {
            const resp = await fetch(`/api/conversations/${convId}/messages`);
            const msgs = await resp.json();
            messagesEl.innerHTML = "";
            showMessagesArea();
            msgs.forEach((m) => appendMessage(m.role, m.content));
            const firstUser = msgs.find((m) => m.role === "user");
            if (firstUser) topbarLabel.textContent = firstUser.content.slice(0, 60);
            scrollToBottom();
        } catch (err) { console.error("Load conversation error:", err); }
    }

    function highlightActive(convId) {
        convList.querySelectorAll(".conv-item").forEach((el) => {
            el.classList.toggle("active", el.dataset.id === convId);
        });
    }

    function newChat() {
        currentConvId = null;
        showWelcomeScreen();
        messageInput.focus();
        sessionId = "s_" + Math.random().toString(36).slice(2, 10);
        loadConversations();
    }

    function filterConvs() {
        const q = searchInput.value.toLowerCase();
        convList.querySelectorAll(".conv-item").forEach((el) => {
            const title = el.querySelector(".conv-title").textContent.toLowerCase();
            el.style.display = title.includes(q) ? "flex" : "none";
        });
    }

    function esc(str) { const d = document.createElement("div"); d.textContent = str; return d.innerHTML; }

    // ═══════════════════════════════════════════════
    // MODALS
    // ═══════════════════════════════════════════════

    function openModal(modal) { modal.hidden = false; }
    function closeModal(modal) { modal.hidden = true; }

    // Click outside modal card to close
    [modalWorkspace, modalSettings].forEach((modal) => {
        if (!modal) return;
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeModal(modal);
        });
    });

    // ── Workspace Settings ──────────────────────────
    const wsName = $("#ws-name");
    const wsInstructions = $("#ws-instructions");
    const wsCharCount = $("#ws-char-count");
    const wsTemperature = $("#ws-temperature");
    const wsTempValue = $("#ws-temp-value");
    const wsDefaultModel = $("#ws-default-model");

    if (btnWorkspace) btnWorkspace.addEventListener("click", () => {
        // Load from localStorage
        wsName.value = localStorage.getItem("geofix_ws_name") || "Home";
        wsInstructions.value = localStorage.getItem("geofix_ws_instructions") || "";
        wsCharCount.textContent = `${wsInstructions.value.length}/1500`;
        wsDefaultModel.value = localStorage.getItem("geofix_ws_model") || "auto";
        wsTemperature.value = localStorage.getItem("geofix_ws_temp") || "0.7";
        wsTempValue.textContent = wsTemperature.value;
        openModal(modalWorkspace);
    });

    if (wsInstructions) wsInstructions.addEventListener("input", () => {
        wsCharCount.textContent = `${wsInstructions.value.length}/1500`;
    });

    if (wsTemperature) wsTemperature.addEventListener("input", () => {
        wsTempValue.textContent = wsTemperature.value;
    });

    // Tabs
    $$(".modal-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            $$(".modal-tab").forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            $$(".tab-pane").forEach((p) => p.classList.remove("active"));
            const pane = $(`#tab-${tab.dataset.tab}`);
            if (pane) pane.classList.add("active");
        });
    });

    $("#ws-cancel")?.addEventListener("click", () => closeModal(modalWorkspace));
    $("#ws-save")?.addEventListener("click", () => {
        localStorage.setItem("geofix_ws_name", wsName.value);
        localStorage.setItem("geofix_ws_instructions", wsInstructions.value);
        localStorage.setItem("geofix_ws_model", wsDefaultModel.value);
        localStorage.setItem("geofix_ws_temp", wsTemperature.value);
        // Update sidebar workspace name
        const logoText = $(".logo-text");
        if (logoText) logoText.textContent = wsName.value || "Home Workspace";
        // Apply default model
        modelSelect.value = wsDefaultModel.value;
        closeModal(modalWorkspace);
    });

    // ── User Settings ───────────────────────────────
    const settingApiKey = $("#setting-api-key");
    const settingDisplayName = $("#setting-display-name");
    const toggleApiKey = $("#toggle-api-key");

    if (btnUserSettings) btnUserSettings.addEventListener("click", () => {
        settingApiKey.value = localStorage.getItem("geofix_api_key") || "";
        settingDisplayName.value = localStorage.getItem("geofix_display_name") || "";
        openModal(modalSettings);
    });

    if (toggleApiKey) toggleApiKey.addEventListener("click", () => {
        settingApiKey.type = settingApiKey.type === "password" ? "text" : "password";
    });

    $("#settings-cancel")?.addEventListener("click", () => closeModal(modalSettings));
    $("#settings-save")?.addEventListener("click", () => {
        const key = settingApiKey.value.trim();
        const name = settingDisplayName.value.trim();
        if (key) localStorage.setItem("geofix_api_key", key);
        else localStorage.removeItem("geofix_api_key");

        if (name) {
            localStorage.setItem("geofix_display_name", name);
            updateProfileUI(name);
        } else {
            localStorage.removeItem("geofix_display_name");
            updateProfileUI("Guest");
        }
        closeModal(modalSettings);
    });

    function updateProfileUI(name) {
        $("#sidebar-username").textContent = name || "Guest";
        // We could also update avatar if we had one
    }

    // ── Theme Toggle ───────────────────────────────
    const themeToggle = $("#theme-toggle");
    const themeMoon = $(".theme-moon");
    const themeSun = $(".theme-sun");

    function setTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("geofix_theme", theme);
        if (theme === "light") {
            themeMoon.style.display = "none";
            themeSun.style.display = "block";
        } else {
            themeMoon.style.display = "block";
            themeSun.style.display = "none";
        }
    }

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = localStorage.getItem("geofix_theme") || "dark";
            setTheme(current === "dark" ? "light" : "dark");
        });

        // Init theme
        const savedTheme = localStorage.getItem("geofix_theme") || "dark";
        setTheme(savedTheme);
    }

    // ═══════════════════════════════════════════════
    // EVENT LISTENERS
    // ═══════════════════════════════════════════════

    btnSend.addEventListener("click", sendMessage);
    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    messageInput.addEventListener("input", () => { updateSendBtn(); autoResize(); });

    btnNewChat.addEventListener("click", newChat);
    searchInput.addEventListener("input", filterConvs);

    fileInput.addEventListener("change", () => {
        const files = Array.from(fileInput.files);
        if (!files.length) return;
        pendingFiles = files;
        filePreview.hidden = false;
        filePreview.innerHTML = files.map((f, i) => `
      <div class="file-chip">📎 ${esc(f.name)}<button class="remove-file" data-index="${i}">×</button></div>`).join("");
        filePreview.querySelectorAll(".remove-file").forEach((btn) => {
            btn.addEventListener("click", () => {
                pendingFiles.splice(+btn.dataset.index, 1);
                if (!pendingFiles.length) { filePreview.hidden = true; filePreview.innerHTML = ""; }
                else fileInput.dispatchEvent(new Event("change"));
            });
        });
        fileInput.value = "";
    });

    $$(".starter-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            messageInput.value = btn.dataset.message;
            updateSendBtn();
            sendMessage();
        });
    });

    // ═══════════════════════════════════════════════
    // KEYBOARD SHORTCUTS
    // ═══════════════════════════════════════════════

    document.addEventListener("keydown", (e) => {
        const mod = e.ctrlKey || e.metaKey;
        if (mod && e.key === "/") { e.preventDefault(); messageInput.focus(); }
        if (mod && e.key === "n") { e.preventDefault(); newChat(); }
        if (mod && e.key === "b") { e.preventDefault(); toggleSidebar(); }
        if (e.key === "Escape") {
            if (!modalWorkspace.hidden) { closeModal(modalWorkspace); return; }
            if (!modalSettings.hidden) { closeModal(modalSettings); return; }
            if (sidebarIsOpen && window.innerWidth <= 768) closeSidebar();
            else messageInput.blur();
        }
    });

    // ═══════════════════════════════════════════════
    // INIT
    // ═══════════════════════════════════════════════

    // Load workspace name
    const savedWsName = localStorage.getItem("geofix_ws_name");
    if (savedWsName) {
        const logoText = $(".logo-text");
        if (logoText) logoText.textContent = savedWsName;
    }

    // Load User Profile
    const savedName = localStorage.getItem("geofix_display_name");
    if (savedName) updateProfileUI(savedName);

    // Check API Key (New Feature)
    const savedKey = localStorage.getItem("geofix_api_key");
    if (!savedKey) {
        setTimeout(() => {
            openModal(modalSettings);
            appendMessage("assistant", "👋 Welcome! Please enter your **Gemini API Key** in settings to start.");
        }, 1000);
    }

    // Load default model
    const savedModel = localStorage.getItem("geofix_ws_model");
    if (savedModel) modelSelect.value = savedModel;

    connect();
    loadConversations();
    messageInput.focus();

    console.log(
        "%c🌍 GeoFix v2.1%c Custom Frontend",
        "background:#2dd4bf;color:#0a0a0a;font-weight:bold;padding:4px 8px;border-radius:4px 0 0 4px",
        "background:#1e1e1e;color:#2dd4bf;font-weight:bold;padding:4px 8px;border-radius:0 4px 4px 0"
    );
})();

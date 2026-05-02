// --- STATE ---
let currentSessionId = null;
const $ = (id) => document.getElementById(id);
const chatContainer = $('chatContainer');
const sessionList = $('sessionList');
const userInput = $('userInput');
const sendBtn = $('sendBtn');
const emptyState = $('emptyState');
const sidebar = $('sidebar');
const voiceBtn = $('voiceBtn');
const closeSidebarBtn = $('closeSidebarBtn');

marked.use({ breaks: true });

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
    loadSessions();
    loadStorage();
    const theme = localStorage.getItem('theme') || 'light';
    if (theme === 'dark') document.documentElement.classList.add('dark');
    userInput.focus();

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
});

// --- THEME ---
$('themeToggle').addEventListener('click', () => {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
});

// --- AUTH ---
async function logout() {
    try {
        await fetch('/auth/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (e) {
        console.error("Logout failed:", e);
    }
}

// --- SIDEBAR ---
function toggleSidebar() {
    const isMobile = window.innerWidth < 768;
    if (isMobile) {
        sidebar.classList.toggle('mobile-hidden');
        sidebar.classList.toggle('mobile-show');
        closeSidebarBtn.style.display = sidebar.classList.contains('mobile-show') ? 'flex' : 'none';
    }
}

// --- VOICE ---
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SR();
    recognition.continuous = false;
    recognition.onstart = () => voiceBtn.classList.add('recording');
    recognition.onend = () => voiceBtn.classList.remove('recording');
    recognition.onresult = (e) => { userInput.value = e.results[0][0].transcript; sendMessage(); };
    voiceBtn.addEventListener('click', () => recognition.start());
} else { voiceBtn.style.display = 'none'; }

// --- HELPERS ---
function setInput(text) { userInput.value = text; userInput.focus(); }

// --- SIDEBAR LOADING ---
function showSidebarLoading(text) {
    const el = $('sidebarLoading');
    $('sidebarLoadingText').textContent = text || 'Loading...';
    el.classList.add('active');
}
function hideSidebarLoading() {
    $('sidebarLoading').classList.remove('active');
}

// --- MODAL ---
let modalCallback = null;
function showModal(title, desc, btnText, iconClass, cb) {
    $('modalTitle').textContent = title;
    $('modalDesc').textContent = desc;
    $('modalConfirmBtn').textContent = btnText;
    $('modalIcon').className = 'modal-icon ' + (iconClass || 'danger');
    modalCallback = cb;
    $('modalConfirmBtn').onclick = () => { hideModal(); if (modalCallback) modalCallback(); };
    $('confirmModal').classList.add('show');
}
function hideModal() { $('confirmModal').classList.remove('show'); }

function showClearAllModal() {
    showModal(
        'Clear All Chats',
        'This will permanently delete all your chat sessions and messages. This action cannot be undone.',
        'Delete All',
        'danger',
        clearAllSessions
    );
}

function showDeleteModal(sessionId) {
    showModal(
        'Delete Chat',
        'Are you sure you want to delete this chat session? This cannot be undone.',
        'Delete',
        'warn',
        () => deleteSession(sessionId)
    );
}

// --- STORAGE ---
async function loadStorage() {
    try {
        const res = await fetch('/storage');
        const data = await res.json();
        const fill = $('storageFill');
        const text = $('storageText');
        const pct = $('storagePct');
        const banner = $('storageBanner');
        const bannerText = $('bannerText');

        text.textContent = data.size_pretty + ' / ' + (data.limit_pretty || '500 MB');
        pct.textContent = data.percentage + '%';
        fill.style.width = Math.min(data.percentage, 100) + '%';

        fill.classList.remove('warning', 'critical');
        banner.classList.remove('warning', 'critical');

        if (data.critical) {
            fill.classList.add('critical');
            banner.classList.add('critical');
            bannerText.textContent = '⚠️ Storage is almost full! Delete old chats to free space.';
        } else if (data.warning) {
            fill.classList.add('warning');
            banner.classList.add('warning');
            bannerText.textContent = 'Storage is getting full (' + data.percentage + '%). Consider cleaning up old chats.';
        }
    } catch (e) { console.error('Storage check failed:', e); }
}

// --- SESSION MANAGEMENT ---
async function loadSessions() {
    try {
        const res = await fetch('/sessions');
        const data = await res.json();
        sessionList.innerHTML = '';

        if (data.sessions && data.sessions.length > 0) {
            data.sessions.forEach(s => {
                const div = document.createElement('div');
                div.className = 'session-item' + (s.id === currentSessionId ? ' active' : '');
                div.onclick = () => { loadChat(s.id); if (window.innerWidth < 768) toggleSidebar(); };
                div.innerHTML = `
                    <span class="title">${escHtml(s.title)}</span>
                    <div class="session-actions">
                        <button onclick="event.stopPropagation(); renameSession('${s.id}', '${escAttr(s.title)}')" title="Rename">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
                        </button>
                        <button onclick="event.stopPropagation(); showDeleteModal('${s.id}')" title="Delete">
                            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                        </button>
                    </div>`;
                sessionList.appendChild(div);
            });
        } else {
            sessionList.innerHTML = '<div style="padding:24px;text-align:center;font-size:12px;color:var(--text-muted);">No chat history yet.</div>';
        }
    } catch (e) { console.error(e); }
}

async function renameSession(id, currentTitle) {
    const newTitle = prompt("Rename chat:", currentTitle);
    if (newTitle && newTitle !== currentTitle) {
        showSidebarLoading('Renaming...');
        try {
            await fetch(`/sessions/${id}/rename`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle })
            });
            loadSessions();
        } catch (e) { alert("Failed to rename"); }
        finally { hideSidebarLoading(); }
    }
}

async function deleteSession(id) {
    showSidebarLoading('Deleting...');
    try {
        await fetch(`/sessions/${id}`, { method: 'DELETE' });
        if (currentSessionId === id) startNewChat();
        else loadSessions();
        loadStorage();
    } catch (e) { alert("Failed to delete"); }
    finally { hideSidebarLoading(); }
}

async function clearAllSessions() {
    showSidebarLoading('Clearing all chats...');
    try {
        await fetch('/sessions/clear-all', { method: 'DELETE' });
        startNewChat();
        loadStorage();
    } catch (e) { alert("Failed to clear sessions"); }
    finally { hideSidebarLoading(); }
}

async function loadChat(id) {
    currentSessionId = id;
    emptyState.style.display = 'none';
    chatContainer.innerHTML = '';
    showSidebarLoading('Loading chat...');
    loadSessions();
    try {
        const res = await fetch(`/sessions/${id}`);
        const data = await res.json();
        if (data.session.messages && data.session.messages.length > 0) {
            data.session.messages.forEach(msg => {
                appendMessage(msg.user, true);
                appendMessage(msg.ai, false);
            });
        } else {
            emptyState.style.display = 'flex';
            chatContainer.appendChild(emptyState);
        }
    } catch (e) { console.error(e); }
    finally { hideSidebarLoading(); }
    scrollToBottom();
}

function startNewChat() {
    currentSessionId = null;
    chatContainer.innerHTML = '';
    chatContainer.appendChild(emptyState);
    emptyState.style.display = 'flex';
    userInput.value = '';
    loadSessions();
    userInput.focus();
}

function appendMessage(text, isUser) {
    emptyState.style.display = 'none';
    const row = document.createElement('div');
    row.className = 'message-row ' + (isUser ? 'user' : 'ai');
    const bubble = document.createElement('div');
    bubble.className = 'bubble markdown-content ' + (isUser ? 'user' : 'ai');
    bubble.innerHTML = isUser ? escHtml(text) : DOMPurify.sanitize(marked.parse(text));
    row.appendChild(bubble);
    chatContainer.appendChild(row);
    scrollToBottom();
    return bubble;
}

// --- CHAT ---
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    appendMessage(text, true);
    userInput.value = '';
    sendBtn.disabled = true;
    showSidebarLoading('Generating...');

    const aiBubble = appendMessage('...', false);
    // Animated typing indicator (bouncing dots like ChatGPT)
    aiBubble.innerHTML = `
        <div class="typing-indicator">
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
            <span class="typing-label">Generating response...</span>
        </div>`;

    let fullText = '';
    try {
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: currentSessionId })
        });

        // Handle HTTP errors immediately
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || `Server error (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let receivedContent = false;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.session_id) {
                            if (currentSessionId !== data.session_id) {
                                currentSessionId = data.session_id;
                                if (data.is_new) loadSessions();
                            }
                        } else if (data.content) {
                            if (!receivedContent) {
                                receivedContent = true;
                                aiBubble.innerHTML = ''; // Clear typing indicator on first token
                            }
                            fullText += data.content;
                            aiBubble.innerHTML = DOMPurify.sanitize(marked.parse(fullText));
                            scrollToBottom();
                        } else if (data.error) {
                            throw new Error(data.error);
                        }
                    } catch (pe) {
                        if (pe.message && pe.message !== 'Unexpected end of JSON input') throw pe;
                    }
                }
            }
        }

        // If stream ended but no content received
        if (!receivedContent && !fullText) {
            aiBubble.innerHTML = '<div class="error-msg">⚠️ No response received. Please try again.</div>';
        }
    } catch (e) {
        console.error('Chat error:', e);
        const errMsg = e.message || 'Unknown error';
        aiBubble.innerHTML = `
            <div class="error-msg">
                <span>⚠️ ${escHtml(errMsg)}</span>
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:6px;">
                Check your Supabase credentials in .env and restart the server.
            </div>`;
    } finally {
        sendBtn.disabled = false;
        hideSidebarLoading();
        loadSessions();
        loadStorage();
        userInput.focus();
    }
}

function scrollToBottom() { chatContainer.scrollTop = chatContainer.scrollHeight; }

// --- UTILS ---
function escHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
function escAttr(s) {
    return s.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

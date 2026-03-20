import './style.css';

const token = localStorage.getItem('access_token');
if (!token) {
  window.location.href = '/login.html';
}

const API_BASE = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/api/chat/ws';

const uploadForm = document.getElementById('uploadForm');
const urlInput = document.getElementById('urlInput');
const uploadStatus = document.getElementById('uploadStatus');
const uploadStatusText = document.getElementById('uploadStatusText');
const videoChip = document.getElementById('videoChip');
const videoChipValue = document.getElementById('videoChipValue');

const chatMessages = document.getElementById('chatMessages');
const welcomeState = document.getElementById('welcomeState');
const typingIndicator = document.getElementById('typingIndicator');

const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const chatList = document.getElementById('chatList');
const currentChatTitle = document.getElementById('currentChatTitle');
const logoutBtn = document.getElementById('logoutBtn');
const connectionBadge = document.getElementById('connectionBadge');
const connectionText = document.getElementById('connectionText');

let currentConvId = null;
let currentVideoId = null;
let chatSocket = null;
let reconnectTimer = null;
let shouldReconnect = true;
let pendingAssistantContentEl = null;
let awaitingAssistant = false;

function formatMessageTime(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function setVideoChip(videoId) {
  currentVideoId = videoId || null;
  if (!currentVideoId) {
    videoChip.hidden = true;
    videoChipValue.textContent = '';
    return;
  }

  videoChip.hidden = false;
  videoChipValue.textContent = currentVideoId;
}

async function fetchAuth(url, options = {}) {
  const headers = {
    ...options.headers,
    Authorization: `Bearer ${token}`
  };

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers
  });

  if (response.status === 401) {
    localStorage.removeItem('access_token');
    window.location.href = '/login.html';
  }
  return response;
}

function setConnectionState(isConnected, text) {
  connectionBadge.classList.toggle('connected', isConnected);
  connectionText.textContent = text;
}

function connectWebSocket() {
  if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  setConnectionState(false, 'Connecting');
  const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
  chatSocket = ws;

  ws.onopen = () => {
    setConnectionState(true, 'Online');
  };

  ws.onmessage = (event) => {
    handleSocketMessage(event.data);
  };

  ws.onerror = () => {
    setConnectionState(false, 'Error');
    if (awaitingAssistant) {
      appendMessage('assistant', 'Connection error while waiting for the reply. Please retry.', { timestamp: new Date() });
      resetPendingState();
    }
  };

  ws.onclose = () => {
    setConnectionState(false, 'Offline');
    if (awaitingAssistant) {
      appendMessage('assistant', 'Chat connection closed before the reply completed. Please retry.', { timestamp: new Date() });
      resetPendingState();
    }
    if (shouldReconnect) {
      scheduleReconnect();
    }
  };
}

function scheduleReconnect() {
  if (reconnectTimer) {
    return;
  }
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, 2000);
}

function handleSocketMessage(rawData) {
  let msg;
  try {
    msg = JSON.parse(rawData);
  } catch {
    appendMessage('assistant', 'Invalid message received from server.', { timestamp: new Date() });
    resetPendingState();
    return;
  }

  if (msg.type === 'ready' || msg.type === 'pong') {
    return;
  }

  if (msg.type === 'assistant_start') {
    typingIndicator.classList.remove('visible');
    const created = appendMessage('assistant', '', { timestamp: new Date() });
    pendingAssistantContentEl = created.content;
    return;
  }

  if (msg.type === 'assistant_chunk') {
    if (!pendingAssistantContentEl) {
      const created = appendMessage('assistant', '', { timestamp: new Date() });
      pendingAssistantContentEl = created.content;
    }
    pendingAssistantContentEl.textContent += msg.delta || '';
    scrollToBottom();
    return;
  }

  if (msg.type === 'assistant_end') {
    resetPendingState();
    return;
  }

  if (msg.type === 'error') {
    appendMessage('assistant', msg.message || 'Server error while processing message.', { timestamp: new Date() });
    resetPendingState();
  }
}

function resetPendingState() {
  pendingAssistantContentEl = null;
  awaitingAssistant = false;
  typingIndicator.classList.remove('visible');
  chatInput.disabled = false;
  sendBtn.disabled = false;
  chatInput.focus();
  scrollToBottom();
}

async function loadConversations() {
  try {
    const res = await fetchAuth('/chat/conversations');
    const convs = await res.json();

    chatList.innerHTML = '';
    convs.forEach((c) => {
      const div = document.createElement('div');
      div.className = `chat-item ${c.id === currentConvId ? 'active' : ''}`;
      div.dataset.conversationId = c.id;
      const icon = document.createElement('span');
      icon.className = 'chat-item-icon';
      icon.textContent = '◦';
      const title = document.createElement('span');
      title.className = 'chat-item-title';
      title.textContent = c.title;
      div.appendChild(icon);
      div.appendChild(title);
      div.onclick = () => selectConversation(c.id, c.title);
      chatList.appendChild(div);
    });
  } catch (err) {
    console.error('Failed to load chats', err);
  }
}

async function loadConversationMessages(conversationId) {
  try {
    const res = await fetchAuth(`/chat/conversations/${conversationId}/messages`);
    const messages = await res.json();
    chatMessages.innerHTML = '';

    if (!Array.isArray(messages) || messages.length === 0) {
      chatMessages.innerHTML = `
        <div class="welcome-state" id="welcomeState">
          <div class="welcome-icon">AI</div>
          <div class="welcome-title">Start a new conversation</div>
          <div class="welcome-subtitle">
            Ask a question directly or link a video above to ground this chat.
          </div>
        </div>
      `;
      return;
    }

    messages.forEach((m) => {
      appendMessage(m.role, m.content, { timestamp: m.created_at });
    });
    scrollToBottom();
  } catch (err) {
    console.error('Failed to load conversation history', err);
  }
}

async function selectConversation(id, title) {
  currentConvId = id;
  currentChatTitle.textContent = title;

  document.querySelectorAll('.chat-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.conversationId === id);
  });

  chatInput.disabled = false;
  sendBtn.disabled = false;
  chatInput.placeholder = 'Ask something...';

  setVideoChip(null);
  urlInput.value = '';
  showUploadStatus('', '');
  await loadConversationMessages(id);
  await loadConversations();
}

newChatBtn.addEventListener('click', async () => {
  try {
    const res = await fetchAuth('/chat/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: `New Chat ${new Date().toLocaleTimeString()}` })
    });
    const data = await res.json();
    await selectConversation(data.conversation_id, data.title);
  } catch (err) {
    console.error('Failed to create chat', err);
  }
});

function socketReady() {
  return chatSocket && chatSocket.readyState === WebSocket.OPEN;
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || !currentConvId || awaitingAssistant) {
    return;
  }

  if (!socketReady()) {
    appendMessage('assistant', 'Chat connection is offline. Reconnecting, please retry.', { timestamp: new Date() });
    connectWebSocket();
    return;
  }

  appendMessage('user', text, { timestamp: new Date() });
  chatInput.value = '';
  autoResizeTextarea();

  awaitingAssistant = true;
  chatInput.disabled = true;
  sendBtn.disabled = true;
  typingIndicator.classList.add('visible');
  scrollToBottom();

  chatSocket.send(JSON.stringify({
    type: 'chat_message',
    conversation_id: currentConvId,
    message: text,
    video_id: currentVideoId
  }));
}

function appendMessage(role, text, options = {}) {
  if (welcomeState && welcomeState.parentNode) {
    welcomeState.parentNode.removeChild(welcomeState);
  }

  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.textContent = role === 'assistant' ? 'AI' : 'U';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  const content = document.createElement('div');
  content.className = 'message-content';
  content.textContent = text;

  const meta = document.createElement('div');
  meta.className = 'message-meta';
  const prefix = role === 'assistant' ? 'AI' : 'You';
  meta.textContent = `${prefix} • ${formatMessageTime(options.timestamp)}`;

  bubble.appendChild(content);
  bubble.appendChild(meta);
  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chatMessages.appendChild(msg);

  scrollToBottom();
  return { msg, content, meta };
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('input', autoResizeTextarea);

function autoResizeTextarea() {
  chatInput.style.height = 'auto';
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
}

uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;
  if (!currentConvId) {
    showUploadStatus('Create or select a chat before uploading a video.', 'error');
    return;
  }

  const videoId = extractVideoId(url);
  if (!videoId) {
    showUploadStatus('Invalid YouTube URL.', 'error');
    return;
  }

  const submitBtn = uploadForm.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing...';
  }
  showUploadStatus('Fetching transcript and generating embeddings...', '');

  try {
    const formData = new FormData();
    formData.append('url', url);
    formData.append('conversation_id', currentConvId);

    const res = await fetch(`${API_BASE}/upload-url`, {
      method: 'POST',
      body: formData
    });

    const data = await res.json();

    if (res.ok) {
      setVideoChip(data.video_id);
      showUploadStatus(`Video ready (${data.video_id})`, 'success');
    } else {
      showUploadStatus(data.detail || data.message || 'Failed to process video.', 'error');
    }
  } catch (err) {
    showUploadStatus('Server error. Check backend status.', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Set Video';
    }
  }
});

function extractVideoId(url) {
  const patterns = [
    /(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})/,
    /(?:youtu\.be\/)([a-zA-Z0-9_-]{11})/,
    /(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})/
  ];

  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }

  if (/^[a-zA-Z0-9_-]{11}$/.test(url)) return url;
  return null;
}

function showUploadStatus(text, type) {
  uploadStatus.classList.add('visible');
  uploadStatus.className = `upload-status visible ${type}`;
  uploadStatusText.textContent = text;
}

logoutBtn.addEventListener('click', async () => {
  try {
    await fetchAuth('/logout', { method: 'POST' });
  } catch (e) {
    console.error(e);
  }

  shouldReconnect = false;
  if (chatSocket) {
    chatSocket.close();
  }

  localStorage.removeItem('access_token');
  window.location.href = '/login.html';
});

connectWebSocket();
loadConversations();

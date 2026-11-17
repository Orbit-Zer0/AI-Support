let conversationId = null;
let sending = false;

let chatEpoch = 0;

let activeController = null;
let stopRequested = false;

const STOP_COOLDOWN_MS = 2000;


const PURIFY_CONFIG = {
  ALLOWED_TAGS: [
    'p', 'br', 'hr', 'strong', 'em', 'b', 'i', 'del', 'code', 'pre',
    'ul', 'ol', 'li', 'blockquote', 'a',
    'h1', 'h2', 'h3', 'h4',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
  ],
  ALLOWED_ATTR: ['href'],
};

if (window.DOMPurify) {
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A') {
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer');
    }
  });
}

function renderBotText(element, text) {
  if (window.marked && window.DOMPurify) {
    const html = String(marked.parse(text, { breaks: true }));
    element.innerHTML = DOMPurify.sanitize(html, PURIFY_CONFIG);
  } else {
    element.style.whiteSpace = 'pre-wrap';
    element.textContent = text;
  }
}


function scrollToBottom() {
  const box = $('messages');
  box.scrollTop = box.scrollHeight;
}

function isNearBottom() {
  const box = $('messages');
  return box.scrollHeight - box.scrollTop - box.clientHeight < 120;
}

function setChatTitle(text) {
  $('chat-title').textContent = text || '';
}

function formatClock(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const today = date.toDateString() === new Date().toDateString();
  const options = today
    ? { hour: '2-digit', minute: '2-digit' }
    : { dateStyle: 'short', timeStyle: 'short' };
  try {
    return new Intl.DateTimeFormat(currentLang, options).format(date);
  } catch (error) {
    return date.toLocaleString();
  }
}

function formatSeconds(ms) {
  const seconds = Math.round(ms / 100) / 10;
  try {
    return seconds.toLocaleString(currentLang, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  } catch (error) {
    return seconds.toFixed(1);
  }
}

function botMetaText(info) {
  if (!info) return '';
  const parts = [];
  const clock = formatClock(info.created_at);
  if (clock) parts.push(clock);
  if (typeof info.first_token_ms === 'number') {
    parts.push(t('meta.thought').replace('{seconds}', formatSeconds(info.first_token_ms)));
  }
  if (typeof info.duration_ms === 'number') {
    parts.push(t('meta.total').replace('{seconds}', formatSeconds(info.duration_ms)));
  }
  if (info.interrupted) parts.push(t('meta.stopped'));
  return parts.join(' · ');
}

function fallbackCopy(text) {
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.append(area);
  area.select();

  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch (error) {
    ok = false;
  }
  area.remove();
  return ok;
}

function setCopyButtonLabel(button, label) {
  button.title = label;
  button.setAttribute('aria-label', label);
}

async function copyText(text, button) {
  let ok = false;
  try {
    await navigator.clipboard.writeText(text);
    ok = true;
  } catch (error) {
    ok = fallbackCopy(text);
  }

  button.dataset.icon = ok ? 'check' : 'x';
  renderIcons(button);
  setCopyButtonLabel(button, ok ? t('btn.copied') : t('btn.copyFailed'));

  setTimeout(() => {
    button.dataset.icon = 'copy';
    renderIcons(button);
    setCopyButtonLabel(button, t('btn.copy'));
  }, 1500);
}

function buildCopyTools(text) {
  const tools = document.createElement('div');
  tools.className = 'message-tools';

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'icon-btn copy-btn';
  button.dataset.icon = 'copy';
  setCopyButtonLabel(button, t('btn.copy'));
  renderIcons(button);
  button.addEventListener('click', () => copyText(text, button));

  tools.append(button);
  return tools;
}


function buildBotFooter(text, { copy, info }) {
  const footer = document.createElement('div');
  footer.className = 'message-footer';

  const meta = document.createElement('span');
  meta.className = 'message-meta';
  meta.textContent = botMetaText(info);
  if (info && typeof info.first_token_ms === 'number') meta.title = t('meta.tooltip');
  footer.append(meta);

  if (copy) footer.append(buildCopyTools(text));
  return footer;
}

function addBotMessage(text, { copy = true, info = null } = {}) {
  const element = document.createElement('div');
  element.className = 'message message-bot';

  const content = document.createElement('div');
  content.className = 'message-content';
  renderBotText(content, text);
  element.append(content);

  if (copy || info) element.append(buildBotFooter(text, { copy, info }));

  $('messages').append(element);
  scrollToBottom();
  return element;
}

function startStreamBubble() {
  const element = document.createElement('div');
  element.className = 'message message-bot';

  const content = document.createElement('div');
  content.className = 'message-content';
  element.append(content);

  $('messages').append(element);
  return { element, content };
}

function finishStreamBubble(bubble, text, info, crisis) {
  renderBotText(bubble.content, text);
  const oldFooter = bubble.element.querySelector('.message-footer');
  if (oldFooter) oldFooter.remove();
  bubble.element.append(buildBotFooter(text, { copy: true, info }));
  bubble.element.classList.toggle('message-crisis', Boolean(crisis));
}

function addUserMessage(text, iso = null) {
  const wrapper = document.createElement('div');
  wrapper.className = 'outgoing';

  const bubble = document.createElement('div');
  bubble.className = 'message message-user';
  bubble.textContent = text;

  const meta = document.createElement('div');
  meta.className = 'message-meta user-meta';
  meta.textContent = formatClock(iso || new Date().toISOString());

  wrapper.append(bubble, meta);
  $('messages').append(wrapper);
  scrollToBottom();
  return { text, wrapper, bubble, meta, status: null };
}

function applyUserInfo(item, info) {
  if (info && info.created_at) item.meta.textContent = formatClock(info.created_at);
}

function addNotice(text) {
  const element = document.createElement('div');
  element.className = 'message-error';
  element.setAttribute('role', 'alert');
  element.textContent = text;
  $('messages').append(element);
  scrollToBottom();
  return element;
}

function startThinking() {
  const element = document.createElement('div');
  element.className = 'message message-bot message-typing';
  const startedAt = performance.now();

  const update = () => {
    const seconds = Math.floor((performance.now() - startedAt) / 1000);
    element.textContent = seconds >= 1
      ? t('chat.thinking').replace('{seconds}', seconds)
      : t('chat.thinkingShort');
  };
  update();
  const timer = setInterval(update, 500);

  $('messages').append(element);
  scrollToBottom();
  return {
    stop() {
      clearInterval(timer);
      element.remove();
    },
  };
}

function buildStatusRow(item, reason, retryable) {
  const row = document.createElement('div');
  row.className = 'message-status';
  row.setAttribute('role', 'alert');

  const text = document.createElement('span');
  text.textContent = `${t('chat.failed')}: ${reason}`;
  row.append(text);

  if (retryable) {
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'link-button status-retry';
    retry.textContent = t('btn.retry');
    retry.disabled = sending;
    retry.addEventListener('click', () => retryItem(item));
    row.append(retry);
  }

  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'link-button';
  remove.textContent = t('btn.delete');
  remove.addEventListener('click', () => item.wrapper.remove());
  row.append(remove);

  return row;
}

function setItemState(item, state, reason = '', retryable = true) {
  item.bubble.classList.toggle('is-pending', state === 'pending');
  item.bubble.classList.toggle('is-failed', state === 'failed');

  if (item.status) {
    item.status.remove();
    item.status = null;
  }
  if (state !== 'failed') return;

  item.status = buildStatusRow(item, reason, retryable);
  item.wrapper.append(item.status);
  scrollToBottom();
}

function setStopVisible(visible) {
  $('stop').hidden = !visible;
  $('send').hidden = visible;
}

function setSending(value) {
  sending = value;
  $('send').disabled = value;
  if (!value) setStopVisible(false);
  document.querySelectorAll('.status-retry').forEach((button) => {
    button.disabled = value;
  });
}

function resetChat() {
  chatEpoch += 1;
  if (activeController) activeController.abort();
  activeController = null;
  stopRequested = false;
  conversationId = null;
  setSending(false);
  $('messages').replaceChildren();
  addBotMessage(t('welcome'), { copy: false });
  setChatTitle('');
  updateActiveChat();
}

function autoResizeInput() {
  const input = $('input');
  input.style.height = 'auto';
  const border = input.offsetHeight - input.clientHeight;
  input.style.height = Math.min(input.scrollHeight + border, 160) + 'px';
}


function handleWholeResponse(item, result, hadConversation) {
  if (result.ok) {
    const data = result.data;
    conversationId = data.conversation_id;
    applyUserInfo(item, data.user_message);
    setItemState(item, 'sent');
    const bubble = addBotMessage(data.response, { info: data.bot_message });
    if (data.crisis) bubble.classList.add('message-crisis');
    afterReply(conversationId, !hadConversation);
    return;
  }

  if (result.status === 401) {
    logout('err.session_expired');
    return;
  }

  let reason;
  if (result.status === 404 && hadConversation) {
    conversationId = null;
    reason = t('err.conversation_not_found');
  } else {
    reason = describeChatError(result);
  }
  setItemState(item, 'failed', reason, result.status !== 400);
}

function scheduleStreamRender(stream) {
  if (stream.renderQueued) return;
  stream.renderQueued = true;
  requestAnimationFrame(() => {
    stream.renderQueued = false;
    if (stream.finished || !stream.bubble) return;
    const follow = isNearBottom();
    renderBotText(stream.bubble.content, stream.text);
    if (follow) scrollToBottom();
  });
}

function interruptStream(item, stream, notice) {
  stream.finished = true;
  setItemState(item, 'sent');
  const info = { created_at: new Date().toISOString(), interrupted: true };
  finishStreamBubble(stream.bubble, stream.text, info, stream.crisis);
  if (notice) addNotice(notice);
  setTimeout(() => refreshChatList(), 1500);
  if (stream.crisis) openHelp();
}

function handleStreamEvent(event, item, thinking, stream, hadConversation) {
  switch (event.type) {
    case 'start':
      conversationId = event.conversation_id;
      stream.crisis = Boolean(event.crisis);
      updateActiveChat();
      break;

    case 'delta':
      if (!stream.bubble) {
        thinking.stop();
        stream.bubble = startStreamBubble();
        setItemState(item, 'sent');
        scrollToBottom();
      }
      stream.text += event.text;
      scheduleStreamRender(stream);
      break;

    case 'done': {
      stream.finished = true;
      thinking.stop();
      conversationId = event.conversation_id;
      applyUserInfo(item, event.user_message);
      setItemState(item, 'sent');
      if (!stream.bubble) stream.bubble = startStreamBubble();
      const follow = isNearBottom();
      finishStreamBubble(stream.bubble, event.response, event.bot_message, event.crisis);
      if (follow) scrollToBottom();
      afterReply(conversationId, !hadConversation);
      break;
    }

    case 'error': {
      thinking.stop();
      if (stream.bubble && stream.text) {
        interruptStream(item, stream, t('err.stream_failed'));
      } else {
        stream.finished = true;
        const key = 'err.' + event.code;
        setItemState(item, 'failed', t(key) !== key ? t(key) : t('err.generic'), true);
      }
      break;
    }

    default:
      break;
  }
}

async function consumeStream(response, item, thinking, stream, hadConversation) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const handle = (line) => {
    const text = line.trim();
    if (text) handleStreamEvent(JSON.parse(text), item, thinking, stream, hadConversation);
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index;
    while ((index = buffer.indexOf('\n')) >= 0) {
      handle(buffer.slice(0, index));
      buffer = buffer.slice(index + 1);
    }
  }
  handle(buffer + decoder.decode());
}

function handleStreamFailure(item, stream, error) {
  console.error(error);
  if (stream.bubble && stream.text) {
    interruptStream(item, stream, t('err.stream_failed'));
    return;
  }
  setItemState(item, 'failed', t('err.network'), true);
}

function handleAbort(item, stream) {
  if (stream.bubble && stream.text) {
    interruptStream(item, stream, '');
    return;
  }
  setItemState(item, 'failed', t('err.stopped'), true);
}

async function deliver(item) {
  if (!localStorage.getItem(TOKEN_KEY)) {
    logout('err.session_expired');
    return;
  }

  const epoch = chatEpoch;
  const hadConversation = conversationId !== null;
  const controller = new AbortController();
  activeController = controller;
  stopRequested = false;

  setSending(true);
  setStopVisible(true);
  setItemState(item, 'pending');
  $('messages').setAttribute('aria-busy', 'true');
  const thinking = startThinking();
  const stream = { bubble: null, text: '', finished: false, renderQueued: false, crisis: false };

  try {
    const body = { message: item.text };
    if (hadConversation) body.conversation_id = conversationId;

    const response = await fetch('/api/chat/stream/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (epoch !== chatEpoch) return;

    const contentType = response.headers.get('Content-Type') || '';
    if (!contentType.includes('application/x-ndjson')) {
      let data = null;
      try {
        data = await response.json();
      } catch (exception) {
      }
      thinking.stop();
      handleWholeResponse(item, { ok: response.ok, status: response.status, data }, hadConversation);
      return;
    }

    await consumeStream(response, item, thinking, stream, hadConversation);
    if (epoch !== chatEpoch) return;
    thinking.stop();
    if (!stream.finished) handleStreamFailure(item, stream, new Error('Stream ended early'));
  } catch (error) {
    if (epoch !== chatEpoch) return;
    thinking.stop();
    if (error && error.name === 'AbortError') {
      handleAbort(item, stream);
    } else {
      handleStreamFailure(item, stream, error);
    }
  } finally {
    thinking.stop();
    if (epoch === chatEpoch) {
      $('messages').removeAttribute('aria-busy');
      activeController = null;
      setStopVisible(false);
      if (stopRequested) {
        stopRequested = false;
        setTimeout(() => {
          if (epoch === chatEpoch) setSending(false);
        }, STOP_COOLDOWN_MS);
      } else {
        setSending(false);
      }
    }
  }
}

function sendFromInput() {
  const input = $('input');
  const text = input.value.trim();
  if (!text || sending) return;

  const item = addUserMessage(text);
  input.value = '';
  autoResizeInput();
  input.focus();
  deliver(item);
}

function retryItem(item) {
  if (sending) return;
  $('messages').append(item.wrapper);
  deliver(item);
}

function stopGeneration() {
  if (!activeController) return;
  stopRequested = true;
  activeController.abort();
}


async function openConversation(id) {
  if (sending) return;
  setSending(true);
  try {
    const result = await api(`/api/conversations/${id}/`, { headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      $('chats-error').textContent = t('err.conversation_load');
      return;
    }
    $('chats-error').textContent = '';

    chatEpoch += 1;
    conversationId = result.data.id;
    $('messages').replaceChildren();
    for (const message of result.data.messages) {
      if (message.role === 'user') {
        addUserMessage(message.content, message.created_at);
      } else {
        const bubble = addBotMessage(message.content, { info: message });
        if (message.crisis) bubble.classList.add('message-crisis');
      }
    }
    setChatTitle(result.data.title);
    updateActiveChat();
    closeSidebarDrawer();
    scrollToBottom();
    $('input').focus();
  } catch (error) {
    $('chats-error').textContent = t('err.network');
    console.error(error);
  } finally {
    setSending(false);
  }
}
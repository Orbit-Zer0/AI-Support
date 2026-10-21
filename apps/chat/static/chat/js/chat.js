let conversationId = null;
let sending = false;

let chatEpoch = 0;


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

function setChatTitle(text) {
  $('chat-title').textContent = text || '';
}

function addBotMessage(text) {
  const element = document.createElement('div');
  element.className = 'message message-bot';
  renderBotText(element, text);
  $('messages').append(element);
  scrollToBottom();
  return element;
}

function addUserMessage(text) {
  const wrapper = document.createElement('div');
  wrapper.className = 'outgoing';

  const bubble = document.createElement('div');
  bubble.className = 'message message-user';
  bubble.textContent = text;

  wrapper.append(bubble);
  $('messages').append(wrapper);
  scrollToBottom();
  return { text, wrapper, bubble, status: null };
}

function addTyping() {
  const element = document.createElement('div');
  element.className = 'message message-bot message-typing';
  element.textContent = t('chat.typing');
  $('messages').append(element);
  scrollToBottom();
  return element;
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

function setSending(value) {
  sending = value;
  $('send').disabled = value;
  document.querySelectorAll('.status-retry').forEach((button) => {
    button.disabled = value;
  });
}

function resetChat() {
  chatEpoch += 1;
  conversationId = null;
  setSending(false);
  $('messages').replaceChildren();
  addBotMessage(t('welcome'));
  setChatTitle('');
  updateActiveChat();
}

function autoResizeInput() {
  const input = $('input');
  input.style.height = 'auto';
  const border = input.offsetHeight - input.clientHeight;
  input.style.height = Math.min(input.scrollHeight + border, 160) + 'px';
}


async function deliver(item) {
  if (!localStorage.getItem(TOKEN_KEY)) {
    logout('err.session_expired');
    return;
  }

  const epoch = chatEpoch;
  const hadConversation = conversationId !== null;

  setSending(true);
  setItemState(item, 'pending');
  const typing = addTyping();

  try {
    const body = { message: item.text };
    if (hadConversation) body.conversation_id = conversationId;

    const result = await api('/api/chat/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(body),
    });

    if (epoch !== chatEpoch) return;
    typing.remove();

    if (result.ok) {
      conversationId = result.data.conversation_id;
      setItemState(item, 'sent');
      const bubble = addBotMessage(result.data.response);
      if (result.data.crisis) bubble.classList.add('message-crisis');
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
  } catch (error) {
    if (epoch !== chatEpoch) return;
    typing.remove();
    setItemState(item, 'failed', t('err.network'), true);
    console.error(error);
  } finally {
    if (epoch === chatEpoch) setSending(false);
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
        addUserMessage(message.content);
      } else {
        const bubble = addBotMessage(message.content);
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
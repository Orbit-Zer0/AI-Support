const COLLAPSED_KEY = 'chats_collapsed';

let chatItems = [];
let chatFilter = '';


function formatDate(iso) {
  const date = new Date(iso);
  try {
    return new Intl.DateTimeFormat(currentLang, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  } catch (error) {
    return date.toLocaleString();
  }
}

function makeIconButton(icon, label, onClick) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'icon-btn';
  button.dataset.icon = icon;
  button.title = label;
  button.setAttribute('aria-label', label);
  button.addEventListener('click', onClick);
  renderIcons(button);
  return button;
}


function clearChatList() {
  chatItems = [];
  chatFilter = '';
  $('chats-search').value = '';
  $('chats-error').textContent = '';
  renderChatList();
}

function updateActiveChat() {
  document.querySelectorAll('.chat-row').forEach((row) => {
    row.classList.toggle('active', Number(row.dataset.id) === conversationId);
  });
}

function renderChatList() {
  const list = $('chats-list');
  const empty = $('chats-empty');
  list.replaceChildren();

  const query = chatFilter.trim().toLowerCase();
  const visible = query
    ? chatItems.filter((item) => (item.title || '').toLowerCase().includes(query))
    : chatItems;

  empty.hidden = visible.length > 0;
  empty.textContent = chatItems.length === 0 ? t('chats.empty') : t('chats.noMatch');

  for (const item of visible) {
    const row = document.createElement('li');
    row.className = 'chat-row';
    row.dataset.id = String(item.id);

    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'chat-open';

    const title = document.createElement('span');
    title.className = 'chat-title-text';
    title.textContent = item.title || t('history.untitled');

    const date = document.createElement('span');
    date.className = 'chat-date';
    date.textContent = formatDate(item.updated_at);

    open.append(title, date);
    open.addEventListener('click', () => openConversation(item.id));

    const actions = document.createElement('div');
    actions.className = 'chat-actions';
    actions.append(
      makeIconButton('edit', t('btn.rename'), () => renameConversation(item.id)),
      makeIconButton('trash', t('btn.delete'), () => deleteConversation(item.id)),
    );

    row.append(open, actions);
    list.append(row);
  }
  updateActiveChat();
}

async function refreshChatList() {
  try {
    const result = await api('/api/conversations/', { headers: authHeaders() });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      $('chats-error').textContent = t('err.history_load');
      return;
    }
    $('chats-error').textContent = '';
    chatItems = result.data;
    renderChatList();
  } catch (error) {
    $('chats-error').textContent = t('err.network');
    console.error(error);
  }
}

async function afterReply(id, isNew) {
  await refreshChatList();
  if (conversationId === id) {
    const item = chatItems.find((chat) => chat.id === id);
    if (item) setChatTitle(item.title);
  }
  if (isNew) requestTitle(id);
}

async function requestTitle(id) {
  try {
    const result = await api(`/api/conversations/${id}/title/`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!result.ok || !result.data || !result.data.title) return;

    const item = chatItems.find((chat) => chat.id === id);
    if (item) item.title = result.data.title;
    renderChatList();
    if (conversationId === id) setChatTitle(result.data.title);
  } catch (error) {
    console.error(error);
  }
}

async function deleteConversation(id) {
  if (sending) return;
  if (!window.confirm(t('confirm.deleteChat'))) return;

  try {
    const result = await api(`/api/conversations/${id}/`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (result.ok || result.status === 404) {
      chatItems = chatItems.filter((chat) => chat.id !== id);
      renderChatList();
      if (id === conversationId) resetChat();
      return;
    }
    $('chats-error').textContent = t('err.delete_failed');
  } catch (error) {
    $('chats-error').textContent = t('err.network');
    console.error(error);
  }
}

async function renameConversation(id) {
  const item = chatItems.find((chat) => chat.id === id);
  if (!item) return;

  const input = window.prompt(t('prompt.rename'), item.title || '');
  if (input === null) return;                   // нажали "Отмена"
  const title = input.trim();
  if (!title || title === item.title) return;

  try {
    const result = await api(`/api/conversations/${id}/`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ title }),
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      const code = result.data && result.data.code;
      const key = code ? 'err.' + code : '';
      $('chats-error').textContent = key && t(key) !== key ? t(key) : t('err.rename_failed');
      return;
    }
    $('chats-error').textContent = '';
    item.title = result.data.title;
    renderChatList();
    if (id === conversationId) setChatTitle(item.title);
  } catch (error) {
    $('chats-error').textContent = t('err.network');
    console.error(error);
  }
}


function setChatsCollapsed(collapsed) {
  $('chat-view').classList.toggle('chats-collapsed', collapsed);
  localStorage.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
}

function restoreSidebarState() {
  setChatsCollapsed(localStorage.getItem(COLLAPSED_KEY) === '1');
}

function openSidebarDrawer() {
  $('chat-view').classList.add('sidebar-open');
  $('scrim').hidden = false;
}

function closeSidebarDrawer() {
  $('chat-view').classList.remove('sidebar-open');
  $('scrim').hidden = true;
}


function renderHelp(data) {
  const list = $('help-list');
  const contacts = data.contacts || [];

  for (const contact of contacts) {
    const row = document.createElement('li');

    const title = document.createElement('strong');
    title.textContent = contact.title;

    const phone = document.createElement('a');
    phone.className = 'help-phone';
    phone.textContent = contact.phone;
    phone.href = 'tel:' + String(contact.phone).replace(/[^\d+]/g, '');

    const description = document.createElement('span');
    description.className = 'help-desc';
    description.textContent = contact.description || '';

    row.append(title, phone, description);
    list.append(row);
  }

  if (contacts.length === 0) {
    $('help-fallback').textContent = data.fallback || t('help.error');
  }
}

async function openHelp() {
  setRailOpen(false);
  const dialog = $('help-dialog');
  $('help-list').replaceChildren();
  $('help-fallback').textContent = '';
  if (!dialog.open) dialog.showModal();

  try {
    const result = await api('/api/crisis-contacts/', { headers: authHeaders() });
    if (result.status === 401) {
      dialog.close();
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      $('help-fallback').textContent = t('help.error');
      return;
    }
    renderHelp(result.data);
  } catch (error) {
    $('help-fallback').textContent = t('help.error');
    console.error(error);
  }
}


function maybeShowNotice() {
  const dialog = $('notice-dialog');
  if (!localStorage.getItem(NOTICE_KEY) && !dialog.open) {
    dialog.showModal();
  }
}

function setUserMenuOpen(open) {
  $('user-zone').classList.toggle('open', open);
  $('btn-profile').setAttribute('aria-expanded', String(open));
}

function closeUserMenu() {
  setUserMenuOpen(false);
}

let railTimer = null;

function isRailOpen() {
  return $('chat-view').classList.contains('rail-open');
}

function setRailOpen(open) {
  clearTimeout(railTimer);
  $('chat-view').classList.toggle('rail-open', open);
}

function cancelRailChange() {
  clearTimeout(railTimer);
}

function requestRail(open, delay) {
  clearTimeout(railTimer);
  if (delay === 0) {
    setRailOpen(open);
    return;
  }
  if (isRailOpen() === open) return;
  railTimer = setTimeout(() => setRailOpen(open), delay);
}
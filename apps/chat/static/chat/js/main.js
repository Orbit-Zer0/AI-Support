document.querySelectorAll('.tab').forEach((button) => {
  button.addEventListener('click', () => switchTab(button.dataset.tab));
});

$('ui-language').addEventListener('change', (event) => {
  setLanguage(event.target.value);
});

$('login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitAuth(event.target, '/api/login/', $('login-error'));
});

$('register-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitAuth(event.target, '/api/register/', $('register-error'));
});


$('logout').addEventListener('click', () => logout());

$('new-chat').addEventListener('click', () => {
  resetChat();
  closeSidebarDrawer();
  $('input').focus();
});

$('chats-search').addEventListener('input', (event) => {
  chatFilter = event.target.value;
  renderChatList();
});

$('chats-collapse').addEventListener('click', () => setChatsCollapsed(true));
$('chats-expand').addEventListener('click', () => setChatsCollapsed(false));
$('sidebar-open').addEventListener('click', openSidebarDrawer);
$('scrim').addEventListener('click', closeSidebarDrawer);

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeSidebarDrawer();
    closeUserMenu();
  }
});

$('btn-profile').addEventListener('click', () => {
  if (window.matchMedia('(hover: none)').matches) {
    setUserMenuOpen(!$('user-zone').classList.contains('open'));
  }
});

document.addEventListener('click', (event) => {
  if (!event.target.closest('#user-zone')) closeUserMenu();
});

$('btn-help').addEventListener('click', openHelp);
$('help-close').addEventListener('click', () => $('help-dialog').close());
$('help-dialog').addEventListener('click', (event) => {
  if (event.target === $('help-dialog')) $('help-dialog').close();
});

$('notice-ok').addEventListener('click', () => $('notice-dialog').close());
$('notice-dialog').addEventListener('close', () => {
  localStorage.setItem(NOTICE_KEY, '1');
});


$('send').addEventListener('click', sendFromInput);

$('input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendFromInput();
  }
});

$('input').addEventListener('input', autoResizeInput);


currentLang = detectLanguage();
renderIcons();
setupContact();
initPasswordToggles();
applyTranslations();
renderSelects();
loadOptions();
restoreSidebarState();

if (localStorage.getItem(TOKEN_KEY)) {
  enterApp();
} else {
  showView('auth');
}
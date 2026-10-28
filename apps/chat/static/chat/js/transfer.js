const MAX_IMPORT_FILE_BYTES = 5 * 1024 * 1024;

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportReadable() {
  const button = $('export-readable-btn');
  const error = $('export-error');
  error.textContent = '';
  button.disabled = true;
  try {
    const response = await fetch('/api/account/export/readable/', { headers: authHeaders() });
    if (response.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!response.ok) {
      let data = null;
      try {
        data = await response.json();
      } catch (exception) {
      }
      error.textContent = response.status === 429
        ? throttledMessage(data)
        : t('profile.exportFailed');
      return;
    }
    const blob = await response.blob();
    downloadBlob(blob, `ai-support-chats-${new Date().toISOString().slice(0, 10)}.html`);
  } catch (exception) {
    error.textContent = t('err.network');
    console.error(exception);
  } finally {
    button.disabled = false;
  }
}

async function importFromFile(file) {
  const error = $('import-error');
  const ok = $('import-ok');
  error.textContent = '';
  ok.textContent = '';
  if (!file) return;

  if (file.size > MAX_IMPORT_FILE_BYTES) {
    error.textContent = t('err.import_too_large');
    return;
  }

  let text;
  try {
    text = await file.text();
    JSON.parse(text);
  } catch (exception) {
    error.textContent = t('profile.importBadJson');
    return;
  }

  const button = $('import-btn');
  button.disabled = true;
  try {
    const result = await api('/api/account/import/', {
      method: 'POST',
      headers: authHeaders(),
      body: text,
    });
    if (result.status === 401) {
      logout('err.session_expired');
      return;
    }
    if (!result.ok) {
      error.textContent = describeAccountError(result);
      return;
    }

    const { imported, skipped } = result.data;
    ok.textContent = t('profile.importDone')
      .replace('{imported}', imported)
      .replace('{duplicates}', skipped.duplicates)
      .replace('{invalid}', skipped.invalid);
    refreshChatList();
  } catch (exception) {
    error.textContent = t('err.network');
    console.error(exception);
  } finally {
    button.disabled = false;
    $('import-input').value = '';
  }
}

function initTransfer() {
  $('export-readable-btn').addEventListener('click', exportReadable);
  $('import-btn').addEventListener('click', () => $('import-input').click());
  $('import-input').addEventListener('change', (event) => {
    importFromFile(event.target.files[0]);
  });
}
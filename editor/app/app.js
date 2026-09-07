import { decryptPayload, encryptMarkdown, serializePayload, validatePayload } from './crypto.js';

const els = Object.fromEntries([
  'open-file','new-source','upload-file','file-input','loaded-panel','filename','metadata',
  'password','unlock','editor-panel','editor','same-password','new-password',
  'confirm-password','save-file','save-as','lock','status','dropzone'
].map(id => [id.replaceAll('-', '_'), document.getElementById(id)]));

let encryptedPayload = null;
let fileHandle = null;
let currentFilename = 'source.md.enc.json';
let unlocked = false;
let dirty = false;
let originalPasswordAvailable = false;

function setStatus(message, kind = '') {
  els.status.textContent = message;
  if (kind) els.status.dataset.kind = kind; else delete els.status.dataset.kind;
}

function setLoaded(payload, filename, handle = null) {
  encryptedPayload = payload;
  fileHandle = handle;
  currentFilename = filename || 'source.md.enc.json';
  els.filename.textContent = currentFilename;
  els.metadata.textContent = `${payload.cipher} · ${payload.kdf} · ${payload.iterations.toLocaleString()} iterations`;
  els.loaded_panel.hidden = false;
  els.editor_panel.hidden = true;
  els.password.value = '';
  originalPasswordAvailable = false;
  setStatus('Encrypted source loaded. Enter its password to decrypt it locally.');
  els.password.focus();
}

async function parseFile(file, handle = null) {
  if (!file) return;
  const text = await file.text();
  let payload;
  try { payload = JSON.parse(text); } catch { throw new Error('The selected file is not valid JSON.'); }
  validatePayload(payload);
  setLoaded(payload, file.name, handle);
}

async function openWithPicker() {
  if (!('showOpenFilePicker' in window)) {
    els.file_input.click();
    return;
  }
  try {
    const [handle] = await window.showOpenFilePicker({
      multiple: false,
      types: [{ description: 'Encrypted Markdown source', accept: { 'application/json': ['.json'] } }]
    });
    const file = await handle.getFile();
    await parseFile(file, handle);
  } catch (error) {
    if (error.name !== 'AbortError') throw error;
  }
}

function unlockEditor(markdown, hasOriginalPassword) {
  els.editor.value = markdown;
  els.editor_panel.hidden = false;
  els.loaded_panel.hidden = true;
  unlocked = true;
  dirty = false;
  originalPasswordAvailable = hasOriginalPassword;
  els.same_password.checked = hasOriginalPassword;
  els.same_password.disabled = !hasOriginalPassword;
  els.new_password.value = '';
  els.confirm_password.value = '';
  updatePasswordFields();
  els.editor.focus();
}

async function unlock() {
  if (!encryptedPayload) return setStatus('Open an encrypted source first.', 'error');
  const password = els.password.value;
  if (!password) return setStatus('Enter the source password.', 'error');
  els.unlock.disabled = true;
  setStatus('Deriving key and decrypting in this browser…');
  try {
    const markdown = await decryptPayload(encryptedPayload, password);
    unlockEditor(markdown, true);
    setStatus('Unlocked in browser memory. Plaintext has not been sent to the web host.', 'ok');
  } catch (error) {
    setStatus(error.message, 'error');
  } finally {
    els.unlock.disabled = false;
  }
}

function newSource() {
  if (dirty && !confirm('Discard the decrypted edits currently in browser memory?')) return;
  encryptedPayload = null;
  fileHandle = null;
  currentFilename = 'new-cheatsheet.md.enc.json';
  els.password.value = '';
  els.filename.textContent = currentFilename;
  els.metadata.textContent = 'New source · not yet encrypted';
  unlockEditor('# New cheat sheet\n\n', false);
  dirty = true;
  setStatus('New source exists only in browser memory. Set a new password and save ciphertext when ready.', 'ok');
}

function updatePasswordFields() {
  const reuse = originalPasswordAvailable && els.same_password.checked;
  els.new_password.disabled = reuse;
  els.confirm_password.disabled = reuse;
  if (reuse) {
    els.new_password.value = '';
    els.confirm_password.value = '';
  }
}

function encryptionPassword() {
  if (originalPasswordAvailable && els.same_password.checked) {
    const value = els.password.value;
    if (!value) throw new Error('The original password is no longer available. Unlock the file again.');
    return value;
  }
  const first = els.new_password.value;
  const second = els.confirm_password.value;
  if (!first) throw new Error('Enter a new encryption password.');
  if (first !== second) throw new Error('New passwords do not match.');
  return first;
}

async function makeEncryptedBlob() {
  if (!unlocked) throw new Error('Unlock or create a source first.');
  const password = encryptionPassword();
  setStatus('Encrypting edited Markdown in browser memory…');
  const payload = await encryptMarkdown(els.editor.value, password);
  const json = serializePayload(payload);
  encryptedPayload = payload;
  return new Blob([json], { type: 'application/json' });
}

async function saveToCurrentFile() {
  try {
    const blob = await makeEncryptedBlob();
    if (fileHandle && 'createWritable' in fileHandle) {
      const writable = await fileHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      dirty = false;
      setStatus(`Re-encrypted and saved ${currentFilename}. Only ciphertext was written.`, 'ok');
      return;
    }
    await saveAs(blob);
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

async function saveAs(existingBlob = null) {
  try {
    const blob = existingBlob || await makeEncryptedBlob();
    if ('showSaveFilePicker' in window) {
      try {
        const handle = await window.showSaveFilePicker({
          suggestedName: currentFilename,
          types: [{ description: 'Encrypted Markdown source', accept: { 'application/json': ['.json'] } }]
        });
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        fileHandle = handle;
        currentFilename = handle.name || currentFilename;
        originalPasswordAvailable = true;
        if (!els.same_password.checked) els.password.value = els.new_password.value;
        els.same_password.disabled = false;
        els.same_password.checked = true;
        updatePasswordFields();
        dirty = false;
        setStatus(`Re-encrypted and saved ${currentFilename}. Only ciphertext was written.`, 'ok');
        return;
      } catch (error) {
        if (error.name === 'AbortError') return;
        throw error;
      }
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = currentFilename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    dirty = false;
    setStatus('Re-encrypted file downloaded. Replace or add the ciphertext file in content/.', 'ok');
  } catch (error) {
    setStatus(error.message, 'error');
  }
}

function lock() {
  if (dirty && !confirm('Discard the decrypted edits currently in browser memory?')) return;
  els.editor.value = '';
  els.password.value = '';
  els.new_password.value = '';
  els.confirm_password.value = '';
  encryptedPayload = null;
  fileHandle = null;
  unlocked = false;
  dirty = false;
  originalPasswordAvailable = false;
  els.editor_panel.hidden = true;
  els.loaded_panel.hidden = true;
  els.filename.textContent = 'No file loaded';
  els.metadata.textContent = '';
  setStatus('Locked. Open an encrypted source or create a new one.');
}

els.open_file.addEventListener('click', () => openWithPicker().catch(e => setStatus(e.message, 'error')));
els.new_source.addEventListener('click', newSource);
els.upload_file.addEventListener('click', () => els.file_input.click());
els.file_input.addEventListener('change', () => parseFile(els.file_input.files[0]).catch(e => setStatus(e.message, 'error')));
els.unlock.addEventListener('click', unlock);
els.password.addEventListener('keydown', e => { if (e.key === 'Enter') unlock(); });
els.editor.addEventListener('input', () => { dirty = true; });
els.same_password.addEventListener('change', updatePasswordFields);
els.save_file.addEventListener('click', saveToCurrentFile);
els.save_as.addEventListener('click', () => saveAs());
els.lock.addEventListener('click', lock);

for (const eventName of ['dragenter', 'dragover']) {
  els.dropzone.addEventListener(eventName, e => {
    e.preventDefault();
    els.dropzone.classList.add('dragging');
  });
}
for (const eventName of ['dragleave', 'drop']) {
  els.dropzone.addEventListener(eventName, e => {
    e.preventDefault();
    els.dropzone.classList.remove('dragging');
  });
}
els.dropzone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0];
  parseFile(file).catch(err => setStatus(err.message, 'error'));
});

window.addEventListener('beforeunload', e => {
  if (!dirty) return;
  e.preventDefault();
  e.returnValue = '';
});

if (!('showOpenFilePicker' in window)) document.querySelector('#picker-note').hidden = false;
setStatus('Ready. No plaintext is stored by this application.');

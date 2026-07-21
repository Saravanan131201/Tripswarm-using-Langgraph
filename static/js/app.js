const App = {
  currentTravelThreadId:  null,
  currentRagThreadId:     null,
  currentSidebarThreadId: null,
  currentTab:             'travel',
  threads:                [],
  sending:                false,
};
 
 
 
// Time Formatting
 
function formatLocalTime(isoString) {
  if (!isoString) return '';
  const raw  = /[Zz]$|[+-]\d{2}:\d{2}$/.test(isoString) ? isoString : isoString + 'Z';
  const date = new Date(raw);
  if (isNaN(date)) return isoString;
 
  const now = new Date();
  const tz  = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const fmt = (d, opts) => new Intl.DateTimeFormat('en-US', { timeZone: tz, ...opts }).format(d);
 
  const todayStr     = fmt(now,  { year: 'numeric', month: '2-digit', day: '2-digit' });
  const msgStr       = fmt(date, { year: 'numeric', month: '2-digit', day: '2-digit' });
  const yesterdayStr = fmt(new Date(now - 86400000), { year: 'numeric', month: '2-digit', day: '2-digit' });
  const timeStr      = fmt(date, { hour: 'numeric', minute: '2-digit', hour12: true });
 
  if (msgStr === todayStr)     return `Today, ${timeStr}`;
  if (msgStr === yesterdayStr) return `Yesterday, ${timeStr}`;
  return `${fmt(date, { day: 'numeric', month: 'short', year: 'numeric' })}, ${timeStr}`;
}
 
 
// Threads
 
async function loadThreads() {
  try {
    const res = await fetch('/api/threads');
    if (!res.ok) return;
    App.threads = await res.json();
    renderThreadList();
  } catch (e) {
    console.error('Failed to load threads', e);
  }
}
 
function renderThreadList() {
  const container = document.getElementById('thread-list');
  const empty     = document.getElementById('thread-empty');
  container.querySelectorAll('.thread-item').forEach(el => el.remove());
 
  if (!App.threads.length) {
    if (empty) empty.style.display = 'flex';
    return;
  }
  if (empty) empty.style.display = 'none';
 
  App.threads.forEach(thread => {
    const isActive = thread.id === App.currentSidebarThreadId;
    const icon     = thread.type === 'travel' ? 'bi-airplane' : 'bi-chat-square-dots';
 
    const item = document.createElement('div');
    item.className          = 'thread-item' + (isActive ? ' active' : '');
    item.dataset.threadId   = thread.id;
    item.dataset.threadType = thread.type;
    item.innerHTML = `
      <i class="bi ${icon} thread-icon"></i>
      <span class="thread-label" title="${escapeHtml(thread.title)}">${escapeHtml(thread.title)}</span>
      <button class="thread-del" title="Delete" onclick="deleteThread(event, ${thread.id})">
        <i class="bi bi-x"></i>
      </button>`;
    item.addEventListener('click', () => switchThread(thread.id, thread.type));
    container.appendChild(item);
  });
}
 
async function newThread(type) {
  const tabName = type === 'rag' ? 'rag' : 'travel';
  const tabBtn  = document.querySelector(`.nav-tab[data-tab="${tabName}"]`);
  if (tabBtn) switchTab(tabName, tabBtn);
 
  try {
    const res = await fetch('/api/threads', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body:   JSON.stringify({ type, title: type === 'travel' ? 'New Trip' : 'New Q&A' }),
    });
    if (!res.ok) return;
    const thread = await res.json();
    App.threads.unshift(thread);
 
    if (type === 'travel') {
      App.currentTravelThreadId = thread.id;
      clearChat('travel');
      updateThreadLabel('travel');
    } else {
      App.currentRagThreadId = thread.id;
      clearChat('rag');
      updateThreadLabel('rag');
    }
    renderThreadList();
  } catch (e) {
    console.error('Failed to create thread', e);
  }
}
 
async function switchThread(threadId, type) {
  const tabName = type === 'travel' ? 'travel' : 'rag';
  const tabBtn  = document.querySelector(`.nav-tab[data-tab="${tabName}"]`);
  if (tabBtn) switchTab(tabName, tabBtn);
 
  App.currentSidebarThreadId = threadId;
  if (type === 'travel') App.currentTravelThreadId = threadId;
  else                   App.currentRagThreadId    = threadId;
 
  renderThreadList();
  clearChat(tabName);
 
  try {
    const res      = await fetch(`/api/threads/${threadId}/messages`);
    if (!res.ok) return;
    const messages = await res.json();
    const cid      = tabName === 'travel' ? 'travel-messages' : 'rag-messages';
    messages.forEach(msg => {
      appendMessage(cid, msg.role, msg.content, null, msg.created_at,
                    tabName === 'travel' && msg.role === 'assistant');
    });
    scrollToBottom(cid);
    updateThreadLabel(tabName);
  } catch (e) {
    console.error('Failed to load thread messages', e);
  }
}
 
async function deleteThread(event, threadId) {
  event.stopPropagation();
  if (!confirm('Delete this chat?')) return;
  try {
    await fetch(`/api/threads/${threadId}`, { method: 'DELETE' });
    App.threads = App.threads.filter(t => t.id !== threadId);
    if (App.currentTravelThreadId === threadId) { App.currentTravelThreadId = null; clearChat('travel'); updateThreadLabel('travel'); }
    if (App.currentRagThreadId    === threadId) { App.currentRagThreadId    = null; clearChat('rag');    updateThreadLabel('rag');    }
    renderThreadList();
  } catch (e) {
    console.error('Failed to delete thread', e);
  }
}
 
 
// Sidebar Toggle
 
function toggleSidebar() {
  const shell = document.getElementById('app-shell');
  if (window.innerWidth <= 768) {
    shell.classList.toggle('sidebar-open');
  } else {
    shell.classList.toggle('sidebar-collapsed');
    document.body.classList.toggle('desktop-sidebar-collapsed', shell.classList.contains('sidebar-collapsed'));
  }
}
 
function closeMobileSidebar() {
  document.getElementById('app-shell').classList.remove('sidebar-open');
}
 
window.addEventListener('resize', () => {
  const shell = document.getElementById('app-shell');
  if (window.innerWidth > 768) {
    shell.classList.remove('sidebar-open');
  } else {
    shell.classList.remove('sidebar-collapsed');
    document.body.classList.remove('desktop-sidebar-collapsed');
  }
});
 
 
// Tabs
 
function switchTab(tab, el) {
  App.currentTab = tab;
 
  // Update URL — push new history entry so back button works
  const params = new URLSearchParams(window.location.search);
  params.set('mode', tab);
  params.delete('q');   // clear one-shot prompt param after first use
  history.pushState({ tab }, '', '/chat?' + params.toString());
 
  document.querySelectorAll('.nav-tab').forEach(btn => btn.classList.remove('active'));
  if (el) el.classList.add('active');
  else { const btn = document.querySelector(`.nav-tab[data-tab="${tab}"]`); if (btn) btn.classList.add('active'); }
 
  document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  const pane = document.getElementById(`tab-${tab}`);
  if (pane) pane.classList.add('active');
 
  if (tab === 'reports') loadReports();
  if (tab === 'docs')    loadDocuments();
}
 
 
// Travel Send
 
async function sendTravel() {
  if (App.sending) return;
  const input   = document.getElementById('travel-input');
  const message = input.value.trim();
  if (!message) return;
 
  App.sending = true;
  input.value = '';
  autoGrow(input);
  document.getElementById('travel-send-btn').disabled = true;
 
  hideWelcome('travel-welcome');
  appendMessage('travel-messages', 'user', message, null, new Date().toISOString(), false);
  const loadingId = appendLoading('travel-messages');
  scrollToBottom('travel-messages');
 
  try {
    const res  = await fetch('/api/travel', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body:   JSON.stringify({ message, thread_id: App.currentTravelThreadId }),
    });
    const data = await res.json();
    removeLoading(loadingId);
 
    if (res.ok) {
      appendMessage('travel-messages', 'assistant', data.response, null, data.assistant_created_at, true);
      if (data.thread_id && !App.currentTravelThreadId) {
        App.currentTravelThreadId = data.thread_id;
        await loadThreads();
      } else if (data.thread_id) {
        const t = App.threads.find(t => t.id === data.thread_id);
        if (t && data.thread_title) t.title = data.thread_title;
        renderThreadList();
      }
      updateThreadLabel('travel');
    } else {
      appendErrorMessage('travel-messages', data.detail || 'Something went wrong. Please try again.');
    }
  } catch (e) {
    removeLoading(loadingId);
    appendErrorMessage('travel-messages', 'Network error. Check your connection and retry.');
  }
 
  scrollToBottom('travel-messages');
  App.sending = false;
  document.getElementById('travel-send-btn').disabled = false;
  input.focus();
}
 
function setQuery(text) {
  const input = document.getElementById('travel-input');
  input.value = text;
  autoGrow(input);
  input.focus();
}
 
 
// RAG Send
 
async function sendRag() {
  if (App.sending) return;
  const input = document.getElementById('rag-input');
  const query = input.value.trim();
  if (!query) return;
 
  App.sending = true;
  input.value = '';
  autoGrow(input);
  document.getElementById('rag-send-btn').disabled = true;
 
  hideWelcome('rag-welcome');
  appendMessage('rag-messages', 'user', query, null, new Date().toISOString(), false);
  const loadingId = appendLoading('rag-messages');
  scrollToBottom('rag-messages');
  document.getElementById('rag-source-badge').innerHTML = '';
 
  try {
    const res  = await fetch('/api/rag', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body:   JSON.stringify({ query, thread_id: App.currentRagThreadId }),
    });
    const data = await res.json();
    removeLoading(loadingId);
 
    if (res.ok) {
      appendMessage('rag-messages', 'assistant', data.answer, data.source, data.assistant_created_at, false);
      if (data.thread_id && !App.currentRagThreadId) {
        App.currentRagThreadId = data.thread_id;
        await loadThreads();
      }
      const badge = document.getElementById('rag-source-badge');
      if (data.source === 'rag') {
        badge.innerHTML = `<span class="source-badge source-rag"><i class="bi bi-search"></i>Hybrid Search</span>`;
      } else {
        badge.innerHTML = `<span class="source-badge source-llm"><i class="bi bi-cpu"></i>LLM</span>`;
      }
      updateThreadLabel('rag');
    } else {
      appendErrorMessage('rag-messages', data.detail || 'Something went wrong. Please try again.');
    }
  } catch (e) {
    removeLoading(loadingId);
    appendErrorMessage('rag-messages', 'Network error. Check your connection and retry.');
  }
 
  scrollToBottom('rag-messages');
  App.sending = false;
  document.getElementById('rag-send-btn').disabled = false;
  input.focus();
}
 
function setRagQuery(text) {
  const input = document.getElementById('rag-input');
  input.value = text;
  autoGrow(input);
  input.focus();
}
 
 
// Message Rendering
 
function appendMessage(containerId, role, content, source = null, created_at = null, showActions = false) {
  const container = document.getElementById(containerId);
  const row       = document.createElement('div');
  row.className   = `msg-row ${role}`;
 
  const bubbleContent = role === 'assistant' ? marked.parse(content) : escapeHtml(content);
 
  if (role === 'user') {
    row.innerHTML = `
      <div class="msg-body">
        <div class="msg-bubble user">${bubbleContent}</div>
        <div class="msg-time user">${formatLocalTime(created_at)}</div>
      </div>
      <div class="msg-avatar user">👤</div>`;
    container.appendChild(row);
    return;
  }
 
  // Source badge
  let sourceBadgeHtml = '';
  if (source === 'rag') sourceBadgeHtml = `<span class="source-badge source-rag"><i class="bi bi-search"></i> Hybrid Search</span>`;
  else if (source === 'llm') sourceBadgeHtml = `<span class="source-badge source-llm"><i class="bi bi-cpu"></i> LLM</span>`;
 
  // Action buttons (travel assistant only)
  let actionsHtml = '', safeId = '';
  if (showActions) {
    safeId = `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    actionsHtml = `
      <div class="msg-actions" id="actions-${safeId}">
        <button class="msg-action-btn" title="Copy to clipboard" onclick="copyMsgContent('${safeId}')">
          <i class="bi bi-clipboard"></i> Copy
        </button>
        <button class="msg-action-btn" title="Download as PDF" onclick="downloadMsgPdf('${safeId}')">
          <i class="bi bi-file-earmark-pdf"></i> PDF
        </button>
        <button class="msg-action-btn" title="Add to My Documents" onclick="addMsgToDocuments('${safeId}')">
          <i class="bi bi-folder-plus"></i> Add to Docs
        </button>
      </div>`;
  }
 
  const footerHtml = `
    <div class="msg-footer">
      <div class="msg-footer-avatar">🤖</div>
      <span class="msg-footer-time">${formatLocalTime(created_at)}</span>
      ${sourceBadgeHtml ? `<div class="msg-footer-dot"></div>${sourceBadgeHtml}` : ''}
      ${showActions ? `<div class="msg-footer-spacer"></div>${actionsHtml}` : ''}
    </div>`;
 
  const bubbleAttrs = showActions ? `id="${safeId}" data-raw="${escapeAttr(content)}"` : '';
 
  row.innerHTML = `
    <div class="msg-body">
      <div class="msg-bubble assistant" ${bubbleAttrs}>${bubbleContent}</div>
      ${footerHtml}
    </div>`;
  container.appendChild(row);
}
 
function appendErrorMessage(containerId, text) {
  const container = document.getElementById(containerId);
  const row = document.createElement('div');
  row.className = 'msg-row assistant';
  row.innerHTML = `
    <div class="msg-body">
      <div class="msg-bubble assistant" style="border-color:rgba(248,113,113,0.2);color:#fca5a5;">${escapeHtml(text)}</div>
      <div class="msg-footer">
        <div class="msg-footer-avatar">⚠️</div>
        <span class="msg-footer-time">${formatLocalTime(new Date().toISOString())}</span>
      </div>
    </div>`;
  container.appendChild(row);
}
 
function appendLoading(containerId) {
  const container = document.getElementById(containerId);
  const id  = `loading-${Date.now()}`;
  const row = document.createElement('div');
  row.id        = id;
  row.className = 'loading-row';
  row.innerHTML = `
    <div class="loading-bubble">
      <div class="loading-avatar">🤖</div>
      <div class="loading-dots"><span></span><span></span><span></span></div>
    </div>`;
  container.appendChild(row);
  return id;
}
 
function removeLoading(id) { const el = document.getElementById(id); if (el) el.remove(); }
function hideWelcome(id)   { const el = document.getElementById(id); if (el) el.style.display = 'none'; }
 
function clearChat(type) {
  const cid = type === 'travel' ? 'travel-messages' : 'rag-messages';
  const wid = type === 'travel' ? 'travel-welcome'  : 'rag-welcome';
  document.getElementById(cid)?.querySelectorAll('.msg-row,.loading-row').forEach(el => el.remove());
  const welcome = document.getElementById(wid);
  if (welcome) welcome.style.display = '';
}
 
function scrollToBottom(cid) { const c = document.getElementById(cid); if (c) c.scrollTop = c.scrollHeight; }
 
function updateThreadLabel(type) {
  const labelId  = type === 'travel' ? 'travel-thread-label' : 'rag-thread-label';
  const el       = document.getElementById(labelId);
  if (!el) return;
  const threadId = type === 'travel' ? App.currentTravelThreadId : App.currentRagThreadId;
  if (!threadId) { el.textContent = ''; return; }
  const thread = App.threads.find(t => t.id === threadId);
  if (thread) el.textContent = `Thread: ${truncate(thread.title, 40)}`;
}
 
 
// Action Buttons
 
function _getRawContent(safeId) {
  const el = document.getElementById(safeId);
  return el ? (el.dataset.raw || el.innerText) : '';
}
 
async function copyMsgContent(safeId) {
  const text = _getRawContent(safeId);
  try {
    await navigator.clipboard.writeText(text);
    _flashActionBtn(safeId, 'copy', '✓ Copied!');
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); ta.remove();
    _flashActionBtn(safeId, 'copy', '✓ Copied!');
  }
}
 
async function downloadMsgPdf(safeId) {
  const text = _getRawContent(safeId);
  _flashActionBtn(safeId, 'pdf', '⏳ Generating…');
  try {
    const res = await fetch('/api/export/pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body:   JSON.stringify({ content: text }),
    });
    if (!res.ok) throw new Error('PDF export failed');
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `trip-plan-${Date.now()}.pdf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    _flashActionBtn(safeId, 'pdf', '✓ Downloaded!');
  } catch (e) {
    console.error(e); _flashActionBtn(safeId, 'pdf', '✗ Failed');
  }
}
 
async function addMsgToDocuments(safeId) {
  const text     = _getRawContent(safeId);
  const filename = `trip-plan-${new Date().toISOString().slice(0,10)}.txt`;
  _flashActionBtn(safeId, 'docs', '⏳ Saving…');
  try {
    const blob     = new Blob([text], { type: 'text/plain' });
    const formData = new FormData();
    formData.append('files', blob, filename);
    const res = await fetch('/api/docs/upload', { method: 'POST', body: formData });
    if (!res.ok) throw new Error('Upload failed');
    _flashActionBtn(safeId, 'docs', '✓ Added!');
  } catch (e) {
    console.error(e); _flashActionBtn(safeId, 'docs', '✗ Failed');
  }
}
 
function _flashActionBtn(safeId, btnType, msg) {
  const actionsEl = document.getElementById(`actions-${safeId}`);
  if (!actionsEl) return;
  const btns = actionsEl.querySelectorAll('.msg-action-btn');
  const map  = { copy: 0, pdf: 1, docs: 2 };
  const btn  = btns[map[btnType]];
  if (!btn) return;
  const orig = btn.innerHTML;
  btn.textContent = msg; btn.disabled = true;
  setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; }, 2500);
}
 
 
// Documents
 
async function loadDocuments() {
  const list = document.getElementById('docs-list');
  list.innerHTML = `<div class="empty-state"><i class="bi bi-hourglass-split"></i><p>Loading…</p></div>`;
  try {
    const res  = await fetch('/api/docs');
    if (!res.ok) throw new Error('Failed');
    const docs = await res.json();
    if (!docs.length) {
      list.innerHTML = `<div class="empty-state"><i class="bi bi-file-earmark-plus"></i><p>No documents uploaded yet.<br>Upload PDFs, Word docs or text files to enhance your Travel Q&amp;A.</p></div>`;
      return;
    }
    list.innerHTML = '';
    docs.forEach(doc => {
      const iconClass = getDocIconClass(doc.filename, doc.content_type);
      const item = document.createElement('div');
      item.className = 'doc-item';
      item.innerHTML = `
        <div class="doc-icon ${iconClass.cls}"><i class="bi ${iconClass.icon}"></i></div>
        <div class="doc-info">
          <div class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
          <div class="doc-meta">${formatBytes(doc.file_size)} · ${formatLocalTime(doc.created_at)}</div>
        </div>
        <button class="doc-del" onclick="deleteDocument(${doc.id})" title="Remove document"><i class="bi bi-trash3"></i></button>`;
      list.appendChild(item);
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><i class="bi bi-exclamation-triangle"></i><p>Failed to load documents.</p></div>`;
  }
}
 
async function uploadDocument(input) {
  if (!input.files.length) return;
  const files    = Array.from(input.files);
  const progress = document.getElementById('upload-progress');
  const label    = document.getElementById('upload-progress-label');
  progress.style.display = 'block';
  label.textContent = `Uploading ${files.length} file(s): ${files.map(f => f.name).join(', ')}`;
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  try {
    const res = await fetch('/api/docs/upload', { method: 'POST', body: formData });
    progress.style.display = 'none'; input.value = '';
    if (!res.ok) { const err = await res.json(); alert('Upload failed: ' + (err.detail || 'Unknown error')); return; }
    await loadDocuments();
  } catch (e) {
    progress.style.display = 'none'; input.value = '';
    alert('Upload failed. Check your connection and try again.');
  }
}
 
async function deleteDocument(docId) {
  if (!confirm('Remove this document from your RAG index?')) return;
  try { await fetch(`/api/docs/${docId}`, { method: 'DELETE' }); await loadDocuments(); }
  catch (e) { alert('Failed to delete document.'); }
}
 
function getDocIconClass(filename, contentType) {
  const name = (filename || '').toLowerCase(), ct = (contentType || '').toLowerCase();
  if (name.endsWith('.pdf') || ct.includes('pdf'))                          return { cls: 'pdf',  icon: 'bi-file-earmark-pdf'  };
  if (name.endsWith('.docx') || name.endsWith('.doc') || ct.includes('word')) return { cls: 'word', icon: 'bi-file-earmark-word' };
  if (name.endsWith('.md'))                                                  return { cls: '',     icon: 'bi-file-earmark-code' };
  return { cls: '', icon: 'bi-file-earmark-text' };
}
 
 
// Reports
 
async function loadReports() {
  const list = document.getElementById('reports-list');
  list.innerHTML = `<div class="empty-state"><i class="bi bi-hourglass-split"></i><p>Loading…</p></div>`;
  try {
    const res     = await fetch('/api/reports');
    if (!res.ok) throw new Error('Failed');
    const reports = await res.json();
    if (!reports.length) {
      list.innerHTML = `<div class="empty-state"><i class="bi bi-journal-plus"></i><p>No saved trips yet.<br>Generate a trip plan and it will appear here automatically.</p></div>`;
      return;
    }
    list.innerHTML = '';
    reports.forEach(report => {
      const card = document.createElement('div');
      card.className = 'report-card';
      card.onclick   = () => openReport(report);
      const plain    = report.content.replace(/[#*`>\-_\[\]]/g, '').trim();
      card.innerHTML = `
        <div class="report-title">${escapeHtml(report.title)}</div>
        <div class="report-date">${formatLocalTime(report.created_at)}</div>
        <div class="report-preview">${escapeHtml(plain.slice(0, 160))}</div>`;
      list.appendChild(card);
    });
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><i class="bi bi-exclamation-triangle"></i><p>Failed to load reports.</p></div>`;
  }
}
 
function openReport(report) {
  document.getElementById('reportModalTitle').textContent = report.title;
  document.getElementById('reportModalBody').innerHTML   = marked.parse(report.content);
  new bootstrap.Modal(document.getElementById('reportModal')).show();
}
 
 
// Utilities
 
function handleKey(event, type) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    if (type === 'travel') sendTravel();
    else                   sendRag();
  }
}
 
function autoGrow(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}
 
function setupTextareaAutoGrow() {
  document.querySelectorAll('.input-bar textarea').forEach(ta => {
    ta.addEventListener('input', () => autoGrow(ta));
  });
}
 
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
 
function escapeAttr(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
 
function truncate(str, len) { return str.length > len ? str.slice(0, len) + '…' : str; }
 
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
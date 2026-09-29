const markers = JSON.parse(document.getElementById('thread-markers').textContent);
const interfaceCatalog = JSON.parse(document.getElementById('thread-interface-catalog-data').textContent);
const workspace = document.querySelector('.thread-workspace');
const threadStack = NiixyUI.createPaneStack(workspace, {
  list: null,
  detail: 'is-detail-open',
  'interface-list': 'is-interface-list-open',
  'interface-detail': 'is-interface-detail-open',
});
const threadMotion = NiixyUI.createWorkspace(workspace, {
  list: {root: true},
  detail: {target: '.thread-detail-pane'},
  'interface-list': {target: '.thread-interface-list-pane'},
  'interface-detail': {target: '.thread-interface-detail-pane'},
}, {track: document.querySelector('.thread-track')});
const list = document.getElementById('thread-list');
const createForm = document.getElementById('thread-create-form');
const createTrigger = document.getElementById('thread-create-trigger');
const createCancel = document.getElementById('thread-create-cancel');
const ruleDialog = document.getElementById('thread-rule-dialog');
const map = new geolonia.Map('#map');
function setThreadStage(stage) {
  threadStack.set(stage);
  threadMotion.set(stage);
  window.setTimeout(() => map.resize(), 260);
}
const markerById = new Map();
const resumeStorageKey = 'niixy:resume:niimap';
let draftMarker;
let creating = false;
let activeRuleCapability;
const selectedInterfaceIds = new Set();
const interfaceValueStore = new Map();
let previewInterfaceId = null;
let previewRequestId = 0;

function ensureInterfaceSelectorPanes() {
  if (document.getElementById('thread-interface-selector')) return;
  document.querySelector('.thread-track').append(document.getElementById('thread-interface-selector-template').content.cloneNode(true));
  NiixyUI.bindTabs(document.querySelector('.thread-interface-catalog'));
  document.getElementById('close-thread-interface-selector').addEventListener('click', closeInterfaceSelector);
  document.getElementById('back-thread-interface-selector').addEventListener('click', () => setThreadStage('interface-list'));
  document.querySelectorAll('[data-select-thread-interface]').forEach((button) => button.addEventListener('click', () => renderInterfacePreview(Number(button.dataset.selectThreadInterface))));
}

function consumeResumeState() {
  const stored = sessionStorage.getItem(resumeStorageKey);
  sessionStorage.removeItem(resumeStorageKey);
  sessionStorage.removeItem('niimap:open-thread');
  sessionStorage.removeItem('niimap:animate-thread');
  sessionStorage.removeItem('niimap:map-view');
  if (!stored) return null;
  try { return JSON.parse(stored); } catch { return null; }
}
function threadIdFromUrl() {
  const value = new URLSearchParams(location.search).get('thread');
  return /^\d+$/.test(value || '') ? value : null;
}
const resumeState = consumeResumeState();
const initialThreadId = threadIdFromUrl();
const activeResumeState = initialThreadId && String(resumeState?.threadId) === initialThreadId ? resumeState : null;
const animateInitialThread = Boolean(activeResumeState?.animate);
const initialThreadPane = initialThreadId && document.querySelector(`[data-thread-detail-pane="${initialThreadId}"]`);
const detailTitle = document.getElementById('thread-detail-title');
if (initialThreadPane) {
  if (!animateInitialThread) {
    setThreadStage('detail');
    workspace.classList.add('is-restoring-detail');
  }
  initialThreadPane.hidden = false;
  detailTitle.textContent = `${initialThreadPane.dataset.threadTitle} (${initialThreadPane.dataset.threadPostCount})`;
} else {
  const url = new URL(location.href);
  url.searchParams.delete('thread');
  history.replaceState({}, '', url);
}
document.documentElement.classList.remove('has-restored-thread-detail');
if (initialThreadPane) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (animateInitialThread) setThreadStage('detail');
    else workspace.classList.remove('is-restoring-detail');
  }));
}

document.getElementById('niimap-home-link')?.addEventListener('click', () => {
  sessionStorage.removeItem(resumeStorageKey);
});

function csrf(form) { return new FormData(form); }
function saveResumeState(threadId, animate = false) {
  const center = map.getCenter();
  sessionStorage.setItem(resumeStorageKey, JSON.stringify({
    threadId: String(threadId),
    animate,
    mapView: {latitude: center.lat, longitude: center.lng, zoom: map.getZoom()},
  }));
}
function restoreMapView() {
  const view = activeResumeState?.mapView;
  if (!view || ![view.latitude, view.longitude, view.zoom].every(Number.isFinite)) return false;
  map.jumpTo({center: [view.longitude, view.latitude], zoom: view.zoom});
  return true;
}
function addRule(capability, audience) {
  const list = document.querySelector(`.thread-rule[data-capability="${capability}"] .thread-rule-list`);
  if (list.querySelector(`[data-audience="${audience}"]`)) return;
  const item = document.createElement('span');
  item.className = 'thread-rule-item';
  item.dataset.audience = audience;
  item.textContent = audience === 'guest' ? 'Guest' : 'NiixyAccount';
  const remove = document.createElement('button');
  remove.type = 'button'; remove.textContent = '×'; remove.setAttribute('aria-label', `${item.textContent}を削除`);
  remove.addEventListener('click', () => item.remove());
  item.append(remove); list.append(item);
}
document.querySelectorAll('.thread-rule').forEach((rule) => {
  const capability = rule.dataset.capability;
  addRule(capability, 'guest'); addRule(capability, 'account');
  rule.querySelector('.thread-rule-add').addEventListener('click', () => { activeRuleCapability = capability; ruleDialog.showModal(); });
});
ruleDialog.querySelectorAll('[data-audience]').forEach((button) => button.addEventListener('click', () => {
  addRule(activeRuleCapability, button.dataset.audience); ruleDialog.close();
}));
function createFormData() {
  const data = csrf(createForm);
  document.querySelectorAll('.thread-rule').forEach((rule) => {
    rule.querySelectorAll('.thread-rule-item').forEach((item) => data.append(`${rule.dataset.capability}_${item.dataset.audience}`, 'true'));
  });
  return data;
}

function interfaceValueKey(interfaceId, fieldKey) { return `${interfaceId}:${fieldKey}`; }
function inputName(interfaceId, fieldKey) { return `interface_value_${interfaceId}_${fieldKey}`; }
function makeFieldControl(implementation, field) {
  const key = interfaceValueKey(implementation.id, field.key);
  const saved = interfaceValueStore.get(key) || [];
  const wrapper = document.createElement('div');
  wrapper.className = 'field thread-interface-field';
  wrapper.dataset.valueKey = key;
  const label = document.createElement('label');
  label.textContent = `${field.label}${field.required ? '（必須）' : ''}`;
  wrapper.append(label);
  const name = inputName(implementation.id, field.key);
  if (field.type === 'long_text') {
    const input = document.createElement('textarea'); input.name = name; input.rows = 4; input.value = saved[0] || ''; input.required = field.required; wrapper.append(input);
  } else if (field.type === 'boolean') {
    const input = document.createElement('select'); input.name = name; input.required = field.required;
    [['', '選択してください'], ['true', 'はい'], ['false', 'いいえ']].forEach(([value, text]) => { const option = document.createElement('option'); option.value = value; option.textContent = text; option.selected = saved[0] === value; input.append(option); }); wrapper.append(input);
  } else if (field.type === 'single_choice') {
    const input = document.createElement('select'); input.name = name; input.required = field.required;
    const empty = document.createElement('option'); empty.value = ''; empty.textContent = '選択してください'; input.append(empty);
    field.settings.options.forEach((value) => { const option = document.createElement('option'); option.value = value; option.textContent = value; option.selected = saved[0] === value; input.append(option); }); wrapper.append(input);
  } else if (field.type === 'multiple_choice') {
    const choices = document.createElement('div'); choices.className = 'thread-interface-choices';
    field.settings.options.forEach((value) => { const choice = document.createElement('label'); const input = document.createElement('input'); input.type = 'checkbox'; input.name = name; input.value = value; input.checked = saved.includes(value); choice.append(input, document.createTextNode(value)); choices.append(choice); }); wrapper.append(choices);
  } else {
    const input = document.createElement('input'); input.name = name; input.required = field.required; input.value = saved[0] || '';
    input.type = {integer: 'number', decimal: 'number', date: 'date', datetime: 'datetime-local'}[field.type] || 'text';
    if (field.type === 'decimal') input.step = 'any'; wrapper.append(input);
  }
  wrapper.addEventListener('input', () => {
    const controls = wrapper.querySelectorAll(`[name="${name}"]`);
    const values = Array.from(controls).filter((control) => control.type !== 'checkbox' || control.checked).map((control) => control.value).filter((value) => value !== '');
    interfaceValueStore.set(key, values);
  });
  return wrapper;
}
function appendImplementation(container, implementation, isSelectedRoot = false) {
  const section = document.createElement('details'); section.className = 'thread-interface-implementation'; section.open = true;
  const summary = document.createElement('summary');
  const name = document.createElement('span');
  name.textContent = `${implementation.name}@${implementation.creator} v${implementation.version}`;
  summary.append(name);
  if (isSelectedRoot) {
    const remove = document.createElement('span'); remove.className = 'remove-thread-interface'; remove.textContent = '×'; remove.setAttribute('role', 'button'); remove.setAttribute('tabindex', '0'); remove.setAttribute('aria-label', `${implementation.name}を外す`);
    const removeInterface = (event) => { event.preventDefault(); event.stopPropagation(); selectedInterfaceIds.delete(implementation.id); renderSelectedInterfaces(); };
    remove.addEventListener('click', removeInterface);
    remove.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') removeInterface(event); });
    summary.append(remove);
  }
  const fields = document.createElement('div'); fields.className = 'thread-interface-implementation-fields';
  implementation.fields.forEach((field) => fields.append(makeFieldControl(implementation, field)));
  if (!implementation.fields.length) { const empty = document.createElement('p'); empty.className = 'empty'; empty.textContent = '入力するFieldはありません。'; fields.append(empty); }
  section.append(summary, fields); container.append(section);
}
function selectedImplementations() {
  const byId = new Map();
  interfaceCatalog.filter((item) => selectedInterfaceIds.has(item.id)).forEach((item) => item.implementations.forEach((implementation) => byId.set(implementation.id, implementation)));
  return Array.from(byId.values());
}
function renderSelectedInterfaces() {
  const container = document.getElementById('selected-thread-interfaces'); container.replaceChildren();
  selectedInterfaceIds.forEach((id) => {
    const input = document.createElement('input'); input.type = 'hidden'; input.name = 'interface_ids'; input.value = id; container.append(input);
  });
  selectedImplementations().forEach((implementation) => appendImplementation(container, implementation, selectedInterfaceIds.has(implementation.id)));
}
async function renderInterfacePreview(id) {
  previewInterfaceId = id;
  const requestId = ++previewRequestId;
  const item = interfaceCatalog.find((candidate) => candidate.id === id);
  document.getElementById('thread-interface-detail-title').textContent = `${item.name}@${item.creator} v${item.version}/${item.kind}`;
  const detail = document.getElementById('thread-interface-selector-detail');
  const loading = document.createElement('p'); loading.className = 'ui-pane-loading'; loading.textContent = '読み込み中...';
  detail.replaceChildren(loading);
  setThreadStage('interface-detail');
  try {
    const fragment = await NiixyUI.fetchFragment(item.detail_url);
    if (requestId !== previewRequestId || previewInterfaceId !== id) return;
    detail.replaceChildren(fragment);
  } catch (error) {
    if (requestId !== previewRequestId || previewInterfaceId !== id) return;
    const message = document.createElement('p'); message.className = 'ui-pane-error'; message.textContent = 'ThreadIFの詳細を読み込めませんでした。';
    detail.replaceChildren(message);
    return;
  }
  const editor = document.createElement('section'); editor.className = 'interface-implementation-editor';
  const editorTitle = document.createElement('h3'); editorTitle.textContent = '実装内容'; editor.append(editorTitle);
  item.implementations.forEach((implementation) => appendImplementation(editor, implementation));
  detail.append(editor);
  const actions = document.createElement('div'); actions.className = 'interface-detail-actions';
  const use = document.createElement('button'); use.className = 'button primary'; use.type = 'button'; use.textContent = selectedInterfaceIds.has(id) ? '入力内容を反映' : 'このThreadIFを実装する';
  use.addEventListener('click', () => { detail.querySelectorAll('.thread-interface-field').forEach((field) => field.dispatchEvent(new Event('input'))); selectedInterfaceIds.add(id); renderSelectedInterfaces(); closeInterfaceSelector(); });
  actions.append(use); detail.append(actions);
}
function openInterfaceSelector(id = null) {
  ensureInterfaceSelectorPanes();
  if (id) renderInterfacePreview(id);
  else setThreadStage('interface-list');
}
function closeInterfaceSelector() {
  previewRequestId += 1;
  previewInterfaceId = null;
  setThreadStage('list');
}
document.getElementById('open-thread-interface-selector').addEventListener('click', () => openInterfaceSelector());
function accountIds() { return new Set(document.getElementById('filter-account-ids').value.toLowerCase().split(/[\s,]+/).filter(Boolean)); }
function applyFilters() {
  const guests = document.getElementById('filter-show-guests').checked;
  const enabled = document.getElementById('filter-account-ids-enabled').checked;
  const ids = accountIds();
  list.querySelectorAll('.thread-item').forEach((item) => {
    const creator = item.dataset.creatorId.toLowerCase();
    const visible = enabled ? Boolean(creator) && ids.has(creator) : Boolean(creator) || guests;
    item.hidden = !visible;
    const marker = markerById.get(item.dataset.threadId);
    if (marker) marker.getElement().hidden = !visible;
  });
  sortByDistance();
}
function sortByDistance() {
  const center = map.getCenter();
  const distance = (thread) => (thread.latitude - center.lat) ** 2 + (thread.longitude - center.lng) ** 2;
  Array.from(list.querySelectorAll('.thread-item')).sort((first, second) => {
    const firstThread = markers.find((thread) => String(thread.id) === first.dataset.threadId);
    const secondThread = markers.find((thread) => String(thread.id) === second.dataset.threadId);
    return distance(firstThread) - distance(secondThread);
  }).forEach((item) => list.append(item));
}
function savePreferences() {
  if (workspace.dataset.authenticated !== 'true') return;
  const data = new FormData();
  data.append('show_guest_threads', document.getElementById('filter-show-guests').checked);
  data.append('account_ids_enabled', document.getElementById('filter-account-ids-enabled').checked);
  data.append('account_section_open', document.getElementById('filter-account-section').open);
  fetch(workspace.dataset.preferencesUrl, {method: 'POST', body: data, credentials: 'same-origin'});
}
function selectThread(id, scroll = false) {
  list.querySelectorAll('.thread-item').forEach((item) => {
    const selected = item.dataset.threadId === String(id);
    item.classList.toggle('is-open', selected);
  });
  markerById.forEach((marker, markerId) => marker.getElement().classList.toggle('is-highlighted', markerId === String(id)));
  showThreadMarker(id);
  const item = list.querySelector(`[data-thread-id="${id}"]`);
  if (scroll && item) item.scrollIntoView({block: 'nearest'});
}
function showThreadMarker(id) {
  const thread = markers.find((item) => String(item.id) === String(id));
  if (!thread) return;

  const coordinates = [thread.longitude, thread.latitude];
  if (map.getBounds().contains(coordinates)) return;

  const bounds = map.getBounds();
  bounds.extend(coordinates);
  map.fitBounds(bounds, {
    duration: 500,
    maxZoom: map.getZoom(),
    padding: 48,
  });
}
function updateThreadUrl(id, replace = false) {
  const url = new URL(location.href);
  const threadId = id ? String(id) : null;
  if (url.searchParams.get('thread') === threadId) return;
  if (threadId) url.searchParams.set('thread', threadId);
  else url.searchParams.delete('thread');
  history[replace ? 'replaceState' : 'pushState']({}, '', url);
}
function openDetail(id, shouldUpdateUrl = true) {
  const pane = document.querySelector(`[data-thread-detail-pane="${id}"]`);
  if (!pane) return false;
  setThreadStage('detail');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => {
    const selected = pane.dataset.threadDetailPane === String(id);
    pane.hidden = !selected;
    if (selected) detailTitle.textContent = `${pane.dataset.threadTitle} (${pane.dataset.threadPostCount})`;
  });
  document.querySelector('.thread-detail-pane').scrollTo({top: 0});
  if (shouldUpdateUrl) updateThreadUrl(id);
  return true;
}
function closeDetail(shouldUpdateUrl = true) {
  setThreadStage('list');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => { pane.hidden = true; });
  markerById.forEach((marker) => marker.getElement().classList.remove('is-highlighted'));
  list.querySelectorAll('.thread-item').forEach((item) => item.classList.remove('is-open'));
  detailTitle.textContent = '';
  if (shouldUpdateUrl) updateThreadUrl(null);
}
function applyThreadStateFromUrl() {
  const url = new URL(location.href);
  const threadId = threadIdFromUrl();
  if (!threadId) {
    closeDetail(false);
    if (url.searchParams.has('thread')) updateThreadUrl(null, true);
    return;
  }
  if (!openDetail(threadId, false)) {
    closeDetail(false);
    updateThreadUrl(null, true);
    return;
  }
  selectThread(threadId, true);
}
createTrigger.addEventListener('click', () => {
  closeDetail();
  sessionStorage.removeItem(resumeStorageKey);
  creating = true;
  createForm.hidden = false;
  list.hidden = true;
  createTrigger.hidden = true;
});
createCancel.addEventListener('click', () => {
  creating = false;
  createForm.reset();
  createForm.hidden = true;
  list.hidden = false;
  createTrigger.hidden = false;
  document.getElementById('thread-location-status').textContent = '地図上の地点を選択してください。';
  document.getElementById('thread-form-error').hidden = true;
  document.getElementById('thread-form-error').textContent = '';
  selectedInterfaceIds.clear();
  interfaceValueStore.clear();
  renderSelectedInterfaces();
  setThreadStage('list');
  draftMarker?.remove();
  draftMarker = undefined;
});
document.getElementById('close-thread-detail').addEventListener('click', () => {
  closeDetail();
  sessionStorage.removeItem(resumeStorageKey);
});
list.addEventListener('click', (event) => {
  const summary = event.target.closest('.thread-summary');
  if (summary) {
    const id = summary.closest('.thread-item').dataset.threadId;
    selectThread(id);
    openDetail(id);
  }
});
createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = createForm.querySelector('button[type="submit"]');
  if (button.disabled) return;
  button.disabled = true; button.textContent = '投稿中...';
  let created = false;
  try {
    const response = await fetch(createForm.action, {method: 'POST', body: createFormData(), headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const data = await response.json();
    if (response.ok) {
      created = true;
      saveResumeState(data.thread_id, true);
      location.assign(data.redirect_url);
      return;
    }
    const error = document.getElementById('thread-form-error');
    error.textContent = Object.values(data.errors || {}).flat().join(' ');
    error.hidden = false;
  } finally {
    if (!created) { button.disabled = false; button.textContent = '作成する'; }
  }
});
document.querySelectorAll('.thread-reply-form').forEach((form) => form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  if (button.disabled) return;
  button.disabled = true; button.textContent = '送信中...';
  let sent = false;
  const data = csrf(form);
  form.dataset.submissionId ||= crypto.randomUUID();
  data.append('submission_id', form.dataset.submissionId);
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    const result = await response.json();
    if (response.ok) {
      sent = true;
      const threadId = form.closest('[data-thread-detail-pane]')?.dataset.threadDetailPane;
      if (threadId) saveResumeState(threadId);
      location.assign(result.redirect_url);
      return;
    }
  } finally {
    if (!sent) { button.disabled = false; button.textContent = '送信'; }
  }
}));
['filter-show-guests', 'filter-account-ids-enabled'].forEach((id) => document.getElementById(id).addEventListener('change', () => { applyFilters(); savePreferences(); }));
document.getElementById('filter-account-ids').addEventListener('input', applyFilters);
document.getElementById('filter-account-section').addEventListener('toggle', savePreferences);
document.getElementById('current-location-trigger').addEventListener('click', () => {
  navigator.geolocation?.getCurrentPosition(
    (position) => map.jumpTo({center: [position.coords.longitude, position.coords.latitude], zoom: 13}),
    () => window.alert('現在地を取得できませんでした。端末またはブラウザの位置情報設定を確認して、もう一度お試しください。'),
    {timeout: 10000, enableHighAccuracy: false},
  );
});
document.getElementById('location-search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = document.getElementById('location-search-input').value.trim();
  if (query.length < 2) return;
  const response = await fetch(`/api/locations/?q=${encodeURIComponent(query)}`);
  const {locations} = await response.json();
  const results = document.getElementById('location-search-results');
  results.replaceChildren();
  if (!locations.length) {
    const item = document.createElement('li'); item.textContent = '見つかりませんでした。'; results.append(item); return;
  }
  locations.forEach((place) => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = `${place.name} / ${place.detail}`;
    button.addEventListener('click', () => { map.easeTo({center: [place.longitude, place.latitude], zoom: 15, duration: 700, essential: true}); results.replaceChildren(); });
    item.append(button); results.append(item);
  });
});
map.on('click', (event) => {
  if (!creating) return;
  const coordinates = [event.lngLat.lng, event.lngLat.lat]; draftMarker?.remove(); draftMarker = new geolonia.Marker({color: '#d05b32'}).setLngLat(coordinates).addTo(map);
  document.getElementById('thread-latitude').value = event.lngLat.lat.toFixed(6); document.getElementById('thread-longitude').value = event.lngLat.lng.toFixed(6); document.getElementById('thread-location-status').textContent = '地点を選択しました。';
});
map.on('load', () => {
  restoreMapView();
  markers.forEach((thread) => { const marker = new geolonia.Marker({color: '#0f766e'}).setLngLat([thread.longitude, thread.latitude]).addTo(map); marker.getElement().classList.add('event-map-marker'); marker.getElement().addEventListener('click', () => { selectThread(thread.id, true); openDetail(thread.id); }); markerById.set(String(thread.id), marker); });
  applyFilters();
  map.on('moveend', () => {
    sortByDistance();
  });
  if (initialThreadPane) selectThread(initialThreadId);
});
window.addEventListener('popstate', applyThreadStateFromUrl);

const markers = JSON.parse(document.getElementById('thread-markers').textContent);
const interfaceCatalog = JSON.parse(document.getElementById('thread-interface-catalog-data').textContent);
const workspace = document.querySelector('.thread-workspace');
const list = document.getElementById('thread-list');
const createForm = document.getElementById('thread-create-form');
const createTrigger = document.getElementById('thread-create-trigger');
const createCancel = document.getElementById('thread-create-cancel');
const ruleDialog = document.getElementById('thread-rule-dialog');
const map = new geolonia.Map('#map');
const markerById = new Map();
const openThreadStorageKey = 'niimap:open-thread';
const animateThreadStorageKey = 'niimap:animate-thread';
const mapViewStorageKey = 'niimap:map-view';
let draftMarker;
let creating = false;
let activeRuleCapability;
const selectedInterfaceIds = new Set();
const interfaceValueStore = new Map();
let previewInterfaceId = null;

const restoredThreadId = sessionStorage.getItem(openThreadStorageKey);
const animateRestoredThread = sessionStorage.getItem(animateThreadStorageKey) === restoredThreadId;
const restoredThreadPane = restoredThreadId && document.querySelector(`[data-thread-detail-pane="${restoredThreadId}"]`);
const detailTitle = document.getElementById('thread-detail-title');
if (restoredThreadPane) {
  if (!animateRestoredThread) {
    workspace.classList.add('is-detail-open');
    workspace.classList.add('is-restoring-detail');
  }
  restoredThreadPane.hidden = false;
  detailTitle.textContent = `${restoredThreadPane.dataset.threadTitle} (${restoredThreadPane.dataset.threadPostCount})`;
} else {
  sessionStorage.removeItem(openThreadStorageKey);
}
sessionStorage.removeItem(animateThreadStorageKey);
document.documentElement.classList.remove('has-restored-thread-detail');
if (restoredThreadPane) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (animateRestoredThread) workspace.classList.add('is-detail-open');
    else workspace.classList.remove('is-restoring-detail');
  }));
}

document.getElementById('niimap-home-link')?.addEventListener('click', () => {
  sessionStorage.removeItem(openThreadStorageKey);
});

function csrf(form) { return new FormData(form); }
function saveMapView() {
  const center = map.getCenter();
  sessionStorage.setItem(mapViewStorageKey, JSON.stringify({
    latitude: center.lat,
    longitude: center.lng,
    zoom: map.getZoom(),
  }));
}
function restoreMapView() {
  const storedView = sessionStorage.getItem(mapViewStorageKey);
  if (!storedView) return false;

  try {
    const view = JSON.parse(storedView);
    if (![view.latitude, view.longitude, view.zoom].every(Number.isFinite)) return false;
    map.jumpTo({center: [view.longitude, view.latitude], zoom: view.zoom});
    return true;
  } catch {
    return false;
  }
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
function renderInterfacePreview(id) {
  previewInterfaceId = id;
  const item = interfaceCatalog.find((candidate) => candidate.id === id);
  const detail = document.getElementById('thread-interface-selector-detail'); detail.replaceChildren();
  const title = document.createElement('h3'); title.textContent = `${item.name}@${item.creator} v${item.version}`; detail.append(title);
  if (item.description) { const description = document.createElement('p'); description.textContent = item.description; detail.append(description); }
  if (item.requires.length) { const requires = document.createElement('p'); requires.className = 'thread-interface-requires'; requires.textContent = `Require: ${item.requires.map((required) => `${required.name}@${required.creator} v${required.version}`).join(', ')}`; detail.append(requires); }
  item.implementations.forEach((implementation) => appendImplementation(detail, implementation));
  const use = document.createElement('button'); use.className = 'button primary'; use.type = 'button'; use.textContent = selectedInterfaceIds.has(id) ? '入力内容を反映' : 'このInterfaceを使用';
  use.addEventListener('click', () => { detail.querySelectorAll('.thread-interface-field').forEach((field) => field.dispatchEvent(new Event('input'))); selectedInterfaceIds.add(id); renderSelectedInterfaces(); closeInterfaceSelector(); });
  detail.append(use);
}
function openInterfaceSelector(id = null) {
  const selector = document.getElementById('thread-interface-selector'); selector.hidden = false;
  requestAnimationFrame(() => selector.classList.add('is-open'));
  if (id) renderInterfacePreview(id);
}
function closeInterfaceSelector() {
  const selector = document.getElementById('thread-interface-selector'); selector.classList.remove('is-open');
  window.setTimeout(() => { selector.hidden = true; }, 260);
}
document.getElementById('open-thread-interface-selector').addEventListener('click', () => openInterfaceSelector());
document.getElementById('close-thread-interface-selector').addEventListener('click', closeInterfaceSelector);
document.querySelectorAll('[data-thread-interface-tab]').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('[data-thread-interface-tab]').forEach((item) => {
    const active = item === tab;
    item.classList.toggle('is-active', active);
    item.setAttribute('aria-selected', String(active));
  });
  document.querySelectorAll('[data-thread-interface-list]').forEach((list) => {
    list.classList.toggle('is-active', list.dataset.threadInterfaceList === tab.dataset.threadInterfaceTab);
  });
}));
document.querySelectorAll('[data-select-thread-interface]').forEach((button) => button.addEventListener('click', () => renderInterfacePreview(Number(button.dataset.selectThreadInterface))));
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
function openDetail(id) {
  workspace.classList.add('is-detail-open');
  document.querySelectorAll('[data-thread-detail-pane]').forEach((pane) => {
    const selected = pane.dataset.threadDetailPane === String(id);
    pane.hidden = !selected;
    if (selected) detailTitle.textContent = `${pane.dataset.threadTitle} (${pane.dataset.threadPostCount})`;
  });
  sessionStorage.setItem(openThreadStorageKey, String(id));
  document.querySelector('.thread-detail-pane').scrollTo({top: 0});
}
createTrigger.addEventListener('click', () => {
  workspace.classList.remove('is-detail-open');
  sessionStorage.removeItem(openThreadStorageKey);
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
  workspace.classList.remove('is-detail-open');
  draftMarker?.remove();
  draftMarker = undefined;
});
document.getElementById('close-thread-detail').addEventListener('click', () => {
  workspace.classList.remove('is-detail-open');
  sessionStorage.removeItem(openThreadStorageKey);
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
      saveMapView();
      sessionStorage.setItem(openThreadStorageKey, String(data.thread_id));
      sessionStorage.setItem(animateThreadStorageKey, String(data.thread_id));
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
      saveMapView();
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
    saveMapView();
  });
  if (restoredThreadPane) selectThread(restoredThreadId);
});

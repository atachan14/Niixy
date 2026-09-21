const markers = JSON.parse(document.getElementById('thread-markers').textContent);
const workspace = document.querySelector('.thread-workspace');
const list = document.getElementById('thread-list');
const createForm = document.getElementById('thread-create-form');
const createTrigger = document.getElementById('thread-create-trigger');
const createCancel = document.getElementById('thread-create-cancel');
const ruleDialog = document.getElementById('thread-rule-dialog');
const map = new geolonia.Map('#map');
const markerById = new Map();
const openThreadStorageKey = 'niimap:open-thread';
let draftMarker;
let creating = false;
let activeRuleCapability;

const restoredThreadId = sessionStorage.getItem(openThreadStorageKey);
const restoredThreadPane = restoredThreadId && document.querySelector(`[data-thread-detail-pane="${restoredThreadId}"]`);
const detailTitle = document.getElementById('thread-detail-title');
if (restoredThreadPane) {
  workspace.classList.add('is-detail-open');
  workspace.classList.add('is-restoring-detail');
  restoredThreadPane.hidden = false;
  detailTitle.textContent = `${restoredThreadPane.dataset.threadTitle} (${restoredThreadPane.dataset.threadPostCount})`;
} else {
  sessionStorage.removeItem(openThreadStorageKey);
}
document.documentElement.classList.remove('has-restored-thread-detail');
if (restoredThreadPane) {
  requestAnimationFrame(() => requestAnimationFrame(() => workspace.classList.remove('is-restoring-detail')));
}

document.getElementById('niimap-home-link')?.addEventListener('click', () => {
  sessionStorage.removeItem(openThreadStorageKey);
});

function csrf(form) { return new FormData(form); }
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
    setThreadPreview(item.querySelector('.thread-preview'), selected);
  });
  markerById.forEach((marker, markerId) => marker.getElement().classList.toggle('is-highlighted', markerId === String(id)));
  showThreadMarker(id);
  const item = list.querySelector(`[data-thread-id="${id}"]`);
  if (scroll && item) item.scrollIntoView({block: 'nearest'});
}
function setThreadPreview(preview, isOpen) {
  if (isOpen) {
    preview.hidden = false;
    requestAnimationFrame(() => preview.classList.add('is-open'));
    return;
  }

  preview.classList.remove('is-open');
  preview.addEventListener('transitionend', () => {
    if (!preview.classList.contains('is-open')) preview.hidden = true;
  }, {once: true});
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
}
createTrigger.addEventListener('click', () => {
  workspace.classList.remove('is-detail-open');
  sessionStorage.removeItem(openThreadStorageKey);
  creating = true;
  createForm.hidden = false;
  list.hidden = true;
  createTrigger.hidden = true;
});
createCancel.addEventListener('click', () => { creating = false; createForm.hidden = true; list.hidden = false; createTrigger.hidden = false; draftMarker?.remove(); draftMarker = undefined; });
document.getElementById('close-thread-detail').addEventListener('click', () => {
  workspace.classList.remove('is-detail-open');
  sessionStorage.removeItem(openThreadStorageKey);
});
list.addEventListener('click', (event) => {
  const summary = event.target.closest('.thread-summary');
  if (summary) selectThread(summary.closest('.thread-item').dataset.threadId);
  const detail = event.target.closest('[data-thread-detail]');
  if (detail) openDetail(detail.dataset.threadDetail);
});
createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = createForm.querySelector('button[type="submit"]');
  if (button.disabled) return;
  button.disabled = true; button.textContent = '投稿中...';
  try {
    const response = await fetch(createForm.action, {method: 'POST', body: createFormData(), headers: {'X-Requested-With': 'XMLHttpRequest'}});
    const data = await response.json();
    if (response.ok) location.assign(data.redirect_url); else document.getElementById('thread-form-error').textContent = Object.values(data.errors || {}).flat().join(' ');
  } finally { button.disabled = false; button.textContent = '作成する'; }
});
document.querySelectorAll('.thread-reply-form').forEach((form) => form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  if (button.disabled) return;
  button.disabled = true; button.textContent = '送信中...';
  const data = csrf(form);
  form.dataset.submissionId ||= crypto.randomUUID();
  data.append('submission_id', form.dataset.submissionId);
  try { const response = await fetch(form.action, {method: 'POST', body: data}); const result = await response.json(); if (response.ok) location.assign(result.redirect_url); } finally { button.disabled = false; button.textContent = '送信'; }
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
  markers.forEach((thread) => { const marker = new geolonia.Marker({color: '#0f766e'}).setLngLat([thread.longitude, thread.latitude]).addTo(map); marker.getElement().classList.add('event-map-marker'); marker.getElement().addEventListener('click', () => selectThread(thread.id, true)); markerById.set(String(thread.id), marker); });
  applyFilters();
  map.on('moveend', sortByDistance);
  if (restoredThreadPane) selectThread(restoredThreadId);
});

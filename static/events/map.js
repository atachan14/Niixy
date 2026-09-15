const markersElement = document.getElementById('event-markers');
const markers = markersElement ? JSON.parse(markersElement.textContent) : [];
const eventsById = new Map(markers.map((event) => [String(event.id), event]));
const searchForm = document.getElementById('location-search-form');
const searchInput = document.getElementById('location-search-input');
const searchStatus = document.getElementById('location-search-status');
const searchResults = document.getElementById('location-search-results');
const createTrigger = document.getElementById('event-create-trigger');
const createCancel = document.getElementById('event-create-cancel');
const createForm = document.getElementById('event-create-form');
const eventPanel = document.getElementById('event-panel');
const eventPanelTitle = document.getElementById('event-panel-title');
const eventLatitude = document.getElementById('event-latitude');
const eventLongitude = document.getElementById('event-longitude');
const eventLocationStatus = document.getElementById('event-location-status');
const eventFormError = document.getElementById('event-form-error');
const eventList = document.querySelector('.event-list');
const filteredEventsEmpty = document.getElementById('filtered-events-empty');
const rangeFilterEnabled = document.getElementById('filter-range-enabled');
const startsAfterFilter = document.getElementById('filter-starts-after');
const endsBeforeFilter = document.getElementById('filter-ends-before');
const ongoingFilter = document.getElementById('filter-ongoing');
const todayFilter = document.getElementById('filter-today');
const tomorrowFilter = document.getElementById('filter-tomorrow');
const endedFilter = document.getElementById('filter-ended');
let searchMarker;
let draftMarker;
let userLocationMarker;
let isCreatingEvent = false;
let isMapLoaded = false;
let pendingUserLocation;
const eventMapMarkers = new Map();
const mapViewStorageKey = 'niimap:map-view';

eventPanel.append(createForm);

function escapeHtml(value) {
  const element = document.createElement('span');
  element.textContent = value;
  return element.innerHTML;
}

const map = new geolonia.Map('#map');

function saveMapView() {
  const center = map.getCenter();
  const view = {
    latitude: center.lat,
    longitude: center.lng,
    zoom: map.getZoom(),
  };

  sessionStorage.setItem(mapViewStorageKey, JSON.stringify(view));
}

function restoreMapView() {
  const storedView = sessionStorage.getItem(mapViewStorageKey);
  sessionStorage.removeItem(mapViewStorageKey);
  if (!storedView) return false;

  try {
    const view = JSON.parse(storedView);
    if (![view.latitude, view.longitude, view.zoom].every(Number.isFinite)) {
      return false;
    }
    map.jumpTo({ center: [view.longitude, view.latitude], zoom: view.zoom });
    return true;
  } catch {
    return false;
  }
}

function hasStoredMapView() {
  return sessionStorage.getItem(mapViewStorageKey) !== null;
}

function toDatetimeLocalValue(date) {
  const timezoneOffset = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - timezoneOffset).toISOString().slice(0, 16);
}

function eventStartsAt(event) {
  return new Date(event.starts_at);
}

function eventEndsAt(event) {
  return event.ends_at ? new Date(event.ends_at) : eventStartsAt(event);
}

function eventOverlapsDay(event, dayOffset, now) {
  const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() + dayOffset);
  const dayEnd = new Date(dayStart);
  dayEnd.setDate(dayEnd.getDate() + 1);
  return eventStartsAt(event) < dayEnd && eventEndsAt(event) >= dayStart;
}

function eventMatchesTimeFilters(event, now) {
  const matches = [];
  const startsAt = eventStartsAt(event);
  const endsAt = eventEndsAt(event);

  if (rangeFilterEnabled.checked) {
    const startsAfter = startsAfterFilter.value ? new Date(startsAfterFilter.value) : null;
    const endsBefore = endsBeforeFilter.value ? new Date(endsBeforeFilter.value) : null;
    if (startsAfter || endsBefore) {
      matches.push(
        (!startsAfter || startsAt >= startsAfter) && (!endsBefore || endsAt <= endsBefore),
      );
    }
  }

  if (ongoingFilter.checked) {
    matches.push(startsAt <= now && endsAt >= now);
  }
  if (todayFilter.checked) {
    matches.push(eventOverlapsDay(event, 0, now));
  }
  if (tomorrowFilter.checked) {
    matches.push(eventOverlapsDay(event, 1, now));
  }
  if (endedFilter.checked) {
    matches.push(endsAt < now);
  }

  return matches.some(Boolean);
}

function updateRangeFilterFields() {
  const disabled = !rangeFilterEnabled.checked;
  startsAfterFilter.disabled = disabled;
  endsBeforeFilter.disabled = disabled;
}

function applyTimeFilters() {
  const now = new Date();
  let visibleCount = 0;
  const eventItems = eventList.querySelectorAll('[data-event-id]');

  eventItems.forEach((item) => {
    const event = eventsById.get(item.dataset.eventId);
    const isVisible = eventMatchesTimeFilters(event, now);
    const marker = eventMapMarkers.get(item.dataset.eventId);

    item.hidden = !isVisible;
    if (marker) {
      marker.getElement().hidden = !isVisible;
    }
    if (isVisible) {
      visibleCount += 1;
    }
  });

  filteredEventsEmpty.hidden = eventItems.length === 0 || visibleCount !== 0;
  sortEventListByDistance();
}

function initializeTimeFilters() {
  startsAfterFilter.value = toDatetimeLocalValue(new Date());
  updateRangeFilterFields();

  [
    rangeFilterEnabled,
    startsAfterFilter,
    endsBeforeFilter,
    ongoingFilter,
    todayFilter,
    tomorrowFilter,
    endedFilter,
  ].forEach((input) => {
    input.addEventListener('change', () => {
      updateRangeFilterFields();
      applyTimeFilters();
    });
  });

  applyTimeFilters();
  window.setInterval(applyTimeFilters, 60000);
}

function distanceFromMapCenter(event) {
  const center = map.getCenter();
  const toRadians = (value) => (value * Math.PI) / 180;
  const latitudeDelta = toRadians(event.latitude - center.lat);
  const longitudeDelta = toRadians(event.longitude - center.lng);
  const latitude = toRadians(center.lat);
  const eventLatitude = toRadians(event.latitude);
  const haversine =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(latitude) * Math.cos(eventLatitude) * Math.sin(longitudeDelta / 2) ** 2;

  return 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

function sortEventListByDistance() {
  const items = Array.from(eventList.querySelectorAll('[data-event-id]'));

  items
    .sort((first, second) => {
      const firstEvent = eventsById.get(first.dataset.eventId);
      const secondEvent = eventsById.get(second.dataset.eventId);
      return distanceFromMapCenter(firstEvent) - distanceFromMapCenter(secondEvent);
    })
    .forEach((item) => eventList.append(item));
}

function setCurrentLocation(coordinates) {
  const markerElement = document.createElement('div');
  markerElement.className = 'user-location-marker';
  markerElement.setAttribute('aria-label', '現在地');

  if (userLocationMarker) {
    userLocationMarker.remove();
  }

  userLocationMarker = new geolonia.Marker({ element: markerElement })
    .setLngLat(coordinates)
    .addTo(map);
  map.jumpTo({ center: coordinates, zoom: 13 });
}

function showCurrentLocation(position) {
  pendingUserLocation = [position.coords.longitude, position.coords.latitude];
  if (isMapLoaded) {
    setCurrentLocation(pendingUserLocation);
  }
}

function centerOnCurrentLocation() {
  if (!navigator.geolocation) {
    return;
  }

  navigator.geolocation.getCurrentPosition(showCurrentLocation, () => {}, {
    enableHighAccuracy: false,
    maximumAge: 300000,
    timeout: 6000,
  });
}

if (!hasStoredMapView()) {
  centerOnCurrentLocation();
}

function setCreateMode(enabled) {
  isCreatingEvent = enabled;
  createTrigger.hidden = enabled;
  createCancel.hidden = !enabled;
  createForm.hidden = !enabled;
  eventPanel.classList.toggle('is-creating', enabled);
  eventPanelTitle.textContent = enabled ? 'Event投稿' : 'Event一覧';
  map.getContainer().classList.toggle('is-creating-event', enabled);

  if (enabled) {
    map.dragPan.disable();
  } else {
    map.dragPan.enable();
  }

  if (!enabled) {
    if (draftMarker) {
      draftMarker.remove();
      draftMarker = undefined;
    }
    createForm.reset();
    clearFormErrors();
    eventLocationStatus.textContent = '地図上の地点を選択してください。';
  }
}

function clearFormErrors() {
  createForm.querySelectorAll('.field-error').forEach((error) => error.remove());
  eventFormError.hidden = true;
  eventFormError.textContent = '';
}

function showFormErrors(errors) {
  clearFormErrors();

  Object.entries(errors).forEach(([fieldName, messages]) => {
    const message = messages.join(' ');
    if (fieldName === 'latitude' || fieldName === 'longitude') {
      eventLocationStatus.textContent = '地図上で地点を選択してください。';
      return;
    }

    const input = createForm.elements.namedItem(fieldName);
    const field = input && input.closest('.field');
    if (!field) {
      eventFormError.textContent = message;
      eventFormError.hidden = false;
      return;
    }

    const error = document.createElement('p');
    error.className = 'field-error';
    error.textContent = message;
    field.append(error);
  });
}

function setEventOpen(item, isOpen) {
  item.querySelector('.event-summary').setAttribute('aria-expanded', String(isOpen));
  const body = item.querySelector('.event-body');
  body.setAttribute('aria-hidden', String(!isOpen));
  item.classList.toggle('is-open', isOpen);
}

document.querySelectorAll('.event-body').forEach((body) => {
  body.hidden = false;
  body.setAttribute('aria-hidden', 'true');
});

function openEventItem(eventId, shouldScroll) {
  const items = Array.from(document.querySelectorAll('[data-event-id]'));
  const selectedItem = items.find((item) => item.dataset.eventId === String(eventId));
  if (!selectedItem) return;
  items.forEach((item) => setEventOpen(item, item === selectedItem));
  if (shouldScroll) {
    const block = window.matchMedia('(max-width: 780px)').matches ? 'nearest' : 'start';
    selectedItem.scrollIntoView({ behavior: 'smooth', block });
  }
}

document.querySelectorAll('.event-summary').forEach((summary) => {
  summary.addEventListener('click', () => {
    const item = summary.closest('[data-event-id]');
    const isOpen = summary.getAttribute('aria-expanded') === 'true';
    document.querySelectorAll('[data-event-id]').forEach((eventItem) => setEventOpen(eventItem, false));
    if (!isOpen) setEventOpen(item, true);
  });
});

createTrigger.addEventListener('click', () => setCreateMode(true));
createCancel.addEventListener('click', () => setCreateMode(false));

createForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearFormErrors();

  try {
    const response = await fetch(createForm.action, {
      method: 'POST',
      body: new FormData(createForm),
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const data = await response.json();

    if (response.ok) {
      saveMapView();
      window.location.assign(data.redirect_url);
      return;
    }

    showFormErrors(data.errors || {});
  } catch (error) {
    eventFormError.textContent = '投稿できませんでした。時間をおいて再度お試しください。';
    eventFormError.hidden = false;
  }
});

if (new URLSearchParams(window.location.search).get('mode') === 'create') {
  setCreateMode(true);
}

map.on('click', (event) => {
  if (!isCreatingEvent) {
    return;
  }

  const coordinates = [event.lngLat.lng, event.lngLat.lat];
  if (draftMarker) {
    draftMarker.remove();
  }

  draftMarker = new geolonia.Marker({ color: '#d05b32' })
    .setLngLat(coordinates)
    .addTo(map);
  eventLatitude.value = event.lngLat.lat.toFixed(6);
  eventLongitude.value = event.lngLat.lng.toFixed(6);
  eventLocationStatus.textContent = '地点を選択しました。もう一度タップすると移動できます。';
});

function clearSearchResults() {
  searchResults.replaceChildren();
}

function selectSearchResult(place) {
  const coordinates = [place.longitude, place.latitude];

  if (searchMarker) {
    searchMarker.remove();
  }

  const popup = new geolonia.Popup({ offset: 24 }).setHTML(
    `<strong>${escapeHtml(place.name)}</strong><br>${escapeHtml(place.detail)}`,
  );

  searchMarker = new geolonia.Marker({ color: '#d05b32' })
    .setLngLat(coordinates)
    .setPopup(popup)
    .addTo(map)
    .togglePopup();

  map.flyTo({ center: coordinates, zoom: 16, essential: true });
  searchStatus.textContent = `${place.name} / ${place.detail}`;
  clearSearchResults();
}

function showSearchResults(places) {
  clearSearchResults();

  if (!places.length) {
    searchStatus.textContent = '見つかりませんでした。';
    return;
  }

  searchStatus.textContent = `${places.length}件の候補`;

  places.forEach((place) => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    const name = document.createElement('strong');
    const detail = document.createElement('span');

    button.type = 'button';
    name.textContent = place.name;
    detail.textContent = place.detail;
    button.append(name, detail);
    button.addEventListener('click', () => selectSearchResult(place));
    item.append(button);
    searchResults.append(item);
  });
}

async function searchLocation(query) {
  searchStatus.textContent = '検索中…';
  clearSearchResults();
  const response = await fetch(`/api/locations/?q=${encodeURIComponent(query)}`);

  if (!response.ok) {
    throw new Error('Location search failed');
  }

  const { locations } = await response.json();
  showSearchResults(locations);
}

searchForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const query = searchInput.value.trim();

  if (query.length < 2) {
    searchStatus.textContent = '2文字以上で検索してください。';
    return;
  }

  try {
    await searchLocation(query);
  } catch (error) {
    searchStatus.textContent = '検索できませんでした。時間をおいて再度お試しください。';
  }
});

map.on('load', () => {
  isMapLoaded = true;
  const restoredMapView = restoreMapView();

  markers.forEach((event) => {
    const coordinates = [event.longitude, event.latitude];
    const marker = new geolonia.Marker({ color: '#0f766e' })
      .setLngLat(coordinates)
      .addTo(map);
    marker.getElement().addEventListener('click', () => openEventItem(event.id, true));
    eventMapMarkers.set(String(event.id), marker);
  });

  sortEventListByDistance();
  map.on('moveend', sortEventListByDistance);
  initializeTimeFilters();
  if (restoredMapView) {
    return;
  }

  if (pendingUserLocation) {
    setCurrentLocation(pendingUserLocation);
  }
});

const DATA_URL = 'data/news.json';
let dashboardData = null;
let map = null;
let markersLayer = null;

const labels = {
  signal: { high: '高', medium: '中', low: '低' },
  classification: { variant: 'Variant', vaccine: 'Vaccine', outbreak: 'Outbreak', general: 'General' },
  topic: {
    vaccine_policy: 'ワクチン政策', variant: '変異株', outbreak: 'アウトブレイク', safety: '安全性', supply_access: '供給・アクセス', research: '研究', general: '一般'
  },
  eventType: {
    outbreak_report: '発生報告', variant_update: '変異株更新', policy_update: '政策更新', safety_update: '安全性更新', study_result: '研究結果', supply_update: '供給更新', general_update: '一般更新'
  }
};

const els = {
  searchInput: document.getElementById('searchInput'),
  regionFilter: document.getElementById('regionFilter'),
  countryFilter: document.getElementById('countryFilter'),
  classificationFilter: document.getElementById('classificationFilter'),
  topicFilter: document.getElementById('topicFilter'),
  eventTypeFilter: document.getElementById('eventTypeFilter'),
  signalFilter: document.getElementById('signalFilter'),
  daysFilter: document.getElementById('daysFilter'),
  officialOnly: document.getElementById('officialOnly'),
  asiaPriorityOnly: document.getElementById('asiaPriorityOnly'),
  resetBtn: document.getElementById('resetBtn'),
  summaryStats: document.getElementById('summaryStats'),
  feedStatus: document.getElementById('feedStatus'),
  newsList: document.getElementById('newsList'),
  lastUpdatedBadge: document.getElementById('lastUpdatedBadge'),
  resultCount: document.getElementById('resultCount'),
  activeFilters: document.getElementById('activeFilters'),
  tpl: document.getElementById('newsCardTemplate')
};

async function main() {
  const res = await fetch(DATA_URL, { cache: 'no-store' });
  dashboardData = await res.json();
  els.lastUpdatedBadge.textContent = `更新: ${formatDateTime(dashboardData.generated_at)}`;
  initMap();
  populateFilterOptions();
  bindEvents();
  render();
}

function bindEvents() {
  Object.values({
    searchInput: els.searchInput,
    regionFilter: els.regionFilter,
    countryFilter: els.countryFilter,
    classificationFilter: els.classificationFilter,
    topicFilter: els.topicFilter,
    eventTypeFilter: els.eventTypeFilter,
    signalFilter: els.signalFilter,
    daysFilter: els.daysFilter,
    officialOnly: els.officialOnly,
    asiaPriorityOnly: els.asiaPriorityOnly
  }).forEach(el => el.addEventListener('input', render));
  els.resetBtn.addEventListener('click', () => {
    els.searchInput.value = '';
    els.regionFilter.value = 'All';
    els.countryFilter.value = 'All';
    els.classificationFilter.value = 'All';
    els.topicFilter.value = 'All';
    els.eventTypeFilter.value = 'All';
    els.signalFilter.value = 'All';
    els.daysFilter.value = '14';
    els.officialOnly.checked = false;
    els.asiaPriorityOnly.checked = false;
    render();
  });
}

function populateFilterOptions() {
  const items = dashboardData.items || [];
  fillSelect(els.regionFilter, unique(items.map(x => x.region).filter(Boolean)), 'All');
  fillSelect(els.countryFilter, unique(items.map(x => x.country).filter(Boolean)), 'All');
  fillSelect(els.classificationFilter, unique(items.map(x => x.primary_classification).filter(Boolean)), 'All');
  fillSelect(els.topicFilter, unique(items.map(x => x.topic).filter(Boolean)), 'All');
  fillSelect(els.eventTypeFilter, unique(items.map(x => x.event_type).filter(Boolean)), 'All');
  fillSelect(els.signalFilter, ['high', 'medium', 'low'], 'All');
}

function fillSelect(select, values, first) {
  select.innerHTML = '';
  [first, ...values].forEach(v => {
    const option = document.createElement('option');
    option.value = v;
    option.textContent = humanizeFilterValue(v);
    select.appendChild(option);
  });
}

function humanizeFilterValue(v) {
  if (v === 'All') return 'すべて';
  return labels.classification[v] || labels.topic[v] || labels.eventType[v] || v;
}

function render() {
  const filtered = applyFilters(dashboardData.items || []);
  renderStats(filtered);
  renderFeeds(dashboardData.feed_status || []);
  renderNews(filtered);
  renderMap(filtered);
  renderActiveFilters(filtered.length);
}

function applyFilters(items) {
  const query = els.searchInput.value.trim().toLowerCase();
  const region = els.regionFilter.value;
  const country = els.countryFilter.value;
  const classification = els.classificationFilter.value;
  const topic = els.topicFilter.value;
  const eventType = els.eventTypeFilter.value;
  const signal = els.signalFilter.value;
  const days = Number(els.daysFilter.value || '14');
  const officialOnly = els.officialOnly.checked;
  const asiaOnly = els.asiaPriorityOnly.checked;
  const now = new Date(dashboardData.generated_at || Date.now());

  return items.filter(item => {
    const itemDate = new Date(item.published || item.discovered_at || dashboardData.generated_at);
    const ageDays = (now - itemDate) / (1000 * 60 * 60 * 24);
    if (ageDays > days) return false;
    if (region !== 'All' && item.region !== region) return false;
    if (country !== 'All' && item.country !== country) return false;
    if (classification !== 'All' && item.primary_classification !== classification && !(item.classifications || []).includes(classification)) return false;
    if (topic !== 'All' && item.topic !== topic) return false;
    if (eventType !== 'All' && item.event_type !== eventType) return false;
    if (signal !== 'All' && item.signal_level !== signal) return false;
    if (officialOnly && !item.is_official) return false;
    if (asiaOnly && !item.is_asia_priority) return false;
    if (query) {
      const haystack = [item.title, item.title_ja, item.summary, item.summary_ja, item.source_name, item.country, item.region, item.topic]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  }).sort((a, b) => new Date(b.published || 0) - new Date(a.published || 0));
}

function renderStats(items) {
  const total = items.length;
  const countries = unique(items.map(x => x.country).filter(Boolean)).length;
  const high = items.filter(x => x.signal_level === 'high').length;
  const deduped = items.filter(x => (x.duplicate_count || 1) > 1).length;

  const stats = [
    ['シグナル数', total],
    ['国・地域数', countries],
    ['高優先度', high],
    ['重複統合済み', deduped]
  ];

  els.summaryStats.innerHTML = stats.map(([label, value]) => `
    <div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
    </div>`).join('');
}

function renderFeeds(feeds) {
  els.feedStatus.innerHTML = feeds.map(feed => `
    <div class="feed-row">
      <div>
        <div class="feed-name">${escapeHtml(feed.name)}</div>
        <div class="feed-meta">${escapeHtml(feed.url || '')}</div>
      </div>
      <div class="${feed.status === 'ok' ? 'feed-ok' : 'feed-error'}">${feed.status === 'ok' ? 'OK' : 'Error'}</div>
    </div>
  `).join('');
}

function renderNews(items) {
  els.resultCount.textContent = `${items.length} 件`;
  els.newsList.innerHTML = '';
  if (!items.length) {
    els.newsList.innerHTML = '<div class="muted">条件に一致するシグナルはありません。</div>';
    return;
  }

  items.forEach(item => {
    const frag = els.tpl.content.cloneNode(true);
    const signalTag = frag.querySelector('.tag-signal');
    signalTag.textContent = `重要度: ${labels.signal[item.signal_level] || item.signal_level}`;
    signalTag.classList.add(item.signal_level || 'low');

    frag.querySelector('.tag-classification').textContent = labels.classification[item.primary_classification] || item.primary_classification || 'General';
    frag.querySelector('.tag-topic').textContent = labels.topic[item.topic] || item.topic || '一般';
    frag.querySelector('.tag-event').textContent = labels.eventType[item.event_type] || item.event_type || '一般更新';
    frag.querySelector('.tag-region').textContent = item.region || 'Unknown region';
    frag.querySelector('.news-date').textContent = formatDate(item.published || item.discovered_at);

    const link = frag.querySelector('.news-title a');
    link.textContent = item.title_ja || item.title;
    link.href = item.link;

    frag.querySelector('.news-source-line').textContent = `${item.source_name || 'Unknown source'} · ${item.country || 'Unknown country'}${item.is_official ? ' · 一次情報' : ''}`;
    frag.querySelector('.news-summary').textContent = item.summary_ja || item.summary || '';
    frag.querySelector('.news-original-title').textContent = item.title || '';
    frag.querySelector('.news-original-summary').textContent = item.summary || '';

    const extra = [];
    if ((item.classifications || []).length > 1) extra.push(`分類: ${escapeHtml(item.classifications.join(', '))}`);
    if ((item.duplicate_count || 1) > 1) extra.push(`重複統合: ${item.duplicate_count}件`);
    if ((item.merged_sources || []).length > 1) extra.push(`ソース: ${escapeHtml(item.merged_sources.join(', '))}`);
    frag.querySelector('.news-footer').innerHTML = extra.join(' · ');

    els.newsList.appendChild(frag);
  });
}

function initMap() {
  map = L.map('map', { scrollWheelZoom: true }).setView([20, 20], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 6,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
}

function markerRadius(item) {
  const base = item.signal_level === 'high' ? 10 : item.signal_level === 'medium' ? 8 : 6;
  return base + Math.min((item.duplicate_count || 1) - 1, 4);
}

function renderMap(items) {
  markersLayer.clearLayers();
  const bounds = [];
  items.filter(x => Number.isFinite(x.lat) && Number.isFinite(x.lon)).forEach(item => {
    const marker = L.circleMarker([item.lat, item.lon], {
      radius: markerRadius(item),
      weight: 1,
      fillOpacity: 0.85
    });
    marker.bindPopup(`
      <strong>${escapeHtml(item.title_ja || item.title)}</strong><br>
      ${escapeHtml(item.country || '')} · ${escapeHtml(labels.classification[item.primary_classification] || item.primary_classification || '')}<br>
      ${escapeHtml(item.summary_ja || item.summary || '')}<br>
      <a href="${item.link}" target="_blank" rel="noopener">記事を開く</a>
    `);
    marker.addTo(markersLayer);
    bounds.push([item.lat, item.lon]);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
}

function renderActiveFilters() {
  const chips = [];
  [['Region', els.regionFilter.value], ['Country', els.countryFilter.value], ['Class', els.classificationFilter.value], ['Topic', els.topicFilter.value], ['Event', els.eventTypeFilter.value], ['Signal', els.signalFilter.value]]
    .forEach(([k, v]) => { if (v !== 'All') chips.push(`${k}: ${humanizeFilterValue(v)}`); });
  if (els.officialOnly.checked) chips.push('一次情報のみ');
  if (els.asiaPriorityOnly.checked) chips.push('アジア優先のみ');
  const days = els.daysFilter.value;
  chips.push(`期間: ${days === '3650' ? '全期間' : `直近${days}日`}`);
  if (els.searchInput.value.trim()) chips.push(`検索: ${els.searchInput.value.trim()}`);
  els.activeFilters.innerHTML = chips.map(c => `<span class="chip">${escapeHtml(c)}</span>`).join('');
}

function unique(arr) { return [...new Set(arr)].sort((a, b) => String(a).localeCompare(String(b))); }
function escapeHtml(str) { return String(str || '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s])); }
function formatDate(s) { if (!s) return ''; return new Date(s).toLocaleDateString('ja-JP'); }
function formatDateTime(s) { if (!s) return ''; return new Date(s).toLocaleString('ja-JP', { hour12: false }); }

main().catch(err => {
  console.error(err);
  document.body.innerHTML = `<div style="padding:24px;font-family:sans-serif;">ダッシュボードを読み込めませんでした。</div>`;
});

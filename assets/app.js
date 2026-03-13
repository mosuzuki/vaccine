
const DATA_URL = 'data/news.json';
let dashboardData = null;
let map = null;
let markersLayer = null;

const policyLabels = {
  recommendation: '推奨・勧告',
  schedule: '接種スケジュール',
  approval: '承認・適応',
  funding: '財政・調達',
  safety: '安全性',
  outbreak_response: '流行対応',
  access_campaign: '接種促進',
  general_policy: '政策一般'
};

const sourceTypeLabels = { official: '一次情報', media: '高信頼メディア' };

const els = {
  searchInput: document.getElementById('searchInput'),
  regionFilter: document.getElementById('regionFilter'),
  countryFilter: document.getElementById('countryFilter'),
  policyFilter: document.getElementById('policyFilter'),
  sourceTypeFilter: document.getElementById('sourceTypeFilter'),
  daysFilter: document.getElementById('daysFilter'),
  plotMode: document.getElementById('plotMode'),
  officialOnly: document.getElementById('officialOnly'),
  asiaOnly: document.getElementById('asiaOnly'),
  resetBtn: document.getElementById('resetBtn'),
  summaryStats: document.getElementById('summaryStats'),
  feedStatus: document.getElementById('feedStatus'),
  newsList: document.getElementById('newsList'),
  lastUpdatedBadge: document.getElementById('lastUpdatedBadge'),
  resultCount: document.getElementById('resultCount'),
  activeFilters: document.getElementById('activeFilters'),
  tpl: document.getElementById('newsCardTemplate')
};

main();

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
  [els.searchInput, els.regionFilter, els.countryFilter, els.policyFilter, els.sourceTypeFilter, els.daysFilter, els.plotMode, els.officialOnly, els.asiaOnly]
    .forEach(el => el.addEventListener('input', render));
  els.resetBtn.addEventListener('click', () => {
    els.searchInput.value = '';
    els.regionFilter.value = 'All';
    els.countryFilter.value = 'All';
    els.policyFilter.value = 'All';
    els.sourceTypeFilter.value = 'All';
    els.daysFilter.value = '14';
    els.plotMode.value = 'topic';
    els.officialOnly.checked = false;
    els.asiaOnly.checked = false;
    render();
  });
}

function populateFilterOptions() {
  const items = dashboardData.items || [];
  fillSelect(els.regionFilter, unique(items.map(x => x.topic_region).filter(Boolean)), 'All');
  fillSelect(els.countryFilter, unique(items.map(x => x.topic_country).filter(Boolean)), 'All');
  fillSelect(els.policyFilter, unique(items.map(x => x.policy_tags || []).flat().filter(Boolean)), 'All');
  fillSelect(els.sourceTypeFilter, ['official', 'media'], 'All');
}

function fillSelect(select, values, first) {
  select.innerHTML = '';
  [first, ...values].forEach(v => {
    const option = document.createElement('option');
    option.value = v;
    option.textContent = humanize(v);
    select.appendChild(option);
  });
}

function humanize(v) {
  if (v === 'All') return 'すべて';
  return policyLabels[v] || sourceTypeLabels[v] || v;
}

function applyFilters(items) {
  const q = els.searchInput.value.trim().toLowerCase();
  const region = els.regionFilter.value;
  const country = els.countryFilter.value;
  const policy = els.policyFilter.value;
  const sourceType = els.sourceTypeFilter.value;
  const days = Number(els.daysFilter.value || '14');
  const officialOnly = els.officialOnly.checked;
  const asiaOnly = els.asiaOnly.checked;
  const now = new Date(dashboardData.generated_at || Date.now());

  return items.filter(item => {
    const dt = new Date(item.published_at || dashboardData.generated_at);
    const ageDays = (now - dt) / (1000 * 60 * 60 * 24);
    if (ageDays > days) return false;
    if (region !== 'All' && item.topic_region !== region) return false;
    if (country !== 'All' && item.topic_country !== country) return false;
    if (policy !== 'All' && !(item.policy_tags || []).includes(policy)) return false;
    if (sourceType !== 'All' && item.source_type !== sourceType) return false;
    if (officialOnly && item.source_type !== 'official') return false;
    if (asiaOnly && item.topic_region !== 'Asia') return false;
    if (q) {
      const hay = [item.title, item.summary, item.title_original, item.summary_original, item.topic_country, item.source_name, item.publisher, (item.policy_tags || []).join(' ')].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }).sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
}

function render() {
  const items = applyFilters(dashboardData.items || []);
  renderStats(items);
  renderFeedStatus(dashboardData.feed_status || []);
  renderCards(items);
  renderMap(items);
  renderActiveFilters(items.length);
}

function renderStats(items) {
  const stats = [
    ['記事数', items.length],
    ['対象国数', unique(items.map(x => x.topic_country).filter(x => x && x !== '不明')).length],
    ['一次情報', items.filter(x => x.source_type === 'official').length],
    ['重複統合', items.filter(x => (x.duplicate_count || 1) > 1).length]
  ];
  els.summaryStats.innerHTML = stats.map(([k, v]) => `<div class="stat-card"><div class="stat-label">${k}</div><div class="stat-value">${v}</div></div>`).join('');
}

function renderFeedStatus(feeds) {
  els.feedStatus.innerHTML = feeds.map(feed => `
    <div class="feed-row">
      <div>
        <div class="feed-name">${escapeHtml(feed.name)}</div>
        <div class="feed-meta">${escapeHtml(feed.url || '')}</div>
      </div>
      <div class="${feed.status === 'ok' ? 'feed-ok' : 'feed-error'}">${feed.status === 'ok' ? `OK (${feed.items})` : 'Error'}</div>
    </div>`).join('');
}

function renderCards(items) {
  els.resultCount.textContent = `${items.length} 件`;
  els.newsList.innerHTML = '';
  if (!items.length) {
    els.newsList.innerHTML = '<div class="muted">条件に一致する記事はありません。</div>';
    return;
  }
  items.forEach(item => {
    const frag = els.tpl.content.cloneNode(true);
    frag.querySelector('.tag-policy').textContent = (item.policy_tags || []).map(x => policyLabels[x] || x).join(' / ') || '政策一般';
    const sourceTag = frag.querySelector('.tag-source-type');
    sourceTag.textContent = sourceTypeLabels[item.source_type] || item.source_type;
    sourceTag.classList.add(item.source_type || 'media');
    frag.querySelector('.tag-region').textContent = item.topic_region || 'Unknown';
    frag.querySelector('.news-date').textContent = formatDate(item.published_at);
    const a = frag.querySelector('.news-title a');
    a.textContent = item.title || item.title_original || '(no title)';
    a.href = item.link || '#';
    frag.querySelector('.news-source-line').textContent = `${item.publisher || item.source_name || ''} · 対象国: ${item.topic_country || '不明'} · 発信元: ${item.source_origin_name || '不明'}`;
    frag.querySelector('.news-summary').textContent = item.summary || item.summary_original || '';
    frag.querySelector('.news-original-title').textContent = item.title_original || '';
    frag.querySelector('.news-original-summary').textContent = item.summary_original || '';
    const footer = [];
    if ((item.duplicate_count || 1) > 1) footer.push(`重複統合 ${item.duplicate_count} 件`);
    if ((item.duplicate_sources || []).length > 1) footer.push(`統合元: ${item.duplicate_sources.join(', ')}`);
    if ((item.variant_tags || []).length) footer.push(`variant: ${item.variant_tags.join(', ')}`);
    footer.push(`地図: ${item.plot_basis === 'topic' ? '対象国' : '発信元'}`);
    frag.querySelector('.news-footer').textContent = footer.join(' · ');
    els.newsList.appendChild(frag);
  });
}

function initMap() {
  map = L.map('map', { scrollWheelZoom: true }).setView([20, 15], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 7,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
}

function renderMap(items) {
  markersLayer.clearLayers();
  const bounds = [];
  const mode = els.plotMode.value;
  items.forEach(item => {
    const lat = mode === 'source' ? item.source_lat : item.plot_lat;
    const lng = mode === 'source' ? item.source_lng : item.plot_lng;
    const label = mode === 'source' ? item.source_origin_name : item.plot_label;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
    const marker = L.circleMarker([lat, lng], { radius: markerRadius(item), weight: 1, fillOpacity: 0.82 });
    marker.bindPopup(`
      <strong>${escapeHtml(item.title || item.title_original || '')}</strong><br>
      ${escapeHtml(label || '')}<br>
      対象国: ${escapeHtml(item.topic_country || '不明')}<br>
      発信元: ${escapeHtml(item.source_origin_name || '不明')}<br>
      <a href="${item.link || '#'}" target="_blank" rel="noopener">記事を開く</a>
    `);
    marker.addTo(markersLayer);
    bounds.push([lat, lng]);
  });
  if (bounds.length) map.fitBounds(bounds, { padding: [28, 28] });
  else map.setView([20, 15], 2);
}

function markerRadius(item) {
  return Math.min(12, 6 + Math.max(0, (item.duplicate_count || 1) - 1));
}

function renderActiveFilters() {
  const chips = [];
  [['地域', els.regionFilter.value], ['国', els.countryFilter.value], ['政策分類', els.policyFilter.value], ['情報源', els.sourceTypeFilter.value]].forEach(([k,v]) => {
    if (v !== 'All') chips.push(`${k}: ${humanize(v)}`);
  });
  chips.push(`期間: ${els.daysFilter.value === '3650' ? '全期間' : `直近${els.daysFilter.value}日`}`);
  chips.push(`地図: ${els.plotMode.value === 'source' ? '発信元' : '対象国優先'}`);
  if (els.officialOnly.checked) chips.push('一次情報のみ');
  if (els.asiaOnly.checked) chips.push('アジアのみ');
  if (els.searchInput.value.trim()) chips.push(`検索: ${els.searchInput.value.trim()}`);
  els.activeFilters.innerHTML = chips.map(x => `<span class="chip">${escapeHtml(x)}</span>`).join('');
}

function unique(arr) { return [...new Set(arr)].sort((a,b)=>String(a).localeCompare(String(b), 'ja')); }
function formatDate(s) { if (!s) return ''; return new Date(s).toLocaleDateString('ja-JP'); }
function formatDateTime(s) { if (!s) return ''; return new Date(s).toLocaleString('ja-JP'); }
function escapeHtml(str='') {
  return str.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

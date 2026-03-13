let allItems = [];
let map;
let markersLayer;

function fmtDate(s){try{return new Date(s).toLocaleString('ja-JP');}catch{return s;}}
function el(id){return document.getElementById(id);}

async function loadData(){
  const res = await fetch('data/news.json?ts=' + Date.now());
  const data = await res.json();
  el('title').textContent = data.title;
  el('description').textContent = data.description;
  el('generatedAt').textContent = '更新: ' + fmtDate(data.generated_at);
  el('itemCount').textContent = '件数: ' + data.item_count;
  allItems = data.items || [];
  const mode = data.map_default_mode || 'source';
  el('mapMode').value = mode;
  buildPolicyFilter();
  renderFeedStatus(data.feed_status || []);
  render();
}

function buildPolicyFilter(){
  const set = new Set();
  allItems.forEach(i => (i.policy_tags || []).forEach(t => set.add(t)));
  const sel = el('policyFilter');
  [...set].sort().forEach(t => {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t; sel.appendChild(opt);
  });
}

function filteredItems(){
  const tier = el('tierFilter').value;
  const policy = el('policyFilter').value;
  const q = el('searchInput').value.trim().toLowerCase();
  return allItems.filter(i => {
    if(tier !== 'all' && String(i.tier) !== tier) return false;
    if(policy !== 'all' && !(i.policy_tags || []).includes(policy)) return false;
    if(q){
      const text = [i.title,i.summary,i.title_original,i.summary_original,i.country,i.source,(i.policy_tags||[]).join(' ')].join(' ').toLowerCase();
      if(!text.includes(q)) return false;
    }
    return true;
  });
}

function renderCards(items){
  const box = el('cards');
  box.innerHTML = '';
  items.forEach(i => {
    const card = document.createElement('article');
    card.className = 'card';
    const tags = [...(i.policy_tags||[]), ...(i.topics||[]).slice(0,2), 'Tier ' + i.tier].map(t => `<span class="tag">${t}</span>`).join('');
    card.innerHTML = `
      <h3><a href="${i.link}" target="_blank" rel="noopener">${i.title || i.title_original}</a></h3>
      <div class="muted">${fmtDate(i.published_at)} / ${i.source} / 発信元: ${i.source_location?.name_ja || '不明'} / 対象国: ${i.target_location?.name_ja || '不明'}</div>
      <div class="tags">${tags}</div>
      <p>${i.summary || ''}</p>
      <details><summary>原文</summary><p>${i.title_original || ''}</p><p>${i.summary_original || ''}</p></details>
    `;
    box.appendChild(card);
  });
}

function renderFeedStatus(feedStatus){
  const box = el('feedStatus');
  box.innerHTML = '';
  feedStatus.forEach(f => {
    const d = document.createElement('div');
    d.className = 'status';
    d.innerHTML = `<strong>${f.name}</strong><div class="muted">Tier ${f.tier || '-'} / ${f.status}${f.items !== undefined ? ' / ' + f.items + '件' : ''}</div>`;
    box.appendChild(d);
  });
}

function ensureMap(){
  if(map) return;
  map = L.map('map').setView([20, 0], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 18, attribution: '&copy; OpenStreetMap'}).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
}

function renderMap(items){
  ensureMap();
  markersLayer.clearLayers();
  const mode = el('mapMode').value;
  items.forEach(i => {
    const loc = mode === 'target' ? (i.target_location || {}) : (i.source_location || {});
    const lat = mode === 'target' ? i.target_location?.lat : i.source_location?.lat;
    const lng = mode === 'target' ? i.target_location?.lng : i.source_location?.lng;
    if(lat == null || lng == null) return;
    const popup = `<strong>${i.title || i.title_original}</strong><br>${i.source}<br>${mode === 'target' ? '対象国' : '発信元'}: ${loc.name_ja || '不明'}<br><a href="${i.link}" target="_blank" rel="noopener">記事を開く</a>`;
    L.marker([lat,lng]).bindPopup(popup).addTo(markersLayer);
  });
}

function render(){
  const items = filteredItems();
  renderCards(items);
  renderMap(items);
}

['mapMode','tierFilter','policyFilter','searchInput'].forEach(id => {
  window.addEventListener('DOMContentLoaded', () => el(id).addEventListener(id==='searchInput'?'input':'change', render));
});
window.addEventListener('DOMContentLoaded', loadData);

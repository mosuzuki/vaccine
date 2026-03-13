const byId = id => document.getElementById(id);
let allItems = [];
let map, markersLayer;

const JA = {
  policy: '政策',
  research: '研究開発',
  communication: 'コミュニケーション',
  recommendation: '勧告',
  schedule: '接種スケジュール',
  approval: '承認・適応',
  financing: '財政・調達',
  safety: '安全性',
  outbreak_response: '流行対応',
  covid: 'COVID-19',
  influenza: 'インフルエンザ',
  rsv: 'RSV',
  measles: '麻疹',
  polio: 'ポリオ',
  hpv: 'HPV',
  pneumococcal: '肺炎球菌',
  pertussis: '百日咳',
  dengue: 'デング',
  mpox: 'mpox',
  cholera: 'コレラ',
  ebola: 'エボラ',
  rotavirus: 'ロタウイルス',
  meningococcal: '髄膜炎菌',
  hepatitis: '肝炎',
  malaria: 'マラリア',
  'Tier 1': 'Tier 1',
  'Tier 3': 'Tier 3'
};

function esc(s=''){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;')}
function fmtDate(v){try{return new Date(v).toLocaleString('ja-JP')}catch{return v||''}}
function ja(v){return JA[v] || v}
function badge(label, cls=''){return `<span class="badge ${cls}">${esc(label)}</span>`}

function renderHeader(data){
  byId('site-title').textContent = data.title || 'Vaccine and Immunization Monitoring';
  byId('site-desc').textContent = data.description || '';
  byId('generated-at').textContent = `更新: ${fmtDate(data.generated_at)}`;
  byId('item-count').textContent = `件数: ${data.item_count || 0}`;
  const plot = byId('plot-mode');
  if (data.plot_mode_default) plot.value = data.plot_mode_default;
}

function renderFeedStatus(feedStatus=[]){
  const el = byId('feed-status');
  el.innerHTML = feedStatus.map(f=>{
    const status = f.status === 'ok' ? 'ok' : 'error';
    const detail = f.status === 'ok' ? `seen ${f.seen ?? 0} / kept ${f.kept ?? 0}` : esc(f.error || '');
    return `<div class="feed-item"><span class="${status}">${esc(f.name)}</span> <span class="small">${detail}</span></div>`;
  }).join('');
}

function passesFilters(item){
  const q = byId('search').value.trim().toLowerCase();
  const topic = byId('topic-filter').value;
  const policy = byId('policy-filter').value;
  const vaccine = byId('vaccine-filter').value;
  const mode = byId('plot-mode').value;
  const hay = [item.title, item.summary_ai, item.title_original, item.summary_ai_original, item.source, item.target_country, item.source_location?.label].join(' ').toLowerCase();
  if (q && !hay.includes(q)) return false;
  if (topic && !(item.topics || []).includes(topic)) return false;
  if (policy && !(item.policy_tags || []).includes(policy)) return false;
  if (vaccine && !(item.vaccines || []).includes(vaccine)) return false;
  if (mode && !item.plot?.[mode]) return false;
  return true;
}

function renderCards(items){
  const el = byId('cards');
  byId('visible-count').textContent = `表示件数: ${items.length}`;
  if (!items.length){
    el.innerHTML = '<div class="small">該当する記事はありません。</div>';
    return;
  }
  el.innerHTML = items.map(item => {
    const topicBadges = (item.topics || []).map(t => badge(ja(t), t)).join('');
    const policyBadges = (item.policy_tags || []).map(t => badge(ja(t), 'subtle')).join('');
    const vaccineBadges = (item.vaccines || []).map(v => badge(ja(v), 'subtle')).join('');
    const variantBadges = (item.variants || []).map(v => badge(v, 'subtle')).join('');
    const duplicate = item.duplicate_count > 1 ? `<span class="small">重複統合: ${item.duplicate_count}件</span>` : '';
    return `
      <article class="card">
        <div class="topline">
          <div class="badges">${topicBadges}${policyBadges}${vaccineBadges}${variantBadges}</div>
          ${duplicate}
        </div>
        <h3><a href="${item.link || '#'}" target="_blank" rel="noopener noreferrer">${esc(item.title || item.title_original || '無題')}</a></h3>
        <div class="sub">${fmtDate(item.published_at)} · ${esc(item.source || '')}</div>
        <p><strong>要点:</strong> ${esc(item.summary_ai || item.summary || item.summary_original || '')}</p>
        <div class="meta-grid">
          <div><strong>対象国:</strong> ${esc(item.target_country || '不明')}</div>
          <div><strong>発信元:</strong> ${esc(item.source_location?.label || '不明')}</div>
          <div><strong>原題:</strong> ${esc(item.title_original || '')}</div>
        </div>
      </article>`;
  }).join('');
}

function setupMap(){
  map = L.map('map', {worldCopyJump:true}).setView([20,0], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 6, attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
}

function renderMap(items){
  if (!map) setupMap();
  markersLayer.clearLayers();
  const mode = byId('plot-mode').value || 'source';
  const pts = [];
  items.forEach(item => {
    const plot = item.plot?.[mode];
    if (!plot || plot.lat == null || plot.lng == null) return;
    const marker = L.marker([plot.lat, plot.lng]);
    marker.bindPopup(`<strong>${esc(item.title || '')}</strong><br>${esc(item.source || '')}<br>${esc(plot.label || '')}<br><a href="${item.link}" target="_blank" rel="noopener noreferrer">記事を開く</a>`);
    marker.addTo(markersLayer);
    pts.push([plot.lat, plot.lng]);
  });
  if (pts.length) map.fitBounds(pts, {padding:[20,20], maxZoom:4});
  else map.setView([20,0],2);
}

function updateView(){
  const filtered = allItems.filter(passesFilters);
  renderCards(filtered);
  renderMap(filtered);
}

async function init(){
  const res = await fetch('./data/news.json', {cache:'no-store'});
  const data = await res.json();
  allItems = (data.items || []).sort((a,b) => (b.published_at || '').localeCompare(a.published_at || ''));
  renderHeader(data);
  renderFeedStatus(data.feed_status || []);
  setupMap();
  updateView();
  ['search','topic-filter','policy-filter','vaccine-filter','plot-mode'].forEach(id => byId(id).addEventListener('input', updateView));
  byId('plot-mode').addEventListener('change', updateView);
}

init().catch(err => { byId('cards').innerHTML = `<div class="small">読み込みに失敗しました: ${esc(String(err))}</div>`; });

const byId = id => document.getElementById(id);
let allItems = [];

const MAX_POLICY_ITEMS = 8;
const MAX_ACADEMIC_ITEMS = 16;

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
  official: 'Official',
  academic: 'Journal',
  preprint: 'Preprint',
  media: 'Media',
  'Tier 1': 'Tier 1',
  'Tier 2': 'Tier 2',
  'Tier 3': 'Tier 3'
};

function esc(s=''){
  return String(s)
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#39;');
}

function fmtDate(v){
  if (!v) return '';
  try{
    return new Date(v).toLocaleDateString('ja-JP', {year:'numeric', month:'short', day:'numeric'});
  }catch{
    return v || '';
  }
}

function ja(v){return JA[v] || v;}
function badge(label, cls=''){return `<span class="badge ${cls}">${esc(label)}</span>`;}

function renderHeader(data, archiveCount=0){
  byId('site-title').textContent = data.title || 'ワクチン・予防接種ダッシュボード（試行版）';
  byId('site-desc').textContent = data.description || '';
  byId('generated-at').textContent = `Updated: ${fmtDate(data.generated_at)}`;
  byId('item-count').textContent = `Recent ${data.days_back || 14} days: ${data.item_count || 0}`;
  byId('archive-count').textContent = `Archive: ${archiveCount || 0}`;
}

function renderFeedStatus(feedStatus=[]){
  const el = byId('feed-status');
  if (!feedStatus.length){
    el.innerHTML = '<div class="small">Feed statusはありません。</div>';
    return;
  }
  el.innerHTML = feedStatus.map(f=>{
    const status = f.status === 'ok' ? 'ok' : 'error';
    const detail = f.status === 'ok' ? `seen ${f.seen ?? 0} / kept ${f.kept ?? 0}` : esc(f.error || '');
    return `<div class="feed-item"><span class="${status}">${esc(f.name)}</span> <span class="small">${detail}</span></div>`;
  }).join('');
}

function passesPeriod(item){
  const period = byId('period-filter').value;
  if (period === 'all') return true;
  const days = Number(period || 14);
  const published = new Date(item.published_at || 0).getTime();
  if (!published) return false;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return published >= cutoff;
}

function matchesSearchAndVaccine(item){
  const q = byId('search').value.trim().toLowerCase();
  const vaccine = byId('vaccine-filter').value;
  const hay = [
    item.title,
    item.summary_ai,
    item.summary,
    item.title_original,
    item.summary_ai_original,
    item.summary_original,
    item.source,
    item.target_country,
    item.source_location?.label,
    item.link
  ].join(' ').toLowerCase();
  if (!passesPeriod(item)) return false;
  if (isTechnicalDocument(item)) return false;
  if (q && !hay.includes(q)) return false;
  if (vaccine && !(item.vaccines || []).includes(vaccine)) return false;
  return true;
}

function textOf(item){
  return [
    item.title,
    item.title_original,
    item.summary_ai,
    item.summary,
    item.summary_original,
    item.source,
    item.link
  ].join(' ').toLowerCase();
}

function isTechnicalDocument(item){
  const t = textOf(item);
  const technicalPatterns = [
    'sopp',
    'standard operating',
    'procedures',
    'procedure',
    'guidance compliance regulatory information',
    'guidance-compliance-regulatory-information',
    'biologics procedures',
    'biologics-procedures',
    'cellular gene therapy guidances',
    'biologics-guidances',
    'regulatory education',
    'redi annual conference',
    'supporting documents',
    'quick guide',
    'data files',
    'what’s new for biologics',
    "what's new for biologics",
    'drugs@fda',
    'assay',
    'blood products',
    'device',
    'plasma-derived',
    'transfusion'
  ];
  return technicalPatterns.some(p => t.includes(p));
}

function isDomestic(item){
  const sourceKey = (item.source_location?.key || '').toLowerCase();
  const target = String(item.target_country || '').toLowerCase();
  const source = String(item.source || '').toLowerCase();
  const title = String(item.title || item.title_original || '').toLowerCase();
  return sourceKey === 'japan' ||
    target === '日本' || target === 'japan' ||
    source.includes('nhk') || source.includes('日経') || source.includes('nikkei') ||
    source.includes('朝日') || source.includes('読売') || source.includes('毎日') ||
    source.includes('mhlw') || source.includes('厚生労働省') ||
    title.includes('日本') || title.includes('国内');
}

function isAcademic(item){
  const type = String(item.source_type || '').toLowerCase();
  if (!(type === 'academic' || type === 'preprint')) return false;
  if (isTechnicalDocument(item)) return false;
  return true;
}

function isPolicyNews(item){
  if (isAcademic(item) || isTechnicalDocument(item)) return false;
  const topics = item.topics || [];
  const tags = item.policy_tags || [];
  const type = String(item.source_type || '').toLowerCase();
  return topics.includes('policy') || tags.length > 0 || type === 'official';
}

function sectionScore(item, sectionType){
  let score = 0;
  const type = String(item.source_type || '').toLowerCase();
  const tier = String(item.source_tier || '');
  const tags = item.policy_tags || [];
  const topics = item.topics || [];
  if (sectionType === 'policy'){
    if (type === 'official') score += 6;
    if (tier === 'Tier 1') score += 3;
    if (topics.includes('policy')) score += 4;
    if (tags.includes('recommendation') || tags.includes('schedule') || tags.includes('approval')) score += 3;
    if (tags.includes('safety') || tags.includes('outbreak_response') || tags.includes('financing')) score += 2;
  } else {
    if (type === 'academic') score += 6;
    if (type === 'preprint') score += 4;
    if (tier === 'Tier 3') score += 2;
    if (topics.includes('research')) score += 3;
  }
  if (item.duplicate_count > 1) score += Math.min(2, item.duplicate_count - 1);
  return score;
}

function sortItems(items, sectionType){
  return items.sort((a,b) => {
    const s = sectionScore(b, sectionType) - sectionScore(a, sectionType);
    if (s !== 0) return s;
    return (b.published_at || '').localeCompare(a.published_at || '');
  });
}

function itemCard(item, mode='policy'){
  const topicBadges = (item.topics || []).slice(0, 2).map(t => badge(ja(t), t)).join('');
  const policyBadges = (item.policy_tags || []).slice(0, 3).map(t => badge(ja(t), 'subtle')).join('');
  const vaccineBadges = (item.vaccines || []).slice(0, 3).map(v => badge(ja(v), 'subtle')).join('');
  const typeBadge = item.source_type ? badge(ja(item.source_type), item.source_type) : '';
  const duplicate = item.duplicate_count > 1 ? `<span class="dup">重複統合 ${item.duplicate_count}件</span>` : '';
  const summary = item.summary_ai || item.summary || item.summary_original || '';
  const target = item.target_country && item.target_country !== '不明' ? `対象: ${esc(item.target_country)}` : '';
  const badges = mode === 'academic' ? `${typeBadge}${vaccineBadges}` : `${topicBadges}${policyBadges}${vaccineBadges}`;
  return `
    <article class="card ${mode === 'academic' ? 'academic-card' : ''}">
      <div class="topline">
        <div class="badges">${badges}</div>
        ${duplicate}
      </div>
      <h4><a href="${esc(item.link || '#')}" target="_blank" rel="noopener noreferrer">${esc(item.title || item.title_original || '無題')}</a></h4>
      <div class="sub">${fmtDate(item.published_at)} · ${esc(item.source || '')}${mode === 'policy' && target ? ` · ${target}` : ''}</div>
      <p>${esc(summary)}</p>
    </article>`;
}

function renderSection(id, countId, items, sectionType, maxItems){
  const el = byId(id);
  const countEl = byId(countId);
  const sorted = sortItems([...items], sectionType);
  countEl.textContent = `${sorted.length}件`;
  if (!sorted.length){
    el.innerHTML = '<div class="empty small">該当する記事はありません。</div>';
    return;
  }
  el.innerHTML = sorted.slice(0, maxItems).map(item => itemCard(item, sectionType)).join('');
}

function updateView(){
  const base = allItems.filter(matchesSearchAndVaccine);
  const policy = base.filter(isPolicyNews);
  const domesticPolicy = policy.filter(isDomestic);
  const internationalPolicy = policy.filter(item => !isDomestic(item));
  const academic = base.filter(isAcademic);

  byId('policy-count').textContent = `${policy.length}件`;
  byId('academic-count').textContent = `${academic.length}件`;

  renderSection('domestic-policy', 'domestic-policy-count', domesticPolicy, 'policy', MAX_POLICY_ITEMS);
  renderSection('international-policy', 'international-policy-count', internationalPolicy, 'policy', MAX_POLICY_ITEMS);
  renderSection('academic-main', 'academic-main-count', academic, 'academic', MAX_ACADEMIC_ITEMS);
}

function setupFeedToggle(){
  const btn = byId('feed-toggle');
  const status = byId('feed-status');
  btn.addEventListener('click', () => {
    const hidden = status.classList.toggle('hidden');
    btn.setAttribute('aria-expanded', String(!hidden));
    btn.textContent = hidden ? 'Feed Statusを表示' : 'Feed Statusを非表示';
  });
}

async function init(){
  const [newsRes, archiveRes] = await Promise.all([
    fetch('./data/news.json', {cache:'no-store'}),
    fetch('./data/archive.json', {cache:'no-store'}).catch(() => null)
  ]);
  const newsData = await newsRes.json();
  let archiveData = { items: newsData.items || [], archive_count: (newsData.items || []).length };
  if (archiveRes && archiveRes.ok) archiveData = await archiveRes.json();
  allItems = (archiveData.items || newsData.items || [])
    .sort((a,b) => (b.published_at || '').localeCompare(a.published_at || ''));
  renderHeader(newsData, archiveData.archive_count || allItems.length);
  renderFeedStatus(newsData.feed_status || []);
  setupFeedToggle();
  updateView();
  ['search','period-filter','vaccine-filter'].forEach(id => byId(id).addEventListener('input', updateView));
}

init().catch(err => {
  const msg = `<div class="empty small">読み込みに失敗しました: ${esc(String(err))}</div>`;
  ['domestic-policy','international-policy','academic-main'].forEach(id => {
    const el = byId(id);
    if (el) el.innerHTML = msg;
  });
});

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

function textOf(item){
  return [
    item.title,
    item.title_original,
    item.summary_ai,
    item.summary,
    item.summary_original,
    item.article_text_original,
    item.source,
    item.link
  ].join(' ').toLowerCase();
}

function isTechnicalDocument(item){
  const t = textOf(item);
  const technicalPatterns = [
    'sopp',
    'standard operating',
    'procedure',
    'procedures',
    'guidance compliance regulatory information',
    'guidance-compliance-regulatory-information',
    'biologics procedures',
    'biologics-procedures',
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
    'transfusion',
    'human cells or tissues',
    'cellular and gene therapy',
    'questions and answers on biosimilar',
    'form 483',
    'cgmp inspection',
    'docket management',
    'confidential submissions'
  ];
  return technicalPatterns.some(p => t.includes(p));
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

function academicCategory(item){
  const t = textOf(item);
  const cats = [];
  if (/effectiveness|real-world|test-negative|case-control|vaccine effectiveness|有効性/.test(t)) cats.push('VE');
  if (/safety|adverse|myocarditis|thrombosis|signal|安全性|副反応/.test(t)) cats.push('Safety');
  if (/immunogenicity|antibody|neutralizing|seroresponse|serology|免疫原性|抗体/.test(t)) cats.push('Immunogenicity');
  if (/trial|phase 1|phase i|phase 2|phase ii|phase 3|phase iii|randomi[sz]ed|臨床試験/.test(t)) cats.push('Clinical trial');
  if (/burden|incidence|prevalence|surveillance|epidemiolog|outbreak|disease burden|疾病負荷|疫学/.test(t)) cats.push('Epi/burden');
  if (/model|modelling|modeling|cost-effectiveness|cost effectiveness|economic|simulation|費用対効果|モデル/.test(t)) cats.push('Modelling/CEA');
  if (/policy|recommendation|program|schedule|implementation|uptake|coverage|hesitancy|confidence|政策|接種率/.test(t)) cats.push('Policy-relevant');
  return cats.length ? cats.slice(0, 3) : ['Evidence'];
}

function rationale(item, sectionType){
  const reasons = [];
  const type = String(item.source_type || '');
  const tier = String(item.source_tier || '');
  const tags = item.policy_tags || [];
  const topics = item.topics || [];
  if (sectionType === 'academic'){
    reasons.push(type === 'preprint' ? 'プレプリント' : '査読付きジャーナル');
    academicCategory(item).forEach(c => reasons.push(c));
  } else {
    if (type === 'official') reasons.push('公的機関');
    if (tier) reasons.push(tier);
    if (topics.includes('policy')) reasons.push('政策関連');
    tags.slice(0, 2).forEach(t => reasons.push(ja(t)));
  }
  if (item.duplicate_count > 1) reasons.push(`重複統合${item.duplicate_count}件`);
  return reasons.slice(0, 5).join(' / ') || 'キーワード・分類条件に一致';
}

function confidence(item, sectionType){
  const type = String(item.source_type || '').toLowerCase();
  const tier = String(item.source_tier || '');
  let score = 0;
  if (sectionType === 'policy'){
    if (type === 'official') score += 3;
    if (tier === 'Tier 1') score += 2;
    if ((item.policy_tags || []).length) score += 1;
  } else {
    if (type === 'academic') score += 3;
    if (type === 'preprint') score += 2;
    if (tier === 'Tier 3') score += 1;
    if (academicCategory(item)[0] !== 'Evidence') score += 1;
  }
  if (item.duplicate_count > 1) score += 1;
  if (score >= 5) return {label:'High', cls:'high'};
  if (score >= 3) return {label:'Medium', cls:'medium'};
  return {label:'Screened', cls:'low'};
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
    if (academicCategory(item).includes('Policy-relevant')) score += 2;
    if (academicCategory(item).includes('VE') || academicCategory(item).includes('Safety')) score += 1;
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

function copyTextForItem(item, mode){
  const title = item.title || item.title_original || '無題';
  const summary = item.summary_ai || item.summary || item.summary_original || '';
  const source = item.source || '';
  const date = fmtDate(item.published_at);
  const link = item.link || '';
  return `${title}\n${date} · ${source}\n${summary}\n${link}`;
}

function itemCard(item, mode='policy'){
  const topicBadges = (item.topics || []).slice(0, 2).map(t => badge(ja(t), t)).join('');
  const policyBadges = (item.policy_tags || []).slice(0, 3).map(t => badge(ja(t), 'subtle')).join('');
  const vaccineBadges = (item.vaccines || []).slice(0, 3).map(v => badge(ja(v), 'subtle')).join('');
  const typeBadge = item.source_type ? badge(ja(item.source_type), item.source_type) : '';
  const academicBadges = academicCategory(item).map(c => badge(c, 'evidence')).join('');
  const duplicate = item.duplicate_count > 1 ? `<span class="dup">重複統合 ${item.duplicate_count}件</span>` : '';
  const summary = item.summary_ai || item.summary || item.summary_original || '';
  const target = item.target_country && item.target_country !== '不明' ? `対象: ${esc(item.target_country)}` : '';
  const badges = mode === 'academic' ? `${typeBadge}${academicBadges}${vaccineBadges}` : `${topicBadges}${policyBadges}${vaccineBadges}`;
  const conf = confidence(item, mode);
  const copy = esc(copyTextForItem(item, mode));
  return `
    <article class="card ${mode === 'academic' ? 'academic-card' : ''}">
      <div class="topline">
        <div class="badges">${badges}</div>
        ${duplicate}
      </div>
      <h4><a href="${esc(item.link || '#')}" target="_blank" rel="noopener noreferrer">${esc(item.title || item.title_original || '無題')}</a></h4>
      <div class="sub">${fmtDate(item.published_at)} · ${esc(item.source || '')}${mode === 'policy' && target ? ` · ${target}` : ''}</div>
      <p>${esc(summary)}</p>
      <div class="card-meta">
        <span><strong>掲載理由:</strong> ${esc(rationale(item, mode))}</span>
        <span class="confidence ${conf.cls}">${conf.label}</span>
      </div>
      <div class="card-actions">
        <a class="open-link" href="${esc(item.link || '#')}" target="_blank" rel="noopener noreferrer">Original</a>
        <button type="button" class="copy-btn" data-copy="${copy}">Copy summary</button>
      </div>
    </article>`;
}

function renderSection(id, countId, items, sectionType, maxItems){
  const el = byId(id);
  const countEl = byId(countId);
  const sorted = sortItems([...items], sectionType);
  countEl.textContent = `${sorted.length}件`;
  if (!sorted.length){
    el.innerHTML = '<div class="empty small">該当する記事はありません。</div>';
    return sorted;
  }
  el.innerHTML = sorted.slice(0, maxItems).map(item => itemCard(item, sectionType)).join('');
  return sorted;
}

function topVaccines(items){
  const counts = new Map();
  items.forEach(item => (item.vaccines || []).forEach(v => counts.set(v, (counts.get(v) || 0) + 1)));
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,3).map(([v,n]) => `${ja(v)} ${n}`).join(' / ') || '-';
}

function renderSummary(base, policy, academic, domesticPolicy, internationalPolicy){
  const period = byId('period-filter').value;
  byId('summary-period').textContent = period === 'all' ? '全期間' : `過去${period}日`;
  byId('summary-policy-count').textContent = policy.length;
  byId('summary-academic-count').textContent = academic.length;
  byId('summary-top-vaccines').textContent = topVaccines(base);

  const topAcademicCats = new Map();
  academic.forEach(item => academicCategory(item).forEach(c => topAcademicCats.set(c, (topAcademicCats.get(c) || 0) + 1)));
  const catText = [...topAcademicCats.entries()].sort((a,b)=>b[1]-a[1]).slice(0,3).map(([c,n])=>`${c} ${n}`).join(' / ') || '該当なし';
  const recentPolicy = sortItems([...policy], 'policy')[0];
  const recentAcademic = sortItems([...academic], 'academic')[0];
  const bullets = [
    `政策関連は国内${domesticPolicy.length}件、海外${internationalPolicy.length}件。公的機関・勧告・承認・安全性関連を優先表示しています。`,
    `学術論文は${academic.length}件。主な分類は ${catText} です。`,
    recentPolicy ? `Policy注目候補: ${recentPolicy.title || recentPolicy.title_original || '無題'}` : 'Policy注目候補: 該当なし',
    recentAcademic ? `Academic注目候補: ${recentAcademic.title || recentAcademic.title_original || '無題'}` : 'Academic注目候補: 該当なし'
  ];
  byId('summary-bullets').innerHTML = bullets.map(b => `<div class="summary-item">${esc(b)}</div>`).join('');
}

function updateView(){
  const base = allItems.filter(matchesSearchAndVaccine);
  const policy = base.filter(isPolicyNews);
  const domesticPolicy = policy.filter(isDomestic);
  const internationalPolicy = policy.filter(item => !isDomestic(item));
  const academic = base.filter(isAcademic);

  byId('policy-count').textContent = `${policy.length}件`;
  byId('academic-count').textContent = `${academic.length}件`;

  renderSummary(base, policy, academic, domesticPolicy, internationalPolicy);
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

function setupCopyButtons(){
  document.addEventListener('click', async (event) => {
    const btn = event.target.closest('.copy-btn');
    if (!btn) return;
    const text = btn.getAttribute('data-copy') || '';
    try{
      await navigator.clipboard.writeText(text);
      const old = btn.textContent;
      btn.textContent = 'Copied';
      setTimeout(() => btn.textContent = old, 1100);
    }catch{
      const old = btn.textContent;
      btn.textContent = 'Copy failed';
      setTimeout(() => btn.textContent = old, 1300);
    }
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
  setupCopyButtons();
  updateView();
  ['search','period-filter','vaccine-filter'].forEach(id => byId(id).addEventListener('input', updateView));
}

init().catch(err => {
  const msg = `<div class="empty small">読み込みに失敗しました: ${esc(String(err))}</div>`;
  ['domestic-policy','international-policy','academic-main','summary-bullets'].forEach(id => {
    const el = byId(id);
    if (el) el.innerHTML = msg;
  });
});

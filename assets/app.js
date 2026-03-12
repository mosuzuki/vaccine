
const state = {
  raw: null,
  filtered: [],
  q: "",
  region: "All regions",
  topic: "All topics",
  sourceType: "All source types",
};

const fmt = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tokyo"
});

function el(id){ return document.getElementById(id); }

function unique(arr){ return [...new Set(arr)].sort((a,b)=>a.localeCompare(b)); }

function safe(v){ return (v ?? "").toString(); }

function renderMeta(data){
  const generated = data.generated_at ? fmt.format(new Date(data.generated_at)) : "unknown";
  el("metaLine").textContent = `最終更新: ${generated} JST / 件数: ${data.stats.total}`;
}

function renderStats(data){
  const stats = data.stats || {};
  const cards = [
    ["Total", stats.total ?? 0],
    ["Last 7 days", stats.last7 ?? 0],
    ["Last 30 days", stats.last30 ?? 0],
    ["Regions", Object.keys(stats.by_region || {}).length],
  ];
  el("stats").innerHTML = cards.map(([k,v]) => `
    <article class="stat-card">
      <div class="stat-label">${k}</div>
      <div class="stat-value">${v}</div>
    </article>
  `).join("");
}

function buildFilters(data){
  const regions = ["All regions", ...unique(data.items.map(x => safe(x.region)).filter(Boolean))];
  const topics = ["All topics", ...unique(data.items.flatMap(x => x.topics || []))];
  const types = ["All source types", ...unique(data.items.map(x => safe(x.source_type)).filter(Boolean))];

  const fill = (id, arr) => {
    el(id).innerHTML = arr.map(v => `<option>${v}</option>`).join("");
  };
  fill("region", regions);
  fill("topic", topics);
  fill("sourceType", types);
}

function matches(item){
  const hay = [
    item.title, item.summary, item.country, item.region,
    ...(item.topics || []), ...(item.keyword_hits || []), item.source_name
  ].join(" ").toLowerCase();

  if (state.q && !hay.includes(state.q.toLowerCase())) return false;
  if (state.region !== "All regions" && item.region !== state.region) return false;
  if (state.topic !== "All topics" && !(item.topics || []).includes(state.topic)) return false;
  if (state.sourceType !== "All source types" && item.source_type !== state.sourceType) return false;
  return true;
}

function badge(text, cls=""){
  return `<span class="badge ${cls}">${text}</span>`;
}

function renderNews(){
  const items = state.raw.items.filter(matches);
  state.filtered = items;
  el("countLabel").textContent = `${items.length}件`;

  el("newsList").innerHTML = items.map(item => {
    const date = item.published_at ? fmt.format(new Date(item.published_at)) : "date unknown";
    const topics = (item.topics || []).slice(0,3).map(t => badge(t)).join("");
    const kws = (item.keyword_hits || []).slice(0,4).map(t => badge(t, "soft")).join("");
    const sourceTypeClass = item.source_type === "official" ? "official" : "aggregated";
    return `
      <article class="news-card">
        <div class="news-meta">
          ${badge(item.region || "Global")}
          ${badge(item.country || "Global", "soft")}
          ${badge(item.source_type || "source", sourceTypeClass)}
        </div>
        <h3><a href="${item.url}" target="_blank" rel="noopener noreferrer">${item.title}</a></h3>
        <p class="summary">${item.summary || ""}</p>
        <div class="news-foot">
          <div class="tags">${topics}${kws}</div>
          <div class="source-line">${item.source_name} / ${date}</div>
        </div>
      </article>
    `;
  }).join("") || `<div class="empty">該当するニュースはありません。</div>`;
}

function renderSources(data){
  el("sourcesList").innerHTML = (data.sources || []).map(s => `
    <li>
      <a href="${s.source_home || s.url}" target="_blank" rel="noopener noreferrer">${s.name}</a>
      <span>${s.source_type}</span>
    </li>
  `).join("");
}

function renderErrors(data){
  const errors = data.errors || [];
  el("errorsBox").innerHTML = errors.length
    ? errors.map(e => `<div class="error-item"><strong>${e.feed}</strong><br>${e.error}</div>`).join("")
    : "なし";
}

async function init(){
  const res = await fetch("data/news.json?_=" + Date.now());
  const data = await res.json();
  state.raw = data;
  renderMeta(data);
  renderStats(data);
  buildFilters(data);
  renderSources(data);
  renderErrors(data);
  bind();
  renderNews();
}

function bind(){
  el("q").addEventListener("input", e => { state.q = e.target.value.trim(); renderNews(); });
  el("region").addEventListener("change", e => { state.region = e.target.value; renderNews(); });
  el("topic").addEventListener("change", e => { state.topic = e.target.value; renderNews(); });
  el("sourceType").addEventListener("change", e => { state.sourceType = e.target.value; renderNews(); });
  el("resetBtn").addEventListener("click", () => {
    state.q = "";
    state.region = "All regions";
    state.topic = "All topics";
    state.sourceType = "All source types";
    el("q").value = "";
    el("region").value = "All regions";
    el("topic").value = "All topics";
    el("sourceType").value = "All source types";
    renderNews();
  });
}

init().catch(err => {
  el("metaLine").textContent = "読み込みに失敗しました";
  el("newsList").innerHTML = `<div class="empty">data/news.json の取得に失敗しました。Actions を一度実行してください。<br>${err}</div>`;
});

async function loadNews() {
  const res = await fetch('./data/news.json?' + Date.now());
  const data = await res.json();

  document.getElementById('title').textContent = data.title || 'Vaccine and Immunization Monitoring';
  document.getElementById('description').textContent = data.description || '';

  const container = document.getElementById('cards');
  container.innerHTML = '';

  for (const item of data.items || []) {
    const el = document.createElement('article');
    el.className = 'card';

    const topics = (item.topics || []).map(t => `<span class="badge">${topicJa(t)}</span>`).join(' ');
    const vaccines = (item.vaccines || []).map(v => `<span class="badge subtle">${v}</span>`).join(' ');
    const variants = (item.variants || []).map(v => `<span class="badge subtle">${v}</span>`).join(' ');
    const dup = item.duplicate_count > 1 ? `<div class="meta small">重複統合: ${item.duplicate_count}件</div>` : '';

    el.innerHTML = `
      <h3><a href="${item.link}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || '')}</a></h3>
      <div class="meta">${fmtDate(item.published_at)} · ${escapeHtml(item.source || '')}</div>
      <div class="badges">${topics} ${vaccines} ${variants}</div>
      <p><strong>要点:</strong> ${escapeHtml(item.summary_ai || item.summary || '')}</p>
      ${dup}
    `;
    container.appendChild(el);
  }

  const feed = document.getElementById('feed-status');
  if (feed) {
    feed.innerHTML = (data.feed_status || []).map(f => {
      const status = f.status === 'ok' ? 'OK' : 'ERR';
      const counts = f.status === 'ok' ? ` / seen ${f.seen ?? 0} / kept ${f.kept ?? 0}` : ` / ${escapeHtml(f.error || '')}`;
      return `<div>${escapeHtml(f.name || '')}: ${status}${counts}</div>`;
    }).join('');
  }
}

function topicJa(t) {
  const map = { policy: '政策', research: '研究開発', communication: 'コミュニケーション', other: 'その他' };
  return map[t] || t;
}

function fmtDate(v) {
  try { return new Date(v).toLocaleString('ja-JP'); } catch { return v || ''; }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

loadNews();

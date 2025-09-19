async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }
function qs(k) { return new URLSearchParams(location.search).get(k); }

async function loadAgent() {
    const id = qs('id') || 'a1';
    const a = await fetchJSON('http://localhost:5050/agents/' + id);
    document.getElementById('agent').innerHTML = `
    <h2>${a.name}</h2>
    <div>Тел: ${a.phone || '—'}</div>
    <div>Email: ${a.email || '—'}</div>`;
    const listings = await fetchJSON('http://localhost:5050/listings?agent_id=' + id);
    const root = document.getElementById('list');
    root.innerHTML = listings.map(item => `
    <article class="listing-card card">
      <img src="${item.images?.[0] || '/images/placeholder.webp'}" alt="${item.title}" />
      <div class="pad">
        <h3>${item.title}</h3>
        <a class="btn" href="/listing.html?id=${item.id}">Открыть</a>
      </div>
    </article>`).join('');
}

document.addEventListener('DOMContentLoaded', loadAgent); 
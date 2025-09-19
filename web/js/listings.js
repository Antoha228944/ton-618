async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }

function serializeQuery(q) {
    const p = new URLSearchParams();
    if (q.query) p.set('q', q.query);
    if (q.min_price) p.set('price_gte', q.min_price);
    if (q.max_price) p.set('price_lte', q.max_price);
    // json-server simple filters; extend as needed
    return p.toString();
}

async function loadListings() {
    const q = document.getElementById('q').value.trim();
    const minPrice = document.getElementById('minPrice').value;
    const maxPrice = document.getElementById('maxPrice').value;
    const qs = serializeQuery({ query: q, min_price: minPrice, max_price: maxPrice });
    const url = 'http://localhost:5050/listings' + (qs ? ('?' + qs) : '');
    const data = await fetchJSON(url);
    const root = document.getElementById('list');
    root.innerHTML = data.map(item => `
    <article class="listing-card card">
      <img src="${item.images?.[0] || '/images/placeholder.webp'}" alt="${item.title}" loading="lazy" />
      <div class="pad">
        <h3 style="margin:0 0 6px">${item.title}</h3>
        <div style="color:var(--muted); font-size:14px">${new Intl.NumberFormat('ru-RU').format(item.price)} ${item.currency}</div>
        <div style="margin-top:8px; display:flex; gap:8px">
          <a class="btn" href="/listing.html?id=${item.id}">Открыть</a>
          <button class="btn" aria-label="Сохранить">❤</button>
        </div>
      </div>
    </article>`).join('');
}

function initMap() {
    const el = document.getElementById('map'); if (!el) return;
    el.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100%">Карта (stub)</div>';
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('applyFilters').addEventListener('click', loadListings);
    document.getElementById('clearFilters').addEventListener('click', () => { q.value = ''; minPrice.value = ''; maxPrice.value = ''; loadListings(); });
    loadListings(); initMap();
}); 
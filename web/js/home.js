async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }

async function loadFeatured() {
    try {
        const data = await fetchJSON('http://localhost:5050/listings?_limit=6');
        const root = document.getElementById('featured');
        root.innerHTML = data.map(item => `
      <article class="listing-card card">
        <img src="${item.images?.[0] || '/images/placeholder.webp'}" alt="${item.title}" loading="lazy" />
        <div class="pad">
          <h3 style="margin:0 0 6px">${item.title}</h3>
          <div style="color:var(--muted); font-size:14px">${new Intl.NumberFormat('ru-RU').format(item.price)} ${item.currency}</div>
        </div>
      </article>`).join('');
    } catch (e) { console.error(e); }
}

function initLottie() {
    if (!window.lottie) return;
    const el = document.getElementById('lottie-hero'); if (!el) return;
    window.lottie.loadAnimation({ container: el, renderer: 'svg', loop: true, autoplay: true, path: '/animations/hero.json' });
}

document.addEventListener('DOMContentLoaded', () => { loadFeatured(); initLottie(); }); 
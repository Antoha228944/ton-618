function splitLetters() {
    const spans = document.querySelectorAll('h1 span');
    if (window.gsap && spans.length) {
        gsap.from(spans, { opacity: 0, y: 16, duration: .6, ease: 'power3.out', stagger: .06 });
    }
}

async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }

async function loadNeoCards() {
    const data = await fetchJSON('http://localhost:5050/listings?_limit=6');
    const root = document.getElementById('neo-cards');
    root.innerHTML = data.map(x => `
    <article class="card-3d card-neo">
      <img class="skeleton" src="${x.images?.[0] || '/images/placeholder.webp'}" alt="${x.title}" />
      <div class="pad">
        <h3 style="margin:0 0 6px">${x.title}</h3>
        <div style="color:#a3a3a3">${new Intl.NumberFormat('ru-RU').format(x.price)} ${x.currency}</div>
      </div>
    </article>`).join('');
    if (window.gsap) {
        gsap.registerPlugin(ScrollTrigger);
        gsap.from('.card-3d', { opacity: 0, y: 30, duration: .6, ease: 'power3.out', stagger: .08, scrollTrigger: { trigger: '#neo-cards', start: 'top 85%' } });
    }
}

function particles() {
    const c = document.getElementById('particles'); if (!c) return; const ctx = c.getContext('2d');
    function resize() { c.width = c.clientWidth; c.height = c.clientHeight; }
    window.addEventListener('resize', resize); resize();
    const dots = Array.from({ length: 40 }, () => ({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - .5) * .2, vy: (Math.random() - .5) * .2 }));
    function frame() {
        ctx.clearRect(0, 0, c.width, c.height);
        ctx.fillStyle = 'rgba(138,43,226,.6)';
        dots.forEach(d => { d.x += d.vx; d.y += d.vy; if (d.x < 0 || d.x > c.width) d.vx *= -1; if (d.y < 0 || d.y > c.height) d.vy *= -1; ctx.fillRect(d.x, d.y, 2, 2); });
        requestAnimationFrame(frame);
    }
    frame();
}

document.addEventListener('DOMContentLoaded', () => { splitLetters(); loadNeoCards(); particles(); }); 
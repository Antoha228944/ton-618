async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }

async function loadPosts() {
    const posts = await fetchJSON('http://localhost:5050/posts');
    const root = document.getElementById('posts');
    root.innerHTML = posts.map(p => `
    <article class="card" style="grid-column: span 6; padding:16px">
      <h2>${p.title}</h2>
      <p style="color:var(--muted)">${p.body?.slice(0, 160) || ''}...</p>
      <a class="btn" href="#">Читать</a>
    </article>`).join('');
}

document.addEventListener('DOMContentLoaded', loadPosts); 
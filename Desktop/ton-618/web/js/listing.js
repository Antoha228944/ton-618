async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }

function qs(key) { return new URLSearchParams(location.search).get(key); }

function setSEO(title, desc) {
    document.getElementById('seo-title').textContent = title;
    document.getElementById('seo-desc').setAttribute('content', desc);
}

function injectJSONLD(item) {
    const ld = {
        "@context": "https://schema.org",
        "@type": "Offer",
        "itemOffered": {
            "@type": "Residence",
            "name": item.title,
            "address": item.address,
            "floorSize": { "@type": "QuantitativeValue", "value": item.area_m2, "unitCode": "MTK" },
            "numberOfRooms": item.rooms,
            "amenityFeature": (item.amenities || []).map(a => ({ "@type": "LocationFeatureSpecification", "name": a }))
        },
        "price": item.price,
        "priceCurrency": item.currency,
        "availability": "https://schema.org/InStock"
    };
    document.getElementById('jsonld').textContent = JSON.stringify(ld);
}

function monthlyPayment(loan, rate, years) {
    const i = (rate / 100) / 12; const n = years * 12; if (i === 0) return loan / n; return loan * (i * Math.pow(1 + i, n)) / (Math.pow(1 + i, n) - 1);
}

function initCalc() {
    const btn = document.getElementById('calcBtn'); if (!btn) return;
    btn.addEventListener('click', () => {
        const loan = +document.getElementById('loan').value || 0;
        const rate = +document.getElementById('rate').value || 0;
        const years = +document.getElementById('years').value || 0;
        const p = monthlyPayment(loan, rate, years);
        document.getElementById('payment').textContent = p ? (`${Math.round(p).toLocaleString('ru-RU')} / мес`) : '';
    });
}

function initMap(coords) {
    const el = document.getElementById('map'); if (!el) return;
    el.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100%">Карта (stub)</div>';
}

async function loadListing() {
    const id = qs('id'); if (!id) return;
    const item = await fetchJSON('http://localhost:5050/listings/' + id);
    setSEO(item.title, item.description);
    injectJSONLD(item);
    document.getElementById('title').textContent = item.title;
    document.getElementById('price').textContent = `${item.price.toLocaleString('ru-RU')} ${item.currency}`;
    document.getElementById('desc').textContent = item.description;
    const feats = [
        ['Тип', item.type], ['Комнаты', item.rooms], ['Ванные', item.bathrooms], ['Площадь', (item.area_m2 ? item.area_m2 + ' м²' : '')]
    ].map(([k, v]) => v ? `<div>${k}: <strong>${v}</strong></div>` : '').join('');
    document.getElementById('features').innerHTML = feats;
    document.getElementById('floorplan').src = item.floorplan || '/images/placeholder-floorplan.svg';
    const g = document.getElementById('gallery');
    const imgs = item.images || [];
    g.innerHTML = [imgs[0] ? `<img class="cover" src="${imgs[0]}" alt="${item.title}" />` : '']
        .concat(imgs.slice(1, 5).map(src => `<img class="thumb" src="${src}" alt="${item.title}" />`)).join('');
    document.getElementById('agent').innerHTML = item.agent_id ? `Агент: ${item.agent_id}` : '—';
    initMap(item.coordinates);
    initCalc();
}

document.addEventListener('DOMContentLoaded', loadListing); 
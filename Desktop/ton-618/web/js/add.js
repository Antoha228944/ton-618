const form = document.getElementById('addForm');
const drop = document.getElementById('drop');
const fileInput = document.getElementById('file');
const thumbs = document.getElementById('thumbs');
const progress = document.getElementById('progress');

function renderThumbs(files) {
    thumbs.innerHTML = '';
    Array.from(files).slice(0, 18).forEach(f => {
        const url = URL.createObjectURL(f);
        const img = document.createElement('img'); img.src = url; img.alt = f.name;
        thumbs.appendChild(img);
    });
}

drop.addEventListener('click', () => fileInput.click());
['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.style.borderColor = 'var(--primary)'; }));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.style.borderColor = 'var(--border)'; }));

drop.addEventListener('drop', e => { const files = e.dataTransfer.files; fileInput.files = files; renderThumbs(files); });
fileInput.addEventListener('change', () => renderThumbs(fileInput.files));

function autosave() {
    const data = {
        title: title.value,
        desc: desc.value,
        price: price.value,
        currency: currency.value,
        rooms: rooms.value,
        area: area.value,
        address: address.value
    };
    localStorage.setItem('draft_listing', JSON.stringify(data));
    progress.textContent = 'Черновик сохранён';
}

document.getElementById('saveDraft').addEventListener('click', autosave);

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    progress.textContent = 'Загрузка... 0%';
    for (let i = 1; i <= 10; i++) {
        await new Promise(r => setTimeout(r, 100));
        progress.textContent = `Загрузка... ${i * 10}%`;
    }
    progress.textContent = 'Сохранено (mock)';
}); 
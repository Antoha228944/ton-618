const dict = {
    ru: {
        hero_h1: "Найдите идеальную недвижимость — быстро и безопасно",
        hero_lead: "Поиск, фильтры, карта и умные рекомендации — всё в одном месте.",
        cta_primary: "Подобрать варианты",
        cta_secondary: "Добавить объект"
    },
    en: {
        hero_h1: "Find your perfect home — fast and safe",
        hero_lead: "Search, filters, map and smart recommendations — all in one.",
        cta_primary: "Find options",
        cta_secondary: "Add listing"
    }
};

const state = { lang: localStorage.getItem('lang') || 'ru' };

function applyI18n() {
    const t = dict[state.lang] || dict.ru;
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (t[key]) el.textContent = t[key];
    });
}

window.i18n = {
    set(lang) { state.lang = lang; localStorage.setItem('lang', lang); applyI18n(); },
    get() { return state.lang; }
};

document.addEventListener('DOMContentLoaded', applyI18n); 
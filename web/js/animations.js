document.addEventListener('DOMContentLoaded', () => {
    if (window.gsap) {
        gsap.registerPlugin(window.ScrollTrigger);
        // Page enter
        const enter = document.querySelector('main');
        if (enter) { gsap.from(enter, { opacity: 0, y: 20, duration: .6, ease: 'power3.out' }); }
        // Stagger cards
        const cards = document.querySelectorAll('.listing-card');
        if (cards.length) {
            gsap.from(cards, { opacity: 0, y: 30, stagger: .06, duration: .6, ease: 'power3.out', scrollTrigger: { trigger: '.listings', start: 'top 85%' } });
        }
    }

    // Ripple hover for primary buttons
    document.querySelectorAll('.btn-primary').forEach(btn => {
        btn.addEventListener('pointerenter', () => { btn.style.transform = 'translateY(-2px)'; });
        btn.addEventListener('pointerleave', () => { btn.style.transform = ''; });
    });
}); 
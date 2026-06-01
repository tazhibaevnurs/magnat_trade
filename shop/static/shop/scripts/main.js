
import initializeModalComponent from "./components/modal.js";
import initializeHeaderComponent from "./components/header.js";
import initializeFooterComponent from "./components/footer.js";

// Cart utilities function
const initializeCartUtils = () => {
    // Function to update cart count in navbar
    window.updateCartCount = (count) => {
        const cartCountElement = document.getElementById('cart-count');
        if (cartCountElement) {
            cartCountElement.textContent = count;
        }
        const cartMobile = document.getElementById('cart-count-mobile');
        if (cartMobile) {
            cartMobile.textContent = count;
        }
    };

    // Function to fetch current cart count from server
    window.refreshCartCount = async () => {
        try {
            const response = await fetch('/api/cart-count/', {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });
            if (response.ok) {
                const data = await response.json();
                window.updateCartCount(data.count);
            }
        } catch (error) {
            console.log('Could not refresh cart count:', error);
        }
    };

    // Listen for cart update events
    document.addEventListener('cartUpdated', (event) => {
        if (event.detail && typeof event.detail.count !== 'undefined') {
            window.updateCartCount(event.detail.count);
        } else {
            window.refreshCartCount();
        }
    });
};

/** Нормализованный путь без завершающего слэша (кроме корня). */
function normalizedPath() {
    const raw = window.location.pathname.replace(/\/+$/, '');
    return raw === '' ? '/' : raw;
}

/**
 * Подгружает только JS текущей страницы — меньше парсинга и сети на остальных URL.
 */
async function loadPageModule() {
    const p = normalizedPath();
    const routes = [
        { match: () => p === '/', load: () => import('./pages/landing.js') },
        { match: () => p === '/shop', load: () => import('./pages/shop.js') },
        { match: () => p === '/cart', load: () => import('./pages/cart.js') },
        { match: () => p === '/sign-in', load: () => import('./pages/sign-in.js') },
        { match: () => p === '/sign-up', load: () => import('./pages/sign-up.js') },
        { match: () => p === '/password-reset', load: () => import('./pages/password-reset-request.js') },
        { match: () => p === '/password-reset/confirm', load: () => import('./pages/password-reset-confirm.js') },
        { match: () => p.startsWith('/product'), load: () => import('./pages/pdp.js') },
        { match: () => p === '/about-us', load: () => import('./pages/about-us.js') },
        { match: () => p === '/contact-us', load: () => import('./pages/contact-us.js') },
        { match: () => p === '/feedback', load: () => import('./pages/feedback.js') },
        { match: () => p === '/profile', load: () => import('./pages/profile.js') },
        { match: () => p === '/checkout', load: () => import('./pages/checkout.js') },
        { match: () => p.startsWith('/orders'), load: () => import('./pages/orders.js') },
    ];
    for (const { match, load } of routes) {
        if (!match()) continue;
        try {
            const mod = await load();
            if (typeof mod.default === 'function') mod.default();
        } catch (err) {
            console.error('Page script failed to load', err);
        }
        return;
    }
}

document.addEventListener('DOMContentLoaded', async () => {

    // Load theme from localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }

    await loadPageModule();

    // Components JavaScript Logic
    initializeModalComponent();
    initializeHeaderComponent();
    initializeFooterComponent();

    // Cart utilities
    initializeCartUtils();

});

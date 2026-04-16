import * as themeUtilities from "../utils/theme.js";
import * as paginationUtilities from "../utils/pagination.js";
import * as responsiveUtilities from "../utils/responsive.js";

const initializeLandingPage = () => {

    if (window.location.pathname !== '/') return;

    const logos = document.querySelectorAll('.logo');
    const hero = document.querySelector('#hero');
    const htmlElement = document.querySelector('html');

    const initializePageTheme = () => {

        const mediaQuery = window.matchMedia('(max-width: 1500px)');

        themeUtilities.getTheme((theme) => {

            themeUtilities.setTheme(theme);

            logos.forEach(logo => logo.src = `/static/shop/images/logo-${ theme }.svg`)

            const useSvgHeroBg = hero && !hero.classList.contains('store-bzr-hero');

            if (useSvgHeroBg && mediaQuery.matches)
                hero.style.backgroundImage = `url(/static/shop/images/hero-${ theme }.svg)`;

            if (useSvgHeroBg) {
                mediaQuery.addEventListener('change', (event) => {
                    if (!hero) return;
                    if (event.matches) {
                        hero.style.backgroundImage = `url(/static/shop/images/hero-${ theme }.svg)`;
                    } else {
                        hero.style.backgroundImage = ``;
                    }
                });
            } else if (hero) {
                hero.style.backgroundImage = ``;
            }

            htmlElement.setAttribute('data-theme', theme);

        });

    };

    const initializePageThemeHandling = () => {
        
        const themeSwitchBtns = document.querySelectorAll('.theme-switcher-btn');

        themeSwitchBtns.forEach(themeSwitchBtn => themeSwitchBtn.addEventListener('click', () => {

            themeUtilities.getTheme((callback) => {

                const alternateTheme =
                (callback === 'light')
                ? 'dark'
                : 'light'

                themeSwitchBtn.innerHTML=
                `
                    <i class="fa-solid ${ alternateTheme === 'light' ? 'fa-moon' : 'fa-sun' }"></i>
                `

                themeUtilities.setTheme(alternateTheme);
                initializePageTheme();

            });

        }));

    };

    const initializePageLayoutHandling = () => {

        const header = document.querySelector('.header');
        const hero = document.querySelector('.hero');

        window.addEventListener('resize', () => responsiveUtilities.equalizeHeaderAndHeroSpacing(header, hero, true));
        window.addEventListener('load', () => responsiveUtilities.equalizeHeaderAndHeroSpacing(header, hero, true));

    };

    const initializeSectionsPaginationHandling = () => {

        const featured = document.querySelector('.featured_products-container');
        const flashDeals = document.querySelector('.flash_deals-container');
        const justForYou = document.querySelector('.just_for_you-container');
        const newArrivals = document.querySelector('.new_arrivals-container');

        if (flashDeals)
            paginationUtilities.handleHorizontalPagination(flashDeals, true);

        if (justForYou)
            paginationUtilities.handleHorizontalPagination(justForYou, true);

        if (featured)
            paginationUtilities.handleHorizontalPagination(featured, true);

        if (newArrivals)
            paginationUtilities.handleHorizontalPagination(newArrivals, true);

    };

    const initializeBazaarHeroSlider = () => {

        const track = document.querySelector('[data-bzr-hero-track]');
        const dotsWrap = document.querySelector('[data-bzr-hero-dots]');
        if (!track || !dotsWrap) return;

        const slides = track.querySelectorAll('.store-bzr-slide');
        const dots = dotsWrap.querySelectorAll('.store-bzr-dot');
        if (!slides.length || !dots.length) return;

        const setActive = (index) => {
            dots.forEach((d, i) => d.setAttribute('aria-current', i === index ? 'true' : 'false'));
        };

        dots.forEach((dot, i) => {
            dot.addEventListener('click', () => {
                slides[i]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
                setActive(i);
            });
        });

        let scrollDebounce;
        track.addEventListener('scroll', () => {
            clearTimeout(scrollDebounce);
            scrollDebounce = setTimeout(() => {
                const w = track.clientWidth || 1;
                const idx = Math.min(
                    slides.length - 1,
                    Math.max(0, Math.round(track.scrollLeft / w))
                );
                setActive(idx);
            }, 80);
        }, { passive: true });

        const advance = () => {
            const w = track.clientWidth || 1;
            const idx = Math.min(
                slides.length - 1,
                Math.max(0, Math.round(track.scrollLeft / w))
            );
            const next = (idx + 1) % slides.length;
            slides[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
            setActive(next);
        };

        let auto = setInterval(advance, 6500);
        track.addEventListener('pointerdown', () => {
            if (auto) clearInterval(auto);
            auto = null;
        }, { once: true });

    };

    initializePageLayoutHandling();
    initializePageTheme();
    initializePageThemeHandling();
    initializeSectionsPaginationHandling();
    initializeBazaarHeroSlider();

    console.log("Initialized landing page logic!");

};

export default initializeLandingPage;

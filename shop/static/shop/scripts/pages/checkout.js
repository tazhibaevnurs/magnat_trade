import * as themeUtilities from "../utils/theme.js";
import * as responsiveUtilities from "../utils/responsive.js";

const initializeCheckoutPage = () => {

    if (window.location.pathname !== '/checkout/') return;

    const logos = document.querySelectorAll('.logo');
    const htmlElement = document.querySelector('html');

    const initializePageTheme = () => {

        themeUtilities.getTheme((theme) => {

            themeUtilities.setTheme(theme);

            logos.forEach(logo => logo.src = `/static/shop/images/logo-${ theme }.svg`)

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
        const feedbackWrapper = document.querySelector('.checkout-wrapper');
        if (header && feedbackWrapper) {
            window.addEventListener('resize', () => responsiveUtilities.equalizeHeaderAndHeroSpacing(header, feedbackWrapper, false));
            window.addEventListener('load', () => responsiveUtilities.equalizeHeaderAndHeroSpacing(header, feedbackWrapper, false));
        }

    };

    initializePageLayoutHandling();
    initializePageTheme();
    initializePageThemeHandling();

};

export default initializeCheckoutPage;

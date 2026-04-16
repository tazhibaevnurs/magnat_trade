import * as themeUtilities from "../utils/theme.js";
import * as responsiveUtilities from "../utils/responsive.js";

const initializeFeedbackPage = () => {

    if (window.location.pathname !== '/feedback/') return;

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

        if (document.body.hasAttribute('data-bazaar-layout')) return;

        const header = document.querySelector('.header');
        const feedbackWrapper = document.querySelector('.feedback-wrapper');

        window.addEventListener('resize', () =>  responsiveUtilities.equalizeHeaderAndHeroSpacing(header, feedbackWrapper, false));
        window.addEventListener('load', () =>  responsiveUtilities.equalizeHeaderAndHeroSpacing(header, feedbackWrapper, false));

    };

    initializePageLayoutHandling();
    initializePageTheme();
    initializePageThemeHandling();

    console.log("Initialized feedback page logic!");

};

export default initializeFeedbackPage;

import * as themeUtilities from "../utils/theme.js";

const initializeProfilePage = () => {
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    if (path !== "/profile") return;

    const logos = document.querySelectorAll(".logo");
    const htmlElement = document.querySelector("html");

    const initializePageTheme = () => {
        themeUtilities.getTheme((theme) => {
            themeUtilities.setTheme(theme);
            logos.forEach((logo) => {
                logo.src = `/static/shop/images/logo-${theme}.svg`;
            });
            htmlElement.setAttribute("data-theme", theme);
        });
    };

    const initializePageThemeHandling = () => {
        const themeSwitchBtns = document.querySelectorAll(".theme-switcher-btn");
        themeSwitchBtns.forEach((themeSwitchBtn) =>
            themeSwitchBtn.addEventListener("click", () => {
                themeUtilities.getTheme((callback) => {
                    const alternateTheme = callback === "light" ? "dark" : "light";
                    themeSwitchBtn.innerHTML = `<i class="fa-solid ${
                        alternateTheme === "light" ? "fa-moon" : "fa-sun"
                    }"></i>`;
                    themeUtilities.setTheme(alternateTheme);
                    initializePageTheme();
                });
            })
        );
    };

    initializePageTheme();
    initializePageThemeHandling();
};

export default initializeProfilePage;

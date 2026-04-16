export const equalizeChildrenHeightInContainer = async (container) => {

    const allChildren = Array.from(container.querySelectorAll(':scope > *'));
    /** Не выравниваем высоту с абсолютным фоном (.sign_up-bg / .sign_in-bg): иначе эталонная высота
     * берётся от фона, а контент принудительно сжимается — ломается вёрстка полей (шаг 2 регистрации). */
    const containerChildrenArray = allChildren.filter((el) => {
        const pos = window.getComputedStyle(el).position;
        return pos !== 'absolute' && pos !== 'fixed';
    });

    if (containerChildrenArray.length <= 1) return;

    const isImageHidden =
        containerChildrenArray.filter((containerChild) => window.getComputedStyle(containerChild).display === 'none')
            .length === 1;

    if (isImageHidden) return;

    containerChildrenArray.forEach((containerChild) => {
        containerChild.style.height = 'auto';
    });

    await new Promise((resolve) => setTimeout(resolve, 5));

    const referenceHeight = containerChildrenArray[0].offsetHeight;

    containerChildrenArray.forEach((containerChild) => {
        if (containerChild.matches('.sign_in-form')) return;
        containerChild.style.height = `${referenceHeight}px`;
    });
};

export const equalizeHeaderAndHeroSpacing = (header, hero, isLandingPage = false) => {

    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;
    const headerHeight = header.offsetHeight;

    if (hero && (hero.classList.contains('store-nm-hero') || hero.classList.contains('store-bzr-hero'))) {
        header.style.height = 'auto';
        hero.style.marginTop = '0';
        hero.style.height = 'auto';
        return;
    }

    header.style.height = `${ headerHeight }px`;
    hero.style.marginTop = `${ headerHeight }px`;
    
    if (viewportWidth <= 800 || viewportHeight <= 900 || !isLandingPage) {
        header.style.height = 'auto';
        hero.style.height = 'auto';
        return;
    };

    hero.style.height = `${ (viewportHeight - headerHeight) - (viewportHeight - headerHeight) * 0.20 }px`

};

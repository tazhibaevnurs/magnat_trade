const initializeFooterComponent = () => {

    const navigationMain = document.querySelector('.footer-middle-navigation');
    const navigationAnchors = navigationMain.querySelectorAll('.anchor-button');

    const currentPage = window.location.pathname.replaceAll('/', '');

    navigationAnchors.forEach((navigationAnchor) => {
        
        const anchorPage = navigationAnchor.href.split('/').at(-1);

        navigationAnchor.classList.remove('active');
        
        if (anchorPage === currentPage)
            navigationAnchor.classList.add('active');

    });

};

export default initializeFooterComponent;

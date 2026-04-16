const initializeHeaderComponent = () => {

    const initializeNavigationModule = () => {
        
        const navigationMain = document.querySelector('.header-bottom-navigation');
        const navigationOther = document.querySelector('.header-top-ctas');

        if (!navigationMain || !navigationOther) return;

        const navigationMainAnchors = navigationMain.querySelectorAll('.anchor-button');
        const navigationOtherAnchors = navigationOther.querySelectorAll('.button-secondary');
        const navigationAnchors = [ ...navigationMainAnchors, ...navigationOtherAnchors ];
        const currentPage = window.location.pathname.replaceAll('/', '');

        navigationAnchors.forEach((navigationAnchor) => {

            if (navigationAnchor.matches('button'))
                return;

            const anchorPage = navigationAnchor.href.split('/').at(-1);

            navigationAnchor.classList.remove('active');

            if (anchorPage === currentPage)
                navigationAnchor.classList.add('active');

        });

    };

    const initializeDropdownModule = () => {

        
        const dropdownWrappers = document.querySelectorAll('.user-dropdown');

        if (!dropdownWrappers || dropdownWrappers.length === 0) return;

        dropdownWrappers.forEach((wrapper) => {
            const trigger = wrapper.querySelector('.dropdown-trigger');
            const menu = wrapper.querySelector('.dropdown-menu');

            if (!trigger || !menu) return;

            
            if (!menu.hasAttribute('data-open')) menu.setAttribute('data-open', 'false');

            trigger.addEventListener('click', (e) => {
                e.stopPropagation();

                const isOpen = menu.getAttribute('data-open') === 'true';
                menu.setAttribute('data-open', isOpen ? 'false' : 'true');

                
                if (menu.style.display) menu.style.display = '';
            });

            
            document.addEventListener('click', (e) => {
                if (!menu.contains(e.target) && !trigger.contains(e.target)) {
                    menu.setAttribute('data-open', 'false');
                }
            });

            
            document.addEventListener('keyup', (e) => {
                if (e.key === 'Escape') {
                    menu.setAttribute('data-open', 'false');
                }
            });
        });

    };

    const initializeLogoutModalModule = () => {
        const logoutTrigger = document.getElementById('logout-trigger');
        const modalOverlay = document.querySelector('.logout-modal-overlay');
        const modalClose = document.getElementById('logout-modal-close');
        const modalCancel = document.getElementById('logout-modal-cancel');

        if (!logoutTrigger || !modalOverlay) return;

        // Show modal when logout is clicked
        logoutTrigger.addEventListener('click', (e) => {
            e.preventDefault();
            modalOverlay.style.display = 'flex';
            
            // Close dropdown menu
            const dropdownMenu = document.querySelector('.dropdown-menu');
            if (dropdownMenu) {
                dropdownMenu.setAttribute('data-open', 'false');
            }
        });

        // Close modal handlers
        const closeModal = () => {
            modalOverlay.style.display = 'none';
        };

        if (modalClose) {
            modalClose.addEventListener('click', closeModal);
        }

        if (modalCancel) {
            modalCancel.addEventListener('click', closeModal);
        }

        // Close modal when clicking outside
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay) {
                closeModal();
            }
        });

        // Close modal on Escape key
        document.addEventListener('keyup', (e) => {
            if (e.key === 'Escape' && modalOverlay.style.display === 'flex') {
                closeModal();
            }
        });
    };

    initializeNavigationModule();
    initializeDropdownModule();
    initializeLogoutModalModule();

};

export default initializeHeaderComponent;

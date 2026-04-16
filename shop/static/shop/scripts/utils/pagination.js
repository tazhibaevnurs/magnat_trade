export const handleHorizontalPagination = (container, autoScroll = false) => {

    const parsedContainer = container.className.replace('-container', '');
    const list = container.querySelector(`.${ parsedContainer }-list`);
    const pagination = container.querySelector(`.${ parsedContainer }-pagination`);
    const paginationPrev = pagination.querySelector(`.${ pagination.className }-prev`);
    const paginationNext = pagination.querySelector(`.${ pagination.className }-next`);
    const interval = 1000;

    let autoScrollInterval = null;
    let isUserInteracting = false;

    const scrollAmount = () => {

        const card = list.querySelector('.product_card');

        if (!card) return 0;
        
        const cardWidth = card.offsetWidth;
        const gap = parseInt(getComputedStyle(list).gap) || 16;

        return cardWidth + gap;

    };

    const handlePaginationActionBtnStates = () => {
        
        const { scrollLeft, scrollWidth, clientWidth } = list;

        paginationPrev.disabled = scrollLeft <= 0;
        paginationNext.disabled = scrollLeft + clientWidth >= scrollWidth - 1;

    };

    const scrollToNext = () => {
        const { scrollLeft, scrollWidth, clientWidth } = list;

        if (scrollLeft + clientWidth >= scrollWidth - 1) {
            list.scrollTo({
                left: 0,
                behavior: 'smooth'
            });
        } else {
            list.scrollBy({
                left: scrollAmount(),
                behavior: 'smooth'
            });
        }
    };

    const startAutoScroll = () => {
        if (autoScroll && !autoScrollInterval) {
            autoScrollInterval = setInterval(() => {
                if (!isUserInteracting) {
                    scrollToNext();
                }
            }, interval);
        }
    };

    const stopAutoScroll = () => {
        if (autoScrollInterval) {
            clearInterval(autoScrollInterval);
            autoScrollInterval = null;
        }
    };

    const resetAutoScroll = () => {
        stopAutoScroll();
        setTimeout(() => {
            isUserInteracting = false;
            startAutoScroll();
        }, interval);
    };

    const initializePaginationActions = () => {
        paginationPrev.addEventListener('click', () => {
            isUserInteracting = true;
            list.scrollBy({
                left: -scrollAmount(),
                behavior: 'smooth'
            });
            resetAutoScroll();
        });

        paginationNext.addEventListener('click', () => {
            isUserInteracting = true;
            list.scrollBy({
                left: scrollAmount(),
                behavior: 'smooth'
            });
            resetAutoScroll();
        });
    };

    const initializeUserInteractionHandlers = () => {
        container.addEventListener('mouseenter', () => {
            isUserInteracting = true;
            stopAutoScroll();
        });

        container.addEventListener('mouseleave', () => {
            isUserInteracting = false;
            startAutoScroll();
        });

        list.addEventListener('scroll', () => {
            handlePaginationActionBtnStates();

            if (!autoScrollInterval && autoScroll && isUserInteracting) {
                resetAutoScroll();
            }
        });

        list.addEventListener('touchstart', () => {
            isUserInteracting = true;
            stopAutoScroll();
        });

        list.addEventListener('touchend', () => {
            resetAutoScroll();
        });

        list.addEventListener('wheel', () => {
            isUserInteracting = true;
            stopAutoScroll();
            resetAutoScroll();
        });
    };

    initializePaginationActions();
    initializeUserInteractionHandlers();
    handlePaginationActionBtnStates();

    if (autoScroll) {
        startAutoScroll();
    }

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopAutoScroll();
        } else if (autoScroll && !isUserInteracting) {
            startAutoScroll();
        }
    });

    return () => {
        stopAutoScroll();
    };

};


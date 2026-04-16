import * as themeUtilities from "../utils/theme.js";
import * as responsiveUtilities from "../utils/responsive.js";

const initializeShopPage = () => {

    if (window.location.pathname !== '/shop/') return;

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

        if (document.querySelector('[data-shop-no-ajax]')) return;

        const header = document.querySelector('.header');
        const hero = document.querySelector('.shop-wrapper');

        window.addEventListener('resize', () =>  responsiveUtilities.equalizeHeaderAndHeroSpacing(header, hero, false));
        window.addEventListener('load', () =>  responsiveUtilities.equalizeHeaderAndHeroSpacing(header, hero, false));

    };

    const initializeAutomaticFiltering = () => {

        if (document.querySelector('[data-shop-no-ajax]')) return;

        const sidebarForm = document.querySelector('.shop-sidebar form');
        const modalForm = document.querySelector('.modal form');

        const renderProductCard = (product) => {
            
            let stockClass = 'in_stock';
            if (!product.is_active) {
                stockClass = 'discontinued';
            } else if (product.stock_quantity === 0) {
                stockClass = 'out_of_stock';
            } else if (product.stock_quantity <= 5) {
                stockClass = 'low_stock';
            }
        
            const getCookie = (name) => {
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            };
        
            const truncateWords = (text, wordCount) => {
                const words = text.split(' ');
                if (words.length > wordCount) {
                    return words.slice(0, wordCount).join(' ') + '...';
                }
                return text;
            };
        
            const canAddToCart = product.is_in_stock && product.stock_quantity > 0 && product.is_active;
        
            return `
                <div class="product_card">
                    <div class="product_card-image-container">
                        <img class="product_card-image" src="${product.image_url}" alt="${product.name} product image" />
                    </div>
                    
                    <div class="product_card-wrapper">
                        <div class="product_card-info">
                            <small class="product_card-info-status">
                                <span class="${stockClass}">
                                    ${product.stock_status}
                                </span>
                                <i class="fa-solid fa-circle"></i>
                                ${product.category_display}
                            </small>
                            <h4 class="product_card-info-label">
                                ${product.name}
                            </h4>
                            <p class="product_card-info-description">
                                ${truncateWords(product.description, 20)}
                            </p>
                        </div>
                        <h3 class="product_card-price">
                            ${product.price} сом
                        </h3>
        
                        <div class="product_card-ctas">
                            ${canAddToCart ? `
                                <form method="post" action="/cart/add/" class="product_card-add_to_cart_form" style="display:flex; gap:0.5rem; width:100%;">
                                    <input type="hidden" name="csrfmiddlewaretoken" value="${getCookie('csrftoken')}">
                                    <input type="hidden" name="product_id" value="${product.id}">
                                    <input type="hidden" name="quantity" value="1">
                                    <button type="submit" class="button-secondary product_card-ctas-primary_btn">
                                        <i class="fa-solid fa-cart-shopping"></i>
                                        В корзину
                                    </button>
                                </form>
                            ` : `
                                <button class="button-secondary product_card-ctas-primary_btn" disabled>
                                    <i class="fa-solid fa-exclamation-triangle"></i>
                                    ${product.stock_status}
                                </button>
                            `}
                            <a href="${product.url}" class="button-icon_outlined product_card-ctas-secondary_btn">
                                <i class="fa-solid fa-square-up-right"></i>
                            </a>
                        </div>
                    </div>
                </div>
            `;
        };

        const fetchAndRenderProducts = async (formData) => {
            const shopListWrapper = document.querySelector('.shop-list-wrapper');

            shopListWrapper.innerHTML = '<div class="shop-list-placeholder"><h3>Загрузка...</h3></div>';

            try {
                const response = await fetch(`/api/shop/products/?${formData.toString()}`);
                const data = await response.json();

                if (data.products.length > 0) {
                    shopListWrapper.innerHTML = data.products.map(product => renderProductCard(product)).join('');
                } else {
                    shopListWrapper.innerHTML = `
                        <div class="shop-list-placeholder">
                            <h3>Товары не найдены</h3>
                            <p>Попробуйте изменить поиск или фильтры.</p>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error fetching products:', error);
                shopListWrapper.innerHTML = `
                    <div class="shop-list-placeholder">
<h3>Ошибка загрузки</h3>
                    <p>Попробуйте позже.</p>
                    </div>
                `;
            }
        };

        const debounce = (func, delay) => {
            let timeoutId;
            return (...args) => {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    func.apply(this, args);
                }, delay);
            };
        };

        const handleFilterChange = (form) => {
            const formData = new FormData(form);
            const urlParams = new URLSearchParams(formData);

            const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
            window.history.pushState({}, '', newUrl);

            fetchAndRenderProducts(urlParams);
        };

        const setupAutoSubmit = (form) => {
            if (!form) return;

            const sortByRadios = form.querySelectorAll('input[name="sort_by"]');
            const categoryCheckboxes = form.querySelectorAll('input[name="categories"]');

            sortByRadios.forEach(radio => {
                radio.addEventListener('change', () => {
                    handleFilterChange(form);
                });
            });

            categoryCheckboxes.forEach(checkbox => {
                checkbox.addEventListener('change', () => {
                    handleFilterChange(form);
                });
            });
        };

        setupAutoSubmit(sidebarForm);
        setupAutoSubmit(modalForm);

        const searchForm = document.querySelector('.shop-list-header-search');
        const searchInput = searchForm ? searchForm.querySelector('input[name="search"]') : null;

        if (searchForm && searchInput) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
            });

            const debouncedSearch = debounce(() => {
                const sidebarFormData = sidebarForm ? new FormData(sidebarForm) : new FormData();

                sidebarFormData.set('search', searchInput.value);
                
                const urlParams = new URLSearchParams(sidebarFormData);

                const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
                window.history.pushState({}, '', newUrl);

                fetchAndRenderProducts(urlParams);
            }, 500);

            searchInput.addEventListener('input', debouncedSearch);

            searchInput.addEventListener('input', () => {
                if (sidebarForm) {
                    const sidebarSearchInput = sidebarForm.querySelector('input[name="search"]');
                    if (sidebarSearchInput) {
                        sidebarSearchInput.value = searchInput.value;
                    }
                }
                if (modalForm) {
                    const modalSearchInput = modalForm.querySelector('input[name="search"]');
                    if (modalSearchInput) {
                        modalSearchInput.value = searchInput.value;
                    }
                }
            });
        }
    };

    initializePageLayoutHandling();
    initializePageTheme();
    initializePageThemeHandling();
    initializeAutomaticFiltering();

    console.log("Initialized shop page logic!");

};

export default initializeShopPage;

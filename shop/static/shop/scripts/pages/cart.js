import * as themeUtilities from "../utils/theme.js";
import * as responsiveUtilities from "../utils/responsive.js";

const initializeCartPage = () => {

    const cartPath = window.location.pathname.replace(/\/+$/, '') || '/';
    if (cartPath !== '/cart') return;

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
        const hero = document.querySelector('.cart-wrapper');

        window.addEventListener('resize', () => responsiveUtilities.equalizeHeaderAndHeroSpacing(header, hero, false));
        window.addEventListener('load', () => responsiveUtilities.equalizeHeaderAndHeroSpacing(header, hero, false));

    };

    const initializeCartFunctionality = () => {
        const showCartToast = (message, variant = 'info') => {
            const root = document.getElementById('cart-toast-root');
            if (!root) return;
            const styles = {
                info: 'border-slate-200 bg-white text-slate-800 shadow-lg',
                warning: 'border-amber-200 bg-amber-50 text-amber-950 shadow-lg',
                danger: 'border-red-200 bg-red-50 text-red-900 shadow-lg',
            };
            const wrap = document.createElement('div');
            wrap.className = `pointer-events-auto flex max-w-md items-start gap-3 rounded-xl border px-4 py-3 text-sm font-medium ${styles[variant] || styles.info}`;
            wrap.setAttribute('role', 'alert');

            const text = document.createElement('span');
            text.className = 'min-w-0 flex-1 leading-relaxed';
            text.textContent = message;

            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className =
                'cart-toast-close shrink-0 rounded-lg p-1 text-slate-500 transition hover:bg-black/5 hover:text-slate-800';
            closeBtn.setAttribute('aria-label', 'Закрыть');
            closeBtn.innerHTML =
                '<svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>';

            const remove = () => {
                wrap.classList.add('opacity-0');
                setTimeout(() => wrap.remove(), 200);
            };
            closeBtn.addEventListener('click', remove);
            wrap.appendChild(text);
            wrap.appendChild(closeBtn);
            wrap.classList.add('transition-opacity', 'duration-200');
            root.appendChild(wrap);
            setTimeout(remove, 5500);
        };

        const showCartConfirm = (message) =>
            new Promise((resolve) => {
                const modal = document.getElementById('cart-confirm-modal');
                const msgEl = document.getElementById('cart-confirm-message');
                const backdrop = document.getElementById('cart-confirm-backdrop');
                const okBtn = document.getElementById('cart-confirm-ok');
                const cancelBtn = document.getElementById('cart-confirm-cancel');
                if (!modal || !msgEl || !okBtn || !cancelBtn) {
                    resolve(false);
                    return;
                }
                let settled = false;
                const finish = (value) => {
                    if (settled) return;
                    settled = true;
                    modal.classList.add('hidden');
                    modal.setAttribute('aria-hidden', 'true');
                    okBtn.removeEventListener('click', onOk);
                    cancelBtn.removeEventListener('click', onCancel);
                    if (backdrop) backdrop.removeEventListener('click', onCancel);
                    document.removeEventListener('keydown', onKey);
                    resolve(value);
                };
                const onOk = () => finish(true);
                const onCancel = () => finish(false);
                const onKey = (e) => {
                    if (e.key === 'Escape') onCancel();
                };
                msgEl.textContent = message;
                modal.classList.remove('hidden');
                modal.setAttribute('aria-hidden', 'false');
                okBtn.addEventListener('click', onOk);
                cancelBtn.addEventListener('click', onCancel);
                if (backdrop) backdrop.addEventListener('click', onCancel);
                document.addEventListener('keydown', onKey);
            });

        const cartLineItems = document.getElementById('cart-line-items');

        const fmtSoms = (n) => `${Number(n).toFixed(2)} сом`;

        const applyCartSummary = (data) => {
            if (!data || data.success === false) return;
            const sub = document.querySelector('.cart-summary-subtotal');
            const ship = document.querySelector('.cart-summary-shipping');
            const tot = document.querySelector('.cart-summary-total');
            if (sub) sub.textContent = fmtSoms(data.subtotal);
            if (ship) ship.textContent = fmtSoms(data.shipping_fee);
            if (tot) tot.textContent = fmtSoms(data.grand_total);
            if (typeof window.updateCartCount === 'function' && typeof data.line_count === 'number') {
                window.updateCartCount(data.line_count);
            }
            document.dispatchEvent(
                new CustomEvent('cartUpdated', { detail: { count: data.line_count } }),
            );
            updateCheckoutButtonState();
        };

        const updateCheckoutButtonState = () => {
            const checkoutButton = document.querySelector('.cart-summary-proceed_to_checkout');
            if (!checkoutButton) return;
            const selected = document.querySelectorAll('input[name="cart-select"]:checked').length;
            const hasLines =
                (cartLineItems?.querySelectorAll('.cart-list-item').length ?? 0) > 0;
            const disabled = !hasLines || selected === 0;
            checkoutButton.disabled = disabled;
            checkoutButton.style.opacity = disabled ? '0.5' : '1';
        };

        const selectAllCheckbox = document.getElementById('cart-select_all');

        const updateSelectAllCheckbox = () => {
            if (!selectAllCheckbox || !cartLineItems) return;
            const total = cartLineItems.querySelectorAll('input[name="cart-select"]').length;
            const checked = cartLineItems.querySelectorAll('input[name="cart-select"]:checked').length;
            if (checked === 0) {
                selectAllCheckbox.indeterminate = false;
                selectAllCheckbox.checked = false;
            } else if (total > 0 && checked === total) {
                selectAllCheckbox.indeterminate = false;
                selectAllCheckbox.checked = true;
            } else {
                selectAllCheckbox.indeterminate = true;
                selectAllCheckbox.checked = false;
            }
        };

        const showCartEmptyState = () => {
            if (!cartLineItems) return;
            cartLineItems.innerHTML =
                '<p class="cart-empty py-12 text-center text-slate-600">Корзина пуста.</p>';
        };

        const postCartFormFetch = async (form) => {
            const fd = new FormData(form);
            const res = await fetch(form.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: fd,
                credentials: 'same-origin',
            });
            let data = {};
            try {
                data = await res.json();
            } catch {
                throw new Error('bad_json');
            }
            if (!res.ok) {
                const msg = data.error || `Ошибка ${res.status}`;
                showCartToast(msg, 'danger');
                throw new Error(msg);
            }
            return data;
        };

        if (cartLineItems) {
            cartLineItems.addEventListener('click', async (e) => {
                const btn = e.target.closest('.counter-btn');
                if (!btn) return;
                e.preventDefault();
                const form = btn.closest('form.update-item-form');
                if (!form) return;
                const row = form.closest('.cart-list-item');
                const input = form.querySelector('input[name="quantity"]');
                if (!input || btn.disabled) return;
                const action = btn.getAttribute('data-action');
                let v = parseInt(input.value, 10) || 0;
                const maxStockRaw = row?.getAttribute('data-max-stock');
                const maxStock = parseInt(maxStockRaw, 10);
                if (action === 'increment') {
                    if (Number.isFinite(maxStock) && v >= maxStock) {
                        showCartToast(`В наличии не более ${maxStock} шт.`, 'warning');
                        input.value = maxStock;
                        return;
                    }
                    v += 1;
                } else if (action === 'decrement') {
                    v = Math.max(0, v - 1);
                } else {
                    return;
                }
                if (Number.isFinite(maxStock) && v > maxStock) {
                    v = maxStock;
                    showCartToast(`В наличии не более ${maxStock} шт.`, 'warning');
                }
                input.value = v;
                btn.disabled = true;
                btn.style.opacity = '0.6';
                try {
                    if (v === 0) {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                        row?.remove();
                        if (data.line_count === 0) showCartEmptyState();
                    } else {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                    }
                    updateSelectAllCheckbox();
                } catch {
                    window.location.reload();
                } finally {
                    btn.disabled = false;
                    btn.style.opacity = '1';
                }
            });

            cartLineItems.addEventListener('blur', async (e) => {
                if (!e.target.matches('input[name="quantity"]')) return;
                const form = e.target.closest('form.update-item-form');
                if (!form) return;
                const row = form.closest('.cart-list-item');
                const input = form.querySelector('input[name="quantity"]');
                let v = parseInt(input?.value, 10) || 0;
                const maxBlur = parseInt(row?.getAttribute('data-max-stock'), 10);
                if (Number.isFinite(maxBlur) && v > maxBlur) {
                    v = maxBlur;
                    if (input) input.value = maxBlur;
                    showCartToast(`В наличии не более ${maxBlur} шт.`, 'warning');
                }
                try {
                    if (v <= 0) {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                        row?.remove();
                        if (data.line_count === 0) showCartEmptyState();
                    } else {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                    }
                    updateSelectAllCheckbox();
                } catch {
                    window.location.reload();
                }
            }, true);

            cartLineItems.addEventListener('change', (e) => {
                if (!e.target.matches('input[name="cart-select"]')) return;
                updateCheckoutButtonState();
                updateSelectAllCheckbox();
            });

            cartLineItems.addEventListener('submit', async (e) => {
                const form = e.target;
                if (form.classList.contains('remove-item-form')) {
                    e.preventDefault();
                    try {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                        const id = form.action.match(/\/cart\/item\/(\d+)\/remove\//)?.[1];
                        if (id) {
                            cartLineItems.querySelector(`.cart-list-item[data-item-id="${id}"]`)?.remove();
                        }
                        if (data.line_count === 0) showCartEmptyState();
                        updateSelectAllCheckbox();
                    } catch {
                        window.location.reload();
                    }
                    return;
                }
                if (!form.classList.contains('update-item-form')) return;
                e.preventDefault();
                const input = form.querySelector('input[name="quantity"]');
                const row = form.closest('.cart-list-item');
                let v = parseInt(input?.value, 10) || 0;
                const maxSubmit = parseInt(row?.getAttribute('data-max-stock'), 10);
                if (Number.isFinite(maxSubmit) && v > maxSubmit) {
                    v = maxSubmit;
                    if (input) input.value = maxSubmit;
                    showCartToast(`В наличии не более ${maxSubmit} шт.`, 'warning');
                }
                try {
                    if (v <= 0) {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                        row?.remove();
                        if (data.line_count === 0) showCartEmptyState();
                    } else {
                        const data = await postCartFormFetch(form);
                        applyCartSummary(data);
                    }
                    updateSelectAllCheckbox();
                } catch {
                    window.location.reload();
                }
            });
        }

        const checkoutForm = document.getElementById('checkout-form');
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const selectedItems = [];
                document.querySelectorAll('input[name="cart-select"]:checked').forEach((checkbox) => {
                    selectedItems.push(checkbox.value);
                });
                if (selectedItems.length === 0) {
                    showCartToast(
                        'Отметьте товары галочками, которые хотите оформить.',
                        'warning',
                    );
                    return;
                }
                checkoutForm.querySelectorAll('input[name="selected_items"]').forEach((input) => input.remove());
                selectedItems.forEach((itemId) => {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'selected_items';
                    input.value = itemId;
                    checkoutForm.appendChild(input);
                });
                checkoutForm.submit();
            });
        }

        if (selectAllCheckbox && cartLineItems) {
            selectAllCheckbox.addEventListener('change', () => {
                const isChecked = selectAllCheckbox.checked;
                cartLineItems.querySelectorAll('input[name="cart-select"]').forEach((checkbox) => {
                    checkbox.checked = isChecked;
                });
                updateCheckoutButtonState();
            });
        }

        const removeSelectedBtn = document.getElementById('remove-selected');
        if (removeSelectedBtn) {
            removeSelectedBtn.addEventListener('click', async () => {
                const checked = document.querySelectorAll('input[name="cart-select"]:checked');
                if (checked.length === 0) {
                    showCartToast('Выберите позиции для удаления из корзины.', 'warning');
                    return;
                }
                const confirmed = await showCartConfirm(
                    'Удалить выбранные позиции из корзины?',
                );
                if (!confirmed) {
                    return;
                }
                const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
                if (!csrftoken) {
                    showCartToast(
                        'Не удалось подтвердить запрос. Обновите страницу.',
                        'danger',
                    );
                    return;
                }
                const ids = Array.from(checked).map((cb) => cb.value);
                removeSelectedBtn.disabled = true;
                removeSelectedBtn.style.opacity = '0.5';
                try {
                    let lastData = null;
                    for (const id of ids) {
                        const res = await fetch(`/cart/item/${id}/remove/`, {
                            method: 'POST',
                            headers: {
                                'X-CSRFToken': csrftoken,
                                'X-Requested-With': 'XMLHttpRequest',
                            },
                            credentials: 'same-origin',
                        });
                        let data = {};
                        try {
                            data = await res.json();
                        } catch {
                            throw new Error('bad_json');
                        }
                        if (!res.ok) {
                            showCartToast(data.error || `Ошибка ${res.status}`, 'danger');
                            throw new Error('remove_failed');
                        }
                        lastData = data;
                        cartLineItems
                            ?.querySelector(`.cart-list-item[data-item-id="${id}"]`)
                            ?.remove();
                    }
                    if (lastData) {
                        applyCartSummary(lastData);
                    }
                    if (lastData && lastData.line_count === 0) {
                        showCartEmptyState();
                    }
                    updateSelectAllCheckbox();
                } catch {
                    showCartToast(
                        'Не удалось удалить позиции. Обновите страницу и попробуйте снова.',
                        'danger',
                    );
                } finally {
                    removeSelectedBtn.disabled = false;
                    removeSelectedBtn.style.opacity = '1';
                }
            });
        }

        updateCheckoutButtonState();
        updateSelectAllCheckbox();
    };

    initializePageLayoutHandling();
    initializePageTheme();
    initializePageThemeHandling();
    initializeCartFunctionality();

    console.log("Initialized cart page logic!");

};

export default initializeCartPage;

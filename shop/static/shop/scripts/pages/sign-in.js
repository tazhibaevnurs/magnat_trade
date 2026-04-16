import * as themeUtilities from "../utils/theme.js";
import * as inputUtilities from "../utils/input.js";
import { loginUser } from "../api/auth.js";

const initializeSignInPage = () => {

    if (window.location.pathname !== '/sign-in/') return;

    const initializePageTheme = () => {

        const htmlElement = document.querySelector('html');
        const signIn = document.querySelector('.sign_in');
        const signInBg = document.querySelector('.sign_in-bg');
        const logos = document.querySelectorAll('.logo');
        const mediaQuery = window.matchMedia('(max-width: 1500px)');

        const authBgTarget = () => signInBg || signIn;

        themeUtilities.getTheme((theme) => {

            themeUtilities.setTheme(theme);

            logos.forEach(logo => logo.src = `/static/shop/images/logo-${ theme }.svg`)

            const bgEl = authBgTarget();
            if (mediaQuery.matches)
                bgEl.style.backgroundImage = `url(/static/shop/images/auth-${ theme }.svg)`;

            mediaQuery.addEventListener('change', (event) => {
                const el = authBgTarget();
                if (event.matches) {
                    el.style.backgroundImage = `url(/static/shop/images/auth-${ theme }.svg)`;
                } else {
                    el.style.backgroundImage = ``;
                }
            }) 

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

    const validateEmail = (email) => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    };

    const showInputError = (inputElement, message) => {
        const inputContainer = inputElement.closest('.sign_in-form-group-input');
        const errorSpan = inputContainer.querySelector('.form-input-error');

        if (inputElement.classList.contains('input-nested')) {
            inputElement.closest('.input-with-btn').classList.add('error');
        } else {
            inputElement.classList.add('error');
        }

        errorSpan.textContent = message;
        errorSpan.style.display = 'block';
    };

    const clearInputError = (inputElement) => {
        const inputContainer = inputElement.closest('.sign_in-form-group-input');
        const errorSpan = inputContainer.querySelector('.form-input-error');

        if (inputElement.classList.contains('input-nested')) {
            inputElement.closest('.input-with-btn').classList.remove('error');
        } else {
            inputElement.classList.remove('error');
        }

        errorSpan.textContent = '';
        errorSpan.style.display = 'none';
    };

    const validateInput = (inputElement) => {
        const inputName = inputElement.name;
        const inputValue = inputElement.value.trim();

        clearInputError(inputElement);

        if (inputName === 'csrfmiddlewaretoken') return true;

        if (inputElement.required && !inputValue) {
            showInputError(inputElement, 'Заполните это поле');
            return false;
        }

        if (inputName === 'email_address' && inputValue) {
            if (!validateEmail(inputValue)) {
                showInputError(inputElement, 'Введите корректный адрес электронной почты');
                return false;
            }
        }

        if (inputName === 'password' && inputValue) {
            if (inputValue.length < 8) {
                showInputError(inputElement, 'Пароль должен быть не короче 8 символов');
                return false;
            }
        }

        return true;
    };

    const validateAllInputs = (formInputs) => {
        let isValid = true;
        formInputs.forEach(input => {
            if (input.name !== 'csrfmiddlewaretoken') {
                if (!validateInput(input)) {
                    isValid = false;
                }
            }
        });
        return isValid;
    };

    const initializeFormHandling = () => {

        const signIn = document.querySelector('.sign_in');
        const form = signIn?.querySelector('form');
        if (!form) return;
        const formError = document.querySelector('.sign_in-form-error');
        const formErrorText = document.querySelector('.sign_in-form-error-text');

        const handleAccountAuthorization = async () => {

            const formData = new FormData(form);
            const formInputs = form.querySelectorAll('input');

            if (!validateAllInputs(formInputs)) {
                return;
            }

            formError.style.display = 'none';

            try {
            
                const result = await loginUser({
                    email_address: formData.get('email_address'),
                    password: formData.get('password')
                });

                if (!result.success)
                    throw new Error(result.err || 'Не удалось войти. Проверьте данные.');

                window.location.href = result.redirect || '/';

            } catch (err) {

                formError.style.display = 'flex';
                formErrorText.innerHTML = err.message;

            }

        };

        const formInputsCheckingHandler = (formInputs, formSubmitBtn) => {

            inputUtilities.handleFormInputsChecking(formInputs, (callback) => {

                (!callback)
                    ? formSubmitBtn.setAttribute('disabled', 'disabled')
                    : formSubmitBtn.removeAttribute('disabled')

            });

        }

        const passwordToggle = form.querySelector('[data-toggle="password"]');

        if (passwordToggle) {
            passwordToggle.addEventListener('click', () => {
                const wrap = passwordToggle.closest('.input-with-btn');
                const input = wrap?.querySelector('input');
                const icon = passwordToggle.querySelector('i');

                inputUtilities.handlePasswordToggle(input, (nextType) => {
                    if (!input) return;
                    input.type = nextType || 'password';
                    if (icon) {
                        icon.classList.remove('fa-eye', 'fa-eye-slash');
                        icon.classList.add(input.type === 'password' ? 'fa-eye-slash' : 'fa-eye');
                    }
                });
            });
        }

        const formInputs = form.querySelectorAll('input');
        const formSubmitBtn = form.querySelector('button[type="submit"]');
        const formResetBtn = form.querySelector('button[type="reset"]');

        formInputs.forEach(formInput => formInput.addEventListener('input', () => {
            formInputsCheckingHandler(formInputs, formSubmitBtn)
        }));

        formInputsCheckingHandler(formInputs, formSubmitBtn);

        formSubmitBtn.addEventListener('click', async (event) => {
            event.preventDefault();
            await handleAccountAuthorization();
        });

        formResetBtn.addEventListener('click', (event) => {
            
            event.preventDefault();

            formInputs.forEach(formInput => {
            
                if (formInput.name === 'csrfmiddlewaretoken')
                    return;
            
                formInput.value = '';
                clearInputError(formInput);

            });

            formInputsCheckingHandler(formInputs, formSubmitBtn);

        });

    };

    initializePageTheme();
    initializePageThemeHandling();
    initializeFormHandling();

    console.log("Initialized sign in page logic!");

};

export default initializeSignInPage;

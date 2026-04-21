import * as themeUtilities from "../utils/theme.js";
import * as inputUtilities from "../utils/input.js";
import { createUser } from "../api/auth.js";

const initializeSignUpPage = () => {

    if (window.location.pathname !== '/sign-up/') return;

    const initializePageTheme = () => {

        const htmlElement = document.querySelector('html');
        const main = document.querySelector('.sign_up');
        const mainBg = document.querySelector('.sign_up-bg');
        const logos = document.querySelectorAll('.logo');
        const mediaQuery = window.matchMedia('(max-width: 1500px)');

        const authBgTarget = () => mainBg || main;

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

    const validatePhoneNumber = (phone) => {
        const d = phone.replace(/\D/g, '');
        if (d.length === 12 && d.startsWith('996')) return true;
        if (d.length === 10 && d.startsWith('0')) return true;
        return false;
    };

    const showInputError = (inputElement, message) => {
        const inputContainer = inputElement.closest('.sign_up-form-group-input');
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
        const inputContainer = inputElement.closest('.sign_up-form-group-input');
        const errorSpan = inputContainer.querySelector('.form-input-error');

        if (inputElement.classList.contains('input-nested')) {
            inputElement.closest('.input-with-btn').classList.remove('error');
        } else {
            inputElement.classList.remove('error');
        }

        errorSpan.textContent = '';
        errorSpan.style.display = 'none';
    };

    const validateInput = (inputElement, allInputs = null) => {
        const inputName = inputElement.name;
        const inputValue = inputElement.value.trim();

        clearInputError(inputElement);

        if (inputElement.required && !inputValue) {
            showInputError(inputElement, 'Заполните это поле');
            return false;
        }

        if (!inputElement.required && !inputValue) {
            return true;
        }

        if (inputName === 'first_name' && inputValue) {
            if (inputValue.length < 2) {
                showInputError(inputElement, 'Имя — не менее 2 символов');
                return false;
            }
            if (!/^[\p{L}\s-]+$/u.test(inputValue)) {
                showInputError(inputElement, 'Используйте только буквы');
                return false;
            }
        }

        if (inputName === 'last_name' && inputValue) {
            if (inputValue.length < 2) {
                showInputError(inputElement, 'Фамилия — не менее 2 символов');
                return false;
            }
            if (!/^[\p{L}\s-]+$/u.test(inputValue)) {
                showInputError(inputElement, 'Используйте только буквы');
                return false;
            }
        }

        if (inputElement.tagName === 'SELECT') {
            return true;
        }

        if (inputName === 'contact_number' && inputValue) {
            if (!validatePhoneNumber(inputValue)) {
                showInputError(inputElement, 'Введите номер в формате +996 XXX XXX XXX или 0XXXXXXXXX');
                return false;
            }
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
            if (!/(?=.*[a-zа-яё])/.test(inputValue)) {
                showInputError(inputElement, 'Пароль должен содержать строчную букву');
                return false;
            }
            if (!/(?=.*[A-ZА-ЯЁ])/.test(inputValue)) {
                showInputError(inputElement, 'Пароль должен содержать заглавную букву');
                return false;
            }
            if (!/(?=.*\d)/.test(inputValue)) {
                showInputError(inputElement, 'Пароль должен содержать хотя бы одну цифру');
                return false;
            }
        }

        if (inputName === 'confirm_password' && inputValue && allInputs) {
            const passwordInput = Array.from(allInputs).find(input => input.name === 'password');
            if (passwordInput && inputValue !== passwordInput.value) {
                showInputError(inputElement, 'Пароли не совпадают');
                return false;
            }
        }

        return true;
    };

    const validateStepInputs = (stepInputs, allInputs) => {
        let isValid = true;
        stepInputs.forEach(input => {
            if (!validateInput(input, allInputs)) {
                isValid = false;
            }
        });
        return isValid;
    };

    const initializeFormHandling = () => {

        /** Нельзя использовать document.querySelector('form') — первой в DOM идёт форма поиска в шапке. */
        const signUp = document.querySelector('.sign_up');
        const form = signUp?.querySelector('form');
        if (!form) return;
        const formStepsProgressBar = document.querySelector('.sign_up-form-progress_bar-level');
        const formCtasContainers = form.querySelectorAll('.sign_up-form-group-ctas-container');
        const formCtasContainersArray = Array.from(formCtasContainers);
        const formGroupContainers = form.querySelectorAll('.sign_up-form-group-container');
        const formGroupContainersArray = Array.from(formGroupContainers);
        const formInputs = form.querySelectorAll('input, select');
        const formInputsArray = Array.from(formInputs);
        const formSubmitBtns = form.querySelectorAll('.sign_up-form-group-ctas-btn[type="submit"]');
        const formSubmitBtnsArray = Array.from(formSubmitBtns);
        const formResetBtns = form.querySelectorAll('.sign_up-form-group-ctas-btn[type="reset"]');
        const formResetBtnsArray = Array.from(formResetBtns);
        const formReturnBtn = form.querySelector(
            '[data-step="2"] .sign_up-form-group-ctas-btn[type="button"]',
        );
        const formError = document.querySelector('.sign_up-form-error');
        const formErrorText = formError.querySelector('.sign_up-form-error-text');
        const stepLabelEl = document.getElementById('sign-up-step-label');
        const quizStepEls = document.querySelectorAll('.sign_up-quiz-step');

        const setQuizStep = (step) => {
            if (stepLabelEl) {
                stepLabelEl.textContent =
                    step === '1'
                        ? 'Шаг 1 из 2 — контакты'
                        : 'Шаг 2 из 2 — почта и пароль';
            }
            quizStepEls.forEach((el) => {
                const m = el.getAttribute('data-quiz-marker');
                el.classList.toggle('sign_up-quiz-step--active', m === step);
                el.setAttribute('aria-selected', m === step ? 'true' : 'false');
            });
        };

        let currentFormStep = "1";
        let segregatedFormInputs = formInputsArray.filter(formInput => formInput.closest('.sign_up-form-group-container[data-step="1"]'));
        let segregatedFormSubmitBtn = formSubmitBtnsArray.find(formSubmitBtn => formSubmitBtn.parentElement.getAttribute('data-step') === "1");

        /** Явные поля шагов: не полагаемся на HTMLInputElement.required (у select в части браузеров кнопка «Далее» не включалась). */
        const STEP1_FIELD_NAMES = ['first_name', 'last_name', 'entity_type', 'contact_number'];
        const STEP2_FIELD_NAMES = ['email_address', 'password', 'confirm_password', 'pow_answer'];

        const isCurrentStepFilled = () => {
            const names = currentFormStep === '1' ? STEP1_FIELD_NAMES : STEP2_FIELD_NAMES;
            for (const name of names) {
                const el = form.elements.namedItem(name);
                if (!el) return false;
                const v = (el.value != null ? String(el.value) : '').trim();
                if (!v) return false;
            }
            return true;
        };

        const updateSubmitButtonState = () => {
            if (!segregatedFormSubmitBtn) return;
            if (isCurrentStepFilled()) segregatedFormSubmitBtn.removeAttribute('disabled');
            else segregatedFormSubmitBtn.setAttribute('disabled', 'disabled');
        };

        const showFirstStep = () => {

            const currentFormGroupContainer = formGroupContainersArray.find(formGroupContainer => formGroupContainer.getAttribute('data-step') === '1');
            const previousFormGroupContainer = formGroupContainersArray.find(formGroupContainer => formGroupContainer.getAttribute('data-step') === '2');
            const currentFormCtasContainer = formCtasContainersArray.find(formCtasContainer => formCtasContainer.getAttribute('data-step') === '1');
            const previousFormCtasContainer = formCtasContainersArray.find(formCtasContainer => formCtasContainer.getAttribute('data-step') === '2');

            previousFormCtasContainer.style.display = 'none';
            currentFormCtasContainer.style.display = 'flex';

            previousFormGroupContainer.style.display = 'none';
            currentFormGroupContainer.style.display = 'flex';
            currentFormGroupContainer.style.flexDirection = 'column';

            formStepsProgressBar.style.width = "50%";

            currentFormStep = "1";
            segregatedFormInputs = formInputsArray.filter(formInput => formInput.closest('.sign_up-form-group-container[data-step="1"]'));
            segregatedFormSubmitBtn = formSubmitBtnsArray.find(formSubmitBtn => formSubmitBtn.parentElement.getAttribute('data-step') === "1");

            setQuizStep('1');
            updateSubmitButtonState();

        };

        const showSecondStep = () => {

            if (!validateStepInputs(segregatedFormInputs, formInputsArray)) {
                return;
            }

            const currentFormGroupContainer = formGroupContainersArray.find(formGroupContainer => formGroupContainer.getAttribute('data-step') === '2');
            const previousFormGroupContainer = formGroupContainersArray.find(formGroupContainer => formGroupContainer.getAttribute('data-step') === '1');
            const currentFormCtasContainer = formCtasContainersArray.find(formCtasContainer => formCtasContainer.getAttribute('data-step') === '2');
            const previousFormCtasContainer = formCtasContainersArray.find(formCtasContainer => formCtasContainer.getAttribute('data-step') === '1');

            previousFormCtasContainer.style.display = 'none';
            currentFormCtasContainer.style.display = 'flex';

            previousFormGroupContainer.style.display = 'none';
            currentFormGroupContainer.style.display = 'flex';
            currentFormGroupContainer.style.flexDirection = 'column';

            formStepsProgressBar.style.width = "100%";

            currentFormStep = "2";
            segregatedFormInputs = formInputsArray.filter(formInput => formInput.closest('.sign_up-form-group-container[data-step="2"]'));
            segregatedFormSubmitBtn = formSubmitBtnsArray.find(formSubmitBtn => formSubmitBtn.parentElement.getAttribute('data-step') === "2");

            setQuizStep('2');
            updateSubmitButtonState();

        };

        const handleAccountCreation = async () => {

            if (!validateStepInputs(segregatedFormInputs, formInputsArray)) {
                return;
            }

            const formData = new FormData(form);

            formError.style.display = 'none';

            try {

                if (formData.get('password') !== formData.get('confirm_password'))
                    throw new Error('Пароли не совпадают');
            
                const result = await createUser({
                    first_name: formData.get('first_name'),
                    last_name: formData.get('last_name'),
                    entity_type: formData.get('entity_type'),
                    house_address: formData.get('house_address'),
                    contact_number: formData.get('contact_number'),
                    email_address: formData.get('email_address'),
                    password: formData.get('password'),
                    pow_token: formData.get('pow_token'),
                    pow_answer: formData.get('pow_answer')
                });

                if (!result.success)
                    throw new Error(result.err || 'Не удалось создать аккаунт.');

                window.location.assign(result.redirect || '/');

            } catch (err) {

                formError.style.display = 'flex';
                formErrorText.innerHTML = err.message;

            }

        };

        const passwordToggles = form.querySelectorAll('[data-toggle="password"]');

        passwordToggles.forEach((passwordToggle) =>
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
            }),
        );

        const onFormFieldChange = (el) => {
            if (el.name === 'csrfmiddlewaretoken') return;
            updateSubmitButtonState();
        };

        formInputs.forEach(formInput => {
            formInput.addEventListener('input', () => onFormFieldChange(formInput));
            formInput.addEventListener('change', () => onFormFieldChange(formInput));
        });

        setQuizStep('1');
        updateSubmitButtonState();

        formSubmitBtnsArray.forEach(formSubmitBtn => formSubmitBtn.addEventListener('click', (event) => {
            
            event.preventDefault();

            currentFormStep === '1'
            ? showSecondStep()
            : handleAccountCreation()

        }));

        formResetBtnsArray.forEach(formResetBtn => formResetBtn.addEventListener('click', (event) => {

            event.preventDefault();

            form.reset();
            formInputsArray.forEach((el) => clearInputError(el));

            updateSubmitButtonState();

        }));

        if (formReturnBtn) formReturnBtn.addEventListener('click', showFirstStep);

    };

    initializePageTheme();
    initializePageThemeHandling();
    initializeFormHandling();

    console.log("Initialized sign up page logic.");

};

export default initializeSignUpPage;

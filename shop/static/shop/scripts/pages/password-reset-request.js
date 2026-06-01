import { requestPasswordReset } from "../api/auth.js";

const initializePasswordResetRequestPage = () => {
    if (window.location.pathname.replace(/\/+$/, "") !== "/password-reset") return;

    const form = document.getElementById("password-reset-request-form");
    if (!form) return;

    const formError = form.querySelector(".sign_in-form-error");
    const formErrorText = form.querySelector(".sign_in-form-error-text");
    const successBox = document.getElementById("password-reset-success");
    const successText = successBox?.querySelector(".sign_in-form-success-text");
    const emailInput = form.querySelector("#email_address");
    const submitBtn = form.querySelector('button[type="submit"]');

    const showError = (message) => {
        if (successBox) successBox.style.display = "none";
        if (formError && formErrorText) {
            formError.style.display = "flex";
            formErrorText.textContent = message;
        }
    };

    const showSuccess = (message) => {
        if (formError) formError.style.display = "none";
        if (successBox && successText) {
            successText.textContent = message;
            successBox.style.display = "block";
        }
        if (emailInput) emailInput.disabled = true;
        if (submitBtn) submitBtn.disabled = true;
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const email = (emailInput?.value || "").trim();
        if (!email) {
            showError("Укажите email.");
            return;
        }

        if (submitBtn) submitBtn.disabled = true;

        try {
            const result = await requestPasswordReset({ email_address: email });
            showSuccess(
                result.message ||
                    "Если этот email зарегистрирован, мы отправили ссылку. Проверьте почту и папку «Спам»."
            );
        } catch (err) {
            showError(err.message || "Не удалось отправить письмо. Попробуйте позже.");
            if (submitBtn) submitBtn.disabled = false;
        }
    });
};

export default initializePasswordResetRequestPage;

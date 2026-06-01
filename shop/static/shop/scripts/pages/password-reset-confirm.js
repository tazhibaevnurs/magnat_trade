import * as inputUtilities from "../utils/input.js";
import { confirmPasswordReset } from "../api/auth.js";

const initializePasswordResetConfirmPage = () => {
    if (window.location.pathname.replace(/\/+$/, "") !== "/password-reset/confirm") return;

    const form = document.getElementById("password-reset-confirm-form");
    if (!form) return;

    const formError = form.querySelector(".sign_in-form-error");
    const formErrorText = form.querySelector(".sign_in-form-error-text");
    const submitBtn = form.querySelector('button[type="submit"]');

    form.querySelectorAll("[data-toggle=\"password\"]").forEach((passwordToggle) => {
        passwordToggle.addEventListener("click", () => {
            const wrap = passwordToggle.closest(".input-with-btn");
            const input = wrap?.querySelector("input");
            const icon = passwordToggle.querySelector("i");
            inputUtilities.handlePasswordToggle(input, (nextType) => {
                if (!input) return;
                input.type = nextType || "password";
                if (icon) {
                    icon.classList.remove("fa-eye", "fa-eye-slash");
                    icon.classList.add(input.type === "password" ? "fa-eye-slash" : "fa-eye");
                }
            });
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const uid = (form.querySelector('[name="uid"]')?.value || "").trim();
        const token = (form.querySelector('[name="token"]')?.value || "").trim();
        const newPassword = form.querySelector("#new_password")?.value || "";
        const confirmPassword = form.querySelector("#confirm_password")?.value || "";

        if (formError) formError.style.display = "none";

        if (newPassword.length < 8) {
            if (formError && formErrorText) {
                formError.style.display = "flex";
                formErrorText.textContent = "Пароль должен быть не короче 8 символов.";
            }
            return;
        }
        if (newPassword !== confirmPassword) {
            if (formError && formErrorText) {
                formError.style.display = "flex";
                formErrorText.textContent = "Пароли не совпадают.";
            }
            return;
        }

        if (submitBtn) submitBtn.disabled = true;

        try {
            const result = await confirmPasswordReset({
                uid,
                token,
                new_password: newPassword,
            });
            window.location.href = result.redirect || "/sign-in/?password_reset=1";
        } catch (err) {
            if (formError && formErrorText) {
                formError.style.display = "flex";
                formErrorText.textContent = err.message || "Не удалось сменить пароль.";
            }
            if (submitBtn) submitBtn.disabled = false;
        }
    });
};

export default initializePasswordResetConfirmPage;

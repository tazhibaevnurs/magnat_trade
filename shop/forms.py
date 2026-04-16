from django.forms import EmailInput
from django.contrib.auth.forms import AuthenticationForm


class EmailLoginForm(AuthenticationForm):
    """Вход по email + пароль (USERNAME_FIELD = email)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.fields["username"]
        user.label = "Эл. почта"
        user.widget = EmailInput(
            attrs={
                "class": "input-unnested",
                "placeholder": "you@example.kg",
                "autocomplete": "email",
            }
        )

        pw = self.fields["password"]
        pw.label = "Пароль"
        pw.widget.attrs.update(
            {
                "class": "input-nested",
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        )

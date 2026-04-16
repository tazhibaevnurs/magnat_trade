from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from shop.forms import EmailLoginForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        "accounts/login/",
        LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailLoginForm,
        ),
        name="login",
    ),
    path("api/v1/", include("api.urls")),
    path('', include('shop.urls')),
    path("__reload__/", include("django_browser_reload.urls"))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

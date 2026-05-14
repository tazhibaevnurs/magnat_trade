from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

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
]

if settings.DEBUG:
    urlpatterns.append(path("__reload__/", include("django_browser_reload.urls")))
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "DJANGO_SERVE_MEDIA", False):
    _media_prefix = (settings.MEDIA_URL or "/media/").strip("/")
    if _media_prefix:
        urlpatterns += [
            re_path(
                rf"^{_media_prefix}/(?P<path>.*)$",
                serve,
                {"document_root": settings.MEDIA_ROOT},
            ),
        ]

from django import template

register = template.Library()


@register.simple_tag
def nav_active(request, *path_prefixes):
    """Активный пункт нижнего меню / навигации по префиксу path."""
    path = getattr(request, "path", "") or ""
    for prefix in path_prefixes:
        if prefix == "/":
            if path == "/":
                return "is-active"
        elif path.startswith(prefix):
            return "is-active"
    return ""


@register.simple_tag
def nav_exact(request, path_expected):
    """Точное совпадение path."""
    if (getattr(request, "path", "") or "") == path_expected:
        return "is-active"
    return ""

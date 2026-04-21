from rest_framework.throttling import SimpleRateThrottle


class IntegrationRateThrottle(SimpleRateThrottle):
    scope = "integration"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class WebhookRateThrottle(SimpleRateThrottle):
    scope = "webhook"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AIGenerationRateThrottle(SimpleRateThrottle):
    """
    Dynamic limits by subscription plan.
    - free: 5/day
    - pro: 50/day
    """

    scope = "ai_generation_free"

    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        plan = getattr(user, "subscription_plan", "free") if user and user.is_authenticated else "free"
        self.scope = "ai_generation_pro" if plan == "pro" else "ai_generation_free"
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f"user:{request.user.pk}"
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}

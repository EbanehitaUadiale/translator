from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class PasswordGateMiddleware:
    """Require a shared password before any of the app is reachable.

    This exists to protect the Anthropic bill rather than the data: every
    translation spends real money on the deployer's API key, so an app open to
    the whole internet is an open wallet. One shared password is enough to keep
    that to people who were handed the link deliberately.

    The gate turns itself off when APP_PASSWORD is unset, which is what makes
    local development and the test suite frictionless.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_allowed(request):
            return self.get_response(request)
        return redirect("unlock")

    def _is_allowed(self, request):
        if not settings.APP_PASSWORD:
            return True
        if request.session.get("unlocked"):
            return True

        path = request.path
        # The unlock page itself, or it's a redirect loop. Static files so the
        # unlock page isn't unstyled. Admin because it has its own login, and
        # locking the operator out of it would be self-defeating.
        return (
            path == reverse("unlock")
            or path.startswith("/static/")
            or path.startswith("/admin/")
        )

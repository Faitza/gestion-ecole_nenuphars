# core/middleware.py
from django.shortcuts import redirect
from django.urls import reverse


class ChangementMotDePasseMiddleware:
    """Un compte créé avec un mot de passe provisoire doit le changer avant tout."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.doit_changer_mot_de_passe:
            autorises = (reverse("core:mot_de_passe"), reverse("core:logout"))
            if request.path not in autorises:
                return redirect("core:mot_de_passe")
        return self.get_response(request)

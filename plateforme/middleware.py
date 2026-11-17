# plateforme/middleware.py
from django.shortcuts import render

from . import ecoles


class EcoleMiddleware:
    """Reconnaît l'école à l'adresse du site et l'active pour toute la requête.

    Placé tout en haut de MIDDLEWARE : la session, le compte connecté et les limites de
    requêtes sont lus ensuite dans la base de l'école."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not ecoles.mode_saas():
            return self.get_response(request)
        hote = request.get_host()
        if ecoles.est_la_plateforme(hote):
            # Adresse principale : la plateforme, avec ses propres pages
            request.urlconf = "plateforme.urls_racine"
            request.plateforme = True
            return self.get_response(request)
        ecole = ecoles.ecole_par_adresse(hote)
        if ecole is None:
            return render(request, "plateforme/introuvable.html", {"ecole": None}, status=404)
        if not ecole.active:
            reponse = render(request, "plateforme/suspendue.html", {"ecole": ecole}, status=503)
            reponse["Retry-After"] = "86400"
            return reponse
        request.ecole = ecole
        with ecoles.activer(ecole):
            return self.get_response(request)

from types import SimpleNamespace

from django.conf import settings

from . import ecoles


def ecole(request):
    """L'école de la page : {{ ecole.nom }}, {{ ecole.nom_court }}, {{ ecole.ville }}.

    À l'adresse principale (la plateforme), c'est le nom de la plateforme."""
    if getattr(request, "plateforme", False):
        nom = settings.SAAS_NOM
        return {"ecole": SimpleNamespace(nom=nom, nom_court=nom, nom_affiche=nom, ville="", code="plateforme")}
    return {"ecole": ecoles.courante()}

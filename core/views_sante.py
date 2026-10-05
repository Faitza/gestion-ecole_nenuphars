# core/views_sante.py
# Adresse /sante/ surveillée par un service d'alerte (UptimeRobot, Better Stack...) :
# il l'ouvre toutes les quelques minutes et vous prévient par e-mail ou SMS si
# elle ne répond plus « ok ». Elle ne montre aucune donnée de l'école.
import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache

journal = logging.getLogger("nenuphars")


@never_cache
def sante(request):
    verifications = {}
    try:
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1")
        verifications["base_de_donnees"] = "ok"
    except Exception:
        journal.exception("Vérification /sante/ : la base de données ne répond pas")
        verifications["base_de_donnees"] = "en panne"
    try:
        cache.set("sante", "ok", 30)
        verifications["cache"] = "ok" if cache.get("sante") == "ok" else "en panne"
    except Exception:
        journal.exception("Vérification /sante/ : le cache ne répond pas")
        verifications["cache"] = "en panne"
    tout_va_bien = all(v == "ok" for v in verifications.values())
    return JsonResponse({"etat": "ok" if tout_va_bien else "en panne", **verifications},
                        status=200 if tout_va_bien else 503)

# core/protection.py
# Protection du site quand il est en ligne :
# - un envoi trop lourd est refusé avant d'être lu (il remplirait le disque) ;
# - chaque visiteur a un nombre de requêtes permis par minute, et les formulaires
#   sensibles (connexion, compte parent, préinscription, contact) bien moins.
# Les compteurs sont gardés dans le cache (voir CACHES dans settings.py).
import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render
from django.urls import reverse

journal = logging.getLogger("nenuphars")

# Formulaires surveillés de près (seulement quand ils sont envoyés, en POST)
FORMULAIRES_CONNEXION = ("core:login", "core:inscription", "core:inscription_mot_de_passe")
FORMULAIRES_PUBLICS = ("site:preinscription", "site:contact")
# Toujours permis : fichiers du site et adresse surveillée par l'alerte « site en panne »
CHEMINS_LIBRES = ("/static/", "/sante/", "/favicon.ico")
# Photos des élèves, du personnel et des activités : comptées à part, avec une limite plus large
CHEMINS_PHOTOS = ("/gestion/photos/", "/activites/photos/")


def adresse_du_visiteur(request):
    """Adresse IP du visiteur. Derrière l'hébergeur, c'est la première de X-Forwarded-For."""
    if settings.DERRIERE_UN_PROXY:
        transmise = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if transmise:
            return transmise.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "inconnue"


def depasse(nom, qui):
    """Compte une requête de plus pour « qui » ; True quand la limite est dépassée."""
    nombre, secondes = settings.LIMITES_REQUETES[nom]
    fenetre = int(time.time() // secondes)
    cle = f"limite:{nom}:{qui}:{fenetre}"
    # add() ne fait rien si la clé existe déjà ; incr() est atomique pour le même cache
    cache.add(cle, 0, timeout=secondes + 5)
    try:
        compte = cache.incr(cle)
    except ValueError:   # la clé vient d'expirer entre les deux appels
        cache.set(cle, 1, timeout=secondes + 5)
        compte = 1
    return compte > nombre


def _trop_de_requetes(request, attente):
    reponse = render(request, "429.html", {"attente": attente}, status=429)
    reponse["Retry-After"] = str(attente)
    return reponse


class TailleEnvoiMiddleware:
    """Refuse un envoi plus lourd que TAILLE_MAX_ENVOI, avant que Django ne le lise."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            taille = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            taille = 0
        if taille > settings.TAILLE_MAX_ENVOI:
            journal.warning("Envoi refusé (%.1f Mo) sur %s depuis %s", taille / (1024 * 1024), request.path,
                            adresse_du_visiteur(request))
            return render(request, "413.html", {"mo_max": settings.TAILLE_MAX_ENVOI // (1024 * 1024)}, status=413)
        return self.get_response(request)


class LimiteRequetesMiddleware:
    """Nombre de requêtes limité par visiteur, plus strict pour les formulaires sensibles."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._chemins = None

    def chemins(self):
        if self._chemins is None:
            self._chemins = {
                "connexion": {reverse(nom) for nom in FORMULAIRES_CONNEXION},
                "formulaires_publics": {reverse(nom) for nom in FORMULAIRES_PUBLICS},
            }
        return self._chemins

    def __call__(self, request):
        if request.path.startswith(CHEMINS_LIBRES):
            return self.get_response(request)
        ip = adresse_du_visiteur(request)
        # Une personne connectée est comptée seule : à l'école, tout le personnel
        # peut partager la même adresse IP (même wifi).
        user = getattr(request, "user", None)
        qui = f"u{user.pk}" if user is not None and user.is_authenticated else ip
        compteur = "photos" if request.path.startswith(CHEMINS_PHOTOS) else "pages"
        if depasse(compteur, qui):
            journal.warning("Trop de requêtes (%s) : %s (%s) sur %s", compteur, qui, ip, request.path)
            return _trop_de_requetes(request, settings.LIMITES_REQUETES[compteur][1])
        if request.method == "POST":
            for nom, chemins in self.chemins().items():
                if request.path in chemins:
                    if nom == "connexion":
                        # Par compte essayé : un mot de passe ne peut pas être deviné à force d'essais,
                        # sans bloquer les autres personnes du même wifi.
                        identifiant = (request.POST.get("username") or request.POST.get("telephone") or "").strip().lower()
                        # Empreinte de l'identifiant : pas de numéro de téléphone en clair dans le cache
                        qui = f"{ip}:{hashlib.sha256(identifiant.encode()).hexdigest()[:16]}"
                    if depasse(nom, qui):
                        journal.warning("Formulaire %s envoyé trop souvent : %s sur %s", nom, qui, request.path)
                        return _trop_de_requetes(request, settings.LIMITES_REQUETES[nom][1])
        return self.get_response(request)
